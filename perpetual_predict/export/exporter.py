"""Export dashboard data from SQLite to JSON files."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from perpetual_predict.config.settings import get_settings
from perpetual_predict.storage.database import Database, get_database
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
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with get_database() as db:
        # 1. Predictions (baseline only — experiment arms are in experiments.json)
        predictions = await db.get_predictions(
            symbol=symbol,
            timeframe=timeframe,
            start_time=cutoff,
            baseline_only=True,
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

        # 5. Prediction accuracy stats (baseline only)
        accuracy = await db.get_prediction_accuracy(
            symbol=symbol,
            days=days,
            baseline_only=True,
        )

        # 6. Experiment data
        experiments_data = await _build_experiments(db)

    # Build and write JSON files
    _write_json(output_path / "predictions.json", _build_predictions(predictions))
    _write_json(output_path / "trades.json", _build_trades(trades))
    _write_json(output_path / "metrics.json", _build_metrics(metrics, accuracy, account, trades))
    _write_json(output_path / "meta.json", _build_meta(predictions, trades))
    if experiments_data["experiments"]:
        _write_json(output_path / "experiments.json", experiments_data)

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
            "position_pct": p.position_pct,
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
            "position_pct": t.position_pct,
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


async def _build_experiments(db: Database) -> dict:
    """Build experiments JSON structure for A/B test dashboard."""
    from perpetual_predict.experiment.analyzer import ExperimentAnalyzer

    experiments = await db.get_experiments()
    if not experiments:
        return {"experiments": []}

    analyzer = ExperimentAnalyzer(db)
    items = []

    for exp in experiments:
        result = await analyzer.analyze(exp.experiment_id)

        # Determine variant arm names from experiment
        variant_names = list(exp.variants.keys()) if exp.variants else ["variant"]
        arm_names = ["control"] + [f"variant_{v}" for v in variant_names]

        # Fetch accounts, predictions, trades per arm
        accounts_data = {}
        preds_by_arm = {}
        trades_by_arm = {}
        equity_curves = {}

        for arm in arm_names:
            acc = await db.get_experiment_account(exp.experiment_id, arm)
            preds = await db.get_predictions_by_experiment(exp.experiment_id, arm)
            trades = await db.get_paper_trades_by_experiment(exp.experiment_id, arm)

            accounts_data[arm] = {
                "initial_balance": acc.initial_balance if acc else 0,
                "current_balance": acc.current_balance if acc else 0,
            }
            preds_by_arm[arm] = preds
            trades_by_arm[arm] = trades
            equity_curves[arm] = _build_equity_curve(acc, trades)

        # Module diffs per variant
        variant_diffs = {}
        for vname in variant_names:
            vmods = exp.variants.get(vname, [])
            added = sorted(set(vmods) - set(exp.control_modules))
            removed = sorted(set(exp.control_modules) - set(vmods))
            variant_diffs[vname] = {"added": added, "removed": removed}

        # Progress (use control sample count)
        sample_size = result.control_sample_size if result else 0
        progress_pct = min(sample_size / exp.min_samples * 100, 100) if exp.min_samples > 0 else 0

        # Prediction comparison: match all arms by target_candle_open
        ctrl_by_candle = {
            p.target_candle_open.isoformat(): p for p in preds_by_arm.get("control", [])
        }
        all_candle_keys = set(ctrl_by_candle.keys())
        for arm in arm_names:
            if arm != "control":
                all_candle_keys &= {
                    p.target_candle_open.isoformat() for p in preds_by_arm.get(arm, [])
                }
        common_candles = sorted(all_candle_keys, reverse=True)

        # Build per-arm lookup
        arm_by_candle = {}
        for arm in arm_names:
            arm_by_candle[arm] = {
                p.target_candle_open.isoformat(): p for p in preds_by_arm.get(arm, [])
            }

        prediction_comparisons = []
        for candle_key in common_candles:
            entry = {
                "target_candle_open": candle_key,
                "target_candle_close": ctrl_by_candle[candle_key].target_candle_close.isoformat(),
                "arms": {},
            }
            for arm in arm_names:
                pred = arm_by_candle[arm].get(candle_key)
                if pred:
                    entry["arms"][arm] = _pred_arm(pred)
            prediction_comparisons.append(entry)

        # Result block (multi-variant)
        result_block = None
        if result:
            variant_results = []
            for vr in result.variant_results:
                variant_results.append({
                    "variant_name": vr.variant_name,
                    "sample_size": vr.sample_size,
                    "accuracy": round(vr.accuracy, 4),
                    "net_return": round(vr.net_return, 2),
                    "sharpe": round(vr.sharpe, 2),
                    "p_value": round(vr.p_value, 4) if vr.p_value is not None else None,
                    "is_significant": vr.is_significant,
                })
            result_block = {
                "control_accuracy": round(result.control_accuracy, 4),
                "control_return": round(result.control_return, 2),
                "control_sharpe": round(result.control_sharpe, 2),
                "control_sample_size": result.control_sample_size,
                "variant_results": variant_results,
            }

        items.append({
            "experiment_id": exp.experiment_id,
            "name": exp.name,
            "description": exp.description,
            "status": exp.status,
            "control_modules": exp.control_modules,
            "variants": {
                vname: exp.variants[vname] for vname in variant_names
            },
            "variant_diffs": variant_diffs,
            "min_samples": exp.min_samples,
            "significance_level": exp.significance_level,
            "primary_metric": exp.primary_metric,
            "created_at": exp.created_at.isoformat() if exp.created_at else None,
            "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
            "winner": exp.winner,
            "sample_size": sample_size,
            "progress_pct": round(progress_pct, 1),
            "result": result_block,
            "accounts": accounts_data,
            "equity_curves": equity_curves,
            "prediction_comparisons": prediction_comparisons,
        })

    return {"experiments": items}


def _pred_arm(p) -> dict:
    """Extract prediction fields for an experiment arm."""
    return {
        "direction": p.direction,
        "confidence": p.confidence,
        "position_pct": p.position_pct,
        "is_correct": p.is_correct,
        "actual_direction": p.actual_direction,
        "actual_price_change": p.actual_price_change,
    }


def _snap_to_4h(dt: datetime) -> str:
    """Snap a datetime to the nearest 4H candle boundary (UTC) as ISO string.

    Candle boundaries: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    utc = dt.astimezone(timezone.utc)
    snapped_hour = (utc.hour // 4) * 4
    return utc.replace(hour=snapped_hour, minute=0, second=0, microsecond=0).isoformat()


def _build_equity_curve(account, trades: list) -> list[dict]:
    """Build equity curve from account + trades for one experiment arm.

    Timestamps are snapped to 4H candle boundaries (UTC) so that
    control and variant curves share identical time keys.
    """
    closed_trades = sorted(
        [t for t in trades if t.balance_after is not None and t.exit_time is not None],
        key=lambda t: t.exit_time,
    )
    curve = []
    if account:
        initial_dt = account.created_at or (
            closed_trades[0].entry_time if closed_trades else datetime.now(timezone.utc)
        )
        curve.append({
            "time": _snap_to_4h(initial_dt),
            "balance": account.initial_balance,
        })
    for t in closed_trades:
        curve.append({
            "time": _snap_to_4h(t.exit_time),
            "balance": t.balance_after,
        })
    # Append current balance if it differs from the last closed trade
    if account and account.current_balance is not None:
        last_balance = curve[-1]["balance"] if curve else None
        if last_balance != account.current_balance:
            curve.append({
                "time": _snap_to_4h(datetime.now(timezone.utc)),
                "balance": account.current_balance,
            })
    return curve


def _write_json(path: Path, data: dict) -> None:
    """Write data to JSON file atomically."""
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.rename(path)
