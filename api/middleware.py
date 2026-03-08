# api/middleware.py
"""
Additional Middleware for Enhanced API Functionality

Includes:
- Request ID tracking
- Response metadata
- Request logging
"""

from __future__ import annotations
import uuid
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from log_manager import get_logger

_request_logger = get_logger("api_requests")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Track requests with unique IDs.

    - Accepts client-provided request ID via X-Client-Request-ID header
    - Generates new ID if not provided
    - Adds X-Request-ID to all responses
    - Stores request_id in request.state for logging
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Get or generate request ID
        client_request_id = request.headers.get("X-Client-Request-ID")
        request_id = client_request_id or f"req_{uuid.uuid4().hex[:16]}"

        # Store in request state for access in routes
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        # If client provided ID, acknowledge it
        if client_request_id:
            response.headers["X-Client-Request-ID"] = client_request_id

        return response


class ResponseMetadataMiddleware(BaseHTTPMiddleware):
    """
    Add metadata to responses.

    - Processing time
    - API version
    - Server information
    """

    def __init__(self, app: ASGIApp, version: str = "1.0.0"):
        super().__init__(app)
        self.version = version

    async def dispatch(self, request: Request, call_next):
        # Track start time
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time_ms = (time.time() - start_time) * 1000

        # Add metadata headers
        response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
        response.headers["X-API-Version"] = self.version

        return response


class ProviderHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add LLM provider information to responses.

    Useful for debugging and monitoring which provider was used.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # If response has provider info in state, add to headers
        if hasattr(request.state, "llm_provider"):
            response.headers["X-LLM-Provider"] = request.state.llm_provider

        if hasattr(request.state, "llm_model"):
            response.headers["X-LLM-Model"] = request.state.llm_model

        if hasattr(request.state, "rag_used"):
            response.headers["X-RAG-Used"] = str(request.state.rag_used)

        return response


class RequestLogMiddleware(BaseHTTPMiddleware):
    """
    Log every HTTP request to the api_requests log file.

    Captures method, path, status_code, duration_ms, and request_id
    (read from request.state.request_id set by RequestIDMiddleware).

    Format:
        method=POST path=/api/chat status=200 duration_ms=21080.5 request_id=req_abc123
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000

        request_id = getattr(request.state, "request_id", "unknown")

        _request_logger.info(
            f"method={request.method} path={request.url.path} "
            f"status={response.status_code} duration_ms={duration_ms:.1f} "
            f"request_id={request_id}"
        )

        return response
