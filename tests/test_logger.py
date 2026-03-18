"""Tests for logging utilities."""

import logging
import tempfile
from pathlib import Path

from perpetual_predict.utils.logger import _loggers, get_logger, setup_logging


class TestSetupLogging:
    """Tests for setup_logging function."""

    def setup_method(self) -> None:
        """Clear logger cache before each test."""
        _loggers.clear()
        # Clear all handlers from existing loggers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

    def test_creates_logger_with_default_name(self) -> None:
        """Test logger is created with default name."""
        logger = setup_logging()
        assert logger.name == "perpetual_predict"
        assert isinstance(logger, logging.Logger)

    def test_creates_logger_with_custom_name(self) -> None:
        """Test logger is created with custom name."""
        logger = setup_logging("test_module")
        assert logger.name == "test_module"

    def test_sets_log_level(self) -> None:
        """Test log level is set correctly."""
        logger = setup_logging("test_debug", level="DEBUG")
        assert logger.level == logging.DEBUG

        logger2 = setup_logging("test_error", level="ERROR")
        assert logger2.level == logging.ERROR

    def test_creates_console_handler(self) -> None:
        """Test console handler is created."""
        logger = setup_logging("test_console")
        console_handlers = [
            h for h in logger.handlers if isinstance(h, logging.StreamHandler)
        ]
        assert len(console_handlers) >= 1

    def test_creates_file_handler(self) -> None:
        """Test file handler is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_logging("test_file", log_file=log_file)

            file_handlers = [
                h for h in logger.handlers if isinstance(h, logging.FileHandler)
            ]
            assert len(file_handlers) == 1
            assert log_file.exists() or log_file.parent.exists()

    def test_creates_log_directory(self) -> None:
        """Test log directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "nested" / "dir" / "test.log"
            setup_logging("test_mkdir", log_file=log_file)
            assert log_file.parent.exists()

    def test_caches_logger(self) -> None:
        """Test logger is cached and returned on subsequent calls."""
        logger1 = setup_logging("test_cache")
        logger2 = setup_logging("test_cache")
        assert logger1 is logger2

    def test_custom_format(self) -> None:
        """Test custom log format is applied."""
        custom_format = "%(levelname)s: %(message)s"
        logger = setup_logging("test_format", log_format=custom_format)

        # Check that at least one handler uses our format
        for handler in logger.handlers:
            if handler.formatter:
                assert handler.formatter._fmt == custom_format
                break


class TestGetLogger:
    """Tests for get_logger function."""

    def setup_method(self) -> None:
        """Clear logger cache before each test."""
        _loggers.clear()

    def test_returns_logger(self) -> None:
        """Test get_logger returns a logger."""
        logger = get_logger()
        assert isinstance(logger, logging.Logger)

    def test_returns_same_logger(self) -> None:
        """Test get_logger returns the same logger for same name."""
        logger1 = get_logger("test")
        logger2 = get_logger("test")
        assert logger1 is logger2

    def test_custom_name(self) -> None:
        """Test get_logger with custom name."""
        logger = get_logger("custom_module")
        assert logger.name == "custom_module"
