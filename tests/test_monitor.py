"""
Mojang API Monitor — 单元测试
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from mojang_api_monitor import DEFAULT_SERVICES, MojangApiStatus, MojangMonitor, MojangService


class TestMojangService:
    """MojangService 模型测试"""

    def test_display_url(self):
        svc = MojangService(name="Test", url="https://example.com/path/to")
        assert svc.display_url == "https://example.com"

    def test_display_url_empty(self):
        svc = MojangService(name="Test", url="")
        assert svc.display_url == ""

    def test_to_dict(self):
        svc = MojangService(
            name="Test",
            url="http://test.com/",
            status="ONLINE",
            last_checked=datetime(2025, 1, 1, 12, 0, 0),
            response_time_ms=123.4,
        )
        d = svc.to_dict()
        assert d["name"] == "Test"
        assert d["display_url"] == "http://test.com"
        assert "last_checked" in d
        assert d["response_time_ms"] == 123.4

    def test_from_dict(self):
        raw = {
            "name": "Minecraft.net",
            "url": "https://minecraft.net/",
            "status": "ONLINE",
            "last_checked": "2025-05-29T16:41:41.0165483Z",
            "response_time_ms": 3249.0,
        }
        svc = MojangService.from_dict(raw)
        assert svc.name == "Minecraft.net"
        assert svc.status == "ONLINE"
        assert svc.response_time_ms == 3249.0
        assert svc.last_checked is not None


class TestMojangApiStatus:
    """MojangApiStatus 模型测试"""

    def test_to_dict(self):
        svc = MojangService(name="A", url="https://a.com/")
        status = MojangApiStatus(services=[svc])
        d = status.to_dict()
        assert len(d["services"]) == 1
        assert d["services"][0]["name"] == "A"
        assert "timestamp" in d

    def test_from_dict(self):
        raw = {
            "services": [
                {
                    "name": "Minecraft.net",
                    "url": "https://minecraft.net/",
                    "status": "ONLINE",
                    "last_checked": "2025-05-29T16:41:41.0165483Z",
                    "response_time_ms": 3249.0,
                }
            ],
            "timestamp": "2025-05-29T16:41:37.7543238Z",
        }
        status = MojangApiStatus.from_dict(raw)
        assert len(status.services) == 1
        assert status.services[0].status == "ONLINE"

    def test_json_roundtrip(self):
        svc = MojangService(name="B", url="https://b.com/", status="ONLINE", response_time_ms=100)
        status = MojangApiStatus(services=[svc])
        data = status.to_dict()
        restored = MojangApiStatus.from_dict(data)
        assert restored.services[0].name == "B"
        assert restored.services[0].response_time_ms == 100


class TestMojangMonitor:
    """MojangMonitor 核心逻辑测试"""

    def test_default_services_count(self):
        monitor = MojangMonitor()
        assert len(monitor.services) == 9

    def test_custom_services(self):
        custom = [MojangService(name="Custom", url="https://example.com/")]
        monitor = MojangMonitor(services=custom)
        assert len(monitor.services) == 1
        assert monitor.services[0].name == "Custom"

    def test_check_service_online(self):
        """模拟一个成功的 HTTP 响应 → 标记为 ONLINE"""
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200

        svc = MojangService(name="MockSvc", url="https://mock.test/")
        with patch.object(requests.Session, "get", return_value=mock_resp):
            monitor = MojangMonitor(services=[svc])
            result = monitor.check_service(svc)

        assert result.status == "ONLINE"
        assert result.last_checked is not None
        assert result.response_time_ms >= 0

    def test_check_service_offline(self):
        """请求异常 → 标记为 OFFLINE"""
        svc = MojangService(name="MockOffline", url="https://offline.test/")
        with patch.object(
            requests.Session, "get",
            side_effect=requests.ConnectionError("Connection refused"),
        ):
            monitor = MojangMonitor(services=[svc])
            result = monitor.check_service(svc)

        assert result.status == "OFFLINE"

    def test_check_service_timeout(self):
        """超时异常 → 标记为 OFFLINE"""
        svc = MojangService(name="MockTimeout", url="https://timeout.test/")
        with patch.object(
            requests.Session, "get",
            side_effect=requests.Timeout("Request timed out"),
        ):
            monitor = MojangMonitor(services=[svc])
            result = monitor.check_service(svc)

        assert result.status == "OFFLINE"

    def test_check_service_dns_fallback(self):
        """
        DNS 解析失败且原 URL 为 http:// → 自动尝试 https:// 降级。
        降级成功 → ONLINE。
        """
        svc = MojangService(name="DNSFallback", url="http://dns-fail.test/")

        real_resp = MagicMock(spec=requests.Response)
        real_resp.status_code = 200

        def side_effect(url, **kwargs):
            if url == "http://dns-fail.test/":
                raise requests.ConnectionError(
                    "Temporary failure in name resolution"
                )
            # fallback https 成功
            return real_resp

        with patch.object(requests.Session, "get", side_effect=side_effect):
            monitor = MojangMonitor(services=[svc])
            result = monitor.check_service(svc)

        assert result.status == "ONLINE"

    def test_check_service_dns_fallback_still_fails(self):
        """
        DNS 解析失败 & fallback https 也失败 → OFFLINE。
        """
        svc = MojangService(name="DNSFailHard", url="http://dead.test/")

        def side_effect(url, **kwargs):
            raise requests.ConnectionError("Temporary failure in name resolution")

        with patch.object(requests.Session, "get", side_effect=side_effect):
            monitor = MojangMonitor(services=[svc])
            result = monitor.check_service(svc)

        assert result.status == "OFFLINE"

    def test_proxy_passthrough(self):
        """proxies 参数正确传给 requests.Session.get"""
        svc = MojangService(name="ProxyTest", url="https://proxy.test/")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200

        proxies = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}

        with patch.object(requests.Session, "get", return_value=mock_resp) as mock_get:
            monitor = MojangMonitor(services=[svc], proxies=proxies)
            monitor.check_service(svc)
            # 验证 get 调用时传入了 proxies
            _, kwargs = mock_get.call_args
            assert kwargs.get("proxies") == proxies

    def test_check_all_services_parallel(self):
        """check_all_services 返回包含全部服务的状态"""
        services = [
            MojangService(name=f"Svc{i}", url=f"https://svc{i}.test/")
            for i in range(3)
        ]

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200

        with patch.object(requests.Session, "get", return_value=mock_resp):
            monitor = MojangMonitor(services=services, max_workers=3)
            status = monitor.check_all_services()

        assert len(status.services) == 3
        assert all(s.status == "ONLINE" for s in status.services)
        assert status.timestamp is not None

    def test_close(self):
        """close() 不抛异常"""
        monitor = MojangMonitor()
        monitor.close()  # should not raise

    def test_non_http_error_marks_offline(self):
        """非请求类异常也正确标记 OFFLINE"""
        svc = MojangService(name="CrazyError", url="https://crazy.test/")
        with patch.object(
            requests.Session, "get",
            side_effect=ValueError("Something weird"),
        ):
            monitor = MojangMonitor(services=[svc])
            result = monitor.check_service(svc)
        assert result.status == "OFFLINE"
