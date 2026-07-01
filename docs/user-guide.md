# 用户指南

## 安装

### 环境要求

在开始之前，你的电脑需要满足以下条件：

| 项目 | 要求 |
|------|------|
| **操作系统** | Windows / macOS / Linux 都可以 |
| **Python** | 3.12 或更高版本 |
| **pip** | Python 自带的包管理器（通常已安装） |
| **conda** | 推荐安装（可选，方便管理 Python 版本） |

> 💡 **什么是 conda？**
> conda 是一个环境管理工具，可以让你在一台电脑上同时安装多个 Python 版本。
> 如果你不想装 conda，直接用系统自带的 Python + venv 也可以。

### 安装 conda（如果没有的话）

```bash
# 下载 Miniconda（轻量版 conda）
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# 运行安装脚本
bash Miniconda3-latest-Linux-x86_64.sh

# 按照提示操作（一路 yes 即可），装完后重新打开终端
```

> macOS 用户请下载 `Miniconda3-latest-MacOSX-x86_64.sh`
> Windows 用户请去官网下载安装包：https://docs.conda.io/en/latest/miniconda.html

### 从源码安装

打开终端（命令行），逐条执行以下命令：

```bash
# 第1步：下载项目代码
git clone https://github.com/dirjaker/model-monitor.git
cd model-monitor

# 第2步：创建 Python 虚拟环境（推荐用 conda）
conda create -n model-monitor python=3.12 -y

# 第3步：激活虚拟环境
conda activate model-monitor

# 第4步：安装项目依赖
pip install -r requirements.txt
```

**安装完成后你会看到类似这样的输出：**

```
Successfully installed fastapi-0.115.x httpx-0.27.x ...
```

### 可选：只安装特定功能

如果你只想要 Web 仪表盘，不需要桌面小组件和 macOS 功能：

```bash
pip install -r requirements.txt --no-deps httpx fastapi uvicorn rich pyyaml mitmproxy websockets
```

如果你用的是 macOS，想打包成独立应用：

```bash
pip install rumps py2app
```

---

## 两种数据采集模式

在打开展示界面之前，需要先采集 API 调用数据。有两种采集方式：

### 1️⃣ 代理模式（推荐给大多数用户）

代理模式会在你的电脑上启动一个「中间人」服务。你把 API 请求发给它，它帮你转发给 DeepSeek，
同时自动记录每次调用的数据。

**启动命令：**

```bash
# 使用默认配置（端口 12345）
python main.py proxy
```

**启动成功后会看到：**

```
代理服务器启动 - http://localhost:12345
数据库: data/usage.db
INFO:     Started server process [12345]
INFO:     Application startup complete.
```

**如果你想换端口或地址：**

```bash
# 指定端口为 9090，监听地址为 127.0.0.1
python main.py proxy -p 9090 --host 127.0.0.1
```

#### 客户端配置代理的 3 种方式

**方式 1：环境变量（最通用）**

```bash
# 在终端执行这两条命令，之后所有 HTTP 请求都会走代理
export HTTP_PROXY=http://localhost:12345
export HTTPS_PROXY=http://localhost:12345

# 测试是否生效
curl -x http://localhost:12345 https://api.deepseek.com/v1/models
```

**方式 2：Python httpx 库**

```python
import httpx

# 在代码中指定代理地址
client = httpx.Client(proxy="http://localhost:12345")
response = client.post(
    "https://api.deepseek.com/v1/chat/completions",
    headers={"Authorization": "Bearer sk-your-key"},
    json={
        "model": "deepseek-v4-pro",
        "messages": [{"role": "user", "content": "你好"}]
    }
)
```

**方式 3：OpenAI Python SDK**

```python
from openai import OpenAI

# 把 base_url 改成代理地址，代理会自动转发给 DeepSeek
client = OpenAI(
    base_url="http://localhost:12345/v1",
    api_key="sk-your-deepseek-key",
)

response = client.chat.completions.create(
    model="deepseek-v4-pro",
    messages=[{"role": "user", "content": "你好"}]
)
```

