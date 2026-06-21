# 用户指南

## 安装

### 从源码安装

```bash
git clone https://github.com/dirjaker/model-monitor.git
cd model-monitor

# 推荐使用 conda 创建虚拟环境
conda create -n model-monitor python=3.12 -y
conda activate model-monitor

# 安装依赖
pip install -r requirements.txt
```

### macOS 应用打包

```bash
# 使用 py2app 打包为原生 .app
python packaging/py2app_setup.py py2app
# 生成的 .app 在 dist/ 目录
```

## 快速开始

### 1. 代理模式（推荐）

代理模式是最常用的监控方式，通过本地 HTTP 代理转发请求到上游 API。

```bash
# 使用默认配置启动代理（端口 8080）
python main.py proxy

# 指定端口
python main.py proxy -p 9090

# 指定监听地址
python main.py proxy --host 127.0.0.1 -p 9090
```

客户端配置代理：

```bash
# Linux / macOS
export HTTP_PROXY=http://localhost:8080
export HTTPS_PROXY=http://localhost:8080

# 或在代码中配置
import httpx
client = httpx.Client(proxy="http://localhost:8080")
```

### 2. 嗅探模式

嗅探模式通过 mitmproxy 被动监控 HTTPS 流量，无需修改客户端代码。

```bash
# 启动嗅探器
python main.py sniffer

# 首次使用需要安装 CA 证书（macOS）
python -c "from src.sniffer.cert import install_cert_macos; install_cert_macos()"

# Linux 需要手动将 CA 证书添加到系统信任存储
# 证书路径: ~/.model-monitor/certs/mitmproxy-ca-cert.pem
```

### 3. Web 仪表盘

```bash
# 启动 Web 仪表盘
python main.py web

# 指定端口
python main.py web -p 8080
```

访问 http://localhost:8000 查看仪表盘。

### 4. 终端界面

```bash
python main.py tui
```

Rich 驱动的终端实时监控，3 秒自动刷新，显示统计概览、模型统计和最近调用记录。

### 5. macOS 图形界面

```bash
# 仅 macOS 可用
python main.py app
```

### 6. 查看统计

```bash
# 命令行查看统计信息
python main.py stats

# 导出数据为 JSON
python main.py export -o data.json -d 30
```

## 配置说明

配置文件路径：`config.yaml`

### 完整配置示例

```yaml
# 运行模式: proxy | sniffer
mode: proxy

# 代理服务器配置
proxy:
  host: 0.0.0.0
  port: 8080
  timeout: 120          # 上游超时（秒）

# 嗅探器配置
sniffer:
  port: 8080
  targets:              # 监控的目标域名
    - api.deepseek.com
    - openrouter.ai

# Web 仪表盘配置
web:
  host: 0.0.0.0
  port: 8000

# 数据库配置
database:
  path: data/usage.db

# API 提供商配置
providers:
  deepseek:
    base_url: https://api.deepseek.com
    api_key: ${DEEPSEEK_API_KEY}    # 支持环境变量引用
    pricing:
      deepseek-chat:
        input: 1.0                  # 每百万 Token 价格（美元）
        output: 2.0
  openrouter:
    base_url: https://openrouter.ai/api
    api_key: ${OPENROUTER_API_KEY}
  mimo:
    base_url: https://openrouter.ai/api/v1
    api_key: ${OPENROUTER_API_KEY}
    pricing:
      mimo-v2.5-pro:
        input: 1.0
        output: 2.0

# 告警配置
alerts:
  enabled: true
  daily_threshold: 10.0             # 日费用阈值（美元）
  monthly_threshold: 200.0          # 月费用阈值（美元）
  webhook_url: https://your-webhook-url
```

### 环境变量覆盖

使用 `MM_<SECTION>_<KEY>` 格式的环境变量覆盖配置：

```bash
# 覆盖代理端口
export MM_PROXY_PORT=9090

# 覆盖 Web 端口
export MM_WEB_PORT=8080

# 覆盖告警开关
export MM_ALERTS_ENABLED=true
```

### 配置管理命令

```bash
# 查看当前配置
python main.py config

# 查看完整配置文件
python main.py config --show

# 修改配置项
python main.py config --set-key proxy.port --set-value 9090
```

## REST API 文档

启动 Web 仪表盘后访问 http://localhost:8000/api/docs 查看交互式 API 文档（Swagger UI）。

### 主要端点

| 端点 | 方法 | 说明 | 参数 |
|------|------|------|------|
| `/api/stats` | GET | 总体统计 | - |
| `/api/calls` | GET | 调用记录 | `limit`, `offset`, `provider`, `model`, `mode` |
| `/api/models` | GET | 按模型统计 | - |
| `/api/daily` | GET | 每日统计 | `days` (1-365) |
| `/api/hourly` | GET | 每小时统计 | `hours` (1-168) |
| `/api/health` | GET | 健康检查 | - |

### 响应格式

所有 API 返回统一 JSON 格式：

```json
{
  "status": "ok",
  "data": { ... }
}
```

### 示例

```bash
# 获取总体统计
curl http://localhost:8000/api/stats

# 获取最近 10 条 DeepSeek 调用
curl "http://localhost:8000/api/calls?limit=10&provider=deepseek"

# 获取最近 7 天的每日统计
curl "http://localhost:8000/api/daily?days=7"
```

## 支持的提供商

| 提供商 | 适配器 | 特性 |
|--------|--------|------|
| DeepSeek | `DeepSeekAdapter` | 非流式 + 流式 Token 解析 |
| OpenRouter | `OpenRouterAdapter` | 非流式 + 流式 Token 解析 |
| MiMo (小米) | `MiMoAdapter` | 通过 OpenRouter 访问，内置定价 |
| 通用 (OpenAI 兼容) | `GenericAdapter` | 兼容所有 OpenAI 格式 API |

## 常见问题

### Q: 代理模式和嗅探模式有什么区别？

- **代理模式**: 需要客户端配置 HTTP 代理，主动转发请求，数据最完整（可记录请求/响应内容）
- **嗅探模式**: 被动监听 HTTPS 流量，无需修改客户端配置，适合监控已有应用

### Q: 如何添加新的 API 提供商？

在 `config.yaml` 的 `providers` 中添加配置，系统会自动使用 `GenericAdapter`（兼容 OpenAI 格式）。如需自定义解析逻辑，可在 `src/proxy/adapters.py` 中添加新的适配器类。

### Q: 数据存储在哪里？

默认存储在 `data/usage.db`（SQLite 数据库），可通过 `database.path` 配置修改。

### Q: 告警通知支持哪些平台？

通过 Webhook 方式发送，支持任何接受 JSON POST 请求的平台（飞书、Slack、钉钉、企业微信等）。
