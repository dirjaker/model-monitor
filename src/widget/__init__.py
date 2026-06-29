"""
桌面小组件 - PySide6 浮窗监控面板

功能：
- 实时显示 API 调用统计、费用、Token 用量
- 系统托盘常驻，可隐藏/显示
- 右键菜单：刷新、设置、置顶、退出
- 设置对话框：刷新间隔、颜色主题、窗口位置管理
- 窗口位置自动记忆（重启后恢复）
- 5 色主题（暗色/深蓝/暮色/极光/月光）
"""

import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.config import Config
from src.database import Database

logger = logging.getLogger(__name__)

# ── 数据文件 ──
CONFIG_DIR = Path.home() / ".config" / "model-monitor"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
POSITION_FILE = CONFIG_DIR / "widget_position.json"
SETTINGS_FILE = CONFIG_DIR / "widget_settings.json"

# ── 默认设置 ──
DEFAULT_SETTINGS = {
    "refresh_interval": 5,
    "theme": "dark",
    "always_on_top": True,
    "opacity": 1.0,
}


# ── 颜色主题 ──
THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "rgba(18, 22, 32, 235)",
        "border": "rgba(60, 70, 90, 180)",
        "title": "#8b95ab",
        "value": "#e8ecf4",
        "unit": "#5a6478",
        "accent": "#7dd3fc",
        "secondary": "#94a3b8",
        "muted": "#64748b",
        "separator": "rgba(60, 70, 90, 100)",
        "success": "#34d399",
        "warning": "#fbbf24",
        "error": "#f87171",
        "card_bg": "rgba(30, 35, 48, 220)",
    },
    "deepblue": {
        "bg": "rgba(8, 16, 40, 240)",
        "border": "rgba(40, 80, 140, 180)",
        "title": "#7b9cd4",
        "value": "#d6e8ff",
        "unit": "#4a6a9a",
        "accent": "#60a5fa",
        "secondary": "#8ba8cc",
        "muted": "#5a7a9a",
        "separator": "rgba(40, 80, 140, 100)",
        "success": "#4ade80",
        "warning": "#facc15",
        "error": "#fb7185",
        "card_bg": "rgba(14, 26, 60, 230)",
    },
    "dusk": {
        "bg": "rgba(28, 18, 35, 240)",
        "border": "rgba(100, 60, 90, 180)",
        "title": "#b08aab",
        "value": "#f0dce8",
        "unit": "#7a5a72",
        "accent": "#c084fc",
        "secondary": "#a88ab8",
        "muted": "#7a6a7a",
        "separator": "rgba(100, 60, 90, 100)",
        "success": "#a7f3d0",
        "warning": "#fde68a",
        "error": "#fca5a5",
        "card_bg": "rgba(40, 28, 48, 230)",
    },
    "aurora": {
        "bg": "rgba(12, 28, 28, 240)",
        "border": "rgba(40, 100, 90, 180)",
        "title": "#6ab8a0",
        "value": "#c8f0e4",
        "unit": "#4a8878",
        "accent": "#5eead4",
        "secondary": "#78b8a8",
        "muted": "#588878",
        "separator": "rgba(40, 100, 90, 100)",
        "success": "#6ee7b7",
        "warning": "#fcd34d",
        "error": "#fca5a5",
        "card_bg": "rgba(18, 38, 38, 230)",
    },
    "moonlight": {
        "bg": "rgba(22, 22, 35, 240)",
        "border": "rgba(80, 80, 120, 180)",
        "title": "#8d8db0",
        "value": "#dcdcf0",
        "unit": "#5a5a78",
        "accent": "#a78bfa",
        "secondary": "#9898b8",
        "muted": "#686880",
        "separator": "rgba(80, 80, 120, 100)",
        "success": "#6ee7b7",
        "warning": "#fbbf24",
        "error": "#f87171",
        "card_bg": "rgba(30, 30, 48, 230)",
    },
}

DEFAULT_THEME = "dark"


