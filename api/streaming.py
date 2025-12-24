# api/streaming.py
"""
Streaming Response Support for LLM Endpoints

Implements Server-Sent Events (SSE) for token-by-token streaming.
"""

from __future__ import annotations
import json
import asyncio
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


# Example async generator (for testing)
async def dummy_token_generator(text: str, delay: float = 0.05) -> AsyncIterator[str]:
    """
    Simulate streaming tokens with delay.

    Args:
        text: Text to stream word by word
        delay: Delay between tokens (seconds)

    Yields:
        Tokens (words)
    """
    words = text.split()
    for word in words:
        await asyncio.sleep(delay)
        yield word + " "


# ─────────────────────────────────────────────
# Chunked Response Builder (for non-streaming fallback)
# ─────────────────────────────────────────────

class ChunkedResponseBuilder:
    """
    Build response in chunks for better perceived performance.

    Even when not streaming token-by-token, we can send intermediate
    progress updates (e.g., "Safety check complete", "RAG retrieval done").
    """

    def __init__(self):
        self.events: list[Dict[str, Any]] = []

    def add_event(self, event_type: str, data: Dict[str, Any]):
        """Add an event to the response"""
        self.events.append({
            "event": event_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        })

    def get_events(self) -> list[Dict[str, Any]]:
        """Get all events"""
        return self.events

    async def stream_events(self) -> AsyncIterator[str]:
        """Stream events as SSE"""
        for event in self.events:
            yield format_sse_event(
                event["event"],
                event["data"]
            )
