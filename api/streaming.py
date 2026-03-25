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
    metadata: Optional[Dict[str, Any]] = None
) -> StreamingResponse:
    """
    Create a streaming response using Server-Sent Events (SSE).

    Args:
        generator: Async generator yielding tokens
        metadata: Optional metadata to send before streaming

    Returns:
        StreamingResponse with content-type: text/event-stream

    SSE Format:
        event: message
        data: {"token": "Hello"}

        event: metadata
        data: {"intent": "info_request", "rag_used": true}

        event: done
        data: {"total_tokens": 150}
    """

    async def event_generator():
        try:
            # Send metadata first (if provided)
            if metadata:
                yield format_sse_event("metadata", metadata)

            # Stream tokens
            token_count = 0
            async for token in generator:
                token_count += 1
                yield format_sse_event("message", {"token": token})

            # Send completion event
            yield format_sse_event("done", {
                "total_tokens": token_count,
                "status": "completed"
            })

        except Exception as e:
            # Send error event
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


