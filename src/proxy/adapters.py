"""
模型提供商适配器 — DeepSeek 专用版

解析 DeepSeek API 响应格式，计算费用。
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# DeepSeek 模型定价（每百万 token 美元）
DEEPSEEK_PRICING: dict[str, dict[str, float]] = {
    "deepseek-chat": {"input": 1.0, "output": 2.0},
    "deepseek-reasoner": {"input": 4.0, "output": 16.0},
    "deepseek-v4-flash": {"input": 1.0, "output": 2.0},
    "deepseek-v4-pro": {"input": 2.0, "output": 8.0},
}


class DeepSeekAdapter:
    """DeepSeek API 适配器"""

    def __init__(self, config: dict[str, Any]):
        self.provider_name = "deepseek"
        self.config = config
        self.pricing: dict[str, dict[str, float]] = {
            **DEEPSEEK_PRICING,
            **config.get("pricing", {}),
        }

    def parse_usage(self, response_body: bytes) -> dict[str, int]:
        """从非流式响应中解析 token 使用量"""
        try:
            data = json.loads(response_body)
            usage = data.get("usage", {})
            return {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            }
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("DeepSeek 响应解析失败: %s", e)
            return {"input_tokens": 0, "output_tokens": 0}

    def parse_streaming_usage(self, full_response: str) -> dict[str, int]:
        """从流式响应中解析 token 使用量"""
        usage = {"input_tokens": 0, "output_tokens": 0}
        lines = full_response.strip().split("\n")
        for line in reversed(lines):
            line = line.strip()
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    continue
                try:
                    data = json.loads(data_str)
                    if "usage" in data:
                        u = data["usage"]
                        usage["input_tokens"] = u.get("prompt_tokens", 0)
                        usage["output_tokens"] = u.get("completion_tokens", 0)
                        return usage
                except (json.JSONDecodeError, KeyError):
                    continue
        return usage

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """计算调用费用"""

        def _find_pricing(m: str) -> dict[str, float]:
            if m in self.pricing:
                return self.pricing[m]
            # 尝试前缀匹配（如 deepseek-chat → deepseek-chat 系）
            for key, value in self.pricing.items():
                if m.startswith(key) or key.startswith(m):
                    return value
            return {}

        model_pricing = _find_pricing(model)
        if not model_pricing:
            # 默认价格
            model_pricing = {"input": 1.0, "output": 2.0}

        input_rate = model_pricing.get("input", 1.0) / 1_000_000
        output_rate = model_pricing.get("output", 2.0) / 1_000_000
        return input_tokens * input_rate + output_tokens * output_rate


def get_adapter(provider_name: str, config: dict[str, Any]) -> DeepSeekAdapter:
    """根据提供商名称获取适配器（仅支持 DeepSeek）"""
    return DeepSeekAdapter(config)
