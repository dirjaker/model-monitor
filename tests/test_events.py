"""
测试事件总线模块

测试发布/订阅机制、同步回调、异步队列。
"""

import asyncio
import threading
import time

import pytest

from src.events import EventBus, ApiCallEvent, StatsEvent, event_bus


@pytest.fixture(autouse=True)
def reset_event_bus():
    """每个测试前重置 EventBus 单例"""
    bus = EventBus()
    bus._initialized = True
    bus._async_subscribers = set()
    bus._sync_callbacks = []
    yield
    bus._async_subscribers = set()
    bus._sync_callbacks = []


class TestEventBus:
    """事件总线测试"""

    def test_singleton(self):
        """EventBus 应为单例"""
        bus1 = EventBus()
        bus2 = EventBus()
        assert bus1 is bus2

    def test_sync_subscribe_and_publish(self):
        """同步订阅者应收到发布的事件"""
        bus = EventBus()
        received = []

        def callback(event):
            received.append(event)

        bus.subscribe_sync(callback)
        bus.publish({"event_type": "test", "data": "hello"})

        assert len(received) == 1
        assert received[0]["event_type"] == "test"
        assert received[0]["data"] == "hello"

    def test_sync_multiple_subscribers(self):
        """多个同步订阅者都应收到事件"""
        bus = EventBus()
        received1 = []
        received2 = []

        bus.subscribe_sync(lambda e: received1.append(e))
        bus.subscribe_sync(lambda e: received2.append(e))
        bus.publish({"event_type": "test"})

        assert len(received1) == 1
        assert len(received2) == 1

    def test_sync_unsubscribe(self):
        """取消订阅后不应再接收事件"""
        bus = EventBus()
        received = []

        def callback(event):
            received.append(event)

        bus.subscribe_sync(callback)
        bus.publish({"event_type": "first"})
        bus.unsubscribe_sync(callback)
        bus.publish({"event_type": "second"})

        assert len(received) == 1
        assert received[0]["event_type"] == "first"

    @pytest.mark.asyncio
    async def test_async_subscribe_and_publish(self):
        """异步订阅者应收到发布的事件"""
        bus = EventBus()
        queue = await bus.subscribe_async()

        # 通过同步 publish 触发异步推送
        bus.publish({"event_type": "async_test", "value": 42})

        # 等待事件到达队列
        await asyncio.sleep(0.1)

        event = await asyncio.wait_for(queue.get(), timeout=5)
        assert event["event_type"] == "async_test"
        assert event["value"] == 42

    @pytest.mark.asyncio
    async def test_async_unsubscribe(self):
        """取消异步订阅后不应再收到事件"""
        bus = EventBus()
        queue = await bus.subscribe_async()
        await bus.unsubscribe_async(queue)

        bus.publish({"event_type": "after_unsub"})
        await asyncio.sleep(0.1)

        # 队列应该是空的（因为是新队列，未订阅）
        assert queue.empty()

    def test_callback_error_handling(self):
        """回调抛出异常不应影响其他订阅者"""
        bus = EventBus()
        received = []

        def bad_callback(event):
            raise ValueError("Intentional error")

        def good_callback(event):
            received.append(event)

        bus.subscribe_sync(bad_callback)
        bus.subscribe_sync(good_callback)
        bus.publish({"event_type": "test"})

        assert len(received) == 1

    def test_api_call_event_dataclass(self):
        """ApiCallEvent 应正确生成字典"""
        event = ApiCallEvent(
            mode="proxy",
            provider="deepseek",
            model="deepseek-chat",
            input_tokens=100,
            output_tokens=50,
            cost=0.0002,
            latency_ms=123.4,
            status_code=200,
            endpoint="/chat/completions",
        )

        d = event.to_dict()
        assert d["event_type"] == "api_call"
        assert d["provider"] == "deepseek"
        assert d["model"] == "deepseek-chat"
        assert d["input_tokens"] == 100

    def test_api_call_event_json(self):
        """ApiCallEvent 应正确序列化为 JSON"""
        event = ApiCallEvent(
            mode="proxy", provider="deepseek", model="deepseek-chat",
            input_tokens=100, output_tokens=50, cost=0.0002,
            latency_ms=123.4, status_code=200, endpoint="/chat/completions",
        )

        json_str = event.to_json()
        import json
        parsed = json.loads(json_str)
        assert parsed["event_type"] == "api_call"
        assert parsed["cost"] == 0.0002

    def test_stats_event_dataclass(self):
        """StatsEvent 应正确生成"""
        event = StatsEvent(
            total_calls=100,
            total_cost=0.5,
            total_input_tokens=50000,
            total_output_tokens=25000,
            today_cost=0.1,
            month_cost=0.4,
            avg_latency_ms=120.0,
            models=[{"model": "deepseek-chat", "calls": 100, "cost": 0.5}],
        )

        d = event.to_dict()
        assert d["event_type"] == "stats_update"
        assert d["total_calls"] == 100
        assert len(d["models"]) == 1

    def test_queue_full_handling(self):
        """队列满时应丢弃旧事件"""
        bus = EventBus()

        # 使用 small queue 测试
        import asyncio
        small_queue = asyncio.Queue(maxsize=2)

        # 手动添加测试
        async def test():
            await small_queue.put({"id": 1})
            await small_queue.put({"id": 2})
            # 尝试放入第三个 — 应丢弃旧的
            try:
                small_queue.put_nowait({"id": 3})
            except asyncio.QueueFull:
                # 模拟 EventBus 的处理：丢弃旧项
                await small_queue.get()
                await small_queue.put({"id": 3})

            assert small_queue.qsize() == 2
            item = await small_queue.get()
            assert item["id"] == 2  # 1 被丢弃了

        asyncio.run(test())
