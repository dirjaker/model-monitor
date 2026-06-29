"""
测试数据库模块

测试线程安全的 SQLite 数据库的 CRUD 操作、统计查询和导出功能。
"""

import json
import os
import tempfile
import time
from datetime import datetime

import pytest

from src.database import Database


@pytest.fixture
def db():
    """创建临时数据库"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    database = Database(tmp.name)
    yield database
    database.close()
    os.unlink(tmp.name)


class TestDatabase:
    """数据库功能测试"""

    def test_init_creates_schema(self, db):
        """初始化应创建所有必要的表"""
        from src.config import Config
        # 验证表存在
        with db._cursor() as cursor:
            tables = cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_names = [t["name"] for t in tables]
            assert "api_calls" in table_names
            assert "daily_summary" in table_names
            assert "schema_version" in table_names

    def test_record_and_get_call(self, db):
        """记录调用后应能正确查询到"""
        call_id = db.record_call(
            mode="proxy",
            provider="deepseek",
            model="deepseek-chat",
            input_tokens=100,
            output_tokens=50,
            cost=0.0002,
            latency_ms=123.4,
            status_code=200,
            endpoint="/chat/completions",
            request_body='{"model":"deepseek-chat"}',
            response_body='{"choices":[{"message":{"content":"hello"}}],"usage":{"prompt_tokens":100,"completion_tokens":50}}',
        )
        assert call_id > 0

        calls = db.get_calls(limit=10)
        assert len(calls) == 1
        assert calls[0]["provider"] == "deepseek"
        assert calls[0]["model"] == "deepseek-chat"
        assert calls[0]["input_tokens"] == 100
        assert calls[0]["output_tokens"] == 50
        assert abs(calls[0]["cost"] - 0.0002) < 0.00001
        assert abs(calls[0]["latency_ms"] - 123.4) < 0.1

    def test_record_multiple_calls(self, db):
        """多次插入应累积数据"""
        for i in range(5):
            db.record_call(
                mode="proxy", provider="deepseek", model="deepseek-chat",
                input_tokens=100, output_tokens=50, cost=0.0002 * (i + 1),
                latency_ms=100 + i, status_code=200, endpoint="/chat/completions",
            )

        stats = db.get_stats()
        assert stats["total_calls"] == 5
        assert stats["total_input_tokens"] == 500
        assert stats["total_output_tokens"] == 250

        calls = db.get_calls(limit=3)
        assert len(calls) == 3

    def test_get_stats_empty(self, db):
        """空数据库应返回零值"""
        stats = db.get_stats()
        assert stats["total_calls"] == 0
        assert stats["total_cost"] == 0
        assert stats["total_input_tokens"] == 0

    def test_get_model_stats(self, db):
        """应按模型分组统计"""
        models_data = [
            ("deepseek-chat", 0.0002),
            ("deepseek-chat", 0.0003),
            ("deepseek-reasoner", 0.0004),
        ]
        for model, cost in models_data:
            db.record_call(
                mode="proxy", provider="deepseek", model=model,
                input_tokens=100, output_tokens=50, cost=cost,
                latency_ms=100, status_code=200, endpoint="/chat/completions",
            )

        stats = db.get_model_stats()
        assert len(stats) == 2
        chat_stats = [s for s in stats if s["model"] == "deepseek-chat"][0]
        reasoner_stats = [s for s in stats if s["model"] == "deepseek-reasoner"][0]
        assert chat_stats["calls"] == 2
        assert reasoner_stats["calls"] == 1
        assert abs(chat_stats["cost"] - 0.0005) < 0.00001

    def test_get_daily_stats(self, db):
        """日统计应按日期聚合"""
        db.record_call(
            mode="proxy", provider="deepseek", model="deepseek-chat",
            input_tokens=100, output_tokens=50, cost=0.0002,
            latency_ms=100, status_code=200, endpoint="/chat/completions",
        )

        daily = db.get_daily_stats(days=7)
        assert len(daily) >= 1
        assert daily[0]["calls"] >= 1
        assert abs(daily[0]["cost"] - 0.0002) < 0.00001

    def test_get_today_cost(self, db):
        """今日费用计算"""
        db.record_call(
            mode="proxy", provider="deepseek", model="deepseek-chat",
            input_tokens=1000, output_tokens=500, cost=0.002,
            latency_ms=100, status_code=200, endpoint="/chat/completions",
        )

        today_cost = db.get_today_cost()
        assert abs(today_cost - 0.002) < 0.0001

    def test_get_month_cost(self, db):
        """本月费用计算"""
        db.record_call(
            mode="proxy", provider="deepseek", model="deepseek-chat",
            input_tokens=1000, output_tokens=500, cost=0.002,
            latency_ms=100, status_code=200, endpoint="/chat/completions",
        )

        month_cost = db.get_month_cost()
        assert abs(month_cost - 0.002) < 0.0001

    def test_filter_by_provider(self, db):
        """应按提供商过滤"""
        db.record_call(mode="proxy", provider="deepseek", model="deepseek-chat",
                       input_tokens=10, output_tokens=5, cost=0.001,
                       latency_ms=10, status_code=200, endpoint="/chat/completions")

        calls = db.get_calls(limit=10, provider="deepseek")
        assert len(calls) == 1

        calls = db.get_calls(limit=10, provider="nonexistent")
        assert len(calls) == 0

    def test_filter_by_model(self, db):
        """应按模型过滤"""
        db.record_call(mode="proxy", provider="deepseek", model="deepseek-chat",
                       input_tokens=10, output_tokens=5, cost=0.001,
                       latency_ms=10, status_code=200, endpoint="/chat/completions")

        calls = db.get_calls(limit=10, model="deepseek-chat")
        assert len(calls) == 1

    def test_filter_by_mode(self, db):
        """应按模式过滤"""
        db.record_call(mode="proxy", provider="deepseek", model="deepseek-chat",
                       input_tokens=10, output_tokens=5, cost=0.001,
                       latency_ms=10, status_code=200, endpoint="/chat/completions")
        db.record_call(mode="sniffer", provider="deepseek", model="deepseek-chat",
                       input_tokens=10, output_tokens=5, cost=0.001,
                       latency_ms=10, status_code=200, endpoint="/chat/completions")

        proxy_calls = db.get_calls(limit=10, mode="proxy")
        assert len(proxy_calls) == 1

        sniffer_calls = db.get_calls(limit=10, mode="sniffer")
        assert len(sniffer_calls) == 1

    def test_export_json(self, db):
        """JSON 导出应包含数据"""
        db.record_call(mode="proxy", provider="deepseek", model="deepseek-chat",
                       input_tokens=100, output_tokens=50, cost=0.0002,
                       latency_ms=100, status_code=200, endpoint="/chat/completions")

        tmp = tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False)
        tmp.close()
        try:
            count = db.export_json(tmp.name, days=7)
            assert count == 1

            with open(tmp.name, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["provider"] == "deepseek"
        finally:
            os.unlink(tmp.name)

    def test_thread_safety(self, db):
        """并发写入应安全"""
        import threading

        errors = []

        def writer(idx):
            try:
                for _ in range(10):
                    db.record_call(
                        mode="proxy", provider="deepseek", model=f"model-{idx}",
                        input_tokens=idx * 10, output_tokens=idx * 5,
                        cost=0.001 * idx, latency_ms=float(idx),
                        status_code=200, endpoint="/chat/completions",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"线程安全问题: {errors}"
        stats = db.get_stats()
        assert stats["total_calls"] == 50