---

### 2️⃣ 嗅探模式（适合不想改代码的用户）

嗅探模式通过 mitmproxy 被动「偷看」你的 HTTPS 流量。你不需要修改任何代码，只需要把系统代理指向嗅探器就行。

**启动命令：**

```bash
python main.py sniffer
```

**首次使用需要安装 CA 证书**（让嗅探器能解密 HTTPS 流量）：

**macOS 用户：**
```bash
# 自动安装证书到系统钥匙串
python -c "from src.sniffer.cert import install_cert_macos; install_cert_macos()"
```

**Linux 用户：**
```bash
# 手动添加到系统信任存储
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

> ⚠️ **重要提示：** 展示形式只负责「看数据」，不负责「采集数据」。
> 你需要先启动 proxy 或 sniffer 来采集数据，展示界面才能显示内容。
>
> **最简单的方式：** 用 Web 仪表盘自带的「启动/停止」按钮来管理采集进程，
> 不需要手动开两个终端。

---

### 🌐 形式一：Web 仪表盘（最推荐）

这是功能最完整、使用最方便的方式。打开浏览器就能看，不需要安装任何额外软件。

#### 启动

```bash
python main.py web
```

**启动成功后会看到：**

```
Web 仪表盘启动 - http://localhost:10004
  局域网: http://192.168.31.xxx:10004
  本地:   http://localhost:10004
INFO:     Application startup complete.
```

**访问地址：**

| 地址 | 说明 | 谁可以用 |
|------|------|----------|
| `http://localhost:10004` | 本机访问 | 你自己 |
| `http://192.168.31.xxx:10004` | 局域网访问 | 同网络的其他设备 |
| `http://你的公网IP:10004` | 公网访问 | 需要配置 frp 或端口转发 |

**如果想换端口：**

```bash
python main.py web -p 8080 --host 0.0.0.0
```

#### 界面各区域说明

打开 Web 仪表盘后，你会看到一个蓝白配色的界面，从上到下依次是：

```
┌──────────────────────────────────────────────────────┐
│  [M] Model Monitor     ● 运行中  |  16:30  ⚙      │  ← 顶部状态栏
├──────────────────────────────────────────────────────┤
│  🔌 代理模式                              ▶ 启动     │
│  127.0.0.1:12345 → api.deepseek.com    未启动        │  ← 采集控制区
├──────────────────────────────────────────────────────┤
│  仪表盘                                              │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌───┐│
│  │总请求│ │总费用│ │今日  │ │本月  │ │输入  │ │输出││  ← 6 个统计卡片
│  │  3   │ │$0.004│ │$0.004│ │$0.004│ │  33  │ │495││
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └───┘│
│                                                      │
│  ┌─ 每日费用 ───────────┐  ┌─ 模型分布 ──────────┐  │
│  │  📊 柱状图           │  │  🍩 饼图            │  │  ← 2 个图表
│  └──────────────────────┘  └─────────────────────┘  │
│  ┌─ 每小时费用 ─────────┐  ┌─ Token 分布 ────────┐  │
│  │  📈 折线图           │  │  🍩 饼图            │  │  ← 2 个图表
│  └──────────────────────┘  └─────────────────────┘  │
│                                                      │
│  调用记录（最多显示 50 条，超出可滚动）               │
│  ┌──────┬────┬────────┬────┬────┬──────┬────┬────┐ │  ← 调用记录表
│  │ 时间 │模式│ 模型   │输入│输出│ 费用 │延迟│状态│ │
│  ├──────┼────┼────────┼────┼────┼──────┼────┼────┤ │
│  │ ...  │代理│deep... │ 14 │198 │$0.00│3510│ 200│ │
│  └──────┴────┴────────┴────┴────┴──────┴────┴────┘ │
│                                                      │
│  ┌─ 模型用量 ────────────────────────────────────┐  │
│  │ 模型         调用    输入    输出    费用  延迟│  │  ← 模型统计表
│  ├──────────────────────────────────────────────┤  │
│  │ deepseek-...   2      28     495   $0.00  3510│  │
│  └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

#### 采集进程管理（Web 界面一键操作）

这是最方便的功能——你不需要手动开终端跑 proxy，直接在网页上操作：

**第1步：** 打开设置面板
- 点击右上角的 **⚙（齿轮）按钮**

**第2步：** 选择采集模式
- 点击 **🔌 代理模式** 或 **📡 嗅探模式**

**第3步：** 配置参数（代理模式下）

| 字段 | 说明 | 默认值 |
|------|------|--------|
| 目标 API | 转发到哪个 API 地址 | `https://api.deepseek.com` |
| 监听主机 | 代理监听哪个网卡 | `127.0.0.1`（改 `0.0.0.0` 可局域网访问） |
| 端口 | 代理端口号 | `12345` |
| 超时 | 请求超时时间（秒） | `120` |

