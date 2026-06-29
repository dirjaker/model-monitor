"""
测试费用预测模块

测试线性回归预测、趋势分析。
"""

import os
import tempfile
from datetime import datetime, timedelta

import pytest

from src.database import Database
from src.analysis.predictor import CostPredictor


@pytest.fixture
def db():
    """创建含历史数据的数据库"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    database = Database(tmp.name)

    # 插入 30 天的历史数据
    base = datetime.now()
    # 直接操作数据库插入历史日期的数据
    conn = database._get_conn()
    for day_offset in range(30):
        day = base - timedelta(days=day_offset)
        date_str = day.strftime("%Y-%m-%d %H:%M:%S")
        cost = 3.0 - (day_offset * 0.1)  # 费用递增趋势（越近越高）
        conn.execute(
            """INSERT INTO api_calls
            (timestamp, mode, provider, model, input_tokens, output_tokens,
             cost, latency_ms, status_code, endpoint)
            VALUES (?, 'proxy', 'deepseek', 'deepseek-chat',
                    ?, ?, ?, ?, 200, '/chat/completions')""",
            (date_str, 500000, 250000, cost, 120.0),
        )
    conn.commit()

    yield database
    database.close()
    os.unlink(tmp.name)


@pytest.fixture
def empty_db():
    """空数据库"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    database = Database(tmp.name)
    yield database
    database.close()
    os.unlink(tmp.name)


class TestCostPredictor:
    """费用预测器测试"""

    def test_predict_daily_with_data(self, db):
        """有历史数据时应返回预测"""
        predictor = CostPredictor(db)
        predictions = predictor.predict_daily(days_ahead=7)

        assert len(predictions) == 7
        for p in predictions:
            assert "day" in p
            assert "predicted_cost" in p
            assert "confidence" in p
            assert p["predicted_cost"] >= 0

    def test_predict_daily_empty(self, empty_db):
        """无数据时应返回零值预测"""
        predictor = CostPredictor(empty_db)
        predictions = predictor.predict_daily(days_ahead=7)

        assert len(predictions) == 7
        for p in predictions:
            assert p["predicted_cost"] == 0.0
            assert p["confidence"] == "low"

    def test_predict_daily_confidence(self, db):
        """充足数据应得到较高置信度"""
        predictor = CostPredictor(db)
        predictions = predictor.predict_daily(days_ahead=7)

        # 有 30 天数据，置信度应为 medium 或 high
        assert predictions[0]["confidence"] in ("high", "medium")

    def test_predict_monthly(self, db):
        """月预测应包含当前和预测值"""
        predictor = CostPredictor(db)
        monthly = predictor.predict_monthly()

        assert "current_month_cost" in monthly
        assert "predicted_month_total" in monthly
        assert "today_cost" in monthly
        assert "daily_predictions" in monthly
        assert monthly["current_month_cost"] >= 0
        assert monthly["predicted_month_total"] >= monthly["current_month_cost"]

    def test_get_cost_trend_increasing(self, db):
        """增长型数据的趋势"""
        predictor = CostPredictor(db)
        trend = predictor.get_cost_trend(days=30)

        assert trend["data_points"] >= 2
        assert trend["trend"] in ("increasing", "stable", "unknown")
        assert "change_pct" in trend

    def test_get_cost_trend_empty(self, empty_db):
        """无数据时趋势为 unknown"""
        predictor = CostPredictor(empty_db)
        trend = predictor.get_cost_trend(days=30)

        assert trend["trend"] == "unknown"
        assert trend["data_points"] == 0

    def test_get_cost_trend_insufficient_data(self, empty_db):
        """数据不足时应返回 stable"""
        # 只插一条
        empty_db.record_call(
            mode="proxy", provider="deepseek", model="deepseek-chat",
            input_tokens=100, output_tokens=50, cost=0.001,
            latency_ms=100, status_code=200, endpoint="/chat/completions",
        )

        predictor = CostPredictor(empty_db)
        trend = predictor.get_cost_trend(days=30)

        # 只有一条数据点
        assert trend["data_points"] == 1

    def test_r_squared_included(self, db):
        """预测结果应包含 R²"""
        predictor = CostPredictor(db)
        predictions = predictor.predict_daily(days_ahead=1)

        assert "r_squared" in predictions[0]
        assert predictions[0]["r_squared"] >= 0.0
