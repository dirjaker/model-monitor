# Model Monitor

Unified API monitoring tool for tracking token usage, costs, and latency across LLM providers.

**Proxy + Sniffer + Dashboard in one tool.**

---

## Architecture

```
+---------------------+     +---------------------+
|    Proxy Mode       |     |   Sniffer Mode      |
|   (HTTP Forward)    |     |  (mitmproxy HTTPS)  |
+----------+----------+     +----------+----------+
           |                            |
           v                            v
+-----------------------------------------------+
|              Unified SQLite DB                |
|           (api_calls, daily_summary)          |
+-----------------------------------------------+
           |              |              |
           v              v              v
+----------+--+  +--------+---+  +------+------+
| Web UI      |  | TUI (Rich) |  | macOS (tk)  |
| (FastAPI)   |  |            |  |             |
+-------------+  +------------+  +-------------+
```

## Features

- **Proxy Mode**: HTTP proxy intercepting LLM API calls, recording usage data
- **Sniffer Mode**: HTTPS traffic capture via mitmproxy with auto-generated CA
- **Web Dashboard**: Single-page dark-themed dashboard with Chart.js visualizations
- **TUI**: Rich terminal dashboard with real-time updates
- **macOS App**: Native tkinter GUI with start/stop controls
- **Analysis**: Cost optimization suggestions, linear regression predictions, threshold alerts
- **Multi-Provider**: DeepSeek, OpenRouter, MiMo (via OpenRouter), extensible adapter system
- **Multi-Account**: Support multiple API keys and provider accounts
- **Webhook Alerts**: Configurable webhook notifications (DingTalk, Feishu, WeCom)

## Requirements

- Python 3.10+
- pip dependencies (see requirements.txt)

## Installation

### From Source

```bash
git clone https://github.com/dirjaker/model-monitor.git
cd model-monitor
git checkout dev
pip install -r requirements.txt
```

### macOS App (py2app)

```bash
make app
# Output: dist/Model Monitor.app
```

## Quick Start

### Proxy Mode

```bash
# Start proxy on default port 8080
python main.py proxy

# Custom port
python main.py proxy -p 9090

# Point your client at the proxy
export HTTPS_PROXY=http://localhost:8080
curl https://api.deepseek.com/v1/chat/completions ...
```

### Sniffer Mode

```bash
# Start sniffer
python main.py sniffer

# Install CA certificate (first time, macOS)
python -c "from src.sniffer.cert import install_cert_macos; install_cert_macos()"
```

### Web Dashboard

```bash
python main.py web
# Open http://localhost:8000
```

### Terminal UI

```bash
python main.py tui
```

### View Stats

```bash
python main.py stats
python main.py export -o data.json -d 30
```

## Configuration

Default config file: `config.yaml`

```yaml
mode: proxy

proxy:
  host: 0.0.0.0
  port: 8080
  timeout: 120

sniffer:
  port: 8080
  targets:
    - api.deepseek.com
    - openrouter.ai

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
      deepseek-reasoner:
        input: 4.0
        output: 16.0
  openrouter:
    base_url: https://openrouter.ai/api
    api_key: ${OPENROUTER_API_KEY}

alerts:
  enabled: false
  daily_threshold: 10.0
  monthly_threshold: 200.0
  webhook_url: ""
```

### Environment Variable Overrides

Any config value can be overridden with `MM_<SECTION>_<KEY>`:

```bash
MM_PROXY_PORT=9090 python main.py proxy
MM_WEB_PORT=3000 python main.py web
```

## API Documentation

| Endpoint | Method | Description |
|---|---|---|
| `/api/stats` | GET | Total statistics (calls, tokens, cost, latency) |
| `/api/calls` | GET | Paginated call log (params: limit, offset, provider, model, mode) |
| `/api/models` | GET | Per-model aggregate statistics |
| `/api/daily` | GET | Daily aggregates (param: days, default 30) |
| `/api/hourly` | GET | Hourly aggregates (param: hours, default 24) |
| `/api/health` | GET | Health check |

Interactive API docs available at `http://localhost:8000/api/docs` when web server is running.

## Project Structure

```
model-monitor/
  main.py              Entry point
  config.yaml          Default configuration
  requirements.txt     Python dependencies
  setup.py             Package / py2app setup
  Makefile             Common commands
  src/
    cli.py             Unified CLI (argparse + rich)
    config.py          YAML config with env var overrides
    database.py        SQLite with WAL, thread-safe
    proxy/
      server.py        Async HTTP proxy (httpx + FastAPI)
      adapters.py      Provider adapters (DeepSeek, OpenRouter)
    sniffer/
      mitm.py          mitmproxy addon
      cert.py          CA certificate management
    web/
      app.py           FastAPI application
      api.py           REST API routes
      static/
        index.html     Single-page dark dashboard
    analysis/
      optimizer.py     Cost optimization analysis
      predictor.py     Linear regression cost prediction
      alerts.py        Threshold-based webhook alerts
    tui/
      app.py           Rich live terminal dashboard
    macos/
      app.py           tkinter GUI
      menu_bar.py      macOS menu bar integration (rumps)
  packaging/
    py2app_setup.py    macOS app bundler
    Info.plist         macOS metadata
  docs/
    architecture.md
    user-guide.md
```

## License

MIT
