from __future__ import annotations
"""
Central log manager — creates date-based log directories and returns loggers.

Usage:
    from log_manager import get_logger
    logger = get_logger("api_requests")
    logger.info("method=POST path=/api/chat status=200 total_ms=21080")

Log files are written to: logs/YYYY/MM/DD/{name}.log
Format per line: 2026-03-08 14:23:45 | <message>
"""

import logging
from datetime import datetime
from pathlib import Path

# Project root is the directory that contains this file
_PROJECT_ROOT = Path(__file__).parent

# Cache: logger name → Logger instance (avoids duplicate handlers)
_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger that writes to logs/YYYY/MM/DD/{name}.log.

    The directory is created automatically.  Loggers are cached so calling
    this function multiple times with the same name is safe and will not add
    duplicate handlers.

    Args:
        name: Log file stem, e.g. "api_requests", "pipeline_metrics",
              "build_index".

    Returns:
        A configured logging.Logger instance.
    """
    if name in _loggers:
        return _loggers[name]

    # Build date-based directory path
    today = datetime.now()
    log_dir = (
        _PROJECT_ROOT
        / "logs"
        / today.strftime("%Y")
        / today.strftime("%m")
        / today.strftime("%d")
    )
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{name}.log"

    # Create a dedicated logger (use a namespaced name to avoid collisions
    # with the root logger or other libraries)
    logger = logging.getLogger(f"app.{name}")
    logger.setLevel(logging.DEBUG)

    # Do not propagate to root logger — no console output from these loggers
    logger.propagate = False

    # Only add a handler if none exist yet (extra safety guard)
    if not logger.handlers:
        handler = logging.FileHandler(log_file, encoding="utf-8", delay=True)
        handler.setLevel(logging.DEBUG)

        # Format: 2026-03-08 14:23:45 | <message>
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _loggers[name] = logger
    return logger
