# 用户指南

## 安装

### 环境要求

- Python 3.12+
- pip 或 conda（推荐）

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

> **桌面小组件**需要 PySide6，若想跳过：
> ```bash
> pip install -r requirements.txt --no-deps httpx fastapi uvicorn rich pyyaml mitmproxy websockets
> ```

> **macOS 打包**需要额外安装：
> ```bash
> pip install rumps py2app
> ```

---

## 两种数据采集模式

在打开展示界面之前，需要先启动采集模式来收集 API 调用数据。

### 1. 代理模式（推荐）

通过本地 HTTP 代理转发请求到 DeepSeek API，自动记录每次调用。

```bash
# 使用默认配置启动（端口 12345）
python main.py proxy

# 指定端口和地址
python main.py proxy -p 9090 --host 127.0.0.1
```

**配置客户端使用代理：**

```bash
# 环境变量方式（全局生效）
export HTTP_PROXY=http://localhost:12345
export HTTPS_PROXY=http://localhost:12345

# 或在使用 SDK 时指定
import httpx
client = httpx.Client(proxy="http://localhost:12345")

# OpenAI Python SDK
from openai import OpenAI
client = OpenAI(
    base_url="http://localhost:12345/v1",
    api_key="sk-your-key",
)
```

### 2. 嗅探模式

通过 mitmproxy 被动监听 HTTPS 流量，**无需修改客户端代码**。

```bash
# 启动嗅探器（端口 8080）
python main.py sniffer

# 首次使用需要安装 CA 证书（macOS）
python -c "from src.sniffer.cert import install_cert_macos; install_cert_macos()"

# Linux 手动添加证书到系统信任存储
sudo cp ~/.model-monitor/certs/mitmproxy-ca-cert.pem /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

**配置系统代理指向嗅探器：**

```bash
export HTTP_PROXY=http://localhost:8080
export HTTPS_PROXY=http://localhost:8080
```

---

## 三种展示形式详解

### 🌐 形式一：Web 仪表盘（推荐）

**命令：** `python main.py web`

跨平台的 Web 可视化面板，功能最完整，支持实时推送和采集进程管理。

**启动：**

```bash
# 默认端口 10004
python main.py web

# 指定端口
python main.py web -p 8080 --host 0.0.0.0
```

**访问地址：**

| 服务 | 地址 |
|------|------|
| Web 仪表盘 | http://localhost:10004 |
| REST API 文档 | http://localhost:10004/api/docs |

**功能特性：**

| 功能 | 说明 |
|------|------|
| 📊 **统计概览** | 总调用数、总费用、总 Token、平均延迟 |
| 📈 **趋势图表** | 每日/每小时调用量和费用趋势 |
| 📋 **模型排行** | 各模型调用次数和费用排行 |
| 🔄 **实时推送** | WebSocket + SSE 双通道，数据变动即时刷新 |
| 🎛️ **采集管理** | 仪表盘内一键启动/停止 proxy 或 sniffer 采集进程 |
| ⚙️ **配置管理** | 在线修改代理端口、嗅探目标等配置并持久化 |

**从仪表盘管理采集进程：**

启动 Web 仪表盘后，可以在页面控制区直接：
1. 选择采集模式（proxy 或 sniffer）
2. 设置端口号
3. 点击「启动」开始采集
4. 点击「停止」结束采集
5. 查看当前采集进程状态

**REST API 示例：**

```bash
# 获取总体统计
curl http://localhost:10004/api/stats

# 获取最近 10 条调用记录
curl "http://localhost:10004/api/calls?limit=10"

# 获取最近 7 天的每日统计
curl "http://localhost:10004/api/daily?days=7"

# 启动采集进程
curl -X POST "http://localhost:10004/api/mode/start?mode=proxy&port=12345"

# 停止采集进程
curl -X POST http://localhost:10004/api/mode/stop

# 查询采集进程状态
curl http://localhost:10004/api/mode/status

