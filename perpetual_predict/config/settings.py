"""Application settings loaded from environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class BinanceConfig:
    """Binance API configuration."""

    api_key: str = ""
    api_secret: str = ""
    base_url: str = "https://fapi.binance.com"
    testnet_url: str = "https://testnet.binancefuture.com"
    use_testnet: bool = False

    @property
    def url(self) -> str:
        """Get the appropriate API URL based on testnet setting."""
        return self.testnet_url if self.use_testnet else self.base_url


@dataclass
class DatabaseConfig:
    """Database configuration."""

    path: Path = field(default_factory=lambda: Path("data/perpetual_predict.db"))

    def __post_init__(self) -> None:
        if isinstance(self.path, str):
            self.path = Path(self.path)


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    file: Path = field(default_factory=lambda: Path("logs/perpetual_predict.log"))
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def __post_init__(self) -> None:
        if isinstance(self.file, str):
            self.file = Path(self.file)


@dataclass
class TradingConfig:
    """Trading parameters configuration."""

    symbol: str = "BTCUSDT"
    timeframe: str = "4h"


@dataclass
class WebSocketConfig:
    """WebSocket connection configuration."""

    binance_ws_url: str = "wss://fstream.binance.com/ws"
    reconnect_delay: float = 5.0
    max_reconnect_attempts: int = 10
    ping_interval: float = 30.0
    ping_timeout: float = 10.0


@dataclass
class WhaleAlertConfig:
    """Whale Alert API configuration."""

    api_key: str = ""
    base_url: str = "https://api.whale-alert.io/v1"
    min_value_usd: int = 1_000_000


@dataclass
class Settings:
    """Application settings container."""

    binance: BinanceConfig = field(default_factory=BinanceConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    whale_alert: WhaleAlertConfig = field(default_factory=WhaleAlertConfig)

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "Settings":
        """Load settings from environment variables.

        Args:
            env_file: Path to .env file. If None, looks for .env in current directory.

        Returns:
            Settings instance populated from environment variables.
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        return cls(
            binance=BinanceConfig(
                api_key=os.getenv("BINANCE_API_KEY", ""),
                api_secret=os.getenv("BINANCE_API_SECRET", ""),
                use_testnet=os.getenv("BINANCE_TESTNET", "false").lower() == "true",
            ),
            database=DatabaseConfig(
                path=Path(os.getenv("DATABASE_PATH", "data/perpetual_predict.db")),
            ),
            logging=LoggingConfig(
                level=os.getenv("LOG_LEVEL", "INFO"),
                file=Path(os.getenv("LOG_FILE", "logs/perpetual_predict.log")),
            ),
            trading=TradingConfig(
                symbol=os.getenv("SYMBOL", "BTCUSDT"),
                timeframe=os.getenv("TIMEFRAME", "4h"),
            ),
            websocket=WebSocketConfig(
                binance_ws_url=os.getenv(
                    "BINANCE_WS_URL", "wss://fstream.binance.com/ws"
                ),
                reconnect_delay=float(os.getenv("WS_RECONNECT_DELAY", "5.0")),
                max_reconnect_attempts=int(os.getenv("WS_MAX_RECONNECT_ATTEMPTS", "10")),
                ping_interval=float(os.getenv("WS_PING_INTERVAL", "30.0")),
                ping_timeout=float(os.getenv("WS_PING_TIMEOUT", "10.0")),
            ),
            whale_alert=WhaleAlertConfig(
                api_key=os.getenv("WHALE_ALERT_API_KEY", ""),
                min_value_usd=int(os.getenv("WHALE_ALERT_MIN_VALUE", "1000000")),
            ),
        )


# Global settings instance - lazy loaded
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance.

    Lazily loads settings from environment on first call.

    Returns:
        The global Settings instance.
    """
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reload_settings(env_file: str | Path | None = None) -> Settings:
    """Reload settings from environment.

    Args:
        env_file: Path to .env file to load.

    Returns:
        The reloaded Settings instance.
    """
    global _settings
    _settings = Settings.from_env(env_file)
    return _settings