**第4步：** 点击 **保存**，关闭设置面板

**第5步：** 点击 **▶ 启动** 按钮

启动成功后，按钮会变成 **■ 停止**，右侧标签显示「运行中」，顶部状态点变绿色。

**第6步：** 用 curl 测试一下：

```bash
curl -s http://localhost:12345/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-你的DeepSeek密钥" \
  -d '{"model":"deepseek-v4-pro","messages":[{"role":"user","content":"你好"}]}'
```

然后看看仪表盘的卡片和图表有没有数据更新。

**第7步：** 想停止就点击 **■ 停止**

#### REST API（供开发者使用）

除了网页界面，你也可以通过 HTTP 请求来获取数据或控制采集：

```bash
# 1️⃣ 查看总体统计
curl http://localhost:10004/api/stats
# 返回示例：
# {"status":"ok","data":{"total_calls":3,"total_cost":0.004,...}}

# 2️⃣ 查看最近调用记录
curl "http://localhost:10004/api/calls?limit=10"

# 3️⃣ 查看近30天每日统计
curl "http://localhost:10004/api/daily?days=30"

# 4️⃣ 查看近24小时统计
curl "http://localhost:10004/api/hourly?hours=24"

# 5️⃣ 按模型统计
curl http://localhost:10004/api/models

# 6️⃣ 健康检查
curl http://localhost:10004/api/health
# 返回：{"status":"ok"}

# 7️⃣ 启动采集进程
curl -X POST "http://localhost:10004/api/mode/start?mode=proxy&port=12345"

# 8️⃣ 停止采集进程
curl -X POST http://localhost:10004/api/mode/stop

# 9️⃣ 查看采集进程状态
curl http://localhost:10004/api/mode/status

# 🔟 修改配置
curl -X POST http://localhost:10004/api/settings \
  -H "Content-Type: application/json" \
  -d '{"proxy_port": 9999}'
```

> 完整的 API 文档可以访问 `http://localhost:10004/api/docs`（Swagger UI）

---

### 🪟 形式二：桌面小组件（适合常驻桌面）

这是一个浮动在桌面的小窗口，实时显示监控数据。支持 Windows、macOS、Linux。

> ⚠️ **前提条件：** 桌面小组件需要 PySide6 图形库，且需要有显示器（SSH 无图形界面不能用）。

#### 启动

```bash
python main.py desktop
```

启动后桌面会出现一个半透明的小窗口：

```
┌─ MODEL MONITOR ──────────────── 运行中 ● ─┐
│                                             │
│  CALLS     COST     TODAY     MONTH         │
│   3       $0.004   $0.004    $0.004         │
│                                             │
│  INPUT TOKENS    OUTPUT TOKENS              │
│    33             495                       │
│  ─────────────────────────────────────────  │
│  模型                 调用   费用            │
│  deepseek-v4-pro        2   $0.0040         │
│  deepseek-chat          1   $0.0000         │
│                                             │
│  最近: deepseek-v4-pro     3510ms           │
└─────────────────────────────────────────────┘
```