# 修改配置
curl -X POST http://localhost:10004/api/settings \
  -H "Content-Type: application/json" \
  -d '{"proxy_port": 9999}'
```

---

### 🪟 形式二：桌面小组件

**命令：** `python main.py desktop`

基于 PySide6 的浮动透明面板，适合常驻桌面角落，随时查看监控数据。

**启动：**

```bash
python main.py desktop
```

**外观特性：**

- 无边框浮动窗口，鼠标拖拽移动
- 半透明背景，可调节透明度
- 窗口置顶（可在设置中关闭）
- 窗口位置自动记忆，重启后恢复

**内置 5 色主题：**

| 主题 | 风格 | 色调 |
|------|------|------|
| `dark` | 暗色经典 | 深灰底 + 蓝紫点缀 |
| `deepblue` | 深邃蓝 | 藏青底 + 蓝光点缀 |
| `dusk` | 暮色紫 | 紫棕底 + 粉紫点缀 |
| `aurora` | 极光绿 | 墨绿底 + 青绿点缀 |
| `moonlight` | 月光白 | 暗紫底 + 淡紫点缀 |

**数据展示：**

| 指标 | 说明 |
|------|------|
| 今日调用 | 当日 API 调用总次数 |
| 今日费用 | 当日累计费用（美元） |
| 本月费用 | 当月累计费用（美元） |
| 总调用 | 历史累计调用次数 |
| 模型排行 | 各模型的调用次数和费用 |
| 状态指示 | 运行状态彩色圆点（正常/警告/错误） |

**操作方式：**

| 操作 | 方式 |
|------|------|
| 移动位置 | 鼠标拖拽窗口任意位置 |
| 隐藏/显示 | 右键托盘图标 → 显示/隐藏 |
| 设置 | 右键托盘图标 → 设置 |
| 刷新 | 右键托盘图标 → 立即刷新（或按设置间隔自动刷新） |
| 退出 | 右键托盘图标 → 退出 |

**设置面板：**

| 设置项 | 说明 |
|--------|------|
| 刷新间隔 | 1-60 秒，自动从数据库刷新数据 |
| 颜色主题 | 5 种预设主题切换 |
| 窗口置顶 | 勾选后小组件始终在最前 |
| 透明度 | 30%-100% 滑块调节 |
| 重置位置 | 恢复窗口到屏幕居中位置 |

> **注意：** 桌面小组件需要 PySide6，无窗口环境（如纯 SSH 终端）无法使用。

---

### 🍎 形式三：macOS 原生应用

**命令：** `python main.py app`

提供两套 macOS 原生界面：tkinter 图形界面和 rumps 菜单栏应用。

**启动：**

```bash
# 仅 macOS 可用
python main.py app
```

#### tkinter 图形界面

启动后显示一个 600×500 的控制面板：

| 区域 | 功能 |
|------|------|
| 标题区 | 显示项目名称和版本 |
| 模式选择 | 单选按钮切换 Proxy / Sniffer 模式 |
| 控制按钮 | Start 启动、Stop 停止 |
| 状态指示 | 绿色 Running / 红色 Stopped |
| 统计面板 | 只读文本区，显示总调用、Token、费用、延迟 |
| 底部按钮 | Refresh 手动刷新、Quit 退出 |

- 统计信息每 5 秒自动刷新

#### rumps 菜单栏

启动后系统菜单栏出现 `MM` 图标，点击展开菜单：

| 菜单项 | 功能 |
|--------|------|
| Show Stats | 弹窗显示总调用、总费用、今日费用、平均延迟 |
| Start Proxy | 后台启动代理模式采集 |
| Start Sniffer | 后台启动嗅探模式采集 |
| — | 分隔线 |
| Quit | 退出菜单栏应用 |

#### macOS 应用打包

```bash
# 安装打包工具
pip install py2app

# 打包为独立 .app
python packaging/py2app_setup.py py2app

