# 更新日志

本文件记录 Model Monitor 项目的所有重要变更。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [1.0.0] - 2025-06-22

### 新增

#### 核心功能
- **统一入口**: `main.py` + `src/cli.py` 提供 8 个子命令（`proxy`、`sniffer`、`web`、`tui`、`app`、`stats`、`export`、`config`）
- **代理模式**: 基于 FastAPI + httpx 的异步 HTTP 代理服务器，支持流式和非流式请求
- **嗅探模式**: 基于 mitmproxy 的 HTTPS 流量嗅探插件
- **统一数据库**: SQLite + WAL 模式，线程安全，记录每次 API 调用详情

#### 多提供商支持
- DeepSeek API 适配器
- OpenRouter API 适配器
- 小米 MiMo 模型适配器（通过 OpenRouter 访问）
- 通用 OpenAI 兼容适配器

#### 监控与分析
- **Web 仪表盘**: FastAPI + Vue.js + ECharts 可视化面板
- **TUI 终端界面**: Rich 驱动的终端实时监控（3 秒刷新）
- **阈值告警**: 日/月费用阈值告警，支持 Webhook 通知
- **费用预测**: 基于线性回归的未来费用预测（含 R² 置信度）
- **优化建议**: 自动分析使用模式，识别高延迟/高费用问题

#### 配置管理
- YAML 配置文件（`config.yaml`）
- 环境变量引用（`${VAR_NAME}`）
- 环境变量覆盖（`MM_<SECTION>_<KEY>`）
- 点号路径访问（`config.get("proxy.port")`）

#### macOS 集成
- macOS 原生 GUI（tkinter）
- 菜单栏集成
- py2app 打包支持

#### 多账户管理
- 多 API Key 账户管理
- 账户余额查询
- 按标签分组

#### REST API
- `GET /api/stats` — 总体统计
- `GET /api/calls` — 调用记录（分页、筛选）
- `GET /api/models` — 按模型统计
- `GET /api/daily` — 每日统计
- `GET /api/hourly` — 每小时统计
- `GET /api/health` — 健康检查
- Swagger UI 交互式文档（`/api/docs`）

#### 数据导出
- JSON 格式数据导出
- 支持按天数范围导出

### 构建
- 项目初始结构搭建
- 代理模式与嗅探模式功能合并
- 统一 README 文档与 SVG Banner
- MIT License