#### 外观特性

| 特性 | 说明 |
|------|------|
| 窗口样式 | 无边框、圆角、半透明 |
| 移动 | 鼠标拖拽窗口任意位置 |
| 置顶 | 始终在其他窗口前面（可关闭） |
| 位置记忆 | 关机重启后自动恢复到上次位置 |
| 透明度 | 30%~100% 可调 |

#### 内置 5 色主题

在设置里可以切换：

| 主题名 | 风格 | 适合场景 |
|--------|------|----------|
| `dark` 🖤 | 深灰底 + 蓝紫点缀 | 默认，通用 |
| `deepblue` 💙 | 藏青底 + 蓝光 | 蓝色系桌面 |
| `dusk` 💜 | 紫棕底 + 粉紫 | 暖色系桌面 |
| `aurora` 💚 | 墨绿底 + 青绿 | 暗色护眼 |
| `moonlight` 🤍 | 暗紫底 + 淡紫 | 柔和风格 |

#### 数据展示说明

| 指标区域 | 显示内容 |
|----------|----------|
| CALLS | 历史总调用次数 |
| COST | 历史总费用（美元） |
| TODAY | 今日累计费用 |
| MONTH | 本月累计费用 |
| INPUT TOKENS | 历史输入 Token 总数 |
| OUTPUT TOKENS | 历史输出 Token 总数 |
| 模型列表 | 每个模型的调用次数和费用 |
| 最近延迟 | 最近一次调用的响应时间 |

#### 操作方式

所有操作都在系统托盘的图标上右键点击：

| 操作 | 步骤 |
|------|------|
| **隐藏/显示** | 右键托盘图标 → 显示/隐藏 |
| **立即刷新** | 右键托盘图标 → 立即刷新 |
| **打开设置** | 右键托盘图标 → 设置 |
| **退出** | 右键托盘图标 → 退出 |

也可以直接拖拽窗口移动。

#### 设置面板

右键 → 设置，可以看到：

| 设置项 | 说明 | 默认值 |
|--------|------|--------|
| 刷新间隔 | 每隔多少秒自动刷新一次数据 | 5 秒 |
| 颜色主题 | 切换 5 种主题 | dark |
| 窗口置顶 | 勾选后小组件始终在最前面 | 开启 |
| 透明度 | 滑块调节，越往右越不透明 | 100% |
| 重置位置 | 恢复窗口到屏幕居中 | 按钮 |

---

### 🍎 形式三：macOS 原生应用（仅 Mac 用户）

提供 macOS 风格的界面和菜单栏集成。

> ⚠️ **仅 macOS 可用**，Windows 和 Linux 无法使用。

#### 启动

```bash
python main.py app
```

启动后会出现一个控制面板窗口。

#### tkinter 图形界面

窗口分为几个区域：

```
┌─────────────── Model Monitor ─────────────────┐
│                                                │
│  Model Monitor                                 │
│  API Usage Monitoring Tool                     │  ← 标题区
│                                                │
│  ┌─ Mode Selection ──────────────────────────┐ │
│  │  ○ Proxy Mode   ○ Sniffer Mode            │ │  ← 模式选择
│  └───────────────────────────────────────────┘ │
│                                                │
│  [Start]  [Stop]            Stopped (红色)     │  ← 控制按钮 + 状态
│                                                │
│  ┌─ Statistics ──────────────────────────────┐ │
│  │  Total Calls:           3                 │ │
│  │  Input Tokens:         33                │ │  ← 统计信息
│  │  Output Tokens:       495                │ │
│  │  Total Cost:       $0.0040               │ │
│  │  Today Cost:       $0.0040               │ │
│  │  Month Cost:       $0.0040               │ │
│  │  Avg Latency:     3510.0ms               │ │
│  │  Last Call:        2025-06-30 17:08...   │ │
│  └──────────────────────────────────────────┘ │
│                                                │
│  [Refresh]                          [Quit]     │  ← 底部按钮
└────────────────────────────────────────────────┘
```

