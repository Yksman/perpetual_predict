"""Paper trading engine — opens/closes positions based on agent predictions."""

import uuid
from datetime import datetime, timezone

from perpetual_predict.config.settings import get_settings
from perpetual_predict.storage.database import Database
from perpetual_predict.storage.models import Prediction
from perpetual_predict.trading.models import PaperAccount, PaperTrade
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


class PaperTradingEngine:
    """Manages paper trading lifecycle: account, positions, PnL."""

    def __init__(self, db: Database, account_id: str = "default"):
        self.db = db
        self.account_id = account_id

    async def ensure_account(
        self, initial_balance: float = 1000.0
    ) -> PaperAccount:
        """Create account if not exists, return it."""
        account = await self.db.get_paper_account(self.account_id)
        if account:
            return account

        now = datetime.now(timezone.utc)
        account = PaperAccount(
            account_id=self.account_id,
            initial_balance=initial_balance,
            current_balance=initial_balance,
            created_at=now,
            updated_at=now,
        )
        await self.db.insert_paper_account(account)
        return account

    async def open_position(
        self,
        prediction: Prediction,
        entry_price: float,
    ) -> PaperTrade | None:
        """Open a paper trade based on prediction.

        Returns None if direction is NEUTRAL, position_ratio is 0, or balance is 0.
        """
        if prediction.direction == "NEUTRAL":
            return None

        if prediction.position_ratio <= 0:
            logger.info("Agent chose position_ratio=0, skipping trade")
            return None

        account = await self.db.get_paper_account(self.account_id)
        if not account or account.current_balance <= 0:
            logger.warning("Paper account balance is 0, skipping trade")
            return None

        settings = get_settings().paper_trading

        # Use agent-decided values, clamped to configured limits
        leverage = max(1.0, min(settings.max_leverage, prediction.leverage))
        position_ratio = max(0.0, min(1.0, prediction.position_ratio))

        side = "LONG" if prediction.direction == "UP" else "SHORT"
        position_size = account.current_balance * position_ratio
        notional_value = position_size * leverage

        # Entry fee on notional
        entry_fee = notional_value * (settings.entry_fee_pct / 100)

        trade = PaperTrade(
            trade_id=str(uuid.uuid4()),
            account_id=self.account_id,
            prediction_id=prediction.prediction_id,
            symbol=prediction.symbol,
            side=side,
            leverage=leverage,
            position_size=position_size,
            position_ratio=position_ratio,
            notional_value=notional_value,
            entry_price=entry_price,
            entry_time=datetime.now(timezone.utc),
            balance_before=account.current_balance,
            confidence=prediction.confidence,
            status="OPEN",
            trading_reasoning=prediction.trading_reasoning,
            entry_fee=entry_fee,
        )

        await self.db.insert_paper_trade(trade)

        logger.info(
            f"Paper trade opened: {side} "
            f"leverage={leverage:.1f}x ratio={position_ratio:.0%} "
            f"size=${position_size:.2f} notional=${notional_value:.2f} "
            f"@ ${entry_price:,.2f}"
        )

        return trade

    async def close_position(
        self,
        prediction_id: str,
        exit_price: float,
    ) -> PaperTrade | None:
        """Close the open trade for a prediction.

        Returns the closed trade with PnL, or None if no open trade found.
        """
        trade = await self.db.get_open_trade(prediction_id)
        if not trade:
            return None

        settings = get_settings().paper_trading

        # Calculate PnL
        price_change = (exit_price - trade.entry_price) / trade.entry_price

        if trade.side == "LONG":
            gross_pnl = trade.notional_value * price_change
        else:  # SHORT
            gross_pnl = trade.notional_value * (-price_change)

        # Fees
        entry_fee = trade.entry_fee or (
            trade.notional_value * (settings.entry_fee_pct / 100)
        )
        exit_fee = trade.notional_value * (settings.exit_fee_pct / 100)
        total_fees = entry_fee + exit_fee

        net_pnl = gross_pnl - total_fees
        balance_after = max(0.0, trade.balance_before + net_pnl)
        return_pct = (net_pnl / trade.position_size * 100) if trade.position_size > 0 else 0.0

        # Update trade
        trade.exit_price = exit_price
        trade.exit_time = datetime.now(timezone.utc)
        trade.entry_fee = entry_fee
        trade.exit_fee = exit_fee
        trade.total_fees = total_fees
        trade.gross_pnl = gross_pnl
        trade.net_pnl = net_pnl
        trade.return_pct = return_pct
        trade.balance_after = balance_after
        trade.status = "CLOSED"

        await self.db.update_paper_trade_close(trade)
        await self.db.update_paper_account_balance(self.account_id, balance_after)

        if balance_after <= 0:
            logger.warning("Paper account liquidated! Balance reached $0.")

        logger.info(
            f"Paper trade closed: {trade.side} PnL ${net_pnl:+.2f} "
            f"({return_pct:+.2f}%) Balance: ${balance_after:.2f}"
        )

        return trade

    async def get_portfolio_context(self) -> dict:
        """Build portfolio context for the LLM prompt.

        Returns dict with balance, recent trades, and risk metrics.
        """
        account = await self.db.get_paper_account(self.account_id)
        if not account:
            return {}

        # Recent closed trades
        recent_trades = await self.db.get_paper_trades(
            account_id=self.account_id, status="CLOSED", limit=20
        )

        total_return_pct = (
            (account.current_balance - account.initial_balance)
            / account.initial_balance
            * 100
        )

        # Win rate from recent trades
        if recent_trades:
            wins = sum(1 for t in recent_trades if t.net_pnl and t.net_pnl > 0)
            win_rate = wins / len(recent_trades) * 100
        else:
            win_rate = 0.0

        # Max drawdown from equity curve
        max_drawdown = self._calculate_max_drawdown(recent_trades)

        # Consecutive losses
        consecutive_losses = 0
        for t in recent_trades:  # already sorted DESC
            if t.net_pnl and t.net_pnl < 0:
                consecutive_losses += 1
            else:
                break

        # Format recent trades summary (last 5)
        trade_lines = []
        for t in recent_trades[:5]:
            pnl_str = f"${t.net_pnl:+.2f}" if t.net_pnl else "$0.00"
            ret_str = f"{t.return_pct:+.2f}%" if t.return_pct else "0.00%"
            trade_lines.append(
                f"  {t.side} {ret_str} (leverage {t.leverage:.1f}x, "
                f"ratio {t.position_ratio:.0%}) → PnL {pnl_str}"
            )

        return {
            "balance": account.current_balance,
            "initial_balance": account.initial_balance,
            "total_return_pct": total_return_pct,
            "max_drawdown_pct": max_drawdown,
            "recent_win_rate": win_rate,
            "consecutive_losses": consecutive_losses,
            "total_trades": len(recent_trades),
            "recent_trades_summary": "\n".join(trade_lines) if trade_lines else "  (no trades yet)",
        }

    def _calculate_max_drawdown(self, trades: list[PaperTrade]) -> float:
        """Calculate max drawdown % from trade history.

        Args:
            trades: List of closed trades sorted DESC by entry_time.

        Returns:
            Max drawdown as negative percentage (e.g., -5.2).
        """
        if not trades:
            return 0.0

        # Build equity curve in chronological order
        equity = []
        for t in reversed(trades):
            if t.balance_after is not None:
                equity.append(t.balance_after)

        if not equity:
            return 0.0

        peak = equity[0]
        max_dd = 0.0
        for balance in equity:
            if balance > peak:
                peak = balance
            dd = (balance - peak) / peak * 100 if peak > 0 else 0.0
            if dd < max_dd:
                max_dd = dd

        return max_dd
