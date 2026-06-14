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
| 🔌 **多协议适配** | 支持 OpenAI、DeepSeek、MiMo 等多种 API 格式 |
| 📊 **实时流量** | 实时监控 API 请求量、延迟、错误率 |
| 💰 **费用追踪** | 按模型、按 Key 统计 Token 消耗和费用 |
| 🔔 **告警通知** | 阈值告警，支持 Webhook 通知 |
| 📈 **Web 仪表盘** | 直观的可视化监控面板 |
| 🖥️ **TUI 终端** | 终端风格的实时监控界面 |


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

# 运行项目
python main.py
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 🌐 Web 仪表盘 | http://localhost:8000 |
| 📡 API 文档 | http://localhost:8000/docs |
| 🖥️ TUI 终端 | `python -m src.tui` |

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | FastAPI, SQLAlchemy |
| **前端** | Vue.js, ECharts |
| **代理** | Python, httpx |
| **通知** | Webhook |

## 📝 开发日志

- [x] 多协议适配器
- [x] 流量分析引擎
- [x] 费用追踪系统
- [x] Web 仪表盘
- [x] TUI 终端
- [ ] macOS 菜单栏
- [ ] 分布式部署
- [ ] 更多模型支持

## 📄 许可证

[MIT License](LICENSE)

---

<div align="center">

🔗 **GitHub**: [dirjaker/model-monitor](https://github.com/dirjaker/model-monitor)

⭐ 如果这个项目对你有帮助，请给一个 Star 支持一下！

</div>
