"""
mitmproxy 嗅探插件
捕获 HTTPS 流量，解析模型 API 调用的使用量数据。
"""

import json
import logging
import time
from typing import Any

from mitmproxy import http
from mitmproxy import ctx

from src.config import Config
from src.database import Database
from src.events import event_bus, ApiCallEvent
from src.proxy.adapters import DeepSeekAdapter
from src.sniffer.cert import ensure_cert

logger = logging.getLogger(__name__)

# 目标 API 域名（仅 DeepSeek）
TARGET_PATTERNS = ["api.deepseek.com"]


class ModelMonitorAddon:
    """mitmproxy 插件，监控模型 API 调用"""

    def __init__(self, config: Config, db: Database):
        self._config = config
        self._db = db
        self._targets = set(config.sniffer_targets or TARGET_PATTERNS)
        self._pending: dict[int, dict[str, Any]] = {}

    def _is_target(self, flow: http.HTTPFlow) -> bool:
        """判断是否为目标请求"""
        host = flow.request.pretty_host
        return any(t in host for t in self._targets)

    def request(self, flow: http.HTTPFlow) -> None:
        """捕获请求"""
        if not self._is_target(flow):
            return

        self._pending[id(flow)] = {
            "start_time": time.monotonic(),
            "method": flow.request.method,
            "url": flow.request.pretty_url,
            "path": flow.request.path,
            "request_body": "",
            "model": "unknown",
            "provider": "unknown",
        }

        # 解析请求体获取模型名称
        if flow.request.content:
            try:
                body = json.loads(flow.request.content)
                self._pending[id(flow)]["model"] = body.get("model", "unknown")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # 识别提供商（仅 DeepSeek）
        self._pending[id(flow)]["provider"] = "deepseek"

        logger.debug("嗅探到请求: %s %s", flow.request.method, flow.request.pretty_url)

    def response(self, flow: http.HTTPFlow) -> None:
        """捕获响应"""
        flow_id = id(flow)
        if flow_id not in self._pending:
            return

        pending = self._pending.pop(flow_id)
        latency_ms = (time.monotonic() - pending["start_time"]) * 1000

        # 获取适配器
        provider = pending["provider"]
        providers_cfg = self._config.providers
        adapter_cfg = providers_cfg.get(provider, {})
        adapter = DeepSeekAdapter(adapter_cfg)

        # 解析使用量
        usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
        if flow.response and flow.response.content:
            usage = adapter.parse_usage(flow.response.content)

        model = pending["model"]
        cost = adapter.calculate_cost(model, usage["input_tokens"], usage["output_tokens"])

        # 仅记录成功的聊天补全请求，过滤掉探测/健康检查/失败等无关请求
        is_chat = "/chat/completions" in pending.get("path", "")
        is_success = flow.response and flow.response.status_code < 400
        if is_chat and is_success:
            # 记录到数据库
            self._db.record_call(
                mode="sniffer",
                provider=provider,
                model=model,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                cost=cost,
                latency_ms=latency_ms,
                status_code=flow.response.status_code if flow.response else 0,
                endpoint=pending["path"],
            )

            # 发布实时事件
            event_bus.publish(ApiCallEvent(
                mode="sniffer",
                provider=provider,
                model=model,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                cost=cost,
                latency_ms=latency_ms,
                status_code=flow.response.status_code if flow.response else 0,
                endpoint=pending["path"],
            ).to_dict())

        logger.info(
            "嗅探记录: %s/%s - 输入:%d 输出:%d 费用:%.4f 延迟:%.1fms",
            provider, model, usage["input_tokens"], usage["output_tokens"], cost, latency_ms,
        )


def run_sniffer(config: Config) -> None:
    """启动嗅探器"""
    from mitmproxy.options import Options
    from mitmproxy.tools.dump import DumpMaster

    db_path = config.db_path
    db = Database(db_path)
    addon = ModelMonitorAddon(config, db)

    # 确保证书已生成
    ensure_cert()

    port = config.sniffer_port
    opts = Options(listen_port=port, ssl_insecure=True)

    logger.info("嗅探器启动，端口: %d", port)
    logger.info("目标: %s", ", ".join(config.sniffer_targets))

    import asyncio

    async def start_master():
        master = DumpMaster(opts)
        master.addons.add(addon)
        await master.run()

    asyncio.run(start_master())
