# 开发指南

## 开发环境搭建

### 环境要求

- Python 3.12+
- conda（推荐）或 venv
- macOS（可选，用于原生 GUI 和菜单栏功能）

### 安装开发依赖

```bash
git clone https://github.com/dirjaker/model-monitor.git
cd model-monitor
git checkout dev

conda create -n model-monitor python=3.12 -y
conda activate model-monitor

pip install -r requirements.txt
```

### 主要依赖

| 包 | 用途 |
|----|------|
| `fastapi` | Web 框架（代理服务器 + 仪表盘） |
| `uvicorn` | ASGI 服务器 |
| `httpx` | 异步 HTTP 客户端（代理转发） |
| `mitmproxy` | HTTPS 流量嗅探 |
| `pyyaml` | YAML 配置解析 |
| `rich` | CLI 日志和输出格式化 |
| `PySide6` | 桌面小组件（可选） |
| `websockets` | WebSocket 实时推送 |
| `rumps` | macOS 菜单栏（可选，仅 macOS） |
| `py2app` | macOS 应用打包（可选，仅 macOS） |

## 项目结构

```
src/
├── __init__.py          # 版本号定义 (__version__)
├── cli.py               # CLI 入口，7 个子命令
├── config.py            # Config 类，YAML 配置
├── database.py          # Database 类，SQLite + WAL
├── events.py            # EventBus 事件总线（发布/订阅）
├── proxy/
│   ├── server.py        # ProxyServer (FastAPI + httpx)
│   └── adapters.py      # DeepSeekAdapter (Token 解析 + 费用计算)
├── sniffer/
│   ├── mitm.py          # ModelMonitorAddon (mitmproxy 插件)
│   └── cert.py          # CA 证书生成与管理
├── web/
│   ├── app.py           # create_app() 工厂函数
│   ├── api.py           # APIRouter REST + WS/SSE + 采集管理
│   └── static/
│       └── index.html   # 前端仪表盘 (Chart.js)
├── widget/
│   └── __init__.py      # 桌面小组件 (PySide6)
└── macos/
    ├── app.py           # MacApp macOS 原生 GUI (tkinter)
    └── menu_bar.py      # MenuBarApp 菜单栏 (rumps)
```

## 核心设计模式

### 事件总线（EventBus）

所有模块通过事件总线解耦通信：

```python
# 发布事件（proxy/sniffer 记录调用后）
from src.events import event_bus, ApiCallEvent
event_bus.publish(ApiCallEvent(
    mode="proxy", provider="deepseek",
    model="deepseek-chat", input_tokens=100,
    output_tokens=50, cost=0.0015,
    latency_ms=320, status_code=200,
).to_dict())

# 订阅事件（WebSocket/SSE/桌面小组件）
from src.events import event_bus
event_bus.subscribe_sync(lambda event: handle_event(event))
```

### 适配器模式（Adapter Pattern）

目前仅内置 DeepSeek 适配器。通过 `BaseAdapter` 抽象类统一接口：

```python
class BaseAdapter(ABC):
    def parse_usage(self, response_body: bytes) -> dict[str, int]:
        """解析非流式响应的 Token 使用量"""
        ...

    def parse_streaming_usage(self, full_response: str) -> dict[str, int]:
        """解析流式响应的 Token 使用量"""
        ...

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """计算调用费用"""
        ...
```

添加新提供商只需：
1. 在 `src/proxy/adapters.py` 中继承 `BaseAdapter`
2. 在 `ProxyServer._resolve_upstream()` 中注册路由
3. 在 `config.yaml` 中添加 `proxy.target`

### 三种展示形式架构

```
                  ┌────────────────────────────┐
                  │        SQLite 数据库         │
                  │      (统一数据源)            │
                  └──────────┬─────────────────┘
                             │ 读取
            ┌────────────────┼────────────────┐
            │                │                │
       ┌────▼─────┐   ┌─────▼─────┐   ┌──────▼──────┐
       │  Web 仪表盘 │   │桌面小组件  │   │ macOS 原生   │
       │ FastAPI +  │   │ PySide6   │   │ tkinter +   │
       │  Chart.js  │   │ 浮动面板   │   │ rumps       │
       │ WS/SSE实时 │   │ 系统托盘   │   │ 菜单栏+GUI  │
       │ REST API   │   │ 5色主题    │   │ py2app打包  │
       └────────────┘   └───────────┘   └─────────────┘
```

三种展示形式共享同一数据源（SQLite），通过 `src/database.py` 读取数据。Web 仪表盘额外通过事件总线获取实时推送。

### 配置驱动

所有可配置项集中在 `config.yaml`，通过 `Config` 类的点号路径访问：

```python
config = Config("config.yaml")
port = config.get("proxy.port")       # → 12345
target = config.get("proxy.target")   # → "https://api.deepseek.com"
```

## 运行与调试

### 启动各模式

```bash
# 代理模式
python main.py proxy -v          # -v 启用详细日志

# 嗅探模式
python main.py sniffer -v

# Web 仪表盘
python main.py web

# 桌面小组件
python main.py desktop

# macOS 原生 GUI
python main.py app               # 仅 macOS

# 导出数据
python main.py export -o data.json

# 查看配置
python main.py config --show
```

### 测试代理

```bash
# 启动代理
python main.py proxy &

# 测试请求
curl -x http://localhost:12345 https://api.deepseek.com/v1/models

# 启动 Web 仪表盘查看数据
python main.py web
```

### 使用自定义配置

```bash
python main.py -c /path/to/config.yaml proxy
```

## 扩展开发

### 添加新 API 提供商

1. 创建适配器类继承 `BaseAdapter`：

```python
# src/proxy/adapters.py
class NewProviderAdapter(BaseAdapter):
    def __init__(self, config: dict):
        super().__init__("newprovider", config)

    def parse_usage(self, body: bytes) -> dict[str, int]:
        data = json.loads(body)
        return {
            "input_tokens": data.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": data.get("usage", {}).get("completion_tokens", 0),
        }
```

2. 在 `ProxyServer._resolve_upstream()` 中处理新提供商域名映射

3. 添加定价到适配器的 `_pricing` 字典

### 添加新展示形式

项目的事件总线设计使其易于扩展新的展示形式：

1. 创建新模块（如 `src/terminal/`）
2. 通过 `Database` 读取数据
3. 通过 `EventBus` 订阅实时事件
4. 在 `src/cli.py` 中注册子命令

## 打包发布

### macOS 应用

```bash
pip install py2app rumps
python packaging/py2app_setup.py py2app
# 生成 dist/Model Monitor.app
```

## 代码规范

- **类型注解**: 使用 Python 3.12+ 类型语法（`dict[str, Any]` 而非 `Dict[str, Any]`）
- **日志**: 使用 `logging` 模块，配合 RichHandler
- **文档字符串**: 所有公共类和方法必须有中文文档字符串
- **配置**: 新增配置项必须在 `Config` 类中添加属性和默认值
- **事件**: 新增事件类型需扩展 `src/events.py` 中的 dataclass
