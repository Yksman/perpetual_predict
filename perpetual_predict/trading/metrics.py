"""Performance metrics calculation for paper trading."""

import math
from dataclasses import dataclass, field

from perpetual_predict.storage.database import Database
from perpetual_predict.trading.models import PaperTrade


@dataclass
class PerformanceMetrics:
    """Comprehensive paper trading performance metrics."""

    # Counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # Rates
    win_rate: float = 0.0
    profit_factor: float = 0.0

    # PnL
    cumulative_pnl: float = 0.0
    total_return_pct: float = 0.0

    # Win/Loss stats
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_win_loss_ratio: float = 0.0

    # Drawdown
    max_drawdown_pct: float = 0.0
    current_drawdown_pct: float = 0.0

    # Risk-adjusted
    sharpe_ratio: float = 0.0

    # Streaks
    current_consecutive_wins: int = 0
    current_consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Balance
    current_balance: float = 0.0
    initial_balance: float = 0.0

    # Monthly breakdown
    monthly_returns: dict[str, float] = field(default_factory=dict)


async def compute_metrics(
    db: Database,
    account_id: str = "default",
) -> PerformanceMetrics:
    """Compute comprehensive performance metrics from trade history.

    Args:
        db: Database connection.
        account_id: Paper trading account ID.

    Returns:
        PerformanceMetrics with all calculated values.
    """
    account = await db.get_paper_account(account_id)
    if not account:
        return PerformanceMetrics()

    # Get all closed trades in chronological order
    trades = await db.get_paper_trades(account_id=account_id, status="CLOSED")
    trades = list(reversed(trades))  # chronological (DB returns DESC)

    metrics = PerformanceMetrics(
        current_balance=account.current_balance,
        initial_balance=account.initial_balance,
    )

    if not trades:
        return metrics

    # Basic counts
    wins = [t for t in trades if t.net_pnl and t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl and t.net_pnl < 0]

    metrics.total_trades = len(trades)
    metrics.winning_trades = len(wins)
    metrics.losing_trades = len(losses)
    metrics.win_rate = len(wins) / len(trades) * 100 if trades else 0.0

    # PnL
    total_wins = sum(t.net_pnl for t in wins if t.net_pnl)
    total_losses = abs(sum(t.net_pnl for t in losses if t.net_pnl))

    metrics.cumulative_pnl = account.current_balance - account.initial_balance
    metrics.total_return_pct = (
        metrics.cumulative_pnl / account.initial_balance * 100
        if account.initial_balance > 0
        else 0.0
    )

    # Profit factor
    metrics.profit_factor = (
        total_wins / total_losses if total_losses > 0 else float("inf") if total_wins > 0 else 0.0
    )

    # Average win/loss
    metrics.avg_win = total_wins / len(wins) if wins else 0.0
    metrics.avg_loss = total_losses / len(losses) if losses else 0.0
    metrics.avg_win_loss_ratio = (
        metrics.avg_win / metrics.avg_loss if metrics.avg_loss > 0 else 0.0
    )

    # Drawdown from equity curve
    equity = []
    for t in trades:
        if t.balance_after is not None:
            equity.append(t.balance_after)

    if equity:
        peak = equity[0]
        max_dd = 0.0
        for balance in equity:
            if balance > peak:
                peak = balance
            dd = (balance - peak) / peak * 100 if peak > 0 else 0.0
            if dd < max_dd:
                max_dd = dd

        metrics.max_drawdown_pct = max_dd

        # Current drawdown
        current_peak = max(equity)
        current_balance = equity[-1]
        metrics.current_drawdown_pct = (
            (current_balance - current_peak) / current_peak * 100
            if current_peak > 0
            else 0.0
        )

    # Sharpe ratio (annualized, 4H intervals)
    returns = [t.return_pct for t in trades if t.return_pct is not None]
    if len(returns) >= 2:
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_return = math.sqrt(variance) if variance > 0 else 0.0
        # Annualization factor: 6 candles/day * 365.25 days/year
        annualization = math.sqrt(6 * 365.25)
        metrics.sharpe_ratio = (
            (mean_return / std_return) * annualization if std_return > 0 else 0.0
        )

    # Consecutive wins/losses
    _compute_streaks(trades, metrics)

    # Monthly returns
    _compute_monthly_returns(trades, metrics)

    return metrics


def _compute_streaks(trades: list[PaperTrade], metrics: PerformanceMetrics) -> None:
    """Compute consecutive win/loss streaks."""
    current_wins = 0
    current_losses = 0
    max_wins = 0
    max_losses = 0

    for t in trades:
        if t.net_pnl and t.net_pnl > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        elif t.net_pnl and t.net_pnl < 0:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)
        else:
            current_wins = 0
            current_losses = 0

    metrics.max_consecutive_wins = max_wins
    metrics.max_consecutive_losses = max_losses
    metrics.current_consecutive_wins = current_wins
    metrics.current_consecutive_losses = current_losses


def _compute_monthly_returns(
    trades: list[PaperTrade], metrics: PerformanceMetrics
) -> None:
    """Compute monthly return breakdown."""
    monthly: dict[str, float] = {}

    for t in trades:
        if t.net_pnl is None or t.exit_time is None:
            continue
        month_key = t.exit_time.strftime("%Y-%m")
        monthly[month_key] = monthly.get(month_key, 0.0) + t.net_pnl

    # Convert to percentages relative to initial balance
    if metrics.initial_balance > 0:
        metrics.monthly_returns = {
            k: v / metrics.initial_balance * 100 for k, v in sorted(monthly.items())
        }
    else:
        metrics.monthly_returns = dict(sorted(monthly.items()))
