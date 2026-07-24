"""
Unit tests for logging utilities.
Tests for logger configuration and formatting.
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from docpipe.utils.infrastructure.logging import (
    ConditionalFormatter,
    get_log_level,
    get_logger,
)


class TestGetLogLevel:
    """Test get_log_level functionality."""

    def test_get_log_level_with_none(self):
        """Test getting log level when name is None."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_log_level(None)
            assert result == logging.INFO

    def test_get_log_level_with_env_variable(self):
        """Test getting log level from environment variable."""
        with patch.dict(os.environ, {"DS_LOG_LEVEL": "DEBUG"}):
            result = get_log_level(None)
            assert result == "DEBUG"

    def test_get_log_level_with_name_parameter(self):
        """Test getting log level with name parameter."""
        result = get_log_level("debug")
        assert result == "DEBUG"

        result = get_log_level("info")
        assert result == "INFO"

        result = get_log_level("warning")
        assert result == "WARNING"

    def test_get_log_level_case_conversion(self):
        """Test that log level name is converted to uppercase."""
        test_cases = ["debug", "Debug", "DEBUG", "info", "Info", "INFO"]

        for name in test_cases:
            result = get_log_level(name)
            assert result == name.upper()


class TestGetLogger:
    """Test get_logger functionality."""

    def test_get_logger_default_parameters(self):
        """Test getting logger with default parameters."""
        logger = get_logger()

        assert logger is not None
        assert isinstance(logger, logging.Logger)
        assert logger.propagate is False

    def test_get_logger_with_custom_name(self):
        """Test getting logger with custom name."""
        logger = get_logger(name="test_logger")

        assert logger.name == "test_logger"

    def test_get_logger_with_string_level(self):
        """Test getting logger with string log level."""
        logger = get_logger(level="DEBUG")

        assert logger.level == logging.DEBUG

    def test_get_logger_with_int_level(self):
        """Test getting logger with integer log level."""
        logger = get_logger(level=logging.WARNING)

        assert logger.level == logging.WARNING

    def test_get_logger_with_file_output(self, tmp_path):
        """Test getting logger with file output."""
        log_file = str(tmp_path / "test.log")
        logger = get_logger(name="test_file_logger", file=log_file)

        # Check that file handler was added
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0

    def test_get_logger_without_json_format(self):
        """Test logger uses normal format by default."""
        with patch.dict(os.environ, {"DS_LOG_JSON": "False"}, clear=True):
            logger = get_logger(name="test_normal_format")

            # Check that handlers use normal formatter
            for handler in logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    assert not isinstance(handler.formatter, ConditionalFormatter)

    def test_get_logger_with_json_format(self):
        """Test logger uses JSON format when enabled."""
        with patch.dict(os.environ, {"DS_LOG_JSON": "True"}, clear=True):
            logger = get_logger(name="test_json_format")

            # Check that handlers use ConditionalFormatter
            has_conditional_formatter = False
            for handler in logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    if isinstance(handler.formatter, ConditionalFormatter):
                        has_conditional_formatter = True

            assert has_conditional_formatter

    def test_get_logger_does_not_duplicate_handlers(self):
        """Test that calling get_logger multiple times doesn't duplicate handlers."""
        logger_name = "test_no_duplicate"

        logger1 = get_logger(name=logger_name)
        initial_handler_count = len(logger1.handlers)

        logger2 = get_logger(name=logger_name)
        final_handler_count = len(logger2.handlers)

        # Handler count should not increase
        assert final_handler_count == initial_handler_count

    def test_get_logger_propagate_is_false(self):
        """Test that logger propagate is set to False."""
        logger = get_logger()
        assert logger.propagate is False

    def test_get_logger_with_different_levels(self):
        """Test getting loggers with different log levels."""
        levels = [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ]

        for level_str, level_int in levels:
            logger = get_logger(name=f"test_{level_str}", level=level_str)
            assert logger.level == level_int

    def test_get_logger_case_insensitive_level(self):
        """Test that log level string is case-insensitive."""
        logger1 = get_logger(name="test_lower", level="debug")
        logger2 = get_logger(name="test_upper", level="DEBUG")
        logger3 = get_logger(name="test_mixed", level="Debug")

        assert logger1.level == logging.DEBUG
        assert logger2.level == logging.DEBUG
        assert logger3.level == logging.DEBUG

    def test_get_logger_with_none_level(self):
        """Test getting logger with None level uses INFO."""
        logger = get_logger(level=None)
        assert logger.level == logging.INFO