**各按钮功能：**

| 按钮 | 功能 |
|------|------|
| **Start** | 启动采集（根据选中的模式启动 proxy 或 sniffer） |
| **Stop** | 停止采集 |
| **Refresh** | 手动刷新统计数据 |
| **Quit** | 退出应用 |

- 统计信息每 **5 秒** 自动刷新一次

#### rumps 菜单栏

除了窗口界面，还有一个菜单栏应用。启动后在屏幕顶部菜单栏会出现 `MM` 图标。

点击展开菜单：

| 菜单项 | 功能 |
|--------|------|
| **Show Stats** | 弹出通知，显示总调用、总费用、今日费用、平均延迟 |
| **Start Proxy** | 后台启动代理采集 |
| **Start Sniffer** | 后台启动嗅探采集 |
| ——— | 分隔线 |
| **Quit** | 退出菜单栏应用 |

#### 打包为独立应用

如果你不想每次都开终端跑命令，可以把应用打包成 `.app` 文件，像普通软件一样双击打开：

```bash
# 安装打包工具
pip install py2app

# 打包
python packaging/py2app_setup.py py2app

# 打包完成后在 dist/ 目录找到 Model Monitor.app
open dist/
```

之后就可以把 `Model Monitor.app` 拖到「应用程序」文件夹了。

---

## 典型使用流程（4 种场景）

根据你的需求选择一种：

### 场景一：Web 仪表盘 + 手动采集（最灵活）

适合想分别控制采集和展示的用户。

```bash
# 终端 1：启动代理采集
python main.py proxy

# 终端 2：启动 Web 仪表盘
python main.py web

# 然后浏览器打开 http://localhost:10004

# 在另一个终端用 curl 测试：
curl -s http://localhost:12345/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-key" \
  -d '{"model":"deepseek-v4-pro","messages":[{"role":"user","content":"hi"}],"stream":false}'

# 回到浏览器看仪表盘有没有数据
```

### 场景二：全程 Web 仪表盘控制（最简单）

只需要启动一个终端，采集和展示都在网页上操作。

```bash
# 只需要启动 Web 仪表盘
python main.py web

# 浏览器打开 http://localhost:10004
# 点击 ⚙ → 选择模式 → 保存 → 点击「启动」
# 采集进程就自动跑起来了
```

### 场景三：桌面小组件常驻

适合喜欢桌面小工具的用户。

```bash
# 终端 1：启动代理采集
python main.py proxy

# 终端 2：启动桌面小组件
python main.py desktop

# 小组件会浮动在桌面上，随时查看数据
```

### 场景四：macOS 原生体验

适合 Mac 用户。

```bash
# 先启动采集
python main.py proxy &

# 再启动 macOS 界面
python main.py app

# 或者打包成独立应用后直接打开
python packaging/py2app_setup.py py2app
open dist/Model Monitor.app
```

---

## 配置说明

配置文件是项目根目录下的 `config.yaml`，所有可选项都在这里。

### 完整配置示例及说明

