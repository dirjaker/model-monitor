"""
REST API 路由
提供统计数据、调用记录等接口。
"""

from typing import Any, Optional

from fastapi import APIRouter, Query

from src.config import Config
from src.database import Database


def create_api_router(config: Config, db: Database) -> APIRouter:
    """创建 API 路由"""
    router = APIRouter(tags=["api"])

    @router.get("/stats")
    async def get_stats() -> dict[str, Any]:
        """获取总体统计"""
        stats = db.get_stats()
        today_cost = db.get_today_cost()
        month_cost = db.get_month_cost()
        stats["today_cost"] = today_cost
        stats["month_cost"] = month_cost
        return {"status": "ok", "data": stats}

    @router.get("/calls")
    async def get_calls(
        limit: int = Query(100, ge=1, le=10000),
        offset: int = Query(0, ge=0),
        provider: Optional[str] = None,
        model: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> dict[str, Any]:
        """获取调用记录"""
        calls = db.get_calls(limit=limit, offset=offset, provider=provider, model=model, mode=mode)
        return {"status": "ok", "data": calls, "count": len(calls)}

    @router.get("/models")
    async def get_models() -> dict[str, Any]:
        """获取模型统计"""
        models = db.get_model_stats()
        return {"status": "ok", "data": models}

    @router.get("/daily")
    async def get_daily(days: int = Query(30, ge=1, le=365)) -> dict[str, Any]:
        """获取每日统计"""
        daily = db.get_daily_stats(days=days)
        return {"status": "ok", "data": daily}

    @router.get("/hourly")
    async def get_hourly(hours: int = Query(24, ge=1, le=168)) -> dict[str, Any]:
        """获取每小时统计"""
        hourly = db.get_hourly_stats(hours=hours)
        return {"status": "ok", "data": hourly}

    @router.get("/health")
    async def health() -> dict[str, str]:
        """健康检查"""
        return {"status": "ok"}

    return router
