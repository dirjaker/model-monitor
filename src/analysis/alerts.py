"""
告警模块
当费用超过阈值时发送告警通知。
"""

import json
import logging
import threading
import time
from typing import Any, Optional

import httpx

from src.config import Config
from src.database import Database

logger = logging.getLogger(__name__)


class AlertLevel:
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertManager:
    """告警管理器"""

    def __init__(self, config: Config, db: Database):
        self._config = config
        self._db = db
        self._enabled = config.alerts_enabled
        self._daily_threshold = config.alerts_daily_threshold
        self._monthly_threshold = config.alerts_monthly_threshold
        self._webhook_url = config.alerts_webhook_url
        self._last_daily_alert: Optional[str] = None
        self._last_monthly_alert: Optional[str] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, interval: int = 300) -> None:
        """启动告警检查（后台线程，默认每5分钟检查一次）"""
        if not self._enabled:
            logger.info("告警功能未启用")
            return

        self._running = True
        self._thread = threading.Thread(target=self._check_loop, args=(interval,), daemon=True)
        self._thread.start()
        logger.info("告警检查已启动，间隔 %d 秒", interval)

    def stop(self) -> None:
        """停止告警检查"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    def _check_loop(self, interval: int) -> None:
        """告警检查循环"""
        while self._running:
            try:
                self.check_thresholds()
            except Exception as e:
                logger.error("告警检查失败: %s", e)
            time.sleep(interval)

    def check_thresholds(self) -> list[dict[str, Any]]:
        """检查阈值并触发告警"""
        alerts: list[dict[str, Any]] = []
        today_str = time.strftime("%Y-%m-%d")

        # 检查日费用
        today_cost = self._db.get_today_cost()
        if today_cost >= self._daily_threshold:
            alert = {
                "level": AlertLevel.WARNING if today_cost < self._daily_threshold * 2 else AlertLevel.CRITICAL,
                "type": "daily_threshold",
                "message": f"日费用 ${today_cost:.2f} 已超过阈值 ${self._daily_threshold:.2f}",
                "cost": today_cost,
                "threshold": self._daily_threshold,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            alerts.append(alert)

            if self._last_daily_alert != today_str:
                self._last_daily_alert = today_str
                self._send_alert(alert)

        # 检查月费用
        month_cost = self._db.get_month_cost()
        if month_cost >= self._monthly_threshold:
            alert = {
                "level": AlertLevel.WARNING if month_cost < self._monthly_threshold * 2 else AlertLevel.CRITICAL,
                "type": "monthly_threshold",
                "message": f"月费用 ${month_cost:.2f} 已超过阈值 ${self._monthly_threshold:.2f}",
                "cost": month_cost,
                "threshold": self._monthly_threshold,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            alerts.append(alert)

            month_str = time.strftime("%Y-%m")
            if self._last_monthly_alert != month_str:
                self._last_monthly_alert = month_str
                self._send_alert(alert)

        return alerts

    def _send_alert(self, alert: dict[str, Any]) -> None:
        """发送告警通知"""
        if not self._webhook_url:
            logger.warning("告警 webhook 未配置，仅记录日志: %s", alert["message"])
            return

        try:
            with httpx.Client(timeout=10) as client:
                payload = {
                    "text": f"[Model Monitor] {alert['level'].upper()}: {alert['message']}",
                    "level": alert["level"],
                    "type": alert["type"],
                    "cost": alert["cost"],
                    "threshold": alert["threshold"],
                    "timestamp": alert["timestamp"],
                }
                resp = client.post(self._webhook_url, json=payload)
                resp.raise_for_status()
                logger.info("告警已发送: %s", alert["message"])
        except Exception as e:
            logger.error("发送告警失败: %s", e)

    def get_status(self) -> dict[str, Any]:
        """获取告警状态"""
        return {
            "enabled": self._enabled,
            "daily_threshold": self._daily_threshold,
            "monthly_threshold": self._monthly_threshold,
            "today_cost": self._db.get_today_cost(),
            "month_cost": self._db.get_month_cost(),
            "webhook_configured": bool(self._webhook_url),
        }
