"""Data models for database storage."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

# Type alias for prediction direction
Direction = Literal["UP", "DOWN", "NEUTRAL"]


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
class MacroIndicator:
    """Macroeconomic indicator data (daily granularity)."""

    source: str  # "fred" or "yfinance"
    indicator: str  # e.g., "DGS10", "DXY", "SPX"
    date: datetime
    value: float
    previous_value: float | None = None

    @property
    def change(self) -> float | None:
        """Day-over-day change in percent."""
        if self.previous_value is None or self.previous_value == 0:
            return None
        return ((self.value - self.previous_value) / abs(self.previous_value)) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "source": self.source,
            "indicator": self.indicator,
            "date": self.date.strftime("%Y-%m-%d"),
            "value": self.value,
            "previous_value": self.previous_value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MacroIndicator":
        """Create from dictionary (database row)."""
        date_val = data["date"]
        if isinstance(date_val, str):
            date_val = datetime.strptime(date_val, "%Y-%m-%d")
        return cls(
            source=data["source"],
            indicator=data["indicator"],
            date=date_val,
            value=data["value"],
            previous_value=data.get("previous_value"),
        )


@dataclass
class Prediction:
    """LLM prediction for price direction."""

    prediction_id: str
    prediction_time: datetime
    target_candle_open: datetime
    target_candle_close: datetime
    symbol: str
    timeframe: str

    # Prediction result
    direction: Direction
    confidence: float
    reasoning: str
    key_factors: list[str] = field(default_factory=list)

    # Claude Code metadata
    session_id: str = ""
    duration_ms: int = 0
    model_usage: dict[str, Any] = field(default_factory=dict)

    # Trading parameters (decided by agent)
    leverage: float = 1.0
    position_ratio: float = 0.0
    trading_reasoning: str = ""

    # Evaluation results (filled after candle closes)
    actual_direction: Direction | None = None
    actual_price_change: float | None = None
    is_correct: bool | None = None
    predicted_return: float | None = None
    evaluated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        import json

        return {
            "prediction_id": self.prediction_id,
            "prediction_time": self.prediction_time.isoformat(),
            "target_candle_open": self.target_candle_open.isoformat(),
            "target_candle_close": self.target_candle_close.isoformat(),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "key_factors": json.dumps(self.key_factors),
            "session_id": self.session_id,
            "duration_ms": self.duration_ms,
            "model_usage": json.dumps(self.model_usage),
            "leverage": self.leverage,
            "position_ratio": self.position_ratio,
            "trading_reasoning": self.trading_reasoning,
            "actual_direction": self.actual_direction,
            "actual_price_change": self.actual_price_change,
            "is_correct": self.is_correct,
            "predicted_return": self.predicted_return,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Prediction":
        """Create from dictionary (database row)."""
        import json

        key_factors = data.get("key_factors", "[]")
        if isinstance(key_factors, str):
            key_factors = json.loads(key_factors)

        model_usage = data.get("model_usage", "{}")
        if isinstance(model_usage, str):
            model_usage = json.loads(model_usage)

        return cls(
            prediction_id=data["prediction_id"],
            prediction_time=datetime.fromisoformat(data["prediction_time"]),
            target_candle_open=datetime.fromisoformat(data["target_candle_open"]),
            target_candle_close=datetime.fromisoformat(data["target_candle_close"]),
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            direction=data["direction"],
            confidence=data["confidence"],
            reasoning=data["reasoning"],
            key_factors=key_factors,
            session_id=data.get("session_id", ""),
            duration_ms=data.get("duration_ms", 0),
            model_usage=model_usage,
            leverage=data.get("leverage", 1.0),
            position_ratio=data.get("position_ratio", 0.0),
            trading_reasoning=data.get("trading_reasoning", ""),
            actual_direction=data.get("actual_direction"),
            actual_price_change=data.get("actual_price_change"),
            is_correct=data.get("is_correct"),
            predicted_return=data.get("predicted_return"),
            evaluated_at=(
                datetime.fromisoformat(data["evaluated_at"])
                if data.get("evaluated_at")
                else None
            ),
        )


@dataclass
class Liquidation:
    """Liquidation (force order) aggregated data for a time period."""

    symbol: str
    timestamp: datetime
    long_liquidation_volume: float  # BTC volume of liquidated longs
    short_liquidation_volume: float  # BTC volume of liquidated shorts
    total_liquidation_volume: float
    liquidation_count: int = 0

    @property
    def imbalance(self) -> float:
        """Calculate liquidation imbalance.

        Positive = more longs liquidated (bearish pressure)
        Negative = more shorts liquidated (bullish pressure)
        """
        total = self.total_liquidation_volume
        if total == 0:
            return 0.0
        return (self.long_liquidation_volume - self.short_liquidation_volume) / total

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "long_liquidation_volume": self.long_liquidation_volume,
            "short_liquidation_volume": self.short_liquidation_volume,
            "total_liquidation_volume": self.total_liquidation_volume,
            "liquidation_count": self.liquidation_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Liquidation":
        """Create from dictionary (database row)."""
        return cls(
            symbol=data["symbol"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            long_liquidation_volume=data["long_liquidation_volume"],
            short_liquidation_volume=data["short_liquidation_volume"],
            total_liquidation_volume=data["total_liquidation_volume"],
            liquidation_count=data.get("liquidation_count", 0),
        )


@dataclass
class PredictionMetrics:
    """Aggregated prediction metrics for a time window."""

    window_start: datetime
    window_end: datetime
    total_predictions: int
    correct_predictions: int
    accuracy: float
    up_predictions: int
    up_correct: int
    down_predictions: int
    down_correct: int
    neutral_predictions: int
    neutral_correct: int
    avg_confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "accuracy": self.accuracy,
            "up_predictions": self.up_predictions,
            "up_correct": self.up_correct,
            "down_predictions": self.down_predictions,
            "down_correct": self.down_correct,
            "neutral_predictions": self.neutral_predictions,
            "neutral_correct": self.neutral_correct,
            "avg_confidence": self.avg_confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PredictionMetrics":
        """Create from dictionary (database row)."""
        return cls(
            window_start=datetime.fromisoformat(data["window_start"]),
            window_end=datetime.fromisoformat(data["window_end"]),
            total_predictions=data["total_predictions"],
            correct_predictions=data["correct_predictions"],
            accuracy=data["accuracy"],
            up_predictions=data["up_predictions"],
            up_correct=data["up_correct"],
            down_predictions=data["down_predictions"],
            down_correct=data["down_correct"],
            neutral_predictions=data["neutral_predictions"],
            neutral_correct=data["neutral_correct"],
            avg_confidence=data["avg_confidence"],
        )
