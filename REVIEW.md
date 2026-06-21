# 代码审查报告 — model-monitor

**审查日期**: 2026-06-21  
**审查范围**: 安全漏洞、代码质量、依赖安全、配置问题、架构问题  
**文件数量**: 27 个 Python 源文件

---

## 🔴 致命问题

### 🔴-1 SSL 验证全局禁用
- **文件**: `src/sniffer/mitm.py` 第 132 行
- **描述**: `ssl_insecure=True` 全局禁用 SSL 证书验证，嗅探器将接受任何证书（包括中间人攻击的伪造证书），使 MITM 保护形同虚设。
- **修复建议**: 默认 `ssl_insecure=False`，需要时通过配置显式开启，并在日志中警告用户。

### 🔴-2 API Key 明文存储在 YAML 配置文件
- **文件**: `src/config.py`, `src/accounts/accounts.py` 第 59 行
- **描述**: 多个 API Key 以明文存储在 `config.yaml` 中，文件权限未强制限制。`AccountManager._save_accounts()` 将所有 API Key 写回文件。
- **修复建议**: (1) 创建配置文件时设置 `chmod 0o600`；(2) 支持从环境变量读取 API Key（如 `DEEPSEEK_API_KEY`）；(3) 考虑使用系统密钥链（macOS Keychain）。

### 🔴-3 请求/响应体记录可能泄露敏感数据
- **文件**: `src/proxy/server.py` 第 178-179 行
- **描述**: `request_body=request_body_str[:2000]` 和 `response_body=...[:2000]` 将请求和响应内容截断后存入数据库，其中可能包含用户对话内容、系统提示词、API Key 等敏感信息。
- **修复建议**: 默认不记录请求/响应体，或提供配置选项控制记录级别，记录时对敏感字段脱敏。

### 🔴-4 默认绑定 0.0.0.0（多处）
- **文件**: `src/config.py` 第 106 行 (proxy), 第 108 行 (web)
- **描述**: 代理服务和 Web 仪表盘默认绑定 `0.0.0.0`，在公网机器上会暴露服务，且 Web 仪表盘无认证。
- **修复建议**: 默认改为 `127.0.0.1`，需要时通过配置显式指定。

### 🔴-5 Web 仪表盘无认证
- **文件**: `src/web/app.py`, `src/web/api.py`
- **描述**: Web 仪表盘和所有 API 端点完全开放，任何人可以查看所有 API 调用记录、费用数据、模型统计等敏感信息。
- **修复建议**: 添加 Basic Auth 或 API Key 认证中间件。

### 🔴-6 subprocess 命令执行（证书生成）
- **文件**: `src/sniffer/cert.py` 第 50-75 行
- **描述**: 使用 `subprocess.run` 执行 `openssl` 命令生成证书，虽参数硬编码无注入风险，但第 93 行使用 `sudo security add-trusted-cert` 修改系统信任存储，需要 root 权限。
- **修复建议**: 将证书安装步骤改为用户手动操作指南，不要自动执行 `sudo` 命令。

---

## 🟡 警告问题

### 🟡-1 生产代码中使用 assert
- **文件**: `src/proxy/server.py` 第 153、204 行
- **描述**: `assert self._client is not None` 在 Python 优化模式（`-O`）下会被跳过，不应用于生产代码的运行时检查。
- **修复建议**: 改为 `if self._client is None: raise RuntimeError("Client not initialized")`。

### 🟡-2 线程本地连接无自动清理
- **文件**: `src/database.py` 第 73-81 行
- **描述**: `_get_conn()` 使用 `threading.local()` 缓存连接，但线程结束时连接不会自动关闭。长时间运行的服务可能累积大量未关闭的 SQLite 连接。
- **修复建议**: 使用 `weakref` 或线程结束回调自动关闭连接，或使用连接池。

### 🟡-3 异常信息直接返回客户端
- **文件**: `src/proxy/server.py` 第 134、137、140 行
- **描述**: 上游连接失败、超时等异常的 `str(e)` 直接返回给客户端，可能泄露内部网络结构（IP 地址、端口等）。
- **修复建议**: 返回通用错误消息，详细错误仅记录到日志。

### 🟡-4 嗅探目标列表过于宽泛
- **文件**: `src/sniffer/mitm.py` 第 22-26 行
- **描述**: `TARGET_PATTERNS` 使用子串匹配（`any(t in host for t in self._targets)`），`"openrouter"` 会匹配任何包含该子串的域名，可能被钓鱼域名利用。
- **修复建议**: 使用精确域名匹配或正则表达式锚定（如 `^api\.deepseek\.com$`）。

