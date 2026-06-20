"""
Mojang API Monitor — 命令行入口

直接运行::

    python -m mojang_api_monitor
    mojang-api-monitor
"""
from __future__ import annotations

import argparse
import json
import sys

from .models import MojangService
from .monitor import MojangMonitor


def _status_display(name: str, url: str, status: str, rt: float) -> str:
    status_cn = "在线" if status == "ONLINE" else "离线"
    return f"| {name:<19} | {url:<27} | {status_cn:<10} | {rt:>8.0f}ms |"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mojang API 服务状态监控工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  mojang-api-monitor                                     # 检查所有服务\n"
            "  mojang-api-monitor -o status.json                      # 导出 JSON\n"
            "  mojang-api-monitor --proxy-http http://127.0.0.1:7897  # 使用代理\n"
            "  mojang-api-monitor -w 5 -t 15                          # 5线程，超时15s\n"
        ),
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="输出 JSON 文件路径（默认仅打印到控制台）",
    )
    parser.add_argument(
        "-t", "--timeout", type=int, default=30,
        help="单个请求超时秒数（默认 30）",
    )
    parser.add_argument(
        "-w", "--workers", type=int, default=9,
        help="并行检测线程数（默认 9，1=顺序检测）",
    )
    parser.add_argument(
        "--proxy-http",
        help="HTTP 代理地址，如 http://127.0.0.1:7897",
    )
    parser.add_argument(
        "--proxy-https",
        help="HTTPS 代理地址，如 http://127.0.0.1:7897",
    )
    args = parser.parse_args(argv)

    # 构造 proxy dict
    proxies = {}
    if args.proxy_http:
        proxies["http"] = args.proxy_http
    if args.proxy_https:
        proxies["https"] = args.proxy_https
    if not proxies:
        proxies = None

    print("开始检查 Mojang API 状态...")
    print("正在检查，请稍候...\n")

    monitor = MojangMonitor(
        timeout=args.timeout,
        proxies=proxies,
        max_workers=args.workers,
    )
    status = monitor.check_all_services()

    # ── 控制台表格输出 ──
    timestamp = status.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    print("===== Mojang 服务状态 =====")
    print(f"检查时间: {timestamp}\n")
    print("+---------------------+-----------------------------+------------+----------------+")
    print("| 服务名称            | URL                         | 状态       | 响应时间       |")
    print("+---------------------+-----------------------------+------------+----------------+")
    for s in status.services:
        print(_status_display(s.name, s.display_url, s.status, s.response_time_ms))
    print("+---------------------+-----------------------------+------------+----------------+\n")

    # ── 统计摘要 ──
    online = sum(1 for s in status.services if s.status == "ONLINE")
    total = len(status.services)
    print(f"总览: {online}/{total} 服务在线\n")

    # ── JSON 导出 ──
    if args.output:
        data = status.to_dict()
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"状态已导出到文件: {args.output}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
