"""
统一 SQLite 数据库模块
管理 API 调用记录和统计摘要，支持并发访问。
"""

import sqlite3
import threading
import logging
import json
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS api_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    mode TEXT NOT NULL DEFAULT 'proxy',
    provider TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0.0,
    latency_ms REAL NOT NULL DEFAULT 0.0,
    status_code INTEGER NOT NULL DEFAULT 200,
    endpoint TEXT NOT NULL DEFAULT '',
    request_body TEXT DEFAULT '',
    response_body TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_api_calls_timestamp ON api_calls(timestamp);
CREATE INDEX IF NOT EXISTS idx_api_calls_provider ON api_calls(provider);
CREATE INDEX IF NOT EXISTS idx_api_calls_model ON api_calls(model);
CREATE INDEX IF NOT EXISTS idx_api_calls_mode ON api_calls(mode);

CREATE TABLE IF NOT EXISTS daily_summary (
    date TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    total_calls INTEGER NOT NULL DEFAULT 0,
    total_input_tokens INTEGER NOT NULL DEFAULT 0,
    total_output_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost REAL NOT NULL DEFAULT 0.0,
    avg_latency_ms REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (date, provider, model)
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""


class Database:
    """线程安全的 SQLite 数据库管理器"""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        # 确保目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # 初始化数据库
        with self._get_conn() as conn:
            self._init_schema(conn)
        logger.info("数据库已初始化: %s", db_path)

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def _cursor(self):
        """上下文管理器，自动提交或回滚"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        """初始化数据库 schema"""
        conn.executescript(SCHEMA_SQL)
        # 检查并记录版本
        try:
            row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
            if row is None:
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            elif row["version"] < SCHEMA_VERSION:
                conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
        except sqlite3.OperationalError:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        conn.commit()

    def record_call(
        self,
        mode: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        latency_ms: float,
        status_code: int = 200,
        endpoint: str = "",
        request_body: str = "",
        response_body: str = "",
    ) -> int:
        """记录一次 API 调用"""
        with self._lock:
            with self._cursor() as cursor:
                cursor.execute(
                    """INSERT INTO api_calls
                    (timestamp, mode, provider, model, input_tokens, output_tokens,
                     cost, latency_ms, status_code, endpoint, request_body, response_body)
                    VALUES (datetime('now', 'localtime'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (mode, provider, model, input_tokens, output_tokens,
                     cost, latency_ms, status_code, endpoint, request_body, response_body),
                )
                call_id = cursor.lastrowid
                logger.info(
                    "记录调用 #%d: %s/%s - 输入:%d 输出:%d 费用:%.4f 延迟:%.1fms",
                    call_id, provider, model, input_tokens, output_tokens, cost, latency_ms,
                )
                return call_id if call_id is not None else 0

    def get_calls(
        self,
        limit: int = 100,
        offset: int = 0,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        mode: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """获取 API 调用记录"""
        conditions: list[str] = []
        params: list[Any] = []
        if provider:
            conditions.append("provider = ?")
            params.append(provider)
        if model:
            conditions.append("model = ?")
            params.append(model)
        if mode:
            conditions.append("mode = ?")
            params.append(mode)
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT * FROM api_calls{where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> dict[str, Any]:
        """获取总体统计"""
        with self._cursor() as cursor:
            row = cursor.execute("""
                SELECT
                    COUNT(*) as total_calls,
                    COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                    COALESCE(SUM(cost), 0) as total_cost,
                    COALESCE(AVG(latency_ms), 0) as avg_latency_ms,
                    MIN(timestamp) as first_call,
                    MAX(timestamp) as last_call
                FROM api_calls
            """).fetchone()
            return dict(row) if row else {}

    def get_daily_stats(self, days: int = 30) -> list[dict[str, Any]]:
        """获取每日统计"""
        with self._cursor() as cursor:
            cursor.execute("""
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as calls,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(cost) as cost,
                    AVG(latency_ms) as avg_latency_ms
                FROM api_calls
                WHERE timestamp >= datetime('now', ?)
                GROUP BY DATE(timestamp)
                ORDER BY date
            """, (f"-{days} days",))
            return [dict(row) for row in cursor.fetchall()]

    def get_model_stats(self) -> list[dict[str, Any]]:
        """获取按模型统计"""
        with self._cursor() as cursor:
            cursor.execute("""
                SELECT
                    provider,
                    model,
                    COUNT(*) as calls,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(cost) as cost,
                    AVG(latency_ms) as avg_latency_ms
                FROM api_calls
                GROUP BY provider, model
                ORDER BY cost DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_hourly_stats(self, hours: int = 24) -> list[dict[str, Any]]:
        """获取每小时统计"""
        with self._cursor() as cursor:
            cursor.execute("""
                SELECT
                    strftime('%Y-%m-%d %H:00', timestamp) as hour,
                    COUNT(*) as calls,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(cost) as cost
                FROM api_calls
                WHERE timestamp >= datetime('now', ?)
                GROUP BY hour
                ORDER BY hour
            """, (f"-{hours} hours",))
            return [dict(row) for row in cursor.fetchall()]

    def get_today_cost(self) -> float:
        """获取今日总费用"""
        with self._cursor() as cursor:
            row = cursor.execute("""
                SELECT COALESCE(SUM(cost), 0) as cost
                FROM api_calls
                WHERE DATE(timestamp) = DATE('now')
            """).fetchone()
            return float(row["cost"]) if row else 0.0

    def get_month_cost(self) -> float:
        """获取本月总费用"""
        with self._cursor() as cursor:
            row = cursor.execute("""
                SELECT COALESCE(SUM(cost), 0) as cost
                FROM api_calls
                WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')
            """).fetchone()
            return float(row["cost"]) if row else 0.0

    def export_json(self, output_path: str, days: int = 30) -> int:
        """导出数据为 JSON"""
        calls = self.get_calls(limit=100000, start_date=f"-{days} days")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(calls, f, ensure_ascii=False, indent=2, default=str)
        logger.info("已导出 %d 条记录到 %s", len(calls), output_path)
        return len(calls)

    def close(self) -> None:
        """关闭当前线程的数据库连接"""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None
