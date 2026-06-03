# api/middleware.py
"""
Additional Middleware for Enhanced API Functionality

Pure ASGI middlewares (not BaseHTTPMiddleware) so that SSE / streaming
responses pass through without buffering.
"""

from __future__ import annotations
import uuid
import time

from starlette.types import ASGIApp, Scope, Receive, Send, Message
from starlette.datastructures import MutableHeaders, Headers

from log_manager import get_logger

_request_logger = get_logger("api_requests")


class RequestIDMiddleware:
    """Track requests with unique IDs.

    - Accepts client-provided request ID via X-Client-Request-ID header
    - Generates new ID if not provided
    - Adds X-Request-ID to all responses
    - Stores request_id in scope["state"] for logging
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        req_headers = Headers(scope=scope)
        client_request_id = req_headers.get("X-Client-Request-ID")
        request_id = client_request_id or f"req_{uuid.uuid4().hex[:16]}"

        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                if client_request_id:
                    headers["X-Client-Request-ID"] = client_request_id
            await send(message)

        await self.app(scope, receive, send_wrapper)


class ResponseMetadataMiddleware:
    """Add metadata to responses: processing time and API version."""

    def __init__(self, app: ASGIApp, version: str = "1.0.0") -> None:
        self.app = app
        self.version = version

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        version = self.version

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                process_time_ms = (time.time() - start_time) * 1000
                headers = MutableHeaders(scope=message)
                headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
                headers["X-API-Version"] = version
            await send(message)

        await self.app(scope, receive, send_wrapper)


class ProviderHeadersMiddleware:
    """Add LLM provider information to non-streaming responses.

    Streaming endpoints (/stream paths) are skipped because request.state
    LLM fields are populated inside the SSE generator — after
    http.response.start has already been sent.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_stream = "/stream" in scope.get("path", "")

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start" and not is_stream:
                state = scope.get("state") or {}
                headers = MutableHeaders(scope=message)
                if "llm_provider" in state:
                    headers["X-LLM-Provider"] = str(state["llm_provider"])
                if "llm_model" in state:
                    headers["X-LLM-Model"] = str(state["llm_model"])
                if "rag_used" in state:
                    headers["X-RAG-Used"] = str(state["rag_used"])
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RequestLogMiddleware:
    """Log every HTTP request.

    Status code is captured from http.response.start; duration is measured
    until the final http.response.body (more_body=False) so streaming
    endpoints report total stream time correctly.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        path = scope.get("path", "")
        method = scope.get("method", "")
        status: list[int] = [0]

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status[0] = message.get("status", 0)
            elif message["type"] == "http.response.body" and not message.get("more_body", False):
                duration_ms = (time.time() - start_time) * 1000
                state = scope.get("state") or {}
                request_id = state.get("request_id", "unknown")
                _request_logger.info(
                    "method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
                    method, path, status[0], duration_ms, request_id,
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)