```yaml
# ── 运行模式（采集模式选择） ──
# proxy  = 代理模式（推荐，功能最完整）
# sniffer = 嗅探模式（无需改代码）
mode: proxy

# ── 代理服务器配置 ──
proxy:
  host: 127.0.0.1       # 监听地址（127.0.0.1=仅本机，0.0.0.0=所有网卡）
  port: 12345            # 监听端口
  timeout: 120           # 请求超时（秒）
  target: https://api.deepseek.com  # 转发目标

# ── 嗅探器配置 ──
sniffer:
  port: 8080             # 嗅探端口
  targets:               # 监控的域名列表
    - api.deepseek.com

# ── Web 仪表盘配置 ──
web:
  host: 0.0.0.0          # 监听地址（0.0.0.0 可以从局域网访问）
  port: 10004            # 端口

# ── 数据库配置 ──
database:
  path: data/usage.db    # SQLite 数据库文件路径

# ── 告警配置（功能保留，默认关闭） ──
alerts:
  enabled: false
  daily_threshold: 10.0       # 每日费用超过 10 美元触发告警
  monthly_threshold: 100.0    # 月度费用超过 100 美元触发告警
  webhook_url: ''             # 告警通知地址（飞书/Slack 等）
```

### 如何修改配置

**方式 1：直接编辑文件**

用任何文本编辑器打开 `config.yaml`，修改后保存，重启服务生效。

**方式 2：命令行修改**

```bash
# 查看当前配置摘要
python main.py config

# 查看完整配置文件内容
python main.py config --show

# 修改代理端口为 9090
python main.py config --set-key proxy.port --set-value 9090

# 修改监听地址为 0.0.0.0
python main.py config --set-key proxy.host --set-value 0.0.0.0
```

**方式 3：Web 界面修改**

打开 `http://localhost:10004`，点击右上角 ⚙，修改后保存即可。

---

## 导出数据

```bash
# 导出最近 30 天的数据到 data.json
python main.py export -o data.json

# 导出最近 7 天的数据
python main.py export -o data.json -d 7

# 使用自定义配置文件导出
python main.py -c /path/to/config.yaml export -o data.json
```

导出的 JSON 文件包含每次 API 调用的详细信息：时间、模型、Token、费用、延迟等。

---

## 常见问题

### Q: 三种展示形式可以同时运行吗？

**可以。** 采集模式（proxy/sniffer）+ 任意展示形式可以同时运行。
但**同一种展示形式只能启动一个实例**（端口冲突）。

例如可以同时跑：`proxy` + `web` + `desktop`（三个进程同时运行）

### Q: 代理模式和嗅探模式有什么区别？

| | 代理模式 | 嗅探模式 |
|--|---------|----------|
| 是否需要改代码 | 需要配置代理地址 | 不需要 |
| 数据完整性 | 完整记录请求+响应 | 只记录核心数据 |
| 适用场景 | 新开发的应用 | 已有的、不方便改代码的应用 |

### Q: 桌面小组件在 Windows/Linux 上能用吗？

**可以。** 桌面小组件基于 PySide6，跨平台支持 Windows、Linux 和 macOS。
但需要有显示器（X11/Wayland），纯 SSH 终端无法使用。

### Q: macOS 原生应用和桌面小组件有什么区别？

- **macOS 原生应用**：tkinter 基础 GUI，外观朴素但轻量；另有 rumps 菜单栏集成。**仅 macOS。**
- **桌面小组件**：PySide6 现代化浮动面板，**跨平台**，5 色主题，功能更丰富。

### Q: 数据存储在哪里？

默认在项目目录下的 `data/usage.db`，是一个 SQLite 数据库文件。
你可以直接复制这个文件来备份数据，也可以通过 `database.path` 配置修改位置。

### Q: 如何查看实时数据变动？

| 展示形式 | 刷新方式 |
|----------|----------|
| **Web 仪表盘** | WebSocket 实时推送 + 每 15 秒自动刷新 |
| **桌面小组件** | 按设置间隔自动刷新（默认 5 秒） |
| **macOS 原生** | 每 5 秒自动刷新 |

### Q: 启动时报 "address already in use" 怎么办？

说明端口被占用了，可能是上次的程序没有完全退出。

```bash
# 查看哪个进程占用了端口（以 12345 为例）
ss -tlnp | grep 12345

# 强制结束进程（把 12345 换成实际 PID）
kill -9 <PID>

# 或者换一个端口启动
python main.py proxy -p 12346
```
