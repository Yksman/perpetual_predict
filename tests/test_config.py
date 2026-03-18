"""Tests for configuration settings."""

import os
from pathlib import Path
from unittest.mock import patch

from perpetual_predict.config import (
    BinanceConfig,
    DatabaseConfig,
    LoggingConfig,
    Settings,
    TradingConfig,
)


class TestBinanceConfig:
    """Tests for BinanceConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = BinanceConfig()
        assert config.api_key == ""
        assert config.api_secret == ""
        assert config.use_testnet is False

    def test_url_property_production(self) -> None:
        """Test URL returns production URL when testnet is disabled."""
        config = BinanceConfig(use_testnet=False)
        assert config.url == "https://fapi.binance.com"

    def test_url_property_testnet(self) -> None:
        """Test URL returns testnet URL when testnet is enabled."""
        config = BinanceConfig(use_testnet=True)
        assert config.url == "https://testnet.binancefuture.com"


class TestDatabaseConfig:
    """Tests for DatabaseConfig."""

    def test_default_path(self) -> None:
        """Test default database path."""
        config = DatabaseConfig()
        assert config.path == Path("data/perpetual_predict.db")

    def test_custom_path_as_string(self) -> None:
        """Test that string path is converted to Path."""
        config = DatabaseConfig(path="custom/path.db")  # type: ignore
        assert config.path == Path("custom/path.db")
        assert isinstance(config.path, Path)


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_default_values(self) -> None:
        """Test default logging configuration."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.file == Path("logs/perpetual_predict.log")

    def test_custom_file_as_string(self) -> None:
        """Test that string file path is converted to Path."""
        config = LoggingConfig(file="custom/log.log")  # type: ignore
        assert config.file == Path("custom/log.log")
        assert isinstance(config.file, Path)


class TestTradingConfig:
    """Tests for TradingConfig."""

    def test_default_values(self) -> None:
        """Test default trading configuration."""
        config = TradingConfig()
        assert config.symbol == "BTCUSDT"
        assert config.timeframe == "4h"


class TestSettings:
    """Tests for Settings."""

    def test_default_settings(self) -> None:
        """Test default settings initialization."""
        settings = Settings()
        assert isinstance(settings.binance, BinanceConfig)
        assert isinstance(settings.database, DatabaseConfig)
        assert isinstance(settings.logging, LoggingConfig)
        assert isinstance(settings.trading, TradingConfig)

    def test_from_env_with_defaults(self) -> None:
        """Test loading settings from empty environment."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()
            assert settings.binance.api_key == ""
            assert settings.trading.symbol == "BTCUSDT"

    def test_from_env_with_custom_values(self) -> None:
        """Test loading settings from environment variables."""
        env_vars = {
            "BINANCE_API_KEY": "test_key",
            "BINANCE_API_SECRET": "test_secret",
            "BINANCE_TESTNET": "true",
            "DATABASE_PATH": "test/db.sqlite",
            "LOG_LEVEL": "DEBUG",
            "LOG_FILE": "test/app.log",
            "SYMBOL": "ETHUSDT",
            "TIMEFRAME": "1h",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings.from_env()
            assert settings.binance.api_key == "test_key"
            assert settings.binance.api_secret == "test_secret"
            assert settings.binance.use_testnet is True
            assert settings.database.path == Path("test/db.sqlite")
            assert settings.logging.level == "DEBUG"
            assert settings.logging.file == Path("test/app.log")
            assert settings.trading.symbol == "ETHUSDT"
            assert settings.trading.timeframe == "1h"
