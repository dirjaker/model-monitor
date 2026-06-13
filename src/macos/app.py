"""
macOS 图形界面
使用 tkinter 提供简单的图形控制面板。
"""

import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from src.config import Config
from src.database import Database

logger = logging.getLogger(__name__)


class MacApp:
    """macOS tkinter 图形界面"""

    def __init__(self, config: Config, db: Database):
        self._config = config
        self._db = db
        self._root: Optional[tk.Tk] = None
        self._running = False
        self._proxy_thread: Optional[threading.Thread] = None
        self._sniffer_thread: Optional[threading.Thread] = None

    def run(self) -> None:
        """启动图形界面"""
        self._root = tk.Tk()
        self._root.title("Model Monitor")
        self._root.geometry("600x500")
        self._root.resizable(True, True)

        self._build_ui()
        self._refresh_stats()

        self._root.mainloop()

    def _build_ui(self) -> None:
        """构建界面"""
        root = self._root
        assert root is not None

        # 标题
        title_frame = ttk.Frame(root, padding=10)
        title_frame.pack(fill=tk.X)
        ttk.Label(title_frame, text="Model Monitor", font=("Helvetica", 18, "bold")).pack()
        ttk.Label(title_frame, text="API Usage Monitoring Tool", foreground="gray").pack()

        # 模式选择
        mode_frame = ttk.LabelFrame(root, text="Mode Selection", padding=10)
        mode_frame.pack(fill=tk.X, padx=10, pady=5)

        self._mode_var = tk.StringVar(value=self._config.mode)
        ttk.Radiobutton(mode_frame, text="Proxy Mode", variable=self._mode_var, value="proxy").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="Sniffer Mode", variable=self._mode_var, value="sniffer").pack(side=tk.LEFT, padx=10)

        # 控制按钮
        ctrl_frame = ttk.Frame(root, padding=10)
        ctrl_frame.pack(fill=tk.X)

        self._start_btn = ttk.Button(ctrl_frame, text="Start", command=self._on_start)
        self._start_btn.pack(side=tk.LEFT, padx=5)

        self._stop_btn = ttk.Button(ctrl_frame, text="Stop", command=self._on_stop, state=tk.DISABLED)
        self._stop_btn.pack(side=tk.LEFT, padx=5)

        self._status_label = ttk.Label(ctrl_frame, text="Stopped", foreground="red")
        self._status_label.pack(side=tk.RIGHT, padx=10)

        # 统计信息
        stats_frame = ttk.LabelFrame(root, text="Statistics", padding=10)
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self._stats_text = tk.Text(stats_frame, height=12, state=tk.DISABLED, font=("Courier", 11))
        self._stats_text.pack(fill=tk.BOTH, expand=True)

        # 底部
        bottom_frame = ttk.Frame(root, padding=5)
        bottom_frame.pack(fill=tk.X)

        ttk.Button(bottom_frame, text="Refresh", command=self._refresh_stats).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="Quit", command=self._on_quit).pack(side=tk.RIGHT, padx=5)

    def _on_start(self) -> None:
        """启动监控"""
        mode = self._mode_var.get()
        self._running = True
        self._start_btn.config(state=tk.DISABLED)
        self._stop_btn.config(state=tk.NORMAL)
        self._status_label.config(text=f"Running ({mode})", foreground="green")

        if mode == "proxy":
            self._proxy_thread = threading.Thread(target=self._run_proxy, daemon=True)
            self._proxy_thread.start()
        elif mode == "sniffer":
            self._sniffer_thread = threading.Thread(target=self._run_sniffer, daemon=True)
            self._sniffer_thread.start()

        logger.info("监控已启动: %s", mode)

    def _on_stop(self) -> None:
        """停止监控"""
        self._running = False
        self._start_btn.config(state=tk.NORMAL)
        self._stop_btn.config(state=tk.DISABLED)
        self._status_label.config(text="Stopped", foreground="red")
        logger.info("监控已停止")

    def _on_quit(self) -> None:
        """退出应用"""
        self._running = False
        if self._root:
            self._root.destroy()

    def _run_proxy(self) -> None:
        """在线程中运行代理"""
        try:
            from src.proxy.server import ProxyServer
            server = ProxyServer(self._config, self._db)
            server.run()
        except Exception as e:
            logger.error("代理启动失败: %s", e)

    def _run_sniffer(self) -> None:
        """在线程中运行嗅探器"""
        try:
            from src.sniffer.mitm import run_sniffer
            run_sniffer(self._config)
        except Exception as e:
            logger.error("嗅探器启动失败: %s", e)

    def _refresh_stats(self) -> None:
        """刷新统计信息"""
        stats = self._db.get_stats()
        today_cost = self._db.get_today_cost()
        month_cost = self._db.get_month_cost()

        text = (
            f"Total Calls:      {stats.get('total_calls', 0):>12,}\n"
            f"Input Tokens:     {stats.get('total_input_tokens', 0):>12,}\n"
            f"Output Tokens:    {stats.get('total_output_tokens', 0):>12,}\n"
            f"Total Cost:       ${stats.get('total_cost', 0):>11.4f}\n"
            f"Today Cost:       ${today_cost:>11.4f}\n"
            f"Month Cost:       ${month_cost:>11.4f}\n"
            f"Avg Latency:      {stats.get('avg_latency_ms', 0):>10.1f}ms\n"
            f"First Call:       {str(stats.get('first_call', '-')):>12}\n"
            f"Last Call:        {str(stats.get('last_call', '-')):>12}\n"
        )

        if self._stats_text:
            self._stats_text.config(state=tk.NORMAL)
            self._stats_text.delete("1.0", tk.END)
            self._stats_text.insert(tk.END, text)
            self._stats_text.config(state=tk.DISABLED)

        # 定时刷新
        if self._root:
            self._root.after(5000, self._refresh_stats)
