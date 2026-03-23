"""Prediction evaluation system."""

from datetime import datetime, timezone
from typing import Literal

from perpetual_predict.storage.database import Database
from perpetual_predict.storage.models import Prediction
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)

Direction = Literal["UP", "DOWN", "NEUTRAL"]

# Threshold for determining neutral movement (±0.2%)
# Based on trading fee (0.2%) - movements below this are not profitable
NEUTRAL_THRESHOLD = 0.002

# Trading fee constants (percentage)
ENTRY_FEE = 0.1  # 진입 수수료 0.1%
EXIT_FEE = 0.1   # 청산 수수료 0.1%
TOTAL_FEE = ENTRY_FEE + EXIT_FEE  # 총 0.2%


class PredictionEvaluator:
    """Evaluates past predictions against actual outcomes."""

    def __init__(
        self,
        db: Database,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
        neutral_threshold: float = NEUTRAL_THRESHOLD,
    ):
        self.db = db
        self.symbol = symbol
        self.timeframe = timeframe
        self.neutral_threshold = neutral_threshold

    async def evaluate_pending_predictions(self) -> list[dict]:
        """Evaluate all pending predictions whose target candles have closed.

        Returns:
            List of evaluation results.
        """
        now = datetime.now(timezone.utc)

        # Get predictions that should have been evaluated by now
        pending = await self.db.get_pending_predictions(
            symbol=self.symbol,
            before_time=now,
        )

        if not pending:
            logger.info("No pending predictions to evaluate")
            return []

        results = []
        for prediction in pending:
            result = await self._evaluate_single(prediction)
            if result:
                results.append(result)

        logger.info(f"Evaluated {len(results)} predictions")

        # Log summary
        if results:
            correct = sum(1 for r in results if r["is_correct"])
            logger.info(f"Results: {correct}/{len(results)} correct ({correct/len(results)*100:.1f}%)")

        return results

    async def _evaluate_single(self, prediction: Prediction) -> dict | None:
        """Evaluate a single prediction.

        Args:
            prediction: Prediction to evaluate.

        Returns:
            Evaluation result dict or None if candle data not available.
        """
        # Get the actual candle for the target period
        # Use both start_time and end_time for exact match (avoids DESC ordering issue)
        candles = await self.db.get_candles(
            symbol=self.symbol,
            timeframe=self.timeframe,
            start_time=prediction.target_candle_open,
            end_time=prediction.target_candle_open,  # Exact match
            limit=1,
        )

        if not candles:
            logger.debug(
                f"Candle not yet available for prediction {prediction.prediction_id}"
            )
            return None

        candle = candles[0]

        # Verify this is the correct candle
        if candle.open_time != prediction.target_candle_open:
            logger.warning(
                f"Candle time mismatch: expected {prediction.target_candle_open}, "
                f"got {candle.open_time}"
            )
            return None

        # Calculate actual direction
        price_change = (candle.close - candle.open) / candle.open
        actual_direction = self._determine_direction(price_change)

        # Check if prediction was correct
        is_correct = prediction.direction == actual_direction

        # Calculate predicted return based on direction
        predicted_return = self._calculate_predicted_return(
            direction=prediction.direction,
            open_price=candle.open,
            close_price=candle.close,
        )

        # Update prediction record in database
        await self.db.update_prediction_evaluation(
            prediction_id=prediction.prediction_id,
            actual_direction=actual_direction,
            actual_price_change=price_change * 100,  # As percentage
            is_correct=is_correct,
            predicted_return=predicted_return,
            evaluated_at=datetime.now(timezone.utc),
        )

        result = {
            "prediction_id": prediction.prediction_id,
            "prediction_time": prediction.prediction_time.isoformat(),
            "target_candle": prediction.target_candle_open.isoformat(),
            "predicted_direction": prediction.direction,
            "predicted_confidence": prediction.confidence,
            "actual_direction": actual_direction,
            "actual_price_change": price_change * 100,
            "is_correct": is_correct,
            "predicted_return": predicted_return,
            "open_price": candle.open,
            "close_price": candle.close,
        }

        log_level = "info" if is_correct else "warning"
        getattr(logger, log_level)(
            f"Evaluated {prediction.prediction_id}: "
            f"Predicted {prediction.direction} ({prediction.confidence:.0%}) → "
            f"Actual {actual_direction} ({price_change*100:+.2f}%) "
            f"Return: {predicted_return:+.2f}% "
            f"{'✓' if is_correct else '✗'}"
        )

        return result

    def _determine_direction(self, price_change: float) -> Direction:
        """Determine direction from price change.

        Args:
            price_change: Fractional price change (e.g., 0.02 = 2%).

        Returns:
            Direction classification.
        """
        if price_change > self.neutral_threshold:
            return "UP"
        elif price_change < -self.neutral_threshold:
            return "DOWN"
        else:
            return "NEUTRAL"

    def _calculate_predicted_return(
        self,
        direction: Direction,
        open_price: float,
        close_price: float,
    ) -> float:
        """Calculate predicted return based on prediction direction.

        Args:
            direction: Predicted direction (UP/DOWN/NEUTRAL).
            open_price: Candle open price.
            close_price: Candle close price.

        Returns:
            Return percentage after fees.
            - UP: gain when price rises, loss when it falls
            - DOWN: gain when price falls, loss when it rises
            - NEUTRAL: 0 (no position, no fees)
        """
        if direction == "NEUTRAL":
            return 0.0

        price_change_pct = (close_price - open_price) / open_price * 100

        if direction == "UP":
            return price_change_pct - TOTAL_FEE
        else:  # DOWN
            return -price_change_pct - TOTAL_FEE


