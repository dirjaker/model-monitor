"""
事件总线模块

提供发布/订阅机制，支持实时数据推送。
- ProxyServer 和 Sniffer 在记录调用后发布事件
- WebSocket/SSE 端点可订阅实时事件流
- 线程安全，支持多生产者和消费者
"""

import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, asdict, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ApiCallEvent:
    """API 调用事件"""

    event_type: str = "api_call"
    mode: str = ""
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    latency_ms: float = 0.0
    status_code: int = 200
    endpoint: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class StatsEvent:
    """统计刷新事件（定时推送全量统计摘要）"""

    event_type: str = "stats_update"
    total_calls: int = 0
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    today_cost: float = 0.0
    month_cost: float = 0.0
    avg_latency_ms: float = 0.0
    models: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["models"] = [dict(m) if hasattr(m, "items") else m for m in self.models]
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class EventBus:
    """线程安全的事件总线（单例）"""

    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        # asyncio 订阅者队列（用于 WebSocket）
        self._async_subscribers: set[asyncio.Queue] = set()
        self._async_lock = asyncio.Lock()

        # 同步回调订阅者
        self._sync_callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._sync_lock = threading.Lock()

        logger.debug("EventBus 已初始化")

    # ── 同步发布（供 proxy/sniffer 使用）──

    def publish(self, event: dict[str, Any]) -> None:
        """发布事件到所有订阅者"""
        # 推送给同步回调
        with self._sync_lock:
            for cb in self._sync_callbacks:
                try:
                    cb(event)
                except Exception as e:
                    logger.warning("同步回调执行失败: %s", e)

        # 推送给 asyncio 队列（通过 run_coroutine_threadsafe）
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(self._publish_async(event), loop)
        except RuntimeError:
            # 没有 running loop，跳过
            pass

    def subscribe_sync(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """添加同步回调订阅者"""
        with self._sync_lock:
            self._sync_callbacks.append(callback)

    def unsubscribe_sync(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """移除同步回调订阅者"""
        with self._sync_lock:
            self._sync_callbacks.remove(callback)

    # ── 异步订阅（供 WebSocket 使用）──

    async def subscribe_async(self) -> asyncio.Queue:
        """创建一个异步订阅队列"""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._async_lock:
            self._async_subscribers.add(queue)
        logger.debug("异步订阅者已添加，当前 %d 个", len(self._async_subscribers))
        return queue

    async def unsubscribe_async(self, queue: asyncio.Queue) -> None:
        """移除异步订阅队列"""
        async with self._async_lock:
            self._async_subscribers.discard(queue)
        logger.debug("异步订阅者已移除，当前 %d 个", len(self._async_subscribers))

    async def _publish_async(self, event: dict[str, Any]) -> None:
        """异步推送事件到所有队列"""
        async with self._async_lock:
            stale: list[asyncio.Queue] = []
            for queue in self._async_subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    # 队列满了，丢弃旧项
                    try:
                        queue.get_nowait()
                        queue.put_nowait(event)
                    except asyncio.QueueEmpty:
                        pass
                    except Exception:
                        stale.append(queue)
                except Exception:
                    stale.append(queue)

            for q in stale:
                self._async_subscribers.discard(q)


# 全局单例
event_bus = EventBus()
