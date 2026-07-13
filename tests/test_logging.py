"""Tests for ChainForge logging system."""

import io
import json
import logging
import sys

import pytest

from chainforge.logging import configure_logging, get_logger, log_data


class TestConfigureLogging:
    def test_text_console_logger(self):
        root = configure_logging(level="DEBUG", format="text", output="stderr")
        assert root.level == logging.DEBUG
        assert len(root.handlers) == 1
        root.handlers.clear()

    def test_json_format(self):
        root = configure_logging(level="INFO", format="json", output="stderr")
        assert len(root.handlers) == 1
        root.handlers.clear()

    def test_file_output(self, tmp_path):
        log_file = tmp_path / "test.log"
        configure_logging(level="INFO", format="text", output=str(log_file))
        logger = get_logger("test")
        logger.info("Hello")
        logger.handlers.clear()
        content = log_file.read_text()
        assert "Hello" in content

    def test_module_levels(self):
        root = configure_logging(level="ERROR", format="text", output="stderr",
                                 module_levels={"agent": "DEBUG"})
        agent_logger = logging.getLogger("chainforge.agent")
        assert agent_logger.level == logging.DEBUG
        root.handlers.clear()


class TestGetLogger:
    def test_logger_namespace(self):
        logger = get_logger("test_mod")
        assert logger.name == "chainforge.test_mod"

    def test_logger_caching(self):
        l1 = get_logger("cache_test")
        l2 = get_logger("cache_test")
        assert l1 is l2


class TestLogData:
    def test_log_data_with_struct(self):
        logger = get_logger("struct_test")
        logger.setLevel(logging.DEBUG)

        # Capture output
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

        log_data(logger, logging.INFO, "test msg", data={"key": "value", "num": 42})
        handler.flush()
        output = stream.getvalue()
        assert "test msg" in output
        logger.removeHandler(handler)


class TestLoggingMiddleware:
    def test_import_and_creation(self):
        from chainforge.middleware.logging_mw import logging_middleware
        mw = logging_middleware()
        assert callable(mw)

    def test_with_custom_logger_name(self):
        from chainforge.middleware.logging_mw import logging_middleware
        mw = logging_middleware(logger_name="custom_agent")
        assert callable(mw)
