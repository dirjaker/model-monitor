# 系统架构

## 概述

Model Monitor 将**代理模式**和**嗅探模式**统一到一个项目中，共享配置管理、数据库存储和事件系统。通过三种展示形式（Web 仪表盘、桌面小组件、macOS 原生应用）提供灵活的数据可视化。支持 WebSocket/SSE 实时数据推送和仪表盘一键启停采集进程。

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
                    │        DeepSeek 适配器           │
                    │  (Token 解析 + 费用计算)          │
                    └──────────────┬──────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────┐
                    │      事件总线 (EventBus)         │
                    │  发布: ApiCallEvent / StatsEvent │
                    └──────────┬──────────┬───────────┘
                               │          │
                    ┌──────────▼──┐ ┌─────▼───────────┐
                    │   SQLite    │ │ 统一数据库       │
                    │  (WAL 模式)  │ │ api_calls /      │
                    │             │ │ daily_summary    │
                    └──────┬──────┘ └──────────────────┘
                           │
              ┌────────────┼────────────────┐
              │            │                │
              ▼            ▼                ▼
     ┌─────────────┐ ┌─────────┐ ┌──────────────┐
     │ Web 仪表盘   │ │桌面小组件│ │ macOS 原生    │
     │ (FastAPI +   │ │(PySide6)│ │ (tkinter/    │
     │  Chart.js)   │ │         │ │  rumps)      │
     │ REST API     │ │ 5色主题  │ │ 菜单栏+GUI   │
     │ WS/SSE实时   │ │ 托盘常驻 │ │ py2app打包   │
     │ 采集进程管理  │ │ 置顶/透明│ │              │
     └─────────────┘ └─────────┘ └──────────────┘
```

## 核心模块

### `src/config.py` — 配置管理

统一配置管理器，基于 YAML 文件加载配置。

- **YAML 加载**: 从 `config.yaml` 读取所有配置项
- **点号路径**: `config.get("proxy.port")` 访问嵌套配置
- **默认值**: 配置文件不存在时使用内置默认值
- **运行时修改**: Web 仪表盘通过 `POST /api/settings` 持久化修改

### `src/database.py` — 数据存储

线程安全的 SQLite 数据库管理器，使用 WAL 模式支持并发读写。

- **api_calls 表**: 记录每次 API 调用的详细信息（时间戳、模式、模型、Token 数、费用、延迟、状态码）
- **daily_summary 表**: 每日聚合统计（按提供商和模型维度）
- **统计接口**: 总体统计、每日统计、每小时统计、按模型统计、今日/本月费用
- **数据导出**: 支持 JSON 格式按天数范围导出

### `src/proxy/` — HTTP 代理服务器

基于 FastAPI 和 httpx 的异步 HTTP 代理服务器。

- **server.py**: `ProxyServer` 类，捕获所有 HTTP 请求，转发到上游 DeepSeek API
- **流式支持**: 完整的 SSE 流式响应透传，在流结束后解析 Token 使用量
- **适配器模式**: `DeepSeekAdapter` 负责响应解析和费用计算
- **数据记录**: 每次调用完成后通过事件总线发布 `ApiCallEvent`

### `src/sniffer/` — mitmproxy 嗅探模式

基于 mitmproxy 的 HTTPS 流量嗅探，被动监控已有的 API 调用。

- **mitm.py**: `ModelMonitorAddon` 插件，通过 request/response 事件捕获目标域名的 API 调用
- **cert.py**: CA 证书自动生成与管理，支持 macOS 系统钥匙串安装
- **目标域名**: 默认监控 `api.deepseek.com`

### `src/web/` — Web 仪表盘

FastAPI Web 应用，提供可视化监控面板和 REST API。

- **app.py**: 应用工厂，挂载静态文件和 API 路由
- **api.py**: REST API 路由 + WebSocket/SSE 实时推送 + 采集进程管理
- **static/**: 原生 HTML/CSS + Chart.js 单页仪表盘，玻璃拟态 DeepSeek 蓝设计

#### REST API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/stats` | GET | 总体统计 |
| `/api/calls` | GET | 调用记录（分页、筛选） |
| `/api/models` | GET | 按模型统计 |
| `/api/daily` | GET | 每日统计 |
| `/api/hourly` | GET | 每小时统计 |
| `/api/health` | GET | 健康检查 |
| `/api/mode/start` | POST | 启动采集进程（proxy/sniffer） |
| `/api/mode/stop` | POST | 停止采集进程 |
| `/api/mode/status` | GET | 查询采集进程状态 |
| `/api/settings` | POST | 持久化配置 |
| `/api/ws` | WebSocket | 实时事件推送 |
| `/api/events` | GET (SSE) | Server-Sent Events 事件流 |

