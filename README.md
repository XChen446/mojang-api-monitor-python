# Mojang API Monitor

[![PyPI](https://img.shields.io/pypi/v/mojang-api-monitor)](https://pypi.org/project/mojang-api-monitor/)
[![Python](https://img.shields.io/pypi/pyversions/mojang-api-monitor)](https://pypi.org/project/mojang-api-monitor/)
[![License](https://img.shields.io/github/license/PCL-Community/Mojang-API-Monitor)](LICENSE)

监控 Mojang API 各服务状态的 Python 库。当 Minecraft 玩家遇到登录错误时，可用此工具快速判断是否为 Mojang 服务器问题。

> 此项目是 [Mojang-API-Monitor](https://github.com/PCL-Community/Mojang-API-Monitor) C# NuGet 包的 Python 移植版。

## 功能

- 监控 9 个 Mojang 服务的在线状态
- 支持**并行检测**，毫秒级完成全部检查
- 自动 **DNS 降级**（部分服务 http 解析失败时自动尝试 https）
- 支持 **HTTP/HTTPS 代理**
- 支持自定义服务列表
- 支持 JSON 序列化/反序列化
- 提供命令行工具和 Python API 两种使用方式

## 监控的服务

| # | 服务名称 | URL |
|---|---------|-----|
| 1 | Minecraft.net | https://minecraft.net/ |
| 2 | Session Minecraft | http://session.minecraft.net/ |
| 3 | Account Mojang | http://account.mojang.com/ |
| 4 | Auth Mojang | https://auth.mojang.com/ |
| 5 | Skins Minecraft | http://skins.minecraft.net/ |
| 6 | Authserver Mojang | https://authserver.mojang.com/ |
| 7 | Sessionserver Mojang | https://sessionserver.mojang.com/ |
| 8 | API Mojang | https://api.mojang.com/ |
| 9 | Textures Minecraft | http://textures.minecraft.net/ |

## 安装

```bash
pip install mojang-api-monitor
```

## 使用

### Python API

```python
from mojang_api_monitor import MojangMonitor

# 创建监控器（支持代理）
monitor = MojangMonitor(
    proxies={"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
)

# 检查所有服务（并行）
status = monitor.check_all_services()

# 遍历结果
for svc in status.services:
    print(f"{svc.name:20s} {svc.status:8s} {svc.response_time_ms:>6.0f}ms")

# 导出 JSON
print(status.to_dict())
```

### 命令行

```bash
# 基础检查
mojang-api-monitor

# 使用代理
mojang-api-monitor --proxy-http http://127.0.0.1:7897

# 导出 JSON
mojang-api-monitor -o status.json

# 自定义超时和并发
mojang-api-monitor -t 15 -w 5
```

### JSON 输出格式

```json
{
  "services": [
    {
      "name": "Minecraft.net",
      "url": "https://minecraft.net/",
      "display_url": "https://minecraft.net",
      "status": "ONLINE",
      "last_checked": "2025-05-29T16:41:41.0165483Z",
      "response_time_ms": 3249.0
    }
  ],
  "timestamp": "2025-05-29T16:41:37.7543238Z"
}
```

## 开发

```bash
# 克隆
git clone https://github.com/PCL-Community/Mojang-API-Monitor.git
cd Mojang-API-Monitor

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 构建
python -m build
```

## 依赖

- Python >= 3.8
- requests >= 2.25

## 许可证

MIT License

## 免责声明

本项目不隶属于 Mojang Studios 或 Microsoft。Minecraft、Mojang 是 Mojang Studios 的商标。
