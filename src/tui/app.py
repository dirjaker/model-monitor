"""
Rich 终端界面
实时显示 API 调用统计和使用量。
"""

import time
import logging
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import Config
from src.database import Database

logger = logging.getLogger(__name__)


class TuiApp:
    """Rich 终端仪表盘"""

    def __init__(self, config: Config, db: Database):
        self._config = config
        self._db = db
        self._console = Console()

    def _make_header(self) -> Panel:
        """生成头部面板"""
        title = Text("Model Monitor Terminal Dashboard", style="bold cyan")
        subtitle = Text(f"Database: {self._config.db_path} | Refresh: 3s", style="dim")
        return Panel(
            Text.assemble(title, "\n", subtitle),
            style="blue",
        )

    def _make_stats_table(self) -> Panel:
        """生成统计概览"""
        stats = self._db.get_stats()
        today_cost = self._db.get_today_cost()
        month_cost = self._db.get_month_cost()

        table = Table(show_header=False, expand=True, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan", ratio=1)
        table.add_column("Value", style="green", ratio=1)
        table.add_column("Metric2", style="cyan", ratio=1)
        table.add_column("Value2", style="green", ratio=1)

        table.add_row(
            "Total Calls",
            f"{stats.get('total_calls', 0):,}",
            "Avg Latency",
            f"{stats.get('avg_latency_ms', 0):.1f}ms",
        )
        table.add_row(
            "Total Cost",
            f"${stats.get('total_cost', 0):.4f}",
            "Today Cost",
            f"${today_cost:.4f}",
        )
        table.add_row(
            "Input Tokens",
            f"{stats.get('total_input_tokens', 0):,}",
            "Output Tokens",
            f"{stats.get('total_output_tokens', 0):,}",
        )
        table.add_row(
            "Month Cost",
            f"${month_cost:.4f}",
            "",
            "",
        )

        return Panel(table, title="[bold]Overview[/bold]", border_style="cyan")

    def _make_model_table(self) -> Panel:
        """生成模型统计表"""
        models = self._db.get_model_stats()

        table = Table(show_header=True, expand=True)
        table.add_column("Provider", style="cyan")
        table.add_column("Model", style="magenta")
        table.add_column("Calls", justify="right", style="green")
        table.add_column("Input", justify="right")
        table.add_column("Output", justify="right")
        table.add_column("Cost", justify="right", style="yellow")
        table.add_column("Latency", justify="right")

        if not models:
            table.add_row("--", "--", "--", "--", "--", "--", "--")
        else:
            for m in models:
                table.add_row(
                    m["provider"],
                    m["model"],
                    f"{m['calls']:,}",
                    f"{m['input_tokens']:,}",
                    f"{m['output_tokens']:,}",
                    f"${m['cost']:.4f}",
                    f"{m['avg_latency_ms']:.1f}ms",
                )

        return Panel(table, title="[bold]Model Statistics[/bold]", border_style="cyan")

    def _make_recent_table(self) -> Panel:
        """生成最近调用表"""
        calls = self._db.get_calls(limit=10)

        table = Table(show_header=True, expand=True)
        table.add_column("Time", style="dim")
        table.add_column("Mode", style="cyan")
        table.add_column("Provider", style="magenta")
        table.add_column("Model", style="green")
        table.add_column("Tokens", justify="right")
        table.add_column("Cost", justify="right", style="yellow")
        table.add_column("Latency", justify="right")

        if not calls:
            table.add_row("--", "--", "--", "--", "--", "--", "--")
        else:
            for c in calls:
                tokens = f"{c['input_tokens']}/{c['output_tokens']}"
                table.add_row(
                    str(c.get("timestamp", ""))[:19],
                    c.get("mode", ""),
                    c.get("provider", ""),
                    c.get("model", ""),
                    tokens,
                    f"${c.get('cost', 0):.4f}",
                    f"{c.get('latency_ms', 0):.1f}ms",
                )

        return Panel(table, title="[bold]Recent Calls[/bold]", border_style="cyan")

    def _build_layout(self) -> Layout:
        """构建布局"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=4),
            Layout(name="body"),
            Layout(name="footer", size=16),
        )
        layout["body"].split_row(
            Layout(name="stats", ratio=1),
            Layout(name="models", ratio=2),
        )
        return layout

    def _render(self, layout: Layout) -> None:
        """渲染界面"""
        layout["header"].update(self._make_header())
        layout["stats"].update(self._make_stats_table())
        layout["models"].update(self._make_model_table())
        layout["footer"].update(self._make_recent_table())

    def run(self) -> None:
        """启动终端界面"""
        layout = self._build_layout()
        try:
            with Live(layout, console=self._console, refresh_per_second=1, screen=True) as live:
                while True:
                    self._render(layout)
                    live.refresh()
                    time.sleep(3)
        except KeyboardInterrupt:
            self._console.print("\n[yellow]终端界面已退出[/yellow]")
