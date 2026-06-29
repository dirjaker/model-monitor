"""
HTTP 代理服务器
使用 httpx 异步客户端转发请求到上游 API，同时记录调用数据。
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

from src.config import Config
from src.database import Database
from src.events import event_bus, ApiCallEvent
from src.proxy.adapters import DeepSeekAdapter

logger = logging.getLogger(__name__)


class ProxyServer:
    """异步 HTTP 代理服务器"""

    def __init__(self, config: Config, db: Database):
        self._config = config
        self._db = db
        self._client: Optional[httpx.AsyncClient] = None
        self._app = self._build_app()

    def _build_app(self) -> FastAPI:
        """构建 FastAPI 应用"""
        app = FastAPI(title="Model Monitor Proxy", docs_url=None, redoc_url=None)

        @app.on_event("startup")
        async def startup() -> None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._config.proxy_timeout, connect=30),
                follow_redirects=True,
                http2=False,
            )
            logger.info("代理客户端已初始化")

        @app.on_event("shutdown")
        async def shutdown() -> None:
            if self._client:
                await self._client.aclose()
                logger.info("代理客户端已关闭")

        @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
        async def proxy_handler(request: Request, path: str) -> Response:
            return await self._handle_request(request, path)

        return app

    def _resolve_upstream(self, request: Request) -> tuple[str, DeepSeekAdapter]:
        """解析上游地址和适配器（仅支持 DeepSeek）"""
        base_url = str(self._config.get("proxy.target", "https://api.deepseek.com"))
        adapter = DeepSeekAdapter({})
        return base_url, adapter

    async def _handle_request(self, request: Request, path: str) -> Response:
        """处理代理请求"""
        start_time = time.monotonic()
        upstream_base, adapter = self._resolve_upstream(request)

        # 构建上游 URL
        upstream_url = f"{upstream_base}/{path}"
        if request.url.query:
            upstream_url += f"?{request.url.query}"

        # 构建请求头
        headers = dict(request.headers)
        headers.pop("host", None)

        # 读取请求体
        body = await request.body()
        request_body_str = ""
        if body:
            request_body_str = body.decode("utf-8", errors="replace")

        is_streaming = False
        parsed_body: dict[str, Any] = {}
        if body:
            try:
                parsed_body = json.loads(body)
                is_streaming = parsed_body.get("stream", False)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        logger.debug("代理请求: %s %s -> %s", request.method, path, upstream_url)

        try:
            if is_streaming:
                return await self._handle_streaming(
                    request, upstream_url, headers, body, adapter, parsed_body, start_time
                )
            else:
                return await self._handle_normal(
                    request, upstream_url, headers, body, adapter, parsed_body, start_time, request_body_str
                )
        except httpx.ConnectError as e:
            logger.error("连接上游失败: %s", e)
            return JSONResponse({"error": "upstream_connection_failed", "detail": str(e)}, status_code=502)
        except httpx.TimeoutException as e:
            logger.error("上游超时: %s", e)
            return JSONResponse({"error": "upstream_timeout", "detail": str(e)}, status_code=504)
        except Exception as e:
            logger.error("代理错误: %s", e, exc_info=True)
            return JSONResponse({"error": "proxy_error", "detail": str(e)}, status_code=500)

    async def _handle_normal(
        self,
        request: Request,
        url: str,
        headers: dict[str, str],
        body: bytes,
        adapter: DeepSeekAdapter,
        parsed_body: dict[str, Any],
        start_time: float,
        request_body_str: str = "",
    ) -> Response:
        """处理普通 (非流式) 请求"""
        assert self._client is not None
        resp = await self._client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
        )
        latency_ms = (time.monotonic() - start_time) * 1000
        response_body = resp.content

        # 解析使用量
        usage = adapter.parse_usage(response_body)
        model = parsed_body.get("model", "unknown")

        # 计算费用
        input_tok = usage.get("input_tokens", 0)
        output_tok = usage.get("output_tokens", 0)
        call_cost = adapter.calculate_cost(model, input_tok, output_tok)

        # 仅记录成功的聊天补全请求，过滤掉探测/健康检查/失败等无关请求
        is_chat = "/chat/completions" in str(request.url.path)
        if is_chat and resp.status_code < 400:
            # 记录到数据库
            self._db.record_call(
                mode="proxy",
                provider=adapter.provider_name,
                model=model,
                input_tokens=input_tok,
                output_tokens=output_tok,
                cost=call_cost,
                latency_ms=latency_ms,
                status_code=resp.status_code,
                endpoint=str(request.url.path),
                request_body=request_body_str[:2000],
                response_body=response_body.decode("utf-8", errors="replace")[:2000],
            )

            # 发布实时事件
            event_bus.publish(ApiCallEvent(
                mode="proxy",
                provider=adapter.provider_name,
                model=model,
                input_tokens=input_tok,
                output_tokens=output_tok,
                cost=call_cost,
                latency_ms=latency_ms,
                status_code=resp.status_code,
                endpoint=str(request.url.path),
            ).to_dict())

        # 返回响应
        resp_headers = dict(resp.headers)
        resp_headers.pop("transfer-encoding", None)
        resp_headers.pop("content-encoding", None)
        resp_headers.pop("content-length", None)
        return Response(
            content=response_body,
            status_code=resp.status_code,
            headers=resp_headers,
        )

    async def _handle_streaming(
        self,
        request: Request,
        url: str,
        headers: dict[str, str],
        body: bytes,
        adapter: DeepSeekAdapter,
        parsed_body: dict[str, Any],
        start_time: float,
    ) -> Response:
        """处理流式请求"""
        assert self._client is not None

        collected_chunks: list[bytes] = []
        collected_content = ""

        async def stream_generator():
            nonlocal collected_content
            async with self._client.stream(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    collected_chunks.append(chunk)
                    yield chunk

            # 流结束后记录
            latency_ms = (time.monotonic() - start_time) * 1000
            full_response = b"".join(collected_chunks).decode("utf-8", errors="replace")
            usage = adapter.parse_streaming_usage(full_response)
            model = parsed_body.get("model", "unknown")

            input_tok = usage.get("input_tokens", 0)
            output_tok = usage.get("output_tokens", 0)
            call_cost = adapter.calculate_cost(model, input_tok, output_tok)

            # 仅记录聊天补全请求
            is_chat = "/chat/completions" in str(request.url.path)
            if is_chat:
                self._db.record_call(
                    mode="proxy",
                    provider=adapter.provider_name,
                    model=model,
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                    cost=call_cost,
                    latency_ms=latency_ms,
                    status_code=200,
                    endpoint=str(request.url.path),
                )

                # 发布实时事件
                event_bus.publish(ApiCallEvent(
                    mode="proxy",
                    provider=adapter.provider_name,
                    model=model,
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                    cost=call_cost,
                    latency_ms=latency_ms,
                    status_code=200,
                    endpoint=str(request.url.path),
                ).to_dict())

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def run(self) -> None:
        """启动代理服务器"""
        uvicorn.run(
            self._app,
            host=self._config.proxy_host,
            port=self._config.proxy_port,
            log_level="info",
        )