class TestConditionalFormatter:
    """Test ConditionalFormatter functionality."""

    @pytest.fixture
    def formatter(self):
        """Create a ConditionalFormatter instance."""
        return ConditionalFormatter(datefmt="%H:%M:%S")

    @pytest.fixture
    def mock_session_info(self):
        """Mock session info."""
        with patch("docpipe.core.models.session_info.get_session_info") as mock:
            session_info = MagicMock()
            session_info.transaction_id = "test-transaction-id"
            mock.return_value = session_info
            yield mock

    def test_formatter_basic_message(self, formatter, mock_session_info):
        """Test formatting a basic log message."""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "Test message" in result
        assert "test_logger" in result
        assert "INFO" in result
        assert "test-transaction-id" in result

    def test_formatter_with_debug_level(self, formatter, mock_session_info):
        """Test that DEBUG level includes file location."""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.DEBUG,
            pathname="/path/to/test.py",
            lineno=42,
            msg="Debug message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "Debug message" in result
        assert "/path/to/test.py:42" in result

    def test_formatter_with_exception_info(self, formatter, mock_session_info):
        """Test formatting with exception information."""
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )

            result = formatter.format(record)

            assert "Error occurred" in result
            assert "exc_info" in result

    def test_formatter_with_stack_info(self, formatter, mock_session_info):
        """Test formatting with stack information."""
        import traceback

        stack_info = "".join(traceback.format_stack())

        record = logging.LogRecord(
            name="test_logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=10,
            msg="Warning message",
            args=(),
            exc_info=None,
        )
        record.stack_info = stack_info

        result = formatter.format(record)

        assert "Warning message" in result
        assert "stack_info" in result

    def test_formatter_json_output(self, formatter, mock_session_info):
        """Test that formatter produces valid JSON."""
        import json

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["message"] == "Test message"
        assert parsed["logger"] == "test_logger"
        assert parsed["logLevel"] == "INFO"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_get_logger_with_empty_name(self):
        """Test getting logger with empty name."""
        logger = get_logger(name="")
        assert logger is not None

    def test_get_logger_with_invalid_level_string(self):
        """Test getting logger with invalid level string raises ValueError."""
        # Invalid level should raise ValueError from logging.getLevelName
        with pytest.raises(ValueError):
            get_logger(level="INVALID_LEVEL")

    def test_get_logger_multiple_calls_same_name(self):
        """Test that multiple calls with same name return same logger."""
        logger1 = get_logger(name="same_logger")
        logger2 = get_logger(name="same_logger")

        assert logger1 is logger2

    def test_formatter_with_empty_message(self):
        """Test formatting record with empty message."""
        formatter = ConditionalFormatter()

        with patch("docpipe.core.models.session_info.get_session_info") as mock:
            session_info = MagicMock()
            session_info.transaction_id = "test-id"
            mock.return_value = session_info

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="",
                args=(),
                exc_info=None,
            )

            result = formatter.format(record)
            assert result is not None

    def test_get_logger_with_very_long_name(self):
        """Test getting logger with very long name."""
        long_name = "a" * 1000
        logger = get_logger(name=long_name)
        assert logger.name == long_name

    def test_get_logger_with_unicode_name(self):
        """Test getting logger with Unicode name."""
        unicode_name = "测试日志器"
        logger = get_logger(name=unicode_name)
        assert logger.name == unicode_name
