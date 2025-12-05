# utils/logger.py
"""
Centralized logging configuration for the cyber chatbot.

Features:
- Structured logging with JSON format option
- Different log levels per environment
- File and console handlers
- Request ID tracking for debugging
"""

from __future__ import annotations

import logging
import sys
from typing import Optional
from pathlib import Path


def setup_logger(
    name: str,
    level: str = "INFO",
    log_file: Optional[str] = None,
    enable_debug: bool = False,
) -> logging.Logger:
    """
    Configure and return a logger instance.

    Args:
        name: Logger name (usually __name__)
        level: Logging level ("DEBUG", "INFO", "WARNING", "ERROR")
        log_file: Optional file path to write logs
        enable_debug: Enable debug mode (overrides level to DEBUG)

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logger(__name__, enable_debug=True)
        >>> logger.info("Pipeline started", extra={"request_id": "123"})
    """
    logger = logging.getLogger(name)

    # Set level
    if enable_debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if enable_debug else logging.INFO)

    # Formatter
    console_format = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        file_format = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


# Global logger instance
_global_logger: Optional[logging.Logger] = None


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get or create the global logger.

    Args:
        name: Optional logger name (defaults to "cyber_chatbot")

    Returns:
        Logger instance
    """
    global _global_logger

    if _global_logger is None:
        _global_logger = setup_logger(
            name or "cyber_chatbot",
            enable_debug=False,  # Will be overridden by config
        )

    return _global_logger


class ContextLogger:
    """
    Logger wrapper that automatically adds context (request_id, session_id) to logs.

    Example:
        >>> ctx_logger = ContextLogger(request_id="req-123", session_id="sess-456")
        >>> ctx_logger.info("Processing request")
        # Output: ... - INFO - [req-123][sess-456] Processing request
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        self.logger = logger or get_logger()
        self.request_id = request_id
        self.session_id = session_id

    def _format_message(self, msg: str) -> str:
        """Add context prefix to message"""
        prefix_parts = []
        if self.request_id:
            prefix_parts.append(f"[{self.request_id}]")
        if self.session_id:
            prefix_parts.append(f"[{self.session_id}]")

        prefix = "".join(prefix_parts)
        return f"{prefix} {msg}" if prefix else msg

    def debug(self, msg: str, **kwargs) -> None:
        self.logger.debug(self._format_message(msg), **kwargs)

    def info(self, msg: str, **kwargs) -> None:
        self.logger.info(self._format_message(msg), **kwargs)

    def warning(self, msg: str, **kwargs) -> None:
        self.logger.warning(self._format_message(msg), **kwargs)

    def error(self, msg: str, **kwargs) -> None:
        self.logger.error(self._format_message(msg), **kwargs)

    def critical(self, msg: str, **kwargs) -> None:
        self.logger.critical(self._format_message(msg), **kwargs)


# Convenience function
def create_context_logger(request_id: Optional[str] = None, session_id: Optional[str] = None) -> ContextLogger:
    """Create a context-aware logger"""
    return ContextLogger(request_id=request_id, session_id=session_id)


if __name__ == "__main__":
    # Test logging
    logger = setup_logger("test", enable_debug=True, log_file="logs/test.log")

    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    # Context logger
    ctx_logger = ContextLogger(logger, request_id="req-001", session_id="sess-xyz")
    ctx_logger.info("Processing pipeline step 1")
    ctx_logger.warning("Potential issue detected")
