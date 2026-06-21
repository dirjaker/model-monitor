# 系统架构

## 概述

Model Monitor 将**代理模式**和**嗅探模式**统一到一个项目中，共享配置管理、数据库存储和 UI 组件。通过适配器模式支持多种 LLM API 提供商，实现统一的流量监控与费用追踪。

## 架构图

```
                    ┌─────────────────────────────────┐
                    │          客户端应用               │
                    │  (Python SDK / curl / 任意 HTTP)  │
                    └──────────┬──────────┬────────────┘
                               │          │
                    ┌──────────▼──┐  ┌────▼──────────┐
                    │  代理模式    │  │  嗅探模式      │
                    │ ProxyServer │  │ MitmAddon      │
                    │ (FastAPI +  │  │ (mitmproxy     │
                    │  httpx)     │  │  插件)         │
                    └──────┬──────┘  └────┬───────────┘
                           │              │
                           ▼              ▼
                    ┌─────────────────────────────────┐
                    │        适配器层 (Adapters)        │
                    │  DeepSeek │ OpenRouter │ MiMo    │
                    │  │ Generic (OpenAI 兼容)          │
                    └──────────────┬──────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────┐
                    │      统一数据库 (SQLite WAL)      │
                    │  api_calls │ daily_summary       │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────┼──────────────────┐
                    │              │                   │
                    ▼              ▼                   ▼
             ┌────────────┐ ┌──────────┐      ┌────────────┐
             │ Web 仪表盘  │ │ TUI 终端 │      │ 智能分析    │
             │ (FastAPI +  │ │ (Rich)   │      │ 告警/预测   │
             │  Vue.js)    │ │          │      │ /优化建议   │
             └────────────┘ └──────────┘      └────────────┘
```

## 核心模块

### `src/config.py` — 配置管理

统一配置管理器，基于 YAML 文件加载配置，支持环境变量覆盖。

- **YAML 加载**: 从 `config.yaml` 读取所有配置项
- **环境变量**: 支持 `${VAR_NAME}` 引用和 `MM_<SECTION>_<KEY>` 覆盖
- **点号路径**: `config.get("proxy.port")` 访问嵌套配置
- **默认值**: 配置文件不存在时使用内置默认值

### `src/database.py` — 数据存储

线程安全的 SQLite 数据库管理器，使用 WAL 模式支持并发读写。

- **api_calls 表**: 记录每次 API 调用的详细信息（时间戳、提供商、模型、Token 数、费用、延迟、状态码、请求/响应内容）
- **daily_summary 表**: 每日聚合统计
- **统计接口**: 总体统计、每日统计、每小时统计、按模型统计、今日/本月费用
- **数据导出**: 支持 JSON 格式导出

### `src/proxy/` — HTTP 代理服务器

基于 FastAPI 和 httpx 的异步 HTTP 代理服务器。

- **server.py**: `ProxyServer` 类，捕获所有 HTTP 请求，根据路径/Host 头自动路由到对应的上游 API 提供商
- **流式支持**: 完整的 SSE 流式响应透传，在流结束后解析 Token 使用量
- **适配器模式**: 通过 `adapters.py` 中的 `BaseAdapter` 抽象类，统一不同提供商的响应解析和费用计算
- **内置适配器**: DeepSeek、OpenRouter、MiMo、Generic（OpenAI 兼容格式）

### `src/sniffer/` — mitmproxy 嗅探模式

基于 mitmproxy 的 HTTPS 流量嗅探，被动监控已有的 API 调用。

- **mitm.py**: `ModelMonitorAddon` 插件，通过 request/response 事件捕获目标域名的 API 调用
- **cert.py**: CA 证书自动生成与管理，支持 macOS 系统钥匙串安装
- **目标域名**: 默认监控 `api.deepseek.com`、`openrouter.ai`、`api.openai.com`，可通过配置自定义

### `src/web/` — Web 仪表盘

FastAPI Web 应用，提供可视化监控面板和 REST API。

- **app.py**: 应用工厂，挂载静态文件和 API 路由
- **api.py**: REST API 路由，提供 `/api/stats`、`/api/calls`、`/api/models`、`/api/daily`、`/api/hourly`、`/api/health` 端点
- **静态文件**: Vue.js + ECharts 单页仪表盘

### `src/analysis/` — 智能分析模块

基于历史数据的费用分析与优化建议。

- **alerts.py**: `AlertManager` 后台线程，定时检查日/月费用是否超过阈值，通过 Webhook 发送告警通知（支持 WARNING 和 CRITICAL 两级）
- **predictor.py**: `CostPredictor` 使用简单线性回归预测未来 N 天的日费用和月总费用，计算 R² 置信度
- **optimizer.py**: `CostOptimizer` 分析使用模式，识别高延迟模型、输出 Token 占比过高、近期费用异常等问题并给出建议

### `src/tui/` — 终端界面

基于 Rich 的终端实时仪表盘。

- 三栏布局：头部信息、统计概览 + 模型统计、最近调用记录
- 每 3 秒自动刷新数据

### `src/macos/` — macOS 原生集成

macOS 菜单栏应用和原生 GUI（tkinter），支持 py2app 打包为独立 `.app`。

### `src/accounts/` — 多账户管理

支持管理多个 API Key 账户，支持余额查询、按标签分组。

### `src/cli.py` — 统一命令行

基于 argparse 的 CLI，提供 8 个子命令：`proxy`、`sniffer`、`web`、`tui`、`app`、`stats`、`export`、`config`。

## 数据流

### 代理模式数据流

1. 客户端将请求发送到本地代理端口（默认 8080）
2. `ProxyServer` 接收请求，根据路径/Host 头识别目标提供商
3. 选择对应的 `Adapter`，使用配置中的 API Key 替换 Authorization 头
4. httpx 异步转发请求到上游 API
5. 适配器解析响应中的 Token 使用量，计算费用
6. 记录到 SQLite 数据库
7. 将响应原样返回给客户端

### 嗅探模式数据流

1. 系统流量通过 mitmproxy（默认 8080 端口）
2. `ModelMonitorAddon` 的 `request` 事件记录请求信息和模型名称
3. `response` 事件获取完整响应
4. 适配器解析 Token 使用量并计算费用
5. 记录到 SQLite 数据库

## 技术选型理由

| 组件 | 选型 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 异步支持好，自带 OpenAPI 文档 |
| HTTP 客户端 | httpx | 原生异步 + HTTP/2 + 流式支持 |
| 嗅探工具 | mitmproxy | Python 原生插件系统，HTTPS 解密成熟 |
| 数据库 | SQLite + WAL | 轻量、免部署、WAL 支持并发读写 |
| 终端 UI | Rich | 功能丰富的终端渲染库 |
| 配置 | YAML + 环境变量 | 人类可读，支持变量引用和环境覆盖 |
