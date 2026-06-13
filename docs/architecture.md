# Architecture

## 系统架构

Model Monitor 将代理模式和嗅探模式统一到一个项目中，共享配置、数据库和 UI 组件。

```
+------------------+     +------------------+
|   Proxy Mode     |     |  Sniffer Mode    |
|  (HTTP Proxy)    |     |  (mitmproxy)     |
+--------+---------+     +--------+---------+
         |                          |
         v                          v
+------------------------------------------+
|           Unified Database               |
|              (SQLite)                    |
+------------------------------------------+
         |                          |
         v                          v
+------------------+     +------------------+
|   Web Dashboard  |     |   TUI / macOS    |
|   (FastAPI)      |     |   (Rich/tk)      |
+------------------+     +------------------+
```

## 模块说明

### src/config.py
统一配置管理，支持 YAML 文件和环境变量覆盖。

### src/database.py
SQLite 数据库，线程安全，WAL 模式支持并发读写。

### src/proxy/
HTTP 代理服务器，使用 httpx 异步转发请求，支持流式响应。

### src/sniffer/
基于 mitmproxy 的 HTTPS 流量嗅探，解析 API 响应中的 token 使用量。

### src/web/
FastAPI Web 应用，提供 REST API 和单页仪表盘。

### src/analysis/
成本优化建议、费用预测、阈值告警。

### src/tui/
Rich 终端仪表盘，实时刷新。

### src/macos/
macOS 原生 GUI 和菜单栏集成。