def load_settings() -> dict[str, Any]:
    """加载小组件设置"""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text("utf-8"))
            return {**DEFAULT_SETTINGS, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict[str, Any]) -> None:
    """保存小组件设置"""
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), "utf-8")
    except OSError as e:
        logger.warning("保存设置失败: %s", e)


def load_position() -> Optional[dict[str, int]]:
    """加载上次窗口位置"""
    if POSITION_FILE.exists():
        try:
            return json.loads(POSITION_FILE.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return None


def save_position(x: int, y: int) -> None:
    """保存窗口位置"""
    try:
        POSITION_FILE.write_text(json.dumps({"x": x, "y": y}), "utf-8")
    except OSError as e:
        logger.warning("保存位置失败: %s", e)


# ── 样式工具 ──


def build_style(theme: dict[str, str]) -> str:
    """根据主题构建设计样式表"""
    return f"""
QWidget#WidgetMain {{
    background-color: {theme["bg"]};
    border: 1px solid {theme["border"]};
    border-radius: 16px;
}}
QLabel {{
    color: {theme["secondary"]};
    font-family: -apple-system, 'SF Pro Display', 'Segoe UI', sans-serif;
}}
QLabel#Title {{
    color: {theme["title"]};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1.5px;
}}
QLabel#Value {{
    color: {theme["value"]};
    font-size: 22px;
    font-weight: 700;
}}
QLabel#Unit {{
    color: {theme["unit"]};
    font-size: 10px;
}}
QLabel#ModelName {{
    color: {theme["accent"]};
    font-size: 11px;
}}
QLabel#ModelValue {{
    color: {theme["secondary"]};
    font-size: 11px;
}}
QLabel#StatusDot {{
    font-size: 8px;
}}
QLabel#StatusDot[status="ok"] {{
    color: {theme["success"]};
}}
QLabel#StatusDot[status="warn"] {{
    color: {theme["warning"]};
}}
QLabel#StatusDot[status="error"] {{
    color: {theme["error"]};
}}
QLabel#Recent {{
    color: {theme["muted"]};
    font-size: 10px;
}}
QFrame#Separator {{
    background-color: {theme["separator"]};
    max-height: 1px;
}}
QPushButton {{
    background-color: rgba(255, 255, 255, 15);
    color: {theme["secondary"]};
    border: 1px solid {theme["border"]};
    border-radius: 8px;
    padding: 6px 16px;
    font-size: 11px;
}}
QPushButton:hover {{
    background-color: rgba(255, 255, 255, 25);
}}
QDialog {{
    background-color: {theme["bg"]};
    border: 1px solid {theme["border"]};
}}
QDialog QLabel {{
    color: {theme["secondary"]};
}}
QDialog QLineEdit, QDialog QSpinBox, QDialog QComboBox {{
    background-color: rgba(255, 255, 255, 10);
    color: {theme["value"]};
    border: 1px solid {theme["border"]};
    border-radius: 6px;
    padding: 4px 8px;
}}
"""


# ── 小组件组件 ──


class StatCard(QtWidgets.QWidget):
    """单个统计指标卡片"""

    def __init__(self, title: str, value: str = "--", unit: str = "", parent=None):
        super().__init__(parent)
        self._prev_value = ""

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._title = QtWidgets.QLabel(title)
        self._title.setObjectName("Title")
        self._title.setAlignment(QtCore.Qt.AlignLeft)

        self._value = QtWidgets.QLabel(value)
        self._value.setObjectName("Value")
        self._value.setAlignment(QtCore.Qt.AlignLeft)

        self._unit = QtWidgets.QLabel(unit)
        self._unit.setObjectName("Unit")
        self._unit.setAlignment(QtCore.Qt.AlignLeft)

        layout.addWidget(self._title)
        layout.addWidget(self._value)
        layout.addWidget(self._unit)

    def update_value(self, value: str, unit: str = ""):
        if value != self._prev_value:
            self._prev_value = value
            # 轻微闪烁反馈
            self._value.setStyleSheet("color: #ffffff; font-size: 22px; font-weight: 700;")
            QtCore.QTimer.singleShot(200, self._reset_value_style)

        self._value.setText(value)
        if unit:
            self._unit.setText(unit)

    def _reset_value_style(self):
        self._value.setStyleSheet("")


class ModelRow(QtWidgets.QWidget):
    """单行模型统计"""

    def __init__(self, name: str = "--", calls: int = 0, cost: float = 0.0, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self._name = QtWidgets.QLabel(name)
        self._name.setObjectName("ModelName")
        self._name.setMinimumWidth(80)

        self._calls = QtWidgets.QLabel(str(calls))
        self._calls.setObjectName("ModelValue")
        self._calls.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self._cost = QtWidgets.QLabel(f"${cost:.4f}")
        self._cost.setObjectName("ModelValue")
        self._cost.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        layout.addWidget(self._name, 2)
        layout.addWidget(self._calls, 1)
        layout.addWidget(self._cost, 1)

    def update_data(self, name: str, calls: int, cost: float):
        short = name.split("/")[-1] if "/" in name else name
        if len(short) > 14:
            short = short[:11] + "..."
        self._name.setText(short)
        self._calls.setText(str(calls))
        self._cost.setText(f"${cost:.4f}")


# ── 设置对话框 ──


class SettingsDialog(QtWidgets.QDialog):
    """小组件设置对话框"""

    def __init__(self, settings: dict[str, Any], parent=None):
        super().__init__(parent)
        self._settings = dict(settings)
        self.setWindowTitle("小组件设置")
        self.setFixedSize(380, 320)
        self.setModal(True)

        theme = THEMES.get(settings.get("theme", DEFAULT_THEME), THEMES[DEFAULT_THEME])
        self.setStyleSheet(build_style(theme))

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # 标题
        title = QtWidgets.QLabel("小组件设置")
        title.setObjectName("Title")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        # 刷新间隔
        interval_layout = QtWidgets.QHBoxLayout()
        interval_layout.addWidget(QtWidgets.QLabel("刷新间隔 (秒)"))
        self._interval_spin = QtWidgets.QSpinBox()
        self._interval_spin.setRange(1, 60)
        self._interval_spin.setValue(self._settings.get("refresh_interval", 5))
        interval_layout.addWidget(self._interval_spin, 1)
        layout.addLayout(interval_layout)

        # 颜色主题
        theme_layout = QtWidgets.QHBoxLayout()
        theme_layout.addWidget(QtWidgets.QLabel("颜色主题"))
        self._theme_combo = QtWidgets.QComboBox()
        self._theme_combo.addItems(list(THEMES.keys()))
        current_theme = self._settings.get("theme", DEFAULT_THEME)
        self._theme_combo.setCurrentText(current_theme)
        theme_layout.addWidget(self._theme_combo, 1)
        layout.addLayout(theme_layout)

        # 置顶
        self._ontop_check = QtWidgets.QCheckBox("窗口置顶")
        self._ontop_check.setChecked(self._settings.get("always_on_top", True))
        layout.addWidget(self._ontop_check)

        # 透明演示
        opacity_layout = QtWidgets.QHBoxLayout()
        opacity_layout.addWidget(QtWidgets.QLabel("透明度"))
        self._opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._opacity_slider.setRange(30, 100)
        self._opacity_slider.setValue(int(self._settings.get("opacity", 1.0) * 100))
        self._opacity_label = QtWidgets.QLabel(f"{self._opacity_slider.value()}%")
        self._opacity_slider.valueChanged.connect(lambda v: self._opacity_label.setText(f"{v}%"))
        opacity_layout.addWidget(self._opacity_slider, 1)
        opacity_layout.addWidget(self._opacity_label)
        layout.addLayout(opacity_layout)

        # 重置位置
        reset_btn = QtWidgets.QPushButton("重置窗口位置")
        reset_btn.clicked.connect(self._reset_position)
        layout.addWidget(reset_btn)

        layout.addStretch()

        # 按钮
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QtWidgets.QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QtWidgets.QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        save_btn.setDefault(True)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _reset_position(self):
        try:
            POSITION_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        QtWidgets.QMessageBox.information(self, "提示", "窗口位置已重置，下次启动将居中显示。")

    def get_updated_settings(self) -> dict[str, Any]:
        return {
            "refresh_interval": self._interval_spin.value(),
            "theme": self._theme_combo.currentText(),
            "always_on_top": self._ontop_check.isChecked(),
            "opacity": self._opacity_slider.value() / 100.0,
        }


# ── 主小组件 ──


class DesktopWidget(QtWidgets.QWidget):
    """主桌面小组件"""

    def __init__(self, config: Config, db: Database, settings: dict[str, Any]):
        super().__init__()
        self._config = config
        self._db = db
        self._settings = settings
        self._drag_pos: Optional[QtCore.QPoint] = None
        self._tray_icon: Optional[QtWidgets.QSystemTrayIcon] = None
        self._status = "ok"  # ok, warn, error

        # 主题
        self._theme_name = settings.get("theme", DEFAULT_THEME)
        self._theme = THEMES.get(self._theme_name, THEMES[DEFAULT_THEME])

        self._setup_window()
        self._build_ui()
        self._setup_tray()
        self._refresh()
        self._restore_position()

        # 定时刷新
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._refresh)
        interval = settings.get("refresh_interval", 5) * 1000
        self._timer.start(interval)

    def _setup_window(self):
        """配置窗口属性"""
        self.setObjectName("WidgetMain")
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFixedWidth(320)
        self.setWindowOpacity(self._settings.get("opacity", 1.0))
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(build_style(self._theme))

    def _setup_tray(self):
        """设置系统托盘"""
        # 创建图标（若无法创建则静默跳过）
        icon = QtGui.QIcon()
        # 使用内置图标
        pixmap = QtGui.QPixmap(32, 32)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(QtGui.QColor("#7dd3fc"))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(4, 4, 24, 24, 6, 6)
        painter.end()
        icon.addPixmap(pixmap)

        self._tray_icon = QtWidgets.QSystemTrayIcon(icon, self)
        self._tray_icon.setToolTip("Model Monitor")

        # 托盘菜单
        tray_menu = QtWidgets.QMenu()

        show_action = tray_menu.addAction("显示/隐藏")
        show_action.triggered.connect(self._toggle_visible)

        refresh_action = tray_menu.addAction("立即刷新")
        refresh_action.triggered.connect(self._refresh)

        tray_menu.addSeparator()

        settings_action = tray_menu.addAction("设置...")
        settings_action.triggered.connect(self._open_settings)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("退出")
        quit_action.triggered.connect(self._quit_app)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _toggle_visible(self):
        """切换显示/隐藏"""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _on_tray_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason):
        """托盘图标点击事件"""
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_visible()

    def _build_ui(self):
        """构建界面"""
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        # ── 标题栏 ──
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)

        title = QtWidgets.QLabel("MODEL MONITOR")
        title.setObjectName("Title")

        status = QtWidgets.QLabel("●")
        status.setObjectName("StatusDot")
        status.setProperty("status", "ok")
        self._status_label = status

        self._status_text = QtWidgets.QLabel("Connected")
        self._status_text.setObjectName("Recent")

        header.addWidget(title)
        header.addStretch()
        header.addWidget(status)
        header.addWidget(self._status_text)
        outer.addLayout(header)

        # ── 核心指标 (2×2 网格) ──
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(12)
        grid.setContentsMargins(0, 0, 0, 0)

        self._card_calls = StatCard("CALLS", "--", "总请求数")
        self._card_cost = StatCard("COST", "$0.00", "总费用")
        self._card_today = StatCard("TODAY", "$0.00", "今日费用")
        self._card_month = StatCard("MONTH", "$0.00", "本月费用")

        grid.addWidget(self._card_calls, 0, 0)
        grid.addWidget(self._card_cost, 0, 1)
        grid.addWidget(self._card_today, 1, 0)
        grid.addWidget(self._card_month, 1, 1)
        outer.addLayout(grid)

        # ── Token 统计 ──
        token_layout = QtWidgets.QHBoxLayout()
        token_layout.setSpacing(16)
        self._card_in = StatCard("INPUT TOKENS", "--", "输入")
        self._card_out = StatCard("OUTPUT TOKENS", "--", "输出")
        token_layout.addWidget(self._card_in)
        token_layout.addWidget(self._card_out)
        outer.addLayout(token_layout)

        # ── 分隔线 ──
        sep = QtWidgets.QFrame()
        sep.setObjectName("Separator")
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        outer.addWidget(sep)

        # ── 模型表头 ──
        model_header = QtWidgets.QHBoxLayout()
        mh_name = QtWidgets.QLabel("MODEL")
        mh_name.setObjectName("Title")
        mh_calls = QtWidgets.QLabel("CALLS")
        mh_calls.setObjectName("Title")
        mh_cost = QtWidgets.QLabel("COST")
        mh_cost.setObjectName("Title")
        mh_calls.setAlignment(QtCore.Qt.AlignRight)
        mh_cost.setAlignment(QtCore.Qt.AlignRight)
        model_header.addWidget(mh_name, 2)
        model_header.addWidget(mh_calls, 1)
        model_header.addWidget(mh_cost, 1)
        outer.addLayout(model_header)

        # ── 模型行 (最多 5 行) ──
        self._model_rows: list[ModelRow] = []
        for _ in range(5):
            row = ModelRow()
            self._model_rows.append(row)
            outer.addWidget(row)

        # ── 底部信息 ──
        bottom = QtWidgets.QHBoxLayout()
        self._latency = QtWidgets.QLabel("延迟: --ms")
        self._latency.setObjectName("Recent")
        self._recent = QtWidgets.QLabel("")
        self._recent.setObjectName("Recent")
        bottom.addWidget(self._latency)
        bottom.addStretch()
        bottom.addWidget(self._recent)
        outer.addLayout(bottom)

        self.adjustSize()
        self.setFixedHeight(self.sizeHint().height())

    def _refresh(self):
        """刷新数据"""
        try:
            stats = self._db.get_stats()
            today = self._db.get_today_cost()
            month_cost_val = self._db.get_month_cost()
            models = self._db.get_model_stats()
            calls = self._db.get_calls(limit=1)

            # 更新卡片
            total_calls = stats.get("total_calls", 0)
            total_cost = stats.get("total_cost", 0)
            self._card_calls.update_value(str(total_calls), "总请求数")
            self._card_cost.update_value(f"${total_cost:.4f}", "总费用")
            self._card_today.update_value(f"${today:.4f}", "今日费用")
            self._card_month.update_value(f"${month_cost_val:.4f}", "本月费用")
            self._card_in.update_value(
                f"{stats.get('total_input_tokens', 0):,}", "输入 Token"
            )
            self._card_out.update_value(
                f"{stats.get('total_output_tokens', 0):,}", "输出 Token"
            )

            # 延迟
            lat = stats.get("avg_latency_ms", 0)
            self._latency.setText(f"延迟: {lat:.0f}ms")

            # 模型行
            for i, row in enumerate(self._model_rows):
                if i < len(models):
                    m = models[i]
                    row.update_data(m["model"], m["calls"], m["cost"])
                    row.show()
                else:
                    row.hide()

            # 最近调用
            if calls:
                c = calls[0]
                model = c.get("model", "?").split("/")[-1]
                if len(model) > 12:
                    model = model[:9] + "..."
                self._recent.setText(f"最近: {model}")
            else:
                self._recent.setText("暂无数据")

            # 状态
            if total_calls == 0:
                self._set_status("warn", "等待数据")
            else:
                self._set_status("ok", "运行中")

        except Exception as e:
            logger.error("刷新失败: %s", e)
            self._set_status("error", f"错误: {e}")

    def _set_status(self, status: str, text: str):
        """更新状态指示器"""
        self._status = status
        self._status_label.setProperty("status", status)
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)
        self._status_text.setText(text)

    def _restore_position(self):
        """恢复上次窗口位置"""
        pos = load_position()
        if pos:
            self.move(pos["x"], pos["y"])
        else:
            # 居中到屏幕右下角
            screen = QtWidgets.QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                x = geo.right() - self.width() - 20
                y = geo.bottom() - self.height() - 60
                self.move(x, y)

    def _open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self._settings, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            new_settings = dialog.get_updated_settings()
            self._settings = new_settings
            save_settings(new_settings)

            # 应用设置
            self._theme_name = new_settings.get("theme", DEFAULT_THEME)
            self._theme = THEMES.get(self._theme_name, THEMES[DEFAULT_THEME])
            self._apply_style()

            # 刷新间隔
            self._timer.setInterval(new_settings.get("refresh_interval", 5) * 1000)

            # 置顶
            flags = self.windowFlags()
            if new_settings.get("always_on_top", True):
                flags |= QtCore.Qt.WindowStaysOnTopHint
            else:
                flags &= ~QtCore.Qt.WindowStaysOnTopHint
            self.setWindowFlags(flags)
            self.show()

            # 透明度
            self.setWindowOpacity(new_settings.get("opacity", 1.0))

    def _quit_app(self):
        """退出应用"""
        if self._tray_icon:
            self._tray_icon.hide()
        QtWidgets.QApplication.quit()

    # ── 拖拽移动 ──

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self._drag_pos is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.LeftButton and self._drag_pos is not None:
            # 保存新位置
            pos = self.pos()
            save_position(pos.x(), pos.y())
            self._drag_pos = None
            event.accept()

    # ── 右键菜单 ──

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent):
        menu = QtWidgets.QMenu(self)

        refresh_action = menu.addAction("🔄 立即刷新")
        refresh_action.triggered.connect(self._refresh)

        settings_action = menu.addAction("⚙️ 设置...")
        settings_action.triggered.connect(self._open_settings)

        # 置顶切换
        is_ontop = bool(self.windowFlags() & QtCore.Qt.WindowStaysOnTopHint)
        ontop_action = menu.addAction("📌 置顶" if not is_ontop else "📌 取消置顶")
        ontop_action.triggered.connect(self._toggle_ontop)

        menu.addSeparator()

        # 快速切换主题（子菜单）
        theme_menu = menu.addMenu("🎨 切换主题")
        for name in THEMES:
            action = theme_menu.addAction(name.capitalize())
            action.setCheckable(True)
            action.setChecked(name == self._theme_name)
            action.triggered.connect(lambda checked, n=name: self._switch_theme(n))

        menu.addSeparator()

        quit_action = menu.addAction("❌ 退出")
        quit_action.triggered.connect(self._quit_app)

        menu.exec(event.globalPos())

    def _toggle_ontop(self):
        """切换置顶状态"""
        flags = self.windowFlags()
        if flags & QtCore.Qt.WindowStaysOnTopHint:
            flags &= ~QtCore.Qt.WindowStaysOnTopHint
            self._settings["always_on_top"] = False
        else:
            flags |= QtCore.Qt.WindowStaysOnTopHint
            self._settings["always_on_top"] = True
        self.setWindowFlags(flags)
        self.show()
        save_settings(self._settings)

    def _switch_theme(self, name: str):
        """切换颜色主题"""
        if name not in THEMES:
            return
        self._theme_name = name
        self._theme = THEMES[name]
        self._settings["theme"] = name
        self._apply_style()
        save_settings(self._settings)


def run_desktop_widget(config: Config, db: Database) -> int:
    """启动桌面小组件"""
    # 在 PySide6 之前需要 QApplication
    app = QtWidgets.QApplication(sys.argv)

    # 应用级设置（高 DPI）
    app.setStyle("Fusion")

    # 全局字体
    font = QtGui.QFont("SF Pro Display", 11)
    font.setStyleStrategy(QtGui.QFont.PreferAntialias)
    app.setFont(font)

    # 加载设置
    settings = load_settings()

    widget = DesktopWidget(config, db, settings)
    widget.show()

    return app.exec()
