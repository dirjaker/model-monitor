# User Guide

## 安装

### 从源码安装

```bash
git clone https://github.com/dirjaker/model-monitor.git
cd model-monitor
pip install -r requirements.txt
```

### macOS 应用

```bash
# 使用 py2app 打包
python packaging/py2app_setup.py py2app
# 生成的 .app 在 dist/ 目录
```

## 快速开始

### 代理模式

```bash
# 使用默认配置启动代理
python main.py proxy

# 指定端口
python main.py proxy -p 9090
```

客户端配置:
```bash
export HTTP_PROXY=http://localhost:8080
export HTTPS_PROXY=http://localhost:8080
```

### 嗅探模式

```bash
# 启动嗅探器
python main.py sniffer

# 安装 CA 证书（首次使用）
python -c "from src.sniffer.cert import install_cert_macos; install_cert_macos()"
```

### Web 仪表盘

```bash
# 启动 Web 仪表盘
python main.py web
# 访问 http://localhost:8000
```

### 终端界面

```bash
python main.py tui
```

## 配置

配置文件: `config.yaml`

```yaml
mode: proxy
proxy:
  host: 0.0.0.0
  port: 8080
sniffer:
  port: 8080
  targets:
    - api.deepseek.com
web:
  host: 0.0.0.0
  port: 8000
database:
  path: data/usage.db
providers:
  deepseek:
    base_url: https://api.deepseek.com
    api_key: ${DEEPSEEK_API_KEY}
    pricing:
      deepseek-chat:
        input: 1.0
        output: 2.0
```

环境变量覆盖: `MM_PROXY_PORT=9090`

## API 文档

启动 Web 仪表盘后访问 `http://localhost:8000/api/docs` 查看交互式 API 文档。

### 主要端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/stats` | GET | 总体统计 |
| `/api/calls` | GET | 调用记录（支持分页、筛选） |
| `/api/models` | GET | 按模型统计 |
| `/api/daily` | GET | 每日统计 |
| `/api/hourly` | GET | 每小时统计 |
| `/api/health` | GET | 健康检查 |