# 生成的 .app 在 dist/ 目录
open dist/
```

> **注意：** `python main.py app` 仅 macOS 可用。如需在 macOS 上运行桌面小组件，请使用 `python main.py desktop`（需要 PySide6）。

---

## 典型使用流程

### 场景一：Web 仪表盘 + 手动采集

```bash
# 终端 1：启动代理采集
python main.py proxy

# 终端 2：启动 Web 仪表盘
python main.py web

# 在客户端代码中配置代理
# export HTTP_PROXY=http://localhost:12345

# 浏览器访问 http://localhost:10004 查看数据
```

### 场景二：全程 Web 仪表盘控制

```bash
# 只需启动 Web 仪表盘
python main.py web

# 在浏览器中 http://localhost:10004
# 通过控制面板启动/停止采集进程
# 所有操作都在一个界面上完成
```

### 场景三：桌面小组件常驻

```bash
# 终端 1：启动代理采集
python main.py proxy

# 终端 2：启动桌面小组件
python main.py desktop

# 小组件常驻桌面角落，实时显示数据
```

### 场景四：macOS 原生体验

```bash
# 启动 macOS 原生 GUI 或先启动代理
python main.py proxy &

# 启动 macOS 界面
python main.py app

# 或打包为独立应用
python packaging/py2app_setup.py py2app
```

---

## 配置说明

配置文件路径：`config.yaml`

### 完整配置

```yaml
# 运行模式: proxy | sniffer
mode: proxy

# 代理服务器配置
proxy:
  host: 127.0.0.1
  port: 12345
  timeout: 120          # 上游超时（秒）
  target: https://api.deepseek.com

# 嗅探器配置
sniffer:
  port: 8080
  targets:
    - api.deepseek.com

# Web 仪表盘配置
web:
  host: 0.0.0.0
  port: 10004

# 数据库配置
database:
  path: data/usage.db

# 告警配置
alerts:
  enabled: false
  daily_threshold: 10.0       # 日费用阈值（美元）
  monthly_threshold: 100.0    # 月费用阈值（美元）
  webhook_url: ''
```

### 配置管理命令

```bash
# 查看当前配置摘要
python main.py config

# 查看完整配置文件
python main.py config --show

# 修改配置项
python main.py config --set-key proxy.port --set-value 9090
```

---

## 数据导出

```bash
# 导出最近 30 天数据
python main.py export -o data.json

# 指定天数
python main.py export -o data.json -d 7

# 使用自定义配置
python main.py -c /path/to/config.yaml export -o data.json
```

---

## 常见问题

### Q: 三种展示形式可以同时运行吗？

**可以。** 代理/嗅探采集模式+任意展示形式可以组合使用。但**同一展示形式只能启动一个实例**（端口冲突）。

### Q: 代理模式和嗅探模式有什么区别？

- **代理模式**: 客户端需配置 HTTP 代理，主动转发请求到上游 API，数据最完整
- **嗅探模式**: 被动监听 HTTPS 流量，无需修改客户端配置，适合监控已有应用

### Q: 桌面小组件在 Windows/Linux 上能用吗？

**可以。** 桌面小组件基于 PySide6，跨平台支持 Windows、Linux 和 macOS。需要 X11/Wayland 显示环境（Linux 服务器无 GUI 则无法使用）。

### Q: macOS 原生应用和桌面小组件有什么区别？

- **macOS 原生应用**：tkinter 基础 GUI，外观朴素但原生轻量；rumps 菜单栏集成。仅 macOS。
- **桌面小组件**：PySide6 现代化浮动面板，跨平台，5 色主题，功能更丰富。

### Q: 数据存储在哪里？

默认存储在 `data/usage.db`（SQLite 数据库），可通过 `database.path` 配置修改。

### Q: 如何查看实时数据变动？

- **Web 仪表盘**: 通过 WebSocket/SSE 自动推送，无需手动刷新
- **桌面小组件**: 按设置间隔自动刷新（默认 5 秒）
- **macOS 原生**: 自动每 5 秒刷新
