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
    console.print(f"[bold green]代理服务器启动[/bold green] - {config.proxy_host}:{config.proxy_port}")
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

    console.print(f"[bold green]Web 仪表盘启动[/bold green] - http://{config.web_host}:{config.web_port}")
    uvicorn.run(app, host=config.web_host, port=config.web_port, log_level="info")
    return 0


def cmd_tui(args: argparse.Namespace) -> int:
    """启动终端界面"""
    from src.config import Config
    from src.database import Database
    from src.tui.app import TuiApp

    config = Config(args.config)
    db = Database(config.db_path)
    tui = TuiApp(config, db)
    try:
        tui.run()
    except KeyboardInterrupt:
        pass
    return 0


def cmd_widget(args: argparse.Namespace) -> int:
    """启动紧凑小组件"""
    from src.config import Config
    from src.database import Database
    from src.tui.widget import WidgetApp

    config = Config(args.config)
    db = Database(config.db_path)
    widget = WidgetApp(config, db)
    try:
        widget.run()
    except KeyboardInterrupt:
        pass
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


def cmd_stats(args: argparse.Namespace) -> int:
    """显示统计信息"""
    from src.config import Config
    from src.database import Database
    from rich.table import Table

    config = Config(args.config)
    db = Database(config.db_path)

    stats = db.get_stats()
    table = Table(title="API 调用统计", show_header=True)
    table.add_column("指标", style="cyan")
    table.add_column("值", style="green")
    table.add_row("总调用次数", str(stats.get("total_calls", 0)))
    table.add_row("总输入 Token", f"{stats.get('total_input_tokens', 0):,}")
    table.add_row("总输出 Token", f"{stats.get('total_output_tokens', 0):,}")
    table.add_row("总费用", f"${stats.get('total_cost', 0):.4f}")
    table.add_row("平均延迟", f"{stats.get('avg_latency_ms', 0):.1f}ms")
    table.add_row("首次调用", str(stats.get("first_call", "-")))
    table.add_row("最近调用", str(stats.get("last_call", "-")))
    console.print(table)

    # 模型统计
    model_stats = db.get_model_stats()
    if model_stats:
        mtable = Table(title="按模型统计", show_header=True)
        mtable.add_column("提供商", style="cyan")
        mtable.add_column("模型", style="magenta")
        mtable.add_column("调用次数", justify="right")
        mtable.add_column("输入 Token", justify="right")
        mtable.add_column("输出 Token", justify="right")
        mtable.add_column("费用", justify="right", style="green")
        mtable.add_column("平均延迟", justify="right")
        for ms in model_stats:
            mtable.add_row(
                ms["provider"],
                ms["model"],
                str(ms["calls"]),
                f"{ms['input_tokens']:,}",
                f"{ms['output_tokens']:,}",
                f"${ms['cost']:.4f}",
                f"{ms['avg_latency_ms']:.1f}ms",
            )
        console.print(mtable)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """导出数据"""
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

    # tui
    p_tui = subparsers.add_parser("tui", help="启动终端界面")
    p_tui.set_defaults(func=cmd_tui)

    # widget
    p_widget = subparsers.add_parser("widget", help="启动紧凑小组件")
    p_widget.set_defaults(func=cmd_widget)

    # desktop
    p_desktop = subparsers.add_parser("desktop", help="启动桌面小组件 (PySide6)")
    p_desktop.set_defaults(func=cmd_desktop)

    # app
    p_app = subparsers.add_parser("app", help="启动图形界面 (仅 macOS)")
    p_app.set_defaults(func=cmd_app)

    # stats
    p_stats = subparsers.add_parser("stats", help="显示统计信息")
    p_stats.set_defaults(func=cmd_stats)

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
