"""
模型提供商适配器
解析不同提供商的 API 响应格式，计算费用。
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """适配器基类"""

    def __init__(self, provider_name: str, config: dict[str, Any]):
        self.provider_name = provider_name
        self.config = config
        self.api_key: str = config.get("api_key", "")
        self.pricing: dict[str, dict[str, float]] = config.get("pricing", {})

    @abstractmethod
    def parse_usage(self, response_body: bytes) -> dict[str, int]:
        """从非流式响应中解析 token 使用量"""
        ...

    def parse_streaming_usage(self, full_response: str) -> dict[str, int]:
        """从流式响应中解析 token 使用量"""
        # 默认从最后一个 chunk 中提取 usage
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
        """计算调用费用（每百万 token 的价格，单位美元）"""
        model_pricing = self.pricing.get(model, {})
        if not model_pricing:
            return 0.0
        input_rate = model_pricing.get("input", 0) / 1_000_000
        output_rate = model_pricing.get("output", 0) / 1_000_000
        return input_tokens * input_rate + output_tokens * output_rate


class DeepSeekAdapter(BaseAdapter):
    """DeepSeek API 适配器"""

    def __init__(self, config: dict[str, Any]):
        super().__init__("deepseek", config)

    def parse_usage(self, response_body: bytes) -> dict[str, int]:
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


class OpenRouterAdapter(BaseAdapter):
    """OpenRouter API 适配器"""

    def __init__(self, config: dict[str, Any]):
        super().__init__("openrouter", config)

    def parse_usage(self, response_body: bytes) -> dict[str, int]:
        try:
            data = json.loads(response_body)
            usage = data.get("usage", {})
            return {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            }
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("OpenRouter 响应解析失败: %s", e)
            return {"input_tokens": 0, "output_tokens": 0}


class GenericAdapter(BaseAdapter):
    """通用适配器，兼容 OpenAI 格式"""

    def __init__(self, provider_name: str, config: dict[str, Any]):
        super().__init__(provider_name, config)

    def parse_usage(self, response_body: bytes) -> dict[str, int]:
        try:
            data = json.loads(response_body)
            usage = data.get("usage", {})
            return {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            }
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("%s 响应解析失败: %s", self.provider_name, e)
            return {"input_tokens": 0, "output_tokens": 0}


def get_adapter(provider_name: str, config: dict[str, Any]) -> BaseAdapter:
    """根据提供商名称获取适配器"""
    adapters: dict[str, type[BaseAdapter]] = {
        "deepseek": DeepSeekAdapter,
        "openrouter": OpenRouterAdapter,
    }
    adapter_cls = adapters.get(provider_name, GenericAdapter)
    if adapter_cls is GenericAdapter:
        return GenericAdapter(provider_name, config)
    return adapter_cls(config)
