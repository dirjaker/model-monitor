"""
小米 MiMo 适配器
支持通过 OpenRouter 访问 MiMo 模型
"""

import json
import logging
from typing import Any

from .adapters import BaseAdapter

logger = logging.getLogger(__name__)


class MiMoAdapter(BaseAdapter):
    """小米 MiMo API 适配器

    通过 OpenRouter 访问 MiMo 模型
    """

    # MiMo 模型定价（参考价，实际价格可能变化）
    PRICING = {
        "mimo-v2.5-pro": {"input": 1.0, "output": 2.0},
        "mimo-v2.5-flash": {"input": 0.5, "output": 1.0},
    }

    def __init__(self, config: dict[str, Any]):
        super().__init__("mimo", config)
        self.base_url = config.get("base_url", "https://openrouter.ai/api/v1")

    def _map_model_name(self, model: str) -> str:
        """映射模型名称到 OpenRouter 格式"""
        return f"xiaomi/{model}"

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
            logger.warning("MiMo 响应解析失败: %s", e)
            return {"input_tokens": 0, "output_tokens": 0}

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """计算费用"""
        pricing = self.PRICING.get(model, self.pricing.get(model, {}))
        if not pricing:
            return 0.0

        input_cost = (input_tokens / 1_000_000) * pricing.get("input", 0)
        output_cost = (output_tokens / 1_000_000) * pricing.get("output", 0)
        return input_cost + output_cost
