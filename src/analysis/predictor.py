"""
费用预测模块
使用简单线性回归预测未来费用。
"""

import logging
import math
from typing import Any, Optional

from src.database import Database

logger = logging.getLogger(__name__)


class CostPredictor:
    """费用预测器"""

    def __init__(self, db: Database):
        self._db = db

    def predict_daily(self, days_ahead: int = 7) -> list[dict[str, Any]]:
        """预测未来 N 天的日费用"""
        # 获取历史数据
        history = self._db.get_daily_stats(days=30)
        if len(history) < 3:
            return [{"day": i + 1, "predicted_cost": 0.0, "confidence": "low"} for i in range(days_ahead)]

        # 提取费用序列
        costs = [float(d.get("cost", 0)) for d in history]
        n = len(costs)

        # 简单线性回归: y = a + b*x
        x_mean = (n - 1) / 2
        y_mean = sum(costs) / n

        numerator = sum((i - x_mean) * (c - y_mean) for i, c in enumerate(costs))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        b = numerator / denominator if denominator != 0 else 0
        a = y_mean - b * x_mean

        # 计算 R^2
        ss_res = sum((costs[i] - (a + b * i)) ** 2 for i in range(n))
        ss_tot = sum((c - y_mean) ** 2 for c in costs)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        # 预测
        predictions: list[dict[str, Any]] = []
        for i in range(days_ahead):
            x = n + i
            predicted = max(0, a + b * x)

            # 置信度判断
            if r_squared > 0.7:
                confidence = "high"
            elif r_squared > 0.4:
                confidence = "medium"
            else:
                confidence = "low"

            predictions.append({
                "day": i + 1,
                "predicted_cost": round(predicted, 4),
                "confidence": confidence,
                "r_squared": round(r_squared, 4),
            })

        return predictions

    def predict_monthly(self) -> dict[str, Any]:
        """预测本月总费用"""
        daily_preds = self.predict_daily(days_ahead=30)
        total = sum(p["predicted_cost"] for p in daily_preds)
        today_cost = self._db.get_today_cost()
        month_cost = self._db.get_month_cost()

        return {
            "current_month_cost": round(month_cost, 4),
            "predicted_month_total": round(month_cost + total, 4),
            "today_cost": round(today_cost, 4),
            "daily_predictions": daily_preds,
        }

    def get_cost_trend(self, days: int = 30) -> dict[str, Any]:
        """获取费用趋势分析"""
        history = self._db.get_daily_stats(days=days)
        if not history:
            return {"trend": "unknown", "change_pct": 0, "data_points": 0}

        costs = [float(d.get("cost", 0)) for d in history]

        if len(costs) < 2:
            return {"trend": "stable", "change_pct": 0, "data_points": len(costs)}

        # 比较最近一周和上一周
        mid = len(costs) // 2
        recent_avg = sum(costs[mid:]) / len(costs[mid:]) if costs[mid:] else 0
        older_avg = sum(costs[:mid]) / len(costs[:mid]) if costs[:mid] else 0

        if older_avg == 0:
            change_pct = 0
        else:
            change_pct = ((recent_avg - older_avg) / older_avg) * 100

        if change_pct > 20:
            trend = "increasing"
        elif change_pct < -20:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "change_pct": round(change_pct, 2),
            "recent_avg": round(recent_avg, 4),
            "older_avg": round(older_avg, 4),
            "data_points": len(costs),
        }