async def get_accuracy_summary(
    db: Database,
    symbol: str = "BTCUSDT",
    days: int = 30,
) -> dict:
    """Get prediction accuracy summary.

    Args:
        db: Database connection.
        symbol: Trading symbol.
        days: Number of days to analyze.

    Returns:
        Dictionary with accuracy metrics.
    """
    accuracy = await db.get_prediction_accuracy(symbol=symbol, days=days)

    # Calculate direction-specific accuracies
    up_acc = (
        accuracy["up_correct"] / accuracy["up_total"]
        if accuracy["up_total"] > 0
        else 0.0
    )
    down_acc = (
        accuracy["down_correct"] / accuracy["down_total"]
        if accuracy["down_total"] > 0
        else 0.0
    )
    neutral_acc = (
        accuracy["neutral_correct"] / accuracy["neutral_total"]
        if accuracy["neutral_total"] > 0
        else 0.0
    )

    return {
        "period_days": days,
        "total_predictions": accuracy["total"],
        "correct_predictions": accuracy["correct"],
        "overall_accuracy": accuracy["accuracy"],
        "average_confidence": accuracy["avg_confidence"],
        "up_predictions": accuracy["up_total"],
        "up_correct": accuracy["up_correct"],
        "up_accuracy": up_acc,
        "down_predictions": accuracy["down_total"],
        "down_correct": accuracy["down_correct"],
        "down_accuracy": down_acc,
        "neutral_predictions": accuracy["neutral_total"],
        "neutral_correct": accuracy["neutral_correct"],
        "neutral_accuracy": neutral_acc,
    }


def format_accuracy_report(summary: dict) -> str:
    """Format accuracy summary as readable report.

    Args:
        summary: Accuracy summary from get_accuracy_summary.

    Returns:
        Formatted report string.
    """
    total = summary["total_predictions"]
    if total == 0:
        return "No predictions to evaluate yet."

    report = f"""
📊 Prediction Accuracy Report ({summary['period_days']} days)

Overall: {summary['correct_predictions']}/{total} ({summary['overall_accuracy']*100:.1f}%)
Average Confidence: {summary['average_confidence']*100:.1f}%

By Direction:
  ⬆️ UP:      {summary['up_correct']}/{summary['up_predictions']} ({summary['up_accuracy']*100:.1f}%)
  ⬇️ DOWN:    {summary['down_correct']}/{summary['down_predictions']} ({summary['down_accuracy']*100:.1f}%)
  ➡️ NEUTRAL: {summary['neutral_correct']}/{summary['neutral_predictions']} ({summary['neutral_accuracy']*100:.1f}%)
"""
    return report.strip()
