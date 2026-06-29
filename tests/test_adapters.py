"""
测试 DeepSeek 适配器

测试请求响应解析、费用计算。
"""

import json

import pytest

from src.proxy.adapters import DeepSeekAdapter, DEEPSEEK_PRICING


SAMPLE_RESPONSE = json.dumps({
    "id": "chatcmpl-123",
    "choices": [{
        "message": {"role": "assistant", "content": "Hello!"},
        "finish_reason": "stop",
    }],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
    },
}).encode("utf-8")

SAMPLE_STREAMING_RESPONSE = (
    'data: {"choices":[{"delta":{"content":"Hel"}}],"usage":null}\n'
    'data: {"choices":[{"delta":{"content":"lo!"}}],"usage":null}\n'
    'data: {"choices":[{"delta":{}}],"usage":{"prompt_tokens":100,"completion_tokens":50}}\n'
    'data: [DONE]\n'
)


@pytest.fixture
def adapter():
    """创建 DeepSeek 适配器"""
    config = {
        "api_key": "sk-test",
        "pricing": {},
    }
    return DeepSeekAdapter(config)


class TestDeepSeekAdapter:
    """DeepSeek 适配器测试"""

    def test_parse_usage(self, adapter):
        """应正确解析非流式响应"""
        usage = adapter.parse_usage(SAMPLE_RESPONSE)
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50

    def test_parse_usage_empty_body(self, adapter):
        """空响应应返回零"""
        usage = adapter.parse_usage(b"")
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 0

    def test_parse_usage_invalid_json(self, adapter):
        """无效 JSON 应返回零"""
        usage = adapter.parse_usage(b"not json")
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 0

    def test_parse_usage_no_usage_field(self, adapter):
        """无 usage 字段应返回零"""
        data = json.dumps({"id": "123", "choices": []}).encode("utf-8")
        usage = adapter.parse_usage(data)
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 0

    def test_parse_streaming_usage(self, adapter):
        """应正确解析流式响应中的使用量"""
        usage = adapter.parse_streaming_usage(SAMPLE_STREAMING_RESPONSE)
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50

    def test_parse_streaming_empty(self, adapter):
        """空流式响应应返回零"""
        usage = adapter.parse_streaming_usage("")
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 0

    def test_calculate_cost_deepseek_chat(self, adapter):
        """deepseek-chat 模型费用"""
        cost = adapter.calculate_cost("deepseek-chat", 1000, 500)
        assert cost > 0
        # deepseek-chat: input=$1/M, output=$2/M
        expected = (1000 / 1_000_000 * 1.0) + (500 / 1_000_000 * 2.0)
        assert abs(cost - expected) < 0.0001

    def test_calculate_cost_deepseek_reasoner(self, adapter):
        """deepseek-reasoner 模型费用"""
        cost = adapter.calculate_cost("deepseek-reasoner", 1000, 500)
        expected = (1000 / 1_000_000 * 4.0) + (500 / 1_000_000 * 16.0)
        assert abs(cost - expected) < 0.0001

    def test_calculate_cost_zero_tokens(self, adapter):
        """零 Token 应返回零费用"""
        cost = adapter.calculate_cost("deepseek-chat", 0, 0)
        assert cost == 0.0

    def test_calculate_cost_unknown_model(self, adapter):
        """未知模型应使用默认价格"""
        cost = adapter.calculate_cost("unknown-model", 1_000_000, 500_000)
        # 默认 input=$1, output=$2 / M
        expected = 1.0 + 1.0  # $1 for input + $1 for output
        assert abs(cost - expected) < 0.01

    def test_calculate_cost_known_model_v4(self, adapter):
        """deepseek-v4 模型系列"""
        cost = adapter.calculate_cost("deepseek-v4-flash", 1_000_000, 1_000_000)
        expected = 1.0 + 2.0  # flash: $1/M in, $2/M out
        assert abs(cost - expected) < 0.01

    def test_default_pricing(self, adapter):
        """默认定价应包含常用模型"""
        assert "deepseek-chat" in adapter.pricing
        assert "deepseek-reasoner" in adapter.pricing
        assert "deepseek-v4-flash" in adapter.pricing
        assert "deepseek-v4-pro" in adapter.pricing

    def test_pricing_from_config(self):
        """配置文件中的定价应覆盖默认"""
        config = {
            "api_key": "sk-test",
            "pricing": {
                "deepseek-chat": {"input": 2.0, "output": 4.0},
            },
        }
        a = DeepSeekAdapter(config)
        cost = a.calculate_cost("deepseek-chat", 1_000_000, 1_000_000)
        expected = 2.0 + 4.0
        assert abs(cost - expected) < 0.01

    def test_provider_name(self, adapter):
        """提供商名称应为 deepseek"""
        assert adapter.provider_name == "deepseek"


