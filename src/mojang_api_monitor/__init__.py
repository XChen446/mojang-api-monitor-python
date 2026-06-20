"""
Mojang API Monitor
==================

监控 Mojang 各 API 服务状态的 Python 库。

快速开始::

    from mojang_api_monitor import MojangMonitor

    monitor = MojangMonitor()
    status = monitor.check_all_services()

    for svc in status.services:
        print(f"{svc.name:20s} {svc.status:8s} {svc.response_time_ms:6.0f}ms")
"""

from .models import MojangApiStatus, MojangService
from .monitor import DEFAULT_SERVICES, MojangMonitor

__all__ = [
    "MojangMonitor",
    "MojangApiStatus",
    "MojangService",
    "DEFAULT_SERVICES",
]

__version__ = "1.0.0"
