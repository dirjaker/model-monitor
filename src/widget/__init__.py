"""
桌面小组件
PySide6 实现的 macOS 风格浮窗监控面板。
"""

import sys
import logging
from typing import Optional

from src.config import Config
from src.database import Database

logger = logging.getLogger(__name__)

# 延迟导入 PySide6，启动时再检查
QtWidgets = QtGui = QtCore = None


def _check_pyside6() -> bool:
    """检查 PySide6 是否可用"""
    global QtWidgets, QtGui, QtCore
    try:
        from PySide6 import QtWidgets as _W, QtGui as _G, QtCore as _C
        QtWidgets, QtGui, QtCore = _W, _G, _C
        return True
    except ImportError:
        return False


# ── 样式 ──────────────────────────────────────────────

WIDGET_STYLE = """
QWidget#WidgetMain {
    background-color: rgba(18, 22, 32, 235);
    border: 1px solid rgba(60, 70, 90, 180);
    border-radius: 16px;
}
QLabel {
    color: #c8ceda;
    font-family: -apple-system, 'SF Pro Display', 'Segoe UI', sans-serif;
}
QLabel#Title {
    color: #8b95ab;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1.5px;
}
QLabel#Value {
    color: #e8ecf4;
    font-size: 22px;
    font-weight: 700;
}
QLabel#Unit {
    color: #5a6478;
    font-size: 10px;
}
QLabel#ModelName {
    color: #7dd3fc;
    font-size: 11px;
}
QLabel#ModelValue {
    color: #94a3b8;
    font-size: 11px;
}
QLabel#StatusDot {
    color: #34d399;
    font-size: 8px;
}
QLabel#Recent {
    color: #64748b;
    font-size: 10px;
}
QFrame#Separator {
    background-color: rgba(60, 70, 90, 100);
    max-height: 1px;
}
"""


class StatCard(QtWidgets.QWidget):
    """单个统计指标卡片"""

    def __init__(self, title: str, value: str = "--", unit: str = "", parent=None):
        super().__init__(parent)
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
        self._value.setText(value)
        if unit:
            self._unit.setText(unit)


class ModelRow(QtWidgets.QWidget):
    """单行模型统计"""

    def __init__(self, name: str, calls: int = 0, cost: float = 0.0, parent=None):
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


class DesktopWidget(QtWidgets.QWidget):
    """主桌面小组件"""

    def __init__(self, config: Config, db: Database, parent=None):
        super().__init__(parent)
        self._config = config
        self._db = db
        self._drag_pos = None

        self._setup_window()
        self._build_ui()
        self._refresh()

        # 定时刷新
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)  # 5秒

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
        self.setStyleSheet(WIDGET_STYLE)

    def _build_ui(self):
        """构建界面"""
        # 外层容器（圆角背景）
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

        self._status_text = QtWidgets.QLabel("Connected")
        self._status_text.setObjectName("Recent")

        header.addWidget(title)
        header.addStretch()
        header.addWidget(status)
        header.addWidget(self._status_text)
        outer.addLayout(header)

        # ── 核心指标（2x2 网格）──
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(12)
        grid.setContentsMargins(0, 0, 0, 0)

        self._card_calls = StatCard("CALLS", "--", "total requests")
        self._card_cost = StatCard("COST", "$0.00", "USD total")
        self._card_today = StatCard("TODAY", "$0.00", "USD today")
        self._card_month = StatCard("MONTH", "$0.00", "USD this month")

        grid.addWidget(self._card_calls, 0, 0)
        grid.addWidget(self._card_cost, 0, 1)
        grid.addWidget(self._card_today, 1, 0)
        grid.addWidget(self._card_month, 1, 1)
        outer.addLayout(grid)

        # ── Token 统计 ──
        token_layout = QtWidgets.QHBoxLayout()
        token_layout.setSpacing(16)
        self._card_in = StatCard("INPUT TOKENS", "--", "processed")
        self._card_out = StatCard("OUTPUT TOKENS", "--", "generated")
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

        # ── 模型行（最多4行）──
        self._model_rows = []
        for i in range(4):
            row = ModelRow("--", 0, 0.0)
            self._model_rows.append(row)
            outer.addWidget(row)

        # ── 底部延迟 + 最近调用 ──
        bottom = QtWidgets.QHBoxLayout()
        self._latency = QtWidgets.QLabel("Latency: --ms")
        self._latency.setObjectName("Recent")
        self._recent = QtWidgets.QLabel("")
        self._recent.setObjectName("Recent")
        bottom.addWidget(self._latency)
        bottom.addStretch()
        bottom.addWidget(self._recent)
        outer.addLayout(bottom)

        # 设置最终高度
        self.adjustSize()
        self.setFixedHeight(self.sizeHint().height())

    def _refresh(self):
        """刷新数据"""
        try:
            stats = self._db.get_stats()
            today = self._db.get_today_cost()
            month = self._db.get_month_cost()
            models = self._db.get_model_stats()
            calls = self._db.get_calls(limit=1)

            # 更新卡片
            self._card_calls.update_value(
                str(stats.get("total_calls", 0)),
                "total requests",
            )
            self._card_cost.update_value(
                f"${stats.get('total_cost', 0):.4f}", "USD total"
            )
            self._card_today.update_value(f"${today:.4f}", "USD today")
            self._card_month.update_value(f"${month:.4f}", "USD this month")
            self._card_in.update_value(
                f"{stats.get('total_input_tokens', 0):,}", "processed"
            )
            self._card_out.update_value(
                f"{stats.get('total_output_tokens', 0):,}", "generated"
            )

            # 延迟
            lat = stats.get("avg_latency_ms", 0)
            self._latency.setText(f"Avg Latency: {lat:.0f}ms")

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
                self._recent.setText(f"Latest: {model}")

        except Exception as e:
            logger.error("刷新失败: %s", e)

    # ── 拖拽移动 ──

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── 右键退出 ──

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu(self)
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(QtWidgets.QApplication.quit)
        menu.exec(event.globalPos())


def run_desktop_widget(config: Config, db: Database) -> int:
    """启动桌面小组件"""
    if not _check_pyside6():
        print("错误: PySide6 未安装")
        print("安装: pip install PySide6")
        return 1

    app = QtWidgets.QApplication(sys.argv)

    # 全局字体
    font = QtGui.QFont("SF Pro Display", 11)
    font.setStyleStrategy(QtGui.QFont.PreferAntialias)
    app.setFont(font)

    widget = DesktopWidget(config, db)
    widget.show()

    return app.exec()