### 🟡-5 accounts.py 中的模块导入可能失败
- **文件**: `src/accounts/accounts.py` 第 9-10 行
- **描述**: `from config import load_config, get_api_key` 和 `from adapters import get_adapter, BaseModelAdapter, BalanceInfo` 使用非包相对导入，在作为包的一部分运行时会失败。
- **修复建议**: 改为 `from src.config import ...` 或使用相对导入。

### 🟡-6 setup.py 中 open() 未使用 with 语句
- **文件**: `setup.py` 第 12 行
- **描述**: `open("README.md", encoding="utf-8").read()` 未使用 `with` 语句，文件句柄不会被显式关闭。
- **修复建议**: 使用 `Path("README.md").read_text(encoding="utf-8")` 或 `with open(...)`。

### 🟡-7 日志可能泄露敏感配置
- **文件**: `src/cli.py` 第 47-48 行
- **描述**: 启动时打印数据库路径等配置信息到终端，`cmd_config --show` 会显示完整配置文件（含 API Key）。
- **修复建议**: `--show` 命令应对 API Key 字段脱敏。

### 🟡-8 `run_sniffer` 中异步/同步混用
- **文件**: `src/sniffer/mitm.py` 第 119-144 行
- **描述**: `run_sniffer` 是同步函数，内部调用 `asyncio.run()`，但如果已经在异步事件循环中调用（如从 FastAPI 启动）会抛出 `RuntimeError`。
- **修复建议**: 提供同步和异步两种启动方式，或在文档中明确调用约束。

### 🟡-9 httpx 客户端连接池无限制
- **文件**: `src/proxy/server.py` 第 39-43 行
- **描述**: `httpx.AsyncClient` 未配置 `max_connections` 和 `max_keepalive_connections`，高并发下可能耗尽文件描述符。
- **修复建议**: 设置合理的连接池限制，如 `limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)`。

---

## 🔵 建议

### 🔵-1 adapter 模式设计良好
- **文件**: `src/proxy/adapters.py`, `src/proxy/adapters_mimo.py`
- **描述**: 适配器模式使用得当，`BaseAdapter` 抽象类 + 具体实现清晰，`get_adapter()` 工厂函数便于扩展。
- **建议**: 保持此设计模式，新增提供商时遵循相同模式。

### 🔵-2 配置管理模块设计良好
- **文件**: `src/config.py`
- **描述**: 支持 YAML 配置 + 环境变量覆盖 + 点号路径访问，设计合理。
- **建议**: 可以添加配置验证（Pydantic Settings 或 JSON Schema）。

### 🔵-3 告警模块设计合理
- **文件**: `src/analysis/alerts.py`
- **描述**: 支持日/月阈值告警、Webhook 通知、去重机制（每日/每月仅告警一次）。
- **建议**: 可以增加邮件通知渠道和告警历史记录。

### 🔵-4 CLI 子命令结构清晰
- **文件**: `src/cli.py`
- **描述**: 使用 argparse 子命令模式，命令结构清晰（proxy/sniffer/web/tui/stats/export/config）。
- **建议**: 考虑使用 `click` 或 `typer` 简化代码。

### 🔵-5 数据库模块线程安全设计
- **文件**: `src/database.py`
- **描述**: 使用 `threading.local()` + `threading.Lock()` 保证线程安全，WAL 模式提升并发读性能。
- **建议**: 设计良好，注意连接生命周期管理即可。

### 🔵-6 缺少单元测试
- **文件**: 项目根目录
- **描述**: 未发现 `tests/` 目录或测试文件。
- **修复建议**: 至少为核心模块（adapters、config、database）添加单元测试。

### 🔵-7 TUI 界面阻塞主线程
- **文件**: `src/tui/app.py` 第 164 行
- **描述**: `while True` + `time.sleep(3)` 无限循环，无法优雅退出（仅靠 KeyboardInterrupt）。
- **修复建议**: 添加退出条件或使用信号处理。

---

## 总结评分

| 维度 | 评分 (满分10) | 说明 |
|------|:---:|------|
| **安全** | 4/10 | SSL 全局禁用、API Key 明文存储、无认证、敏感数据记录、默认公网暴露 |
| **质量** | 7/10 | 代码结构清晰、模块化好、异常处理较完善，但 assert 误用、连接管理可改进 |
| **架构** | 8/10 | 适配器模式、配置管理、模块分离设计优秀，是三个项目中架构最好的 |
