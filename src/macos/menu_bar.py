"""
macOS 菜单栏集成
使用 rumps 在系统菜单栏显示监控状态。
"""

import logging
import threading
from typing import Optional

from src.config import Config
from src.database import Database

logger = logging.getLogger(__name__)


class MenuBarApp:
    """macOS 菜单栏应用"""

    def __init__(self, config: Config, db: Database):
        self._config = config
        self._db = db
        self._app = None

    def run(self) -> None:
        """启动菜单栏应用"""
        try:
            import rumps
        except ImportError:
            logger.error("rumps 未安装，请运行: pip install rumps")
            return

        class MonitorStatusBarApp(rumps.App):
            def __init__(app_self, *args, **kwargs):
                super().__init__("MM", *args, **kwargs)
                app_self.menu = [
                    rumps.MenuItem("Show Stats", callback=self._show_stats),
                    rumps.MenuItem("Start Proxy", callback=self._start_proxy),
                    rumps.MenuItem("Start Sniffer", callback=self._start_sniffer),
                    None,  # 分隔符
                    rumps.MenuItem("Quit", callback=self._quit),
                ]

        self._app = MonitorStatusBarApp()
        self._app.run()

    def _show_stats(self, _sender) -> None:
        """显示统计信息"""
        try:
            import rumps
        except ImportError:
            return

        stats = self._db.get_stats()
        today_cost = self._db.get_today_cost()
        msg = (
            f"Total Calls: {stats.get('total_calls', 0):,}\n"
            f"Total Cost: ${stats.get('total_cost', 0):.4f}\n"
            f"Today Cost: ${today_cost:.4f}\n"
            f"Avg Latency: {stats.get('avg_latency_ms', 0):.1f}ms"
        )
        rumps.alert(title="Model Monitor Stats", message=msg)

    def _start_proxy(self, _sender) -> None:
        """启动代理"""
        thread = threading.Thread(target=self._run_proxy, daemon=True)
        thread.start()

    def _start_sniffer(self, _sender) -> None:
        """启动嗅探器"""
        thread = threading.Thread(target=self._run_sniffer, daemon=True)
        thread.start()

    def _run_proxy(self) -> None:
        try:
            from src.proxy.server import ProxyServer
            server = ProxyServer(self._config, self._db)
            server.run()
        except Exception as e:
            logger.error("代理启动失败: %s", e)

    def _run_sniffer(self) -> None:
        try:
            from src.sniffer.mitm import run_sniffer
            run_sniffer(self._config)
        except Exception as e:
            logger.error("嗅探器启动失败: %s", e)

    def _quit(self, _sender) -> None:
        """退出应用"""
        if self._app:
            import rumps
            rumps.quit_application()
