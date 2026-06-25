"""
紧凑小组件终端界面
类似 conky/rainmeter 风格的迷你监控面板。
"""

import time
import logging

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import Config
from src.database import Database

logger = logging.getLogger(__name__)


class WidgetApp:
    """迷你终端小组件"""

    def __init__(self, config: Config, db: Database):
        self._config = config
        self._db = db
        self._console = Console()

    def _build_widget(self) -> Panel:
        """构建小组件"""
        stats = self._db.get_stats()
        today_cost = self._db.get_today_cost()
        month_cost = self._db.get_month_cost()
        models = self._db.get_model_stats()
        calls = self._db.get_calls(limit=5)

        # 左侧统计
        st = Table(show_header=False, box=None, padding=(0, 1))
        st.add_column("k", style="dim")
        st.add_column("v", style="bold green")
        st.add_row("Calls", str(stats.get("total_calls", 0)))
        st.add_row("Cost", f"${stats.get('total_cost', 0):.4f}")
        st.add_row("Today", f"${today_cost:.4f}")
        st.add_row("Month", f"${month_cost:.4f}")
        st.add_row("InTok", f"{stats.get('total_input_tokens', 0):,}")
        st.add_row("OutTok", f"{stats.get('total_output_tokens', 0):,}")
        st.add_row("Latency", f"{stats.get('avg_latency_ms', 0):.0f}ms")

        # 右侧模型表
        mt = Table(show_header=True, box=None, padding=(0, 1))
        mt.add_column("Model", style="cyan", max_width=16)
        mt.add_column("#", justify="right", style="green")
        mt.add_column("Cost", justify="right", style="yellow")
        mt.add_column("Lat", justify="right")
        if not models:
            mt.add_row("--", "--", "--", "--")
        else:
            for m in models:
                n = m["model"]
                if len(n) > 16:
                    n = n[:13] + "..."
                mt.add_row(
                    n,
                    str(m["calls"]),
                    f"${m['cost']:.4f}",
                    f"{m['avg_latency_ms']:.0f}ms",
                )

        # 底部最近调用
        if calls:
            parts = []
            for c in calls:
                s = c.get("model", "?").split("/")[-1]
                if len(s) > 10:
                    s = s[:7] + "..."
                parts.append(f"[cyan]{s}[/cyan] ${c.get('cost', 0):.4f}")
            recent_line = " │ ".join(parts)
        else:
            recent_line = "[dim]No recent calls[/dim]"

        # 用 Columns 横排两个表
        from rich.columns import Columns
        top = Columns([st, mt], padding=1)
        content = Text.from_markup(recent_line)

        # 组合成单个 Panel
        from rich.console import Group
        group = Group(top, "", content)

        return Panel(
            group,
            title="[bold cyan]Model Monitor[/bold cyan]",
            subtitle="[dim]Ctrl+C to exit[/dim]",
            border_style="blue",
            width=66,
        )

    def run(self) -> None:
        """启动小组件"""
        try:
            with Live(
                self._build_widget(),
                console=self._console,
                refresh_per_second=1,
                screen=False,
            ) as live:
                while True:
                    live.update(self._build_widget())
                    time.sleep(3)
        except KeyboardInterrupt:
            self._console.print("\n[dim]Widget exited[/dim]")
