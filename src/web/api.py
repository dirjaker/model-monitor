"""REST API + WebSocket/SSE 实时推送 + 采集进程管理"""

import asyncio
import json
import logging
import os
import signal
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.config import Config
from src.database import Database
from src.events import event_bus, StatsEvent

logger = logging.getLogger(__name__)

# ── 采集进程管理 ──
_collector_proc: Optional[asyncio.subprocess.Process] = None
_collector_mode: str = ""
ROOT_DIR = Path(__file__).resolve().parent.parent.parent


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

    # ── 采集进程管理 ──

    @router.post("/mode/start")
    async def start_mode(mode: str = "proxy", port: int = 12345, host: str = "127.0.0.1") -> dict[str, Any]:
        """启动采集进程（proxy 或 sniffer）"""
        global _collector_proc, _collector_mode

        if _collector_proc and _collector_proc.returncode is None:
            return {"status": "error", "message": f"采集进程已在运行 (mode={_collector_mode}, pid={_collector_proc.pid})"}

        cmd: list[str] = ["python", "main.py", mode]
        if mode == "proxy":
            cmd.extend(["-p", str(port), "--host", host])
        elif mode == "sniffer":
            cmd.extend(["-p", str(port)])

        logger.info("启动采集进程: %s", " ".join(cmd))

        _collector_proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(ROOT_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _collector_mode = mode

        # 启动后台任务读取输出
        asyncio.create_task(_read_output(_collector_proc))

        return {"status": "started", "mode": mode, "host": host, "port": port, "pid": _collector_proc.pid}

    @router.post("/mode/stop")
    async def stop_mode() -> dict[str, Any]:
        """停止采集进程"""
        global _collector_proc, _collector_mode

        if not _collector_proc or _collector_proc.returncode is not None:
            return {"status": "stopped", "message": "没有运行中的采集进程"}

        pid = _collector_proc.pid
        logger.info("停止采集进程 pid=%d", pid)

        try:
            _collector_proc.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(_collector_proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                _collector_proc.kill()
                await _collector_proc.wait()
        except ProcessLookupError:
            pass

        _collector_mode = ""
        return {"status": "stopped", "pid": pid}

    @router.get("/mode/status")
    async def get_mode_status() -> dict[str, Any]:
        """获取采集进程状态"""
        global _collector_proc, _collector_mode

        if _collector_proc and _collector_proc.returncode is None:
            return {
                "status": "running",
                "mode": _collector_mode,
                "pid": _collector_proc.pid,
            }

        if _collector_proc and _collector_proc.returncode is not None:
            # 进程已退出
            _collector_mode = ""

        return {"status": "stopped", "mode": "", "pid": 0}

    # ── 配置持久化 ──

    @router.post("/settings")
    async def save_settings(body: dict[str, Any]) -> dict[str, Any]:
        """保存配置到 config.yaml"""
        try:
            # 代理配置
            if "proxy_host" in body:
                config.set("proxy.host", body["proxy_host"])
            if "proxy_port" in body:
                config.set("proxy.port", int(body["proxy_port"]))
            if "proxy_timeout" in body:
                config.set("proxy.timeout", int(body["proxy_timeout"]))
            if "proxy_target" in body:
                config.set("proxy.target", body["proxy_target"])
            if "proxy_key" in body:
                config.set("providers.deepseek.api_key", body["proxy_key"])

            # 嗅探配置
            if "sniff_port" in body:
                config.set("sniffer.port", int(body["sniff_port"]))
            if "sniff_target" in body:
                config.set("sniffer.targets", [t.strip() for t in body["sniff_target"].split(",")])
            if "sniff_key" in body:
                config.set("providers.deepseek.api_key", body["sniff_key"])

            config.save()
            logger.info("配置已持久化到 %s", config._path)
            return {"status": "ok", "message": "配置已保存"}
        except Exception as e:
            logger.error("保存配置失败: %s", e)
            return {"status": "error", "message": str(e)}

    # ── 实时推送端点 ──

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket 实时事件流"""
        await websocket.accept()
        queue = await event_bus.subscribe_async()
        logger.info("WebSocket 客户端已连接")

        try:
            await websocket.send_json({"event_type": "connected", "message": "Model Monitor 实时推送已连接"})

            while True:
                receive_task = asyncio.create_task(websocket.receive_text())
                event_task = asyncio.create_task(queue.get())

                done, pending = await asyncio.wait(
                    [receive_task, event_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    task.cancel()

                if receive_task in done:
                    msg = receive_task.result()
                    if msg == "ping":
                        await websocket.send_json({"event_type": "pong"})
                    elif msg == "stats":
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
        """Server-Sent Events 事件流"""
        from fastapi.responses import StreamingResponse

        queue = await event_bus.subscribe_async()

        async def event_generator():
            try:
                yield "event: connected\ndata: {\"event_type\": \"connected\", \"message\": \"连接成功\"}\n\n"

                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30)
                        data = json.dumps(event, ensure_ascii=False)
                        yield f"event: {event.get('event_type', 'message')}\ndata: {data}\n\n"
                    except asyncio.TimeoutError:
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


async def _read_output(proc: asyncio.subprocess.Process) -> None:
    """后台读取子进程输出并记录日志"""
    try:
        stdout_task = asyncio.create_task(_read_stream(proc.stdout, "stdout"))
        stderr_task = asyncio.create_task(_read_stream(proc.stderr, "stderr"))
        await asyncio.wait([stdout_task, stderr_task])
    except Exception as e:
        logger.warning("采集进程输出读取结束: %s", e)


async def _read_stream(stream: Optional[asyncio.StreamReader], label: str) -> None:
    """读取流式输出"""
    if not stream:
        return
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                logger.info("[%s] %s", label, text)
    except Exception:
        pass


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
