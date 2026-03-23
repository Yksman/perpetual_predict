"""Export dashboard data from SQLite to JSON files."""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from perpetual_predict.config.settings import get_settings
from perpetual_predict.storage.database import get_database
from perpetual_predict.trading.metrics import compute_metrics
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


async def export_dashboard_data(
    output_dir: str | Path | None = None,
    history_days: int | None = None,
) -> Path:
    """Export dashboard data from database to JSON files.

    Args:
        output_dir: Directory to write JSON files. Defaults to settings value.
        history_days: Number of days of history to include. Defaults to settings value.

    Returns:
        Path to the output directory.
    """
    settings = get_settings()
    output_path = Path(output_dir or settings.dashboard.export_dir)
    days = history_days or settings.dashboard.history_days

    output_path.mkdir(parents=True, exist_ok=True)

    symbol = settings.trading.symbol
    timeframe = settings.trading.timeframe
    account_id = settings.paper_trading.account_id
    cutoff = datetime.utcnow() - timedelta(days=days)

    async with get_database() as db:
        # 1. Predictions (all within date range)
        predictions = await db.get_predictions(
            symbol=symbol,
            timeframe=timeframe,
            start_time=cutoff,
        )

        # 2. Paper trades (all closed)
        trades = await db.get_paper_trades(
            account_id=account_id,
            status="CLOSED",
        )

        # 3. Account state
        account = await db.get_paper_account(account_id)

        # 4. Performance metrics
        metrics = await compute_metrics(db, account_id)

        # 5. Prediction accuracy stats
        accuracy = await db.get_prediction_accuracy(
            symbol=symbol,
            days=days,
        )

    # Build and write JSON files
    _write_json(output_path / "predictions.json", _build_predictions(predictions))
    _write_json(output_path / "trades.json", _build_trades(trades))
    _write_json(output_path / "metrics.json", _build_metrics(metrics, accuracy, account, trades))
    _write_json(output_path / "meta.json", _build_meta(predictions, trades))

    logger.info(
        f"Exported dashboard data: {len(predictions)} predictions, "
        f"{len(trades)} trades → {output_path}"
    )
    return output_path


def push_to_data_branch(export_dir: str | Path | None = None) -> bool:
    """Push exported JSON files to the git data branch.

    Args:
        export_dir: Directory containing JSON files. Defaults to settings value.

    Returns:
        True if push succeeded.
    """
    settings = get_settings()
    export_path = Path(export_dir or settings.dashboard.export_dir)
    branch = settings.dashboard.git_data_branch

    script = Path(__file__).parent.parent.parent / "scripts" / "push_dashboard_data.sh"
    if not script.exists():
        logger.error(f"Push script not found: {script}")
        return False

    result = subprocess.run(
        ["bash", str(script), str(export_path), branch],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        logger.error(f"Push failed: {result.stderr}")
        return False

    logger.info(f"Pushed dashboard data to branch '{branch}'")
    return True


def _build_predictions(predictions: list) -> dict:
    """Build predictions JSON structure."""
    items = []
    for p in predictions:
        items.append({
            "id": p.prediction_id,
            "time": p.prediction_time.isoformat(),
            "target_open": p.target_candle_open.isoformat(),
            "target_close": p.target_candle_close.isoformat(),
            "direction": p.direction,
            "confidence": p.confidence,
            "key_factors": p.key_factors,
            "reasoning": p.reasoning,
            "leverage": p.leverage,
            "position_ratio": p.position_ratio,
            "is_correct": p.is_correct,
            "actual_direction": p.actual_direction,
            "actual_price_change": p.actual_price_change,
            "predicted_return": p.predicted_return,
            "evaluated_at": p.evaluated_at.isoformat() if p.evaluated_at else None,
        })
    return {"predictions": items}


def _build_trades(trades: list) -> dict:
    """Build trades JSON structure."""
    items = []
    for t in trades:
        items.append({
            "id": t.trade_id,
            "prediction_id": t.prediction_id,
            "side": t.side,
            "leverage": t.leverage,
            "position_size": t.position_size,
            "position_ratio": t.position_ratio,
            "entry_price": t.entry_price,
            "entry_time": t.entry_time.isoformat(),
            "exit_price": t.exit_price,
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            "net_pnl": t.net_pnl,
            "return_pct": t.return_pct,
            "balance_after": t.balance_after,
            "confidence": t.confidence,
        })
    return {"trades": items}


def _build_metrics(metrics, accuracy: dict, account, trades: list) -> dict:
    """Build metrics JSON structure including equity curve."""
    # Build equity curve from trades (chronological order)
    sorted_trades = sorted(
        [t for t in trades if t.balance_after is not None and t.exit_time is not None],
        key=lambda t: t.exit_time,
    )
    equity_curve = []
    if account:
        equity_curve.append({
            "time": account.created_at.isoformat(),
            "balance": account.initial_balance,
        })
    for t in sorted_trades:
        equity_curve.append({
            "time": t.exit_time.isoformat(),
            "balance": t.balance_after,
        })

    return {
        "account": {
            "initial_balance": metrics.initial_balance,
            "current_balance": metrics.current_balance,
        },
        "performance": {
            "total_trades": metrics.total_trades,
            "winning_trades": metrics.winning_trades,
            "losing_trades": metrics.losing_trades,
            "win_rate": round(metrics.win_rate, 2),
            "profit_factor": round(metrics.profit_factor, 2),
            "cumulative_pnl": round(metrics.cumulative_pnl, 2),
            "total_return_pct": round(metrics.total_return_pct, 2),
            "avg_win": round(metrics.avg_win, 2),
            "avg_loss": round(metrics.avg_loss, 2),
            "max_drawdown_pct": round(metrics.max_drawdown_pct, 2),
            "current_drawdown_pct": round(metrics.current_drawdown_pct, 2),
            "sharpe_ratio": round(metrics.sharpe_ratio, 2),
            "max_consecutive_wins": metrics.max_consecutive_wins,
            "max_consecutive_losses": metrics.max_consecutive_losses,
        },
        "monthly_returns": {
            k: round(v, 2) for k, v in metrics.monthly_returns.items()
        },
        "prediction_accuracy": {
            "total": accuracy.get("total", 0),
            "correct": accuracy.get("correct", 0),
            "accuracy": round(accuracy.get("accuracy", 0), 2),
            "avg_confidence": round(accuracy.get("avg_confidence", 0), 2),
            "by_direction": {
                "UP": {
                    "total": accuracy.get("up_total", 0),
                    "correct": accuracy.get("up_correct", 0),
                },
                "DOWN": {
                    "total": accuracy.get("down_total", 0),
                    "correct": accuracy.get("down_correct", 0),
                },
                "NEUTRAL": {
                    "total": accuracy.get("neutral_total", 0),
                    "correct": accuracy.get("neutral_correct", 0),
                },
            },
        },
        "equity_curve": equity_curve,
    }


def _build_meta(predictions: list, trades: list) -> dict:
    """Build meta JSON with export timestamp and counts."""
    return {
        "exported_at": datetime.utcnow().isoformat(),
        "version": 1,
        "counts": {
            "predictions": len(predictions),
            "trades": len(trades),
        },
    }


def _write_json(path: Path, data: dict) -> None:
    """Write data to JSON file atomically."""
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.rename(path)
