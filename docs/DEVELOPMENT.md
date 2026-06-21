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
| `rich` | 终端 UI 渲染 |

## 项目结构

```
src/
├── __init__.py          # 版本号定义 (__version__)
├── cli.py               # CLI 入口，8 个子命令
├── config.py            # Config 类，YAML + 环境变量
├── database.py          # Database 类，SQLite + WAL
├── proxy/
│   ├── server.py        # ProxyServer (FastAPI + httpx)
│   ├── adapters.py      # BaseAdapter + DeepSeek/OpenRouter/Generic
│   └── adapters_mimo.py # MiMoAdapter
├── sniffer/
│   ├── mitm.py          # ModelMonitorAddon (mitmproxy 插件)
│   └── cert.py          # CA 证书生成与管理
├── web/
│   ├── app.py           # create_app() 工厂函数
│   ├── api.py           # APIRouter REST 端点
│   └── static/          # 前端静态文件 (HTML/JS/CSS)
├── analysis/
│   ├── alerts.py        # AlertManager 后台线程告警
│   ├── predictor.py     # CostPredictor 线性回归预测
│   └── optimizer.py     # CostOptimizer 使用模式分析
├── tui/
│   └── app.py           # TuiApp Rich 终端仪表盘
├── macos/
│   ├── app.py           # MacApp macOS 原生 GUI
│   └── menu_bar.py      # 菜单栏集成
└── accounts/
    └── accounts.py      # AccountManager 多账户管理
```

## 核心设计模式

### 适配器模式（Adapter Pattern）

所有 API 提供商通过 `BaseAdapter` 抽象类统一接口：

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
2. 在 `get_adapter()` 函数中注册
3. 在 `config.yaml` 中添加提供商配置

### 配置驱动

所有可配置项集中在 `config.yaml`，支持：
- YAML 文件加载
- `${VAR_NAME}` 环境变量引用
- `MM_<SECTION>_<KEY>` 环境变量覆盖
- 点号路径访问（如 `config.get("proxy.port")`）

### 线程安全数据库

`Database` 类使用 `threading.local()` 为每个线程维护独立连接，配合 `threading.Lock()` 保护写操作，SQLite WAL 模式支持并发读。

## 运行与调试

### 启动各模式

```bash
# 代理模式
python main.py proxy -v          # -v 启用详细日志

# 嗅探模式
python main.py sniffer -v

# Web 仪表盘
python main.py web

# 终端界面
python main.py tui

# 查看统计
python main.py stats
```

### 测试代理

```bash
# 启动代理
python main.py proxy &

# 测试请求
curl -x http://localhost:8080 https://api.deepseek.com/v1/models

# 查看统计
python main.py stats
```

### 使用自定义配置

```bash
python main.py -c /path/to/config.yaml proxy
```

## 添加新提供商适配器

1. 创建适配器类：

```python
# src/proxy/adapters.py
class NewProviderAdapter(BaseAdapter):
    def __init__(self, config: dict[str, Any]):
        super().__init__("newprovider", config)

    def parse_usage(self, response_body: bytes) -> dict[str, int]:
        data = json.loads(response_body)
        usage = data.get("usage", {})
        return {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }
```

2. 注册适配器：

```python
# src/proxy/adapters.py 的 get_adapter() 函数
adapters = {
    "deepseek": DeepSeekAdapter,
    "openrouter": OpenRouterAdapter,
    "mimo": MiMoAdapter,
    "newprovider": NewProviderAdapter,  # 新增
}
```

3. 添加配置：

```yaml
# config.yaml
providers:
  newprovider:
    base_url: https://api.newprovider.com
    api_key: ${NEWPROVIDER_API_KEY}
    pricing:
      model-name:
        input: 1.0
        output: 2.0
```

## 打包发布

### macOS 应用

```bash
python packaging/py2app_setup.py py2app
# 生成 dist/Model Monitor.app
```

## 代码规范

- 类型注解：使用 Python 3.12+ 类型语法（`dict[str, Any]` 而非 `Dict[str, Any]`）
- 日志：使用 `logging` 模块，配合 RichHandler
- 文档字符串：所有公共类和方法必须有中文文档字符串
- 配置：新增可配置项必须在 `Config` 类中添加属性和默认值
