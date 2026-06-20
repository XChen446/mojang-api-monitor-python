"""
Mojang API Monitor — 数据模型

兼容原 C# 库的 JSON 结构，支持序列化/反序列化。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

# .NET DateTime 序列化为 ISO 8601 时微秒段可达 7 位（100-ns tick）
# Python 的 %f 只吃 ≤6 位，这里用正则兼容
_DOTNET_ISO_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.(\d+)(Z|[+-]\d{2}:\d{2})$"
)


def _parse_dotnet_iso(value: str) -> datetime:
    """解析 .NET 风格的 ISO 8601 时间字符串（兼容 0-7 位小数秒）。"""
    m = _DOTNET_ISO_RE.match(value)
    if not m:
        raise ValueError(f"Cannot parse datetime: {value!r}")
    base_part = m.group(1)
    frac = m.group(2).ljust(6, "0")[:6]  # 补齐/截断到 6 位微秒
    tz_part = m.group(3)
    dt = datetime.strptime(f"{base_part}.{frac}", "%Y-%m-%dT%H:%M:%S.%f")
    if tz_part == "Z":
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # handle offset like +08:00
        sign = 1 if tz_part[0] == "+" else -1
        h, m_ = divmod(abs(int(tz_part[1:3]) * 60 + int(tz_part[4:6])), 60)
        dt = dt.replace(tzinfo=timezone(offset=sign * (h * 60 + m_)))
    return dt


@dataclass
class MojangService:
    """表示一个 Mojang 服务及其状态"""

    name: str
    """服务名称（如 "Minecraft.net"）"""

    url: str
    """服务 URL（用于请求检测的实际地址）"""

    status: str = "UNKNOWN"
    """服务状态："ONLINE" 或 "OFFLINE" 或 "UNKNOWN" """

    last_checked: Optional[datetime] = None
    """最后检查时间 (UTC)"""

    response_time_ms: float = 0.0
    """响应时间（毫秒）"""

    @property
    def display_url(self) -> str:
        """提取主域名部分的简短显示 URL"""
        if not self.url:
            return ""
        parsed = urlparse(self.url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def to_dict(self) -> dict:
        """序列化为字典"""
        d = asdict(self)
        d["display_url"] = self.display_url
        if d.get("last_checked") and isinstance(d["last_checked"], datetime):
            d["last_checked"] = d["last_checked"].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        return d

    @classmethod
    def from_dict(cls, data: dict) -> MojangService:
        """从字典反序列化"""
        raw_lc = data.get("last_checked")
        last_checked = _parse_dotnet_iso(raw_lc) if isinstance(raw_lc, str) else raw_lc
        return cls(
            name=data["name"],
            url=data["url"],
            status=data.get("status", "UNKNOWN"),
            last_checked=last_checked,
            response_time_ms=float(data.get("response_time_ms", 0.0)),
        )


@dataclass
class MojangApiStatus:
    """表示所有 Mojang 服务的整体状态"""

    services: List[MojangService] = field(default_factory=list)
    """所有 Mojang 服务的状态列表"""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """状态检查的时间戳 (UTC)"""

    def to_dict(self) -> dict:
        """序列化为字典（兼容原 C# JSON 输出格式）"""
        return {
            "services": [s.to_dict() for s in self.services],
            "timestamp": self.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }

    @classmethod
    def from_dict(cls, data: dict) -> MojangApiStatus:
        """从字典反序列化"""
        services = [MojangService.from_dict(s) for s in data.get("services", [])]
        raw_ts = data.get("timestamp")
        ts = _parse_dotnet_iso(raw_ts) if isinstance(raw_ts, str) else None
        return cls(services=services, timestamp=ts or datetime.now(timezone.utc))
