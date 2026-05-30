"""Unit tests for llm.utils.logger (centralized logging helpers)."""

from __future__ import annotations

import logging

from llm.utils.logger import (
    setup_logger,
    get_logger,
    create_context_logger,
    ContextLogger,
)


class TestSetupLogger:
    def test_basic_logger(self):
        log = setup_logger("test.basic", level="INFO")
        assert isinstance(log, logging.Logger)
        assert log.level == logging.INFO
        assert log.handlers  # console handler attached

    def test_debug_overrides_level(self):
        log = setup_logger("test.debug", level="WARNING", enable_debug=True)
        assert log.level == logging.DEBUG

    def test_duplicate_handlers_prevented(self):
        log1 = setup_logger("test.dup")
        n = len(log1.handlers)
        log2 = setup_logger("test.dup")  # same name -> no new handlers
        assert log2 is log1
        assert len(log2.handlers) == n

    def test_file_handler(self, tmp_path):
        log_file = tmp_path / "logs" / "app.log"
        log = setup_logger("test.file", log_file=str(log_file))
        log.info("hello file")
        assert log_file.exists()
        assert any(isinstance(h, logging.FileHandler) for h in log.handlers)


class TestGlobalLogger:
    def test_get_logger_is_singleton(self):
        a = get_logger()
        b = get_logger()
        assert a is b


class TestContextLogger:
    def test_format_message_with_ids(self):
        cl = ContextLogger(request_id="req-1", session_id="sess-2")
        msg = cl._format_message("processing")
        assert "[req-1]" in msg and "[sess-2]" in msg and "processing" in msg

    def test_format_message_without_ids(self):
        cl = ContextLogger()
        assert cl._format_message("plain") == "plain"

    def test_all_levels_do_not_raise(self, caplog):
        cl = create_context_logger(request_id="r1")
        with caplog.at_level(logging.DEBUG):
            cl.debug("d")
            cl.info("i")
            cl.warning("w")
            cl.error("e")
            cl.critical("c")
        # context prefix applied
        assert any("[r1]" in rec.message for rec in caplog.records)

    def test_create_context_logger_returns_instance(self):
        assert isinstance(create_context_logger(), ContextLogger)
