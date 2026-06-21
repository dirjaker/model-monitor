<div align="center">

<img src="assets/banner.svg" width="100%" alt="模型 API 监控工具">

<br>

### 📡 模型 API 监控工具

[![Stars](https://img.shields.io/github/stars/dirjaker/model-monitor?style=flat-square&label=Stars&color=FFD700)](https://github.com/dirjaker/model-monitor/stargazers)
[![Forks](https://img.shields.io/github/forks/dirjaker/model-monitor?style=flat-square&label=Forks&color=4A90D9)](https://github.com/dirjaker/model-monitor/network/members)
[![Contributors](https://img.shields.io/github/contributors/dirjaker/model-monitor?style=flat-square&label=Contributors&color=8B4513)](https://github.com/dirjaker/model-monitor/graphs/contributors)
[![License](https://img.shields.io/github/license/dirjaker/model-monitor?style=flat-square&label=License&color=20B2AA)](https://github.com/dirjaker/model-monitor/blob/dev/LICENSE)

</div>

---

## ✨ 功能特性

| 功能 | 描述 |
|------|------|
| 🔌 **多协议适配** | 支持 OpenAI、DeepSeek、OpenRouter、MiMo 等多种 API 格式 |
| 📊 **实时流量** | 实时监控 API 请求量、延迟、错误率，支持流式与非流式请求 |
| 💰 **费用追踪** | 按模型、按 Key 统计 Token 消耗和费用，支持每日/每月汇总 |
| 🔔 **阈值告警** | 日/月费用阈值告警，支持 Webhook 通知（飞书、Slack 等） |
| 📈 **费用预测** | 基于历史数据的线性回归费用预测，提供趋势分析 |
| 💡 **优化建议** | 自动分析使用模式，提供降本增效建议 |
| 🌐 **Web 仪表盘** | FastAPI + Vue.js 可视化监控面板，含 REST API 文档 |
| 🖥️ **TUI 终端** | Rich 驱动的终端实时监控界面 |
| 🍎 **macOS 原生** | macOS 菜单栏集成与原生 GUI（py2app 打包） |
| 🔄 **双模式运行** | 代理模式（HTTP Proxy）和嗅探模式（mitmproxy）灵活切换 |
| 📦 **多账户管理** | 支持多 API Key 账户管理，余额检查 |


## 🚀 快速开始

```bash
# 克隆项目
git clone https://github.com/dirjaker/model-monitor.git
cd model-monitor

# 创建虚拟环境
conda create -n model-monitor python=3.12 -y
conda activate model-monitor

# 安装依赖
pip install -r requirements.txt

# 运行项目（默认代理模式）
python main.py proxy
```

### 命令行用法

```bash
python main.py proxy          # HTTP 代理模式
python main.py sniffer        # mitmproxy 嗅探模式
python main.py web            # Web 仪表盘
python main.py tui            # 终端界面
python main.py stats          # 查看统计
python main.py export -o data.json  # 导出数据
python main.py config --show  # 查看配置
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 🌐 Web 仪表盘 | http://localhost:8000 |
| 📡 API 文档 | http://localhost:8000/api/docs |
| 🖥️ TUI 终端 | `python main.py tui` |

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | FastAPI, SQLAlchemy, uvicorn |
| **前端** | Vue.js, ECharts |
| **代理** | httpx (异步 HTTP/2), mitmproxy |
| **数据库** | SQLite (WAL 模式) |
| **终端** | Rich |
| **通知** | Webhook (httpx) |

## 📁 项目结构

```
model-monitor/
├── main.py                  # 统一入口
├── src/
│   ├── cli.py               # 命令行界面
│   ├── config.py            # YAML 配置管理
│   ├── database.py          # SQLite 数据库
│   ├── proxy/               # HTTP 代理服务器
│   │   ├── server.py        #   异步代理 (FastAPI + httpx)
│   │   ├── adapters.py      #   多提供商适配器
│   │   └── adapters_mimo.py #   MiMo 适配器
│   ├── sniffer/             # mitmproxy 嗅探
│   │   ├── mitm.py          #   嗅探插件
│   │   └── cert.py          #   CA 证书管理
│   ├── web/                 # Web 仪表盘
│   │   ├── app.py           #   FastAPI 应用
│   │   ├── api.py           #   REST API 路由
│   │   └── static/          #   前端静态文件
│   ├── analysis/            # 智能分析
│   │   ├── alerts.py        #   阈值告警
│   │   ├── predictor.py     #   费用预测
│   │   └── optimizer.py     #   成本优化建议
│   ├── tui/                 # Rich 终端界面
│   ├── macos/               # macOS 原生集成
│   └── accounts/            # 多账户管理
├── config.yaml              # 配置文件
├── docs/                    # 文档
└── packaging/               # 打包脚本
```

## 📄 许可证

[MIT License](LICENSE)

---

<div align="center">

🔗 **GitHub**: [dirjaker/model-monitor](https://github.com/dirjaker/model-monitor)

⭐ 如果这个项目对你有帮助，请给一个 Star 支持一下！

</div>
