"""REST API + WebSocket/SSE 实时推送"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.config import Config
from src.database import Database
from src.events import event_bus, StatsEvent

logger = logging.getLogger(__name__)


def create_api_router(config: Config, db: Database) -> APIRouter:
    """创建 API 路由"""
    router = APIRouter(tags=["api"])

    # ── REST 端点 ──

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

    # ── 实时推送端点 ──

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket 实时事件流

        建立连接后持续推送 JSON 事件。
        客户端可发送 'ping' 保活，回复 'pong'。
        """
        await websocket.accept()
        queue = await event_bus.subscribe_async()
        logger.info("WebSocket 客户端已连接")

        try:
            # 发送初始连接确认
            await websocket.send_json({"event_type": "connected", "message": "Model Monitor 实时推送已连接"})

            while True:
                # 同时监听 websocket 消息和事件队列
                receive_task = asyncio.create_task(websocket.receive_text())
                event_task = asyncio.create_task(queue.get())

                done, pending = await asyncio.wait(
                    [receive_task, event_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # 取消未完成的任务
                for task in pending:
                    task.cancel()

                if receive_task in done:
                    msg = receive_task.result()
                    if msg == "ping":
                        await websocket.send_json({"event_type": "pong"})
                    elif msg == "stats":
                        # 请求全量统计刷新
                        stats = _build_stats_event(db)
                        await websocket.send_json(stats.to_dict())

                if event_task in done:
                    try:
                        event = event_task.result()
                        await websocket.send_json(event)
                    except Exception as e:
                        logger.warning("WebSocket 发送事件失败: %s", e)

        except WebSocketDisconnect:
            logger.info("WebSocket 客户端已断开")
        except Exception as e:
            logger.error("WebSocket 错误: %s", e)
        finally:
            await event_bus.unsubscribe_async(queue)

    @router.get("/events")
    async def sse_events():
        """Server-Sent Events 事件流（兼容 WebSocket 不可用时）

        使用 SSE 协议推送实时事件。
        """
        from fastapi.responses import StreamingResponse

        queue = await event_bus.subscribe_async()

        async def event_generator():
            try:
                # 初始连接消息
                yield "event: connected\ndata: {\"event_type\": \"connected\", \"message\": \"连接成功\"}\n\n"

                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30)
                        data = json.dumps(event, ensure_ascii=False)
                        yield f"event: {event.get('event_type', 'message')}\ndata: {data}\n\n"
                    except asyncio.TimeoutError:
                        # 发送心跳保活
                        yield ": heartbeat\n\n"

            except asyncio.CancelledError:
                pass
            finally:
                await event_bus.unsubscribe_async(queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    return router


def _build_stats_event(db: Database) -> StatsEvent:
    """从数据库构建全量统计事件"""
    stats = db.get_stats()
    models = db.get_model_stats()
    today = db.get_today_cost()
    month_cost = db.get_month_cost()

    return StatsEvent(
        total_calls=stats.get("total_calls", 0),
        total_cost=stats.get("total_cost", 0),
        total_input_tokens=stats.get("total_input_tokens", 0),
        total_output_tokens=stats.get("total_output_tokens", 0),
        today_cost=today,
        month_cost=month_cost,
        avg_latency_ms=stats.get("avg_latency_ms", 0),
        models=models,
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
