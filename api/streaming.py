# api/streaming.py
"""
Streaming Response Support for LLM Endpoints

Implements Server-Sent Events (SSE) for token-by-token streaming.
"""

from __future__ import annotations
import json
from typing import AsyncIterator, Dict, Any, Optional
from fastapi.responses import StreamingResponse


async def stream_chat_response(
    generator: AsyncIterator[str],
    metadata: Optional[Dict[str, Any]] = None,
    sources: Optional[list] = None,
    done_extra: Optional[Dict[str, Any]] = None,
) -> StreamingResponse:
    """
    Create a streaming response using Server-Sent Events (SSE).

    SSE event order:
        event: metadata   — intent, safety, rag_used, layer_path
        event: sources    — rag_sources list (only if sources provided)
        event: message    — one per token
        event: done       — total_tokens, status + done_extra fields
    """

    async def event_generator():
        try:
            if metadata:
                yield format_sse_event("metadata", metadata)

            if sources is not None:
                yield format_sse_event("sources", {"rag_sources": sources})

            token_count = 0
            async for token in generator:
                token_count += 1
                yield format_sse_event("message", {"token": token})

            done_payload: Dict[str, Any] = {"total_tokens": token_count, "status": "completed"}
            if done_extra:
                done_payload.update(done_extra)
            yield format_sse_event("done", done_payload)

        except Exception as e:
            yield format_sse_event("error", {
                "message": str(e),
                "type": type(e).__name__
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


def format_sse_event(event: str, data: Dict[str, Any]) -> str:
    """
    Format data as Server-Sent Event.

    Args:
        event: Event type (message, metadata, done, error)
        data: Event data (will be JSON serialized)

    Returns:
        Formatted SSE string

    Format:
        event: message
        data: {"token": "Hello"}

        (blank line to separate events)
    """
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {json_data}\n\n"


