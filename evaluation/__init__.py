"""Evaluation harness paketi — İP/H ölçüm scriptleri (ip_metrics, load_test, h1, survey)."""

from __future__ import annotations

import sys


def force_utf8_output() -> None:
    """stdout/stderr'i UTF-8'e sabitle.

    Windows konsolu/redirect'i varsayılan olarak cp125x kullanır → Türkçe karakterler
    (İ ş ğ ı ç) `?`/� olarak bozulur. Eval scriptleri Türkçe log basar; bu yüzden her
    main() en başta bunu çağırır. Yalnızca main()'de çağrıldığı için (import'ta değil)
    test/diğer importer'ları etkilemez. Py3.7+ `reconfigure` gerektirir; yoksa sessiz geçer.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass
