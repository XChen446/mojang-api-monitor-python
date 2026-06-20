"""
Mojang API Monitor — 核心监控逻辑
"""
from __future__ import annotations

import concurrent.futures
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import requests
from requests.exceptions import RequestException, Timeout

from .models import MojangApiStatus, MojangService

logger = logging.getLogger(__name__)

# 9 个默认 Mojang 服务（与原 C# 库完全一致）
DEFAULT_SERVICES: List[MojangService] = [
    MojangService(name="Minecraft.net", url="https://minecraft.net/"),
    MojangService(name="Session Minecraft", url="http://session.minecraft.net/"),
    MojangService(name="Account Mojang", url="http://account.mojang.com/"),
    MojangService(name="Auth Mojang", url="https://auth.mojang.com/"),
    MojangService(name="Skins Minecraft", url="http://skins.minecraft.net/"),
    MojangService(name="Authserver Mojang", url="https://authserver.mojang.com/"),
    MojangService(name="Sessionserver Mojang", url="https://sessionserver.mojang.com/"),
    MojangService(name="API Mojang", url="https://api.mojang.com/"),
    MojangService(name="Textures Minecraft", url="http://textures.minecraft.net/"),
]


class MojangMonitor:
    """
    Mojang API 服务状态监控器。

    支持并发检测、代理转发、超时配置、自定义服务列表。

    用法::

        monitor = MojangMonitor(proxies={"http": "http://127.0.0.1:7897"})
        status = monitor.check_all_services()
        print(status.to_dict())
    """

    def __init__(
        self,
        services: Optional[Sequence[MojangService]] = None,
        timeout: int = 30,
        proxies: Optional[Dict[str, str]] = None,
        max_workers: int = 9,
    ):
        """
        :param services:   自定义服务列表，默认使用原 C# 库的 9 个服务
        :param timeout:    单个请求超时秒数（默认 30）
        :param proxies:    代理配置，如 {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
        :param max_workers: 并行检测的最大线程数（默认 9，即对所有服务同时检测）
        """
        self.services: List[MojangService] = list(services or DEFAULT_SERVICES)
        self.timeout = timeout
        self.proxies = proxies
        self.max_workers = min(max_workers, len(self.services))

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })

    # ------------------------------------------------------------------
    #  对外接口
    # ------------------------------------------------------------------

    def check_all_services(self) -> MojangApiStatus:
        """
    并行检测所有服务的状态。

        :returns: 包含所有服务状态的 :class:`MojangApiStatus` 对象
        """
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            results: List[MojangService] = list(
                executor.map(self._check_single_service, self.services)
            )
        return MojangApiStatus(services=results)

    def check_service(self, service: MojangService) -> MojangService:
        """
    检测单个服务的状态。

        （对外暴露的便捷方法，内部也用于并行调用）
        """
        return self._check_single_service(service)

    # ------------------------------------------------------------------
    #  内部实现
    # ------------------------------------------------------------------

    def _check_single_service(self, service: MojangService) -> MojangService:
        start = time.perf_counter()
        try:
            resp = self._session.get(
                service.url,
                timeout=self.timeout,
                proxies=self.proxies,
                allow_redirects=True,
            )
            elapsed = round((time.perf_counter() - start) * 1000, 1)
            service.response_time_ms = elapsed
            # 只要服务器返回了响应就算 ONLINE（兼容原 C# 行为）
            service.status = "ONLINE"
            logger.info(
                "%s -> %s (%sms)", service.name, resp.status_code, elapsed
            )

        except (RequestException, Timeout, OSError) as exc:
            elapsed = round((time.perf_counter() - start) * 1000, 1)
            service.response_time_ms = elapsed

            error_msg = str(exc).lower()

            # DNS 解析失败 -> 尝试 http → https 降级（兼容原 C# 逻辑）
            if (
                service.url.startswith("http://")
                and _is_dns_error(error_msg)
            ):
                alt_url = service.url.replace("http://", "https://")
                try:
                    resp = self._session.get(
                        alt_url,
                        timeout=self.timeout,
                        proxies=self.proxies,
                        allow_redirects=True,
                    )
                    service.status = "ONLINE"
                    logger.info(
                        "%s -> %s (fallback %s)", service.name, resp.status_code, alt_url
                    )
                except (RequestException, Timeout, OSError):
                    service.status = "OFFLINE"
                    logger.warning(
                        "%s OFFLINE (fallback also failed): %s", service.name, exc
                    )
            else:
                service.status = "OFFLINE"
                logger.warning("%s OFFLINE: %s", service.name, exc)

        except Exception as exc:
            elapsed = round((time.perf_counter() - start) * 1000, 1)
            service.response_time_ms = elapsed
            service.status = "OFFLINE"
            logger.error("%s UNKNOWN ERROR: %s", service.name, exc)

        service.last_checked = datetime.now(timezone.utc)
        return service

    def close(self) -> None:
        """关闭底层 HTTP 会话，释放连接池"""
        self._session.close()


def _is_dns_error(msg: str) -> bool:
    """判断异常信息是否表示 DNS 解析错误（兼容中英文环境）"""
    keywords = (
        "nodename nor servname provided",
        "name or service not known",
        "temporary failure in name resolution",
        "failed to resolve",
        "name does not resolve",
        "不知道这样的主机",
        "找不到请求的类型的数据",
        "getaddrinfo failed",
        "no address associated with hostname",
    )
    return any(k in msg for k in keywords)
