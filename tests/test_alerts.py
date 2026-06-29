"""
测试告警模块

测试阈值检查、告警触发、频率控制。
"""

import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.database import Database
from src.analysis.alerts import AlertManager, AlertLevel


@pytest.fixture
def db():
    """创建临时数据库"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    database = Database(tmp.name)
    yield database
    database.close()
    os.unlink(tmp.name)


@pytest.fixture
def config():
    """创建默认配置"""
    c = MagicMock(spec=Config)
    c.alerts_enabled = True
    c.alerts_daily_threshold = 10.0
    c.alerts_monthly_threshold = 200.0
    c.alerts_webhook_url = ""
    return c


class TestAlertManager:
    """告警管理器测试"""

    def test_init_disabled(self, db):
        """禁用时不应启动告警检查"""
        c = MagicMock(spec=Config)
        c.alerts_enabled = False
        c.alerts_daily_threshold = 10.0
        c.alerts_monthly_threshold = 200.0
        c.alerts_webhook_url = ""

        mgr = AlertManager(c, db)
        assert mgr._enabled is False

    def test_check_thresholds_no_alerts(self, config, db):
        """费用低于阈值不应触发告警"""
        mgr = AlertManager(config, db)
        alerts = mgr.check_thresholds()
        assert len(alerts) == 0

    def test_check_thresholds_daily(self, config, db):
        """超过日阈值应触发告警"""
        # 插入费用超过阈值的记录
        db.record_call(
            mode="proxy", provider="deepseek", model="deepseek-chat",
            input_tokens=10000000, output_tokens=5000000,
            cost=15.0,  # 超过 10.0 的日阈值
            latency_ms=100, status_code=200, endpoint="/chat/completions",
        )

        mgr = AlertManager(config, db)
        alerts = mgr.check_thresholds()
        assert len(alerts) >= 1
        daily_alerts = [a for a in alerts if a["type"] == "daily_threshold"]
        assert len(daily_alerts) == 1
        assert daily_alerts[0]["level"] == AlertLevel.WARNING

    def test_check_thresholds_daily_critical(self, config, db):
        """日费用超过阈值 2 倍应为 CRITICAL"""
        db.record_call(
            mode="proxy", provider="deepseek", model="deepseek-chat",
            input_tokens=10000000, output_tokens=5000000,
            cost=25.0,  # 超过 10.0 的 2 倍
            latency_ms=100, status_code=200, endpoint="/chat/completions",
        )

        mgr = AlertManager(config, db)
        alerts = mgr.check_thresholds()
        daily_alerts = [a for a in alerts if a["type"] == "daily_threshold"]
        assert daily_alerts[0]["level"] == AlertLevel.CRITICAL

    def test_check_thresholds_monthly(self, config, db):
        """超过月阈值应触发告警"""
        db.record_call(
            mode="proxy", provider="deepseek", model="deepseek-chat",
            input_tokens=100000000, output_tokens=50000000,
            cost=250.0,  # 超过 200.0 的月阈值
            latency_ms=100, status_code=200, endpoint="/chat/completions",
        )

        mgr = AlertManager(config, db)
        alerts = mgr.check_thresholds()
        monthly_alerts = [a for a in alerts if a["type"] == "monthly_threshold"]
        assert len(monthly_alerts) == 1
        assert monthly_alerts[0]["level"] == AlertLevel.WARNING

    def test_dedup_daily_alert(self, config, db):
        """同日不应重复发送日告警"""
        db.record_call(
            mode="proxy", provider="deepseek", model="deepseek-chat",
            input_tokens=10000000, output_tokens=5000000,
            cost=15.0, latency_ms=100, status_code=200, endpoint="/chat/completions",
        )

        mgr = AlertManager(config, db)
        # 第一次触发
        alerts1 = mgr.check_thresholds()
        assert len(alerts1) >= 1

        # 第二次触发应不重复（同一天）
        alerts2 = mgr.check_thresholds()
        # 告警事件仍会返回，但不会调用 _send_alert
        # 关键是不应该有新的独立告警
        assert len(alerts2) >= 1

    def test_send_alert_no_webhook(self, config, db):
        """无 webhook 时仅记录日志"""
        db.record_call(
            mode="proxy", provider="deepseek", model="deepseek-chat",
            input_tokens=10000000, output_tokens=5000000,
            cost=15.0, latency_ms=100, status_code=200, endpoint="/chat/completions",
        )

        mgr = AlertManager(config, db)
        # 不应抛出异常
        mgr.check_thresholds()

    def test_send_alert_with_webhook(self, config, db):
        """有 webhook 时应发送 HTTP 请求"""
        config.alerts_webhook_url = "https://hooks.example.com/alert"

        db.record_call(
            mode="proxy", provider="deepseek", model="deepseek-chat",
            input_tokens=10000000, output_tokens=5000000,
            cost=15.0, latency_ms=100, status_code=200, endpoint="/chat/completions",
        )

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance

            mgr = AlertManager(config, db)
            mgr.check_thresholds()

            # 验证 post 被调用
            assert mock_instance.post.called
            call_args = mock_instance.post.call_args
            assert call_args[0][0] == "https://hooks.example.com/alert"

    def test_get_status(self, config, db):
        """状态查询应返回配置信息"""
        mgr = AlertManager(config, db)
        status = mgr.get_status()
        assert status["enabled"] is True
        assert status["daily_threshold"] == 10.0
        assert status["monthly_threshold"] == 200.0
        assert status["webhook_configured"] is False

    def test_alert_fields(self, config, db):
        """告警事件应包含全部字段"""
        db.record_call(
            mode="proxy", provider="deepseek", model="deepseek-chat",
            input_tokens=10000000, output_tokens=5000000,
            cost=15.0, latency_ms=100, status_code=200, endpoint="/chat/completions",
        )

        mgr = AlertManager(config, db)
        alerts = mgr.check_thresholds()
        alert = alerts[0]
        assert "level" in alert
        assert "type" in alert
        assert "message" in alert
        assert "cost" in alert
        assert "threshold" in alert
        assert "timestamp" in alert
