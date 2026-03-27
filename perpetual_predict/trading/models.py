"""Data models for paper trading."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


@dataclass
class PaperAccount:
    """Paper trading account state."""

    account_id: str
    initial_balance: float
    current_balance: float
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "account_id": self.account_id,
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PaperAccount":
        """Create from dictionary (database row)."""
        return cls(
            account_id=data["account_id"],
            initial_balance=data["initial_balance"],
            current_balance=data["current_balance"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


@dataclass
class PaperTrade:
    """Paper trading position record."""

    trade_id: str
    account_id: str
    prediction_id: str
    symbol: str

    # Position details
    side: Literal["LONG", "SHORT"]
    position_pct: float
    notional_value: float

    # Entry
    entry_price: float
    entry_time: datetime

    # Balance snapshot
    balance_before: float
    confidence: float
    status: Literal["OPEN", "CLOSED"] = "OPEN"
    trading_reasoning: str = ""

    # Exit (filled on close)
    exit_price: float | None = None
    exit_time: datetime | None = None

    # PnL (filled on close)
    entry_fee: float | None = None
    exit_fee: float | None = None
    total_fees: float | None = None
    gross_pnl: float | None = None
    net_pnl: float | None = None
    return_pct: float | None = None
    balance_after: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "trade_id": self.trade_id,
            "account_id": self.account_id,
            "prediction_id": self.prediction_id,
            "symbol": self.symbol,
            "side": self.side,
            "position_pct": self.position_pct,
            "notional_value": self.notional_value,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "balance_before": self.balance_before,
            "confidence": self.confidence,
            "status": self.status,
            "trading_reasoning": self.trading_reasoning,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "entry_fee": self.entry_fee,
            "exit_fee": self.exit_fee,
            "total_fees": self.total_fees,
            "gross_pnl": self.gross_pnl,
            "net_pnl": self.net_pnl,
            "return_pct": self.return_pct,
            "balance_after": self.balance_after,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PaperTrade":
        """Create from dictionary (database row)."""
        return cls(
            trade_id=data["trade_id"],
            account_id=data["account_id"],
            prediction_id=data["prediction_id"],
            symbol=data["symbol"],
            side=data["side"],
            position_pct=data.get("position_pct", 0.0),
            notional_value=data["notional_value"],
            entry_price=data["entry_price"],
            entry_time=datetime.fromisoformat(data["entry_time"]),
            balance_before=data["balance_before"],
            confidence=data["confidence"],
            status=data.get("status", "OPEN"),
            trading_reasoning=data.get("trading_reasoning", ""),
            exit_price=data.get("exit_price"),
            exit_time=(
                datetime.fromisoformat(data["exit_time"])
                if data.get("exit_time")
                else None
            ),
            entry_fee=data.get("entry_fee"),
            exit_fee=data.get("exit_fee"),
            total_fees=data.get("total_fees"),
            gross_pnl=data.get("gross_pnl"),
            net_pnl=data.get("net_pnl"),
            return_pct=data.get("return_pct"),
            balance_after=data.get("balance_after"),
        )