#### 实时推送

Web 仪表盘支持两种实时数据推送方式：

- **WebSocket** (`/api/ws`): 全双工通信，支持实时推送和客户端主动请求（`stats` 命令）
- **SSE** (`/api/events`): 单向服务器推送，30 秒心跳保活

### `src/widget/` — 桌面小组件

基于 PySide6 的浮动监控面板。

- 无边框浮动窗口，支持鼠标拖拽移动
- **5 色主题**: dark / deepblue / dusk / aurora / moonlight
- 系统托盘常驻，右键菜单（显示/隐藏、立即刷新、设置、退出）
- 设置对话框：刷新间隔、颜色主题、窗口置顶、透明度、重置位置
- 窗口位置自动记忆（JSON 持久化）
- 显示实时统计数据：总调用数、费用、Token 用量、延迟

### `src/macos/` — macOS 原生集成

提供两套 macOS 原生界面：

- **tkinter GUI** (`app.py`): 图形控制面板，模式选择、启动/停止、统计文本显示，5 秒自动刷新
- **rumps 菜单栏** (`menu_bar.py`): 系统菜单栏集成，显示统计信息弹窗，一键启停采集

### `src/events.py` — 事件总线

线程安全的事件发布/订阅机制。

- **ApiCallEvent**: proxy/sniffer 记录调用后发布
- **StatsEvent**: WebSocket/SSE 推送全量统计摘要
- 支持同步回调（供桌面小组件）和异步队列（供 WebSocket/SSE）

## 数据流

### 代理模式数据流

1. 客户端将请求发送到本地代理端口（默认 12345）
2. `ProxyServer` 接收请求，转发到上游 DeepSeek API
3. 等待响应，适配器解析 Token 使用量和费用
4. 记录到 SQLite 数据库
5. 通过事件总线发布 `ApiCallEvent`
6. 响应原样返回给客户端
7. Web 仪表盘通过 WebSocket/SSE 实时更新

### 嗅探模式数据流

1. 系统流量通过 mitmproxy（默认 8080 端口）
2. `ModelMonitorAddon` 的 `request` 事件记录请求信息
3. `response` 事件获取完整响应
4. 适配器解析 Token 使用量并计算费用
5. 记录到 SQLite 数据库

## 三种展示形式

| 形式 | 实现 | 特点 |
|------|------|------|
| **Web 仪表盘** | FastAPI + Chart.js + WebSocket/SSE | 跨平台，功能最全，含采集进程管理 |
| **桌面小组件** | PySide6 浮动面板 | 轻量常驻，5 色主题，系统托盘控制 |
| **macOS 原生** | tkinter GUI + rumps 菜单栏 | 原生体验，菜单栏快捷操作，可打包为独立 .app |

## 技术选型理由

| 组件 | 选型 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 异步支持好，自带 OpenAPI 文档 |
| HTTP 客户端 | httpx | 原生异步 + HTTP/2 + 流式支持 |
| 嗅探工具 | mitmproxy | Python 原生插件系统，HTTPS 解密成熟 |
| 数据库 | SQLite + WAL | 轻量、免部署、WAL 支持并发读写 |
| 桌面 UI | PySide6 | 跨平台、现代化 UI、系统托盘支持 |
| 事件系统 | 自定义 EventBus | 轻量级发布/订阅，支持同步 + 异步 |
| 配置 | YAML | 人类可读，点号路径访问 |
