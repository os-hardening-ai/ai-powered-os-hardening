"""
Thread-local LLM token accumulator.

Her LLM client çağrısından sonra add() çağrılır.
Pipeline başında reset(), sonunda get() ile toplam okunur.

asyncio.to_thread() her pipeline çağrısını ayrı thread'de çalıştırdığı için
thread-local izolasyon = request izolasyonu.

NOT: QueryPlanner'ın ThreadPoolExecutor alt-thread'leri bu sayacı göremez
(thread-local her thread'e ayrıdır). Safety + Generation + FilterAgent
ana pipeline thread'inde çalıştığı için takip edilir (~%65–70 kapsama).
"""
from __future__ import annotations

import threading

_local = threading.local()


def reset() -> None:
    _local.total = 0


def add(n: int) -> None:
    _local.total = getattr(_local, "total", 0) + n


def get() -> int:
    return getattr(_local, "total", 0)
