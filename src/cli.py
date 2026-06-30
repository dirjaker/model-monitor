"""
统一命令行界面
提供子命令: proxy, sniffer, web, tui, app, stats, export, config
"""

import argparse
import logging
import sys
import os
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from src import __version__

console = Console()


def setup_logging(verbose: bool = False) -> None:
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def cmd_proxy(args: argparse.Namespace) -> int:
    """启动代理模式"""
    from src.config import Config
    from src.proxy.server import ProxyServer

    config = Config(args.config)
    if args.port:
        config.set("proxy.port", args.port)
    if args.host:
        config.set("proxy.host", args.host)

    db_path = config.db_path
    from src.database import Database
    db = Database(db_path)

    server = ProxyServer(config, db)
    display_host = "localhost" if config.proxy_host in ("0.0.0.0", "127.0.0.1") else config.proxy_host
    console.print(f"[bold green]代理服务器启动[/bold green] - http://{display_host}:{config.proxy_port}")
    console.print(f"数据库: {db_path}")
    try:
        server.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]正在停止代理服务器...[/yellow]")
    return 0


def cmd_sniffer(args: argparse.Namespace) -> int:
    """启动嗅探模式"""
    from src.config import Config
    from src.sniffer.mitm import run_sniffer

    config = Config(args.config)
    if args.port:
        config.set("sniffer.port", args.port)

    console.print(f"[bold green]嗅探模式启动[/bold green] - 端口 {config.sniffer_port}")
    console.print(f"目标: {', '.join(config.sniffer_targets)}")
    try:
        run_sniffer(config)
    except KeyboardInterrupt:
        console.print("\n[yellow]正在停止嗅探器...[/yellow]")
    return 0


def _get_lan_ip() -> str:
    """获取局域网 IP 地址"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def cmd_web(args: argparse.Namespace) -> int:
    """启动 Web 仪表盘"""
    from src.config import Config
    from src.web.app import create_app
    from src.database import Database
    import uvicorn

    config = Config(args.config)
    if args.port:
        config.set("web.port", args.port)
    if args.host:
        config.set("web.host", args.host)

    db = Database(config.db_path)
    app = create_app(config, db)

    display_host = "localhost" if config.web_host == "0.0.0.0" else config.web_host
    console.print(f"[bold green]Web 仪表盘启动[/bold green] - http://{display_host}:{config.web_port}")
    if config.web_host == "0.0.0.0":
        console.print(f"  局域网: http://{_get_lan_ip()}:{config.web_port}")
        console.print(f"  本地:   http://localhost:{config.web_port}")
    uvicorn.run(app, host=config.web_host, port=config.web_port, log_level="info")
    return 0



def cmd_desktop(args: argparse.Namespace) -> int:
    """启动桌面小组件"""
    from src.config import Config
    from src.database import Database
    from src.widget import run_desktop_widget

    config = Config(args.config)
    db = Database(config.db_path)
    return run_desktop_widget(config, db)


def cmd_app(args: argparse.Namespace) -> int:
    """启动 macOS 图形界面"""
    if sys.platform != "darwin":
        console.print("[red]图形界面仅支持 macOS[/red]")
        return 1
    from src.config import Config
    from src.database import Database
    from src.macos.app import MacApp

    config = Config(args.config)
    db = Database(config.db_path)
    app = MacApp(config, db)
    app.run()
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """导出数据为 JSON"""
    from src.config import Config
    from src.database import Database

    config = Config(args.config)
    db = Database(config.db_path)
    count = db.export_json(args.output, days=args.days)
    console.print(f"[green]已导出 {count} 条记录到 {args.output}[/green]")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """显示或修改配置"""
    from src.config import Config

    config = Config(args.config)
    if args.show:
        import yaml
        with open(config._path, "r", encoding="utf-8") as f:
            content = f.read()
        console.print(f"[bold]配置文件: {config._path}[/bold]")
        console.print(content)
    elif args.set_key and args.set_value:
        config.set(args.set_key, args.set_value)
        config.save()
        console.print(f"[green]已设置 {args.set_key} = {args.set_value}[/green]")
    else:
        console.print(f"[bold]当前配置[/bold]")
        console.print(f"  模式: {config.mode}")
        console.print(f"  代理: {config.proxy_host}:{config.proxy_port}")
        console.print(f"  嗅探: 端口 {config.sniffer_port}")
        console.print(f"  Web: {config.web_host}:{config.web_port}")
        console.print(f"  数据库: {config.db_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器"""
    parser = argparse.ArgumentParser(
        prog="model-monitor",
        description="模型 API 监控工具 - 统一代理与嗅探模式",
    )
    parser.add_argument("--version", action="version", version=f"model-monitor {__version__}")
    parser.add_argument("-c", "--config", default=None, help="配置文件路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志输出")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # proxy
    p_proxy = subparsers.add_parser("proxy", help="启动 HTTP 代理模式")
    p_proxy.add_argument("-p", "--port", type=int, help="代理端口")
    p_proxy.add_argument("--host", help="监听地址")
    p_proxy.set_defaults(func=cmd_proxy)

    # sniffer
    p_sniffer = subparsers.add_parser("sniffer", help="启动 HTTPS 嗅探模式")
    p_sniffer.add_argument("-p", "--port", type=int, help="嗅探端口")
    p_sniffer.set_defaults(func=cmd_sniffer)

    # web
    p_web = subparsers.add_parser("web", help="启动 Web 仪表盘")
    p_web.add_argument("-p", "--port", type=int, help="Web 端口")
    p_web.add_argument("--host", help="监听地址")
    p_web.set_defaults(func=cmd_web)

    # desktop
    p_desktop = subparsers.add_parser("desktop", help="启动桌面小组件 (PySide6)")
    p_desktop.set_defaults(func=cmd_desktop)

    # app
    p_app = subparsers.add_parser("app", help="启动图形界面 (仅 macOS)")
    p_app.set_defaults(func=cmd_app)

    # export
    p_export = subparsers.add_parser("export", help="导出数据为 JSON")
    p_export.add_argument("-o", "--output", default="export.json", help="输出文件路径")
    p_export.add_argument("-d", "--days", type=int, default=30, help="导出天数")
    p_export.set_defaults(func=cmd_export)

    # config
    p_config = subparsers.add_parser("config", help="查看或修改配置")
    p_config.add_argument("--show", action="store_true", help="显示完整配置文件")
    p_config.add_argument("--set-key", help="设置配置键")
    p_config.add_argument("--set-value", help="设置配置值")
    p_config.set_defaults(func=cmd_config)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI 主入口"""
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose if hasattr(args, "verbose") else False)

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)
