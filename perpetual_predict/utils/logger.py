"""Logging configuration and setup."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from perpetual_predict.config import get_settings

# Log rotation defaults
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 5  # Keep 5 backup files

# Module-level logger cache
_loggers: dict[str, logging.Logger] = {}


def setup_logging(
    name: str = "perpetual_predict",
    level: str | None = None,
    log_file: Path | str | None = None,
    log_format: str | None = None,
) -> logging.Logger:
    """Set up and configure a logger.

    Creates a logger with both console and file handlers. If the log file's
    directory doesn't exist, it will be created.

    Args:
        name: Logger name (usually __name__ of the calling module).
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               If None, uses value from settings.
        log_file: Path to log file. If None, uses value from settings.
        log_format: Log message format. If None, uses value from settings.

    Returns:
        Configured logger instance.
    """
    # Return cached logger if exists
    if name in _loggers:
        return _loggers[name]

    settings = get_settings()

    # Use provided values or fall back to settings
    level = level or settings.logging.level
    log_file = Path(log_file) if log_file else settings.logging.file
    log_format = log_format or settings.logging.format

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Prevent adding handlers multiple times
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter(log_format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with rotation - create directory if needed
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=DEFAULT_MAX_BYTES,
            backupCount=DEFAULT_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        logger.warning(f"Could not create file handler: {e}")

    # Cache the logger
    _loggers[name] = logger

    return logger


def get_logger(name: str = "perpetual_predict") -> logging.Logger:
    """Get or create a logger with the given name.

    This is a convenience function that calls setup_logging with default settings.

    Args:
        name: Logger name (usually __name__ of the calling module).

    Returns:
        Logger instance.
    """
    return setup_logging(name)
