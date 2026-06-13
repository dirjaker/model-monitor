"""
成本优化建议模块
分析使用模式，提供降低成本的建议。
"""

import logging
from typing import Any

from src.database import Database

logger = logging.getLogger(__name__)


class CostOptimizer:
    """成本优化分析器"""

    def __init__(self, db: Database):
        self._db = db

    def analyze(self) -> list[dict[str, Any]]:
        """生成优化建议"""
        suggestions: list[dict[str, Any]] = []

        # 获取模型统计
        model_stats = self._db.get_model_stats()
        if not model_stats:
            return [{"type": "info", "title": "无数据", "description": "暂无 API 调用数据，无法生成优化建议。"}]

        # 分析高频低效模型
        for stat in model_stats:
            model = stat["model"]
            calls = stat["calls"]
            avg_latency = stat.get("avg_latency_ms", 0)
            total_cost = stat.get("cost", 0)

            # 建议1: 高延迟模型
            if avg_latency > 5000 and calls > 10:
                suggestions.append({
                    "type": "warning",
                    "title": f"高延迟模型: {model}",
                    "description": f"平均延迟 {avg_latency:.0f}ms，共 {calls} 次调用。建议检查是否可以使用更快的模型或减少输入长度。",
                    "potential_saving": "减少等待时间",
                })

            # 建议2: 高费用模型
            if total_cost > 1.0:
                # 检查输入/输出 token 比例
                input_tokens = stat.get("input_tokens", 0)
                output_tokens = stat.get("output_tokens", 0)
                if input_tokens > 0 and output_tokens / input_tokens > 3:
                    suggestions.append({
                        "type": "tip",
                        "title": f"输出 token 占比高: {model}",
                        "description": f"输出 token 是输入的 {output_tokens/input_tokens:.1f} 倍。建议使用 max_tokens 参数限制输出长度。",
                        "potential_saving": f"预计可节省 ${total_cost * 0.2:.2f}",
                    })

        # 分析每日使用趋势
        daily = self._db.get_daily_stats(days=7)
        if len(daily) >= 3:
            recent_costs = [d.get("cost", 0) for d in daily[-3:]]
            avg_recent = sum(recent_costs) / len(recent_costs)
            if avg_recent > 5.0:
                suggestions.append({
                    "type": "warning",
                    "title": "近期费用较高",
                    "description": f"近3天日均费用 ${avg_recent:.2f}。建议检查是否有异常调用或可以缓存的请求。",
                    "potential_saving": f"日均 ${avg_recent:.2f}",
                })

        if not suggestions:
            suggestions.append({
                "type": "success",
                "title": "使用模式健康",
                "description": "当前使用模式未发现明显优化空间。",
            })

        return suggestions
