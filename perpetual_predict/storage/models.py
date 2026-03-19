"""Data models for database storage."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Candle:
    """OHLCV candlestick data."""

    symbol: str
    timeframe: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: datetime
    quote_volume: float
    trades: int
    taker_buy_base: float
    taker_buy_quote: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "open_time": self.open_time.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "close_time": self.close_time.isoformat(),
            "quote_volume": self.quote_volume,
            "trades": self.trades,
            "taker_buy_base": self.taker_buy_base,
            "taker_buy_quote": self.taker_buy_quote,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Candle":
        """Create from dictionary (database row)."""
        return cls(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            open_time=datetime.fromisoformat(data["open_time"]),
            open=data["open"],
            high=data["high"],
            low=data["low"],
            close=data["close"],
            volume=data["volume"],
            close_time=datetime.fromisoformat(data["close_time"]),
            quote_volume=data["quote_volume"],
            trades=data["trades"],
            taker_buy_base=data["taker_buy_base"],
            taker_buy_quote=data["taker_buy_quote"],
        )


@dataclass
class FundingRate:
    """Perpetual futures funding rate data."""

    symbol: str
    funding_time: datetime
    funding_rate: float
    mark_price: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "symbol": self.symbol,
            "funding_time": self.funding_time.isoformat(),
            "funding_rate": self.funding_rate,
            "mark_price": self.mark_price,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FundingRate":
        """Create from dictionary (database row)."""
        return cls(
            symbol=data["symbol"],
            funding_time=datetime.fromisoformat(data["funding_time"]),
            funding_rate=data["funding_rate"],
            mark_price=data["mark_price"],
        )


@dataclass
class OpenInterest:
    """Open interest data."""

    symbol: str
    timestamp: datetime
    open_interest: float
    open_interest_value: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "open_interest": self.open_interest,
            "open_interest_value": self.open_interest_value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OpenInterest":
        """Create from dictionary (database row)."""
        return cls(
            symbol=data["symbol"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            open_interest=data["open_interest"],
            open_interest_value=data["open_interest_value"],
        )


@dataclass
class LongShortRatio:
    """Long/Short ratio data."""

    symbol: str
    timestamp: datetime
    long_ratio: float
    short_ratio: float
    long_short_ratio: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "long_ratio": self.long_ratio,
            "short_ratio": self.short_ratio,
            "long_short_ratio": self.long_short_ratio,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LongShortRatio":
        """Create from dictionary (database row)."""
        return cls(
            symbol=data["symbol"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            long_ratio=data["long_ratio"],
            short_ratio=data["short_ratio"],
            long_short_ratio=data["long_short_ratio"],
        )


@dataclass
class FearGreedIndex:
    """Fear & Greed Index data."""

    timestamp: datetime
    value: int
    classification: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "classification": self.classification,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FearGreedIndex":
        """Create from dictionary (database row)."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            value=data["value"],
            classification=data["classification"],
        )


@dataclass
class Liquidation:
    """Liquidation event data."""

    symbol: str
    side: str  # "BUY" or "SELL"
    price: float
    original_qty: float
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "price": self.price,
            "original_qty": self.original_qty,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Liquidation":
        """Create from dictionary (database row)."""
        return cls(
            symbol=data["symbol"],
            side=data["side"],
            price=data["price"],
            original_qty=data["original_qty"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class WhaleTransaction:
    """Large cryptocurrency transaction data from Whale Alert."""

    tx_hash: str
    amount_usd: float
    from_owner: str | None
    to_owner: str | None
    transaction_type: str  # e.g., "transfer", "mint", "burn"
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "tx_hash": self.tx_hash,
            "amount_usd": self.amount_usd,
            "from_owner": self.from_owner,
            "to_owner": self.to_owner,
            "transaction_type": self.transaction_type,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WhaleTransaction":
        """Create from dictionary (database row)."""
        return cls(
            tx_hash=data["tx_hash"],
            amount_usd=data["amount_usd"],
            from_owner=data.get("from_owner"),
            to_owner=data.get("to_owner"),
            transaction_type=data["transaction_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class NewsItem:
    """Cryptocurrency news item from CryptoPanic."""

    url: str
    title: str
    sentiment: str | None  # "bullish", "bearish", "neutral", or None
    published_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "url": self.url,
            "title": self.title,
            "sentiment": self.sentiment,
            "published_at": self.published_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NewsItem":
        """Create from dictionary (database row)."""
        return cls(
            url=data["url"],
            title=data["title"],
            sentiment=data.get("sentiment"),
            published_at=datetime.fromisoformat(data["published_at"]),
        )
