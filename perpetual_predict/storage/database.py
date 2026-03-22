"""SQLite database connection and operations."""

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite

from perpetual_predict.config import get_settings
from perpetual_predict.storage.models import (
    Candle,
    FearGreedIndex,
    FundingRate,
    Liquidation,
    LongShortRatio,
    OpenInterest,
    Prediction,
    PredictionMetrics,
)

# SQL table creation statements
CREATE_CANDLES_TABLE = """
CREATE TABLE IF NOT EXISTS candles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    close_time TEXT NOT NULL,
    quote_volume REAL NOT NULL,
    trades INTEGER NOT NULL,
    taker_buy_base REAL NOT NULL,
    taker_buy_quote REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timeframe, open_time)
)
"""

CREATE_FUNDING_RATES_TABLE = """
CREATE TABLE IF NOT EXISTS funding_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    funding_time TEXT NOT NULL,
    funding_rate REAL NOT NULL,
    mark_price REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, funding_time)
)
"""

CREATE_OPEN_INTEREST_TABLE = """
CREATE TABLE IF NOT EXISTS open_interest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open_interest REAL NOT NULL,
    open_interest_value REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timestamp)
)
"""

CREATE_LONG_SHORT_RATIO_TABLE = """
CREATE TABLE IF NOT EXISTS long_short_ratio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    long_ratio REAL NOT NULL,
    short_ratio REAL NOT NULL,
    long_short_ratio REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timestamp)
)
"""

CREATE_FEAR_GREED_TABLE = """
CREATE TABLE IF NOT EXISTS fear_greed_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    value INTEGER NOT NULL,
    classification TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(timestamp)
)
"""

CREATE_PREDICTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id TEXT NOT NULL UNIQUE,
    prediction_time TEXT NOT NULL,
    target_candle_open TEXT NOT NULL,
    target_candle_close TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence REAL NOT NULL,
    reasoning TEXT NOT NULL,
    key_factors TEXT DEFAULT '[]',
    session_id TEXT DEFAULT '',
    duration_ms INTEGER DEFAULT 0,
    model_usage TEXT DEFAULT '{}',
    actual_direction TEXT,
    actual_price_change REAL,
    is_correct INTEGER,
    evaluated_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timeframe, target_candle_open)
)
"""

CREATE_LIQUIDATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS liquidations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    long_liquidation_volume REAL NOT NULL,
    short_liquidation_volume REAL NOT NULL,
    total_liquidation_volume REAL NOT NULL,
    liquidation_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timestamp)
)
"""

CREATE_PREDICTION_METRICS_TABLE = """
CREATE TABLE IF NOT EXISTS prediction_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    total_predictions INTEGER NOT NULL,
    correct_predictions INTEGER NOT NULL,
    accuracy REAL NOT NULL,
    up_predictions INTEGER DEFAULT 0,
    up_correct INTEGER DEFAULT 0,
    down_predictions INTEGER DEFAULT 0,
    down_correct INTEGER DEFAULT 0,
    neutral_predictions INTEGER DEFAULT 0,
    neutral_correct INTEGER DEFAULT 0,
    avg_confidence REAL DEFAULT 0.5,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(window_start, window_end)
)
"""

# Index creation for performance
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_candles_symbol_time ON candles(symbol, timeframe, open_time)",
    "CREATE INDEX IF NOT EXISTS idx_funding_symbol_time ON funding_rates(symbol, funding_time)",
    "CREATE INDEX IF NOT EXISTS idx_oi_symbol_time ON open_interest(symbol, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_lsr_symbol_time ON long_short_ratio(symbol, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_fg_time ON fear_greed_index(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_liquidations_symbol_time ON liquidations(symbol, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_predictions_pending ON predictions(is_correct) WHERE is_correct IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_predictions_time ON predictions(target_candle_open DESC)",
    "CREATE INDEX IF NOT EXISTS idx_predictions_symbol ON predictions(symbol, timeframe)",
]


class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: Path | str | None = None):
        """Initialize database manager.

        Args:
            db_path: Path to SQLite database file. If None, uses settings.
        """
        if db_path is None:
            db_path = get_settings().database.path
        self.db_path = Path(db_path)
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open database connection and create tables."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row

        # Create tables
        await self._connection.execute(CREATE_CANDLES_TABLE)
        await self._connection.execute(CREATE_FUNDING_RATES_TABLE)
        await self._connection.execute(CREATE_OPEN_INTEREST_TABLE)
        await self._connection.execute(CREATE_LONG_SHORT_RATIO_TABLE)
        await self._connection.execute(CREATE_FEAR_GREED_TABLE)
        await self._connection.execute(CREATE_LIQUIDATIONS_TABLE)
        await self._connection.execute(CREATE_PREDICTIONS_TABLE)
        await self._connection.execute(CREATE_PREDICTION_METRICS_TABLE)

        # Create indexes
        for index_sql in CREATE_INDEXES:
            await self._connection.execute(index_sql)

        await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get the database connection."""
        if self._connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    # Candle operations
    async def insert_candle(self, candle: Candle) -> None:
        """Insert a candle record."""
        sql = """
        INSERT OR REPLACE INTO candles
        (symbol, timeframe, open_time, open, high, low, close, volume,
         close_time, quote_volume, trades, taker_buy_base, taker_buy_quote)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (
                candle.symbol,
                candle.timeframe,
                candle.open_time.isoformat(),
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
                candle.close_time.isoformat(),
                candle.quote_volume,
                candle.trades,
                candle.taker_buy_base,
                candle.taker_buy_quote,
            ),
        )
        await self.connection.commit()

    async def insert_candles(self, candles: list[Candle]) -> None:
        """Insert multiple candle records."""
        sql = """
        INSERT OR REPLACE INTO candles
        (symbol, timeframe, open_time, open, high, low, close, volume,
         close_time, quote_volume, trades, taker_buy_base, taker_buy_quote)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        data = [
            (
                c.symbol,
                c.timeframe,
                c.open_time.isoformat(),
                c.open,
                c.high,
                c.low,
                c.close,
                c.volume,
                c.close_time.isoformat(),
                c.quote_volume,
                c.trades,
                c.taker_buy_base,
                c.taker_buy_quote,
            )
            for c in candles
        ]
        await self.connection.executemany(sql, data)
        await self.connection.commit()

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list[Candle]:
        """Get candles for a symbol and timeframe."""
        sql = "SELECT * FROM candles WHERE symbol = ? AND timeframe = ?"
        params: list[Any] = [symbol, timeframe]

        if start_time:
            sql += " AND open_time >= ?"
            params.append(start_time.isoformat())
        if end_time:
            sql += " AND open_time <= ?"
            params.append(end_time.isoformat())

        sql += " ORDER BY open_time DESC"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [Candle.from_dict(dict(row)) for row in rows]

    # Funding rate operations
    async def insert_funding_rate(self, rate: FundingRate) -> None:
        """Insert a funding rate record."""
        sql = """
        INSERT OR REPLACE INTO funding_rates
        (symbol, funding_time, funding_rate, mark_price)
        VALUES (?, ?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (
                rate.symbol,
                rate.funding_time.isoformat(),
                rate.funding_rate,
                rate.mark_price,
            ),
        )
        await self.connection.commit()

    async def insert_funding_rates(self, rates: list[FundingRate]) -> None:
        """Insert multiple funding rate records."""
        sql = """
        INSERT OR REPLACE INTO funding_rates
        (symbol, funding_time, funding_rate, mark_price)
        VALUES (?, ?, ?, ?)
        """
        data = [
            (r.symbol, r.funding_time.isoformat(), r.funding_rate, r.mark_price)
            for r in rates
        ]
        await self.connection.executemany(sql, data)
        await self.connection.commit()

    async def get_funding_rates(
        self,
        symbol: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list[FundingRate]:
        """Get funding rates for a symbol."""
        sql = "SELECT * FROM funding_rates WHERE symbol = ?"
        params: list[Any] = [symbol]

        if start_time:
            sql += " AND funding_time >= ?"
            params.append(start_time.isoformat())
        if end_time:
            sql += " AND funding_time <= ?"
            params.append(end_time.isoformat())

        sql += " ORDER BY funding_time DESC"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [FundingRate.from_dict(dict(row)) for row in rows]

    # Open interest operations
    async def insert_open_interest(self, oi: OpenInterest) -> None:
        """Insert an open interest record."""
        sql = """
        INSERT OR REPLACE INTO open_interest
        (symbol, timestamp, open_interest, open_interest_value)
        VALUES (?, ?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (
                oi.symbol,
                oi.timestamp.isoformat(),
                oi.open_interest,
                oi.open_interest_value,
            ),
        )
        await self.connection.commit()

    async def insert_open_interests(self, ois: list[OpenInterest]) -> None:
        """Insert multiple open interest records."""
        sql = """
        INSERT OR REPLACE INTO open_interest
        (symbol, timestamp, open_interest, open_interest_value)
        VALUES (?, ?, ?, ?)
        """
        data = [
            (o.symbol, o.timestamp.isoformat(), o.open_interest, o.open_interest_value)
            for o in ois
        ]
        await self.connection.executemany(sql, data)
        await self.connection.commit()

    async def get_open_interests(
        self,
        symbol: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list[OpenInterest]:
        """Get open interest records for a symbol."""
        sql = "SELECT * FROM open_interest WHERE symbol = ?"
        params: list[Any] = [symbol]

        if start_time:
            sql += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            sql += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        sql += " ORDER BY timestamp DESC"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [OpenInterest.from_dict(dict(row)) for row in rows]

    # Long/Short ratio operations
    async def insert_long_short_ratio(self, ratio: LongShortRatio) -> None:
        """Insert a long/short ratio record."""
        sql = """
        INSERT OR REPLACE INTO long_short_ratio
        (symbol, timestamp, long_ratio, short_ratio, long_short_ratio)
        VALUES (?, ?, ?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (
                ratio.symbol,
                ratio.timestamp.isoformat(),
                ratio.long_ratio,
                ratio.short_ratio,
                ratio.long_short_ratio,
            ),
        )
        await self.connection.commit()

    async def insert_long_short_ratios(self, ratios: list[LongShortRatio]) -> None:
        """Insert multiple long/short ratio records."""
        sql = """
        INSERT OR REPLACE INTO long_short_ratio
        (symbol, timestamp, long_ratio, short_ratio, long_short_ratio)
        VALUES (?, ?, ?, ?, ?)
        """
        data = [
            (
                r.symbol,
                r.timestamp.isoformat(),
                r.long_ratio,
                r.short_ratio,
                r.long_short_ratio,
            )
            for r in ratios
        ]
        await self.connection.executemany(sql, data)
        await self.connection.commit()

    async def get_long_short_ratios(
        self,
        symbol: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list[LongShortRatio]:
        """Get long/short ratio records for a symbol."""
        sql = "SELECT * FROM long_short_ratio WHERE symbol = ?"
        params: list[Any] = [symbol]

        if start_time:
            sql += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            sql += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        sql += " ORDER BY timestamp DESC"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [LongShortRatio.from_dict(dict(row)) for row in rows]

    # Fear & Greed Index operations
    async def insert_fear_greed(self, fg: FearGreedIndex) -> None:
        """Insert a Fear & Greed Index record."""
        sql = """
        INSERT OR REPLACE INTO fear_greed_index
        (timestamp, value, classification)
        VALUES (?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (fg.timestamp.isoformat(), fg.value, fg.classification),
        )
        await self.connection.commit()

    async def insert_fear_greeds(self, fgs: list[FearGreedIndex]) -> None:
        """Insert multiple Fear & Greed Index records."""
        sql = """
        INSERT OR REPLACE INTO fear_greed_index
        (timestamp, value, classification)
        VALUES (?, ?, ?)
        """
        data = [(f.timestamp.isoformat(), f.value, f.classification) for f in fgs]
        await self.connection.executemany(sql, data)
        await self.connection.commit()

    async def get_fear_greeds(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list[FearGreedIndex]:
        """Get Fear & Greed Index records."""
        sql = "SELECT * FROM fear_greed_index WHERE 1=1"
        params: list[Any] = []

        if start_time:
            sql += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            sql += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        sql += " ORDER BY timestamp DESC"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [FearGreedIndex.from_dict(dict(row)) for row in rows]

    # Liquidation operations
    async def insert_liquidation(self, liq: Liquidation) -> None:
        """Insert a liquidation record."""
        sql = """
        INSERT OR REPLACE INTO liquidations
        (symbol, timestamp, long_liquidation_volume, short_liquidation_volume,
         total_liquidation_volume, liquidation_count)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (
                liq.symbol,
                liq.timestamp.isoformat(),
                liq.long_liquidation_volume,
                liq.short_liquidation_volume,
                liq.total_liquidation_volume,
                liq.liquidation_count,
            ),
        )
        await self.connection.commit()

    async def insert_liquidations(self, liqs: list[Liquidation]) -> None:
        """Insert multiple liquidation records."""
        sql = """
        INSERT OR REPLACE INTO liquidations
        (symbol, timestamp, long_liquidation_volume, short_liquidation_volume,
         total_liquidation_volume, liquidation_count)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        data = [
            (
                liq.symbol,
                liq.timestamp.isoformat(),
                liq.long_liquidation_volume,
                liq.short_liquidation_volume,
                liq.total_liquidation_volume,
                liq.liquidation_count,
            )
            for liq in liqs
        ]
        await self.connection.executemany(sql, data)
        await self.connection.commit()

    async def get_liquidations(
        self,
        symbol: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list[Liquidation]:
        """Get liquidation records for a symbol."""
        sql = "SELECT * FROM liquidations WHERE symbol = ?"
        params: list[Any] = [symbol]

        if start_time:
            sql += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            sql += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        sql += " ORDER BY timestamp DESC"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [Liquidation.from_dict(dict(row)) for row in rows]

    # Prediction operations
    async def insert_prediction(self, prediction: Prediction) -> None:
        """Insert a prediction record."""
        import json

        sql = """
        INSERT OR REPLACE INTO predictions
        (prediction_id, prediction_time, target_candle_open, target_candle_close,
         symbol, timeframe, direction, confidence, reasoning, key_factors,
         session_id, duration_ms, model_usage,
         actual_direction, actual_price_change, is_correct, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (
                prediction.prediction_id,
                prediction.prediction_time.isoformat(),
                prediction.target_candle_open.isoformat(),
                prediction.target_candle_close.isoformat(),
                prediction.symbol,
                prediction.timeframe,
                prediction.direction,
                prediction.confidence,
                prediction.reasoning,
                json.dumps(prediction.key_factors),
                prediction.session_id,
                prediction.duration_ms,
                json.dumps(prediction.model_usage),
                prediction.actual_direction,
                prediction.actual_price_change,
                prediction.is_correct,
                prediction.evaluated_at.isoformat() if prediction.evaluated_at else None,
            ),
        )
        await self.connection.commit()

    async def get_prediction(self, prediction_id: str) -> Prediction | None:
        """Get a single prediction by ID."""
        sql = "SELECT * FROM predictions WHERE prediction_id = ?"
        async with self.connection.execute(sql, (prediction_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return Prediction.from_dict(dict(row))
            return None

    async def get_pending_predictions(
        self,
        symbol: str | None = None,
        before_time: datetime | None = None,
    ) -> list[Prediction]:
        """Get predictions that haven't been evaluated yet."""
        sql = "SELECT * FROM predictions WHERE is_correct IS NULL"
        params: list[Any] = []

        if symbol:
            sql += " AND symbol = ?"
            params.append(symbol)

        if before_time:
            sql += " AND target_candle_close <= ?"
            params.append(before_time.isoformat())

        sql += " ORDER BY target_candle_open ASC"

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [Prediction.from_dict(dict(row)) for row in rows]

    async def get_predictions(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        evaluated_only: bool = False,
        limit: int | None = None,
    ) -> list[Prediction]:
        """Get predictions with optional filters."""
        sql = "SELECT * FROM predictions WHERE 1=1"
        params: list[Any] = []

        if symbol:
            sql += " AND symbol = ?"
            params.append(symbol)
        if timeframe:
            sql += " AND timeframe = ?"
            params.append(timeframe)
        if start_time:
            sql += " AND prediction_time >= ?"
            params.append(start_time.isoformat())
        if end_time:
            sql += " AND prediction_time <= ?"
            params.append(end_time.isoformat())
        if evaluated_only:
            sql += " AND is_correct IS NOT NULL"

        sql += " ORDER BY prediction_time DESC"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [Prediction.from_dict(dict(row)) for row in rows]

    async def update_prediction_evaluation(
        self,
        prediction_id: str,
        actual_direction: str,
        actual_price_change: float,
        is_correct: bool,
        evaluated_at: datetime,
    ) -> None:
        """Update a prediction with evaluation results."""
        sql = """
        UPDATE predictions
        SET actual_direction = ?, actual_price_change = ?,
            is_correct = ?, evaluated_at = ?
        WHERE prediction_id = ?
        """
        await self.connection.execute(
            sql,
            (
                actual_direction,
                actual_price_change,
                is_correct,
                evaluated_at.isoformat(),
                prediction_id,
            ),
        )
        await self.connection.commit()

    async def get_latest_prediction(
        self,
        symbol: str,
        timeframe: str,
    ) -> Prediction | None:
        """Get the most recent prediction for a symbol/timeframe."""
        sql = """
        SELECT * FROM predictions
        WHERE symbol = ? AND timeframe = ?
        ORDER BY prediction_time DESC
        LIMIT 1
        """
        async with self.connection.execute(sql, (symbol, timeframe)) as cursor:
            row = await cursor.fetchone()
            if row:
                return Prediction.from_dict(dict(row))
            return None

    # Prediction metrics operations
    async def insert_prediction_metrics(self, metrics: PredictionMetrics) -> None:
        """Insert or update prediction metrics."""
        sql = """
        INSERT OR REPLACE INTO prediction_metrics
        (window_start, window_end, total_predictions, correct_predictions,
         accuracy, up_predictions, up_correct, down_predictions, down_correct,
         neutral_predictions, neutral_correct, avg_confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (
                metrics.window_start.isoformat(),
                metrics.window_end.isoformat(),
                metrics.total_predictions,
                metrics.correct_predictions,
                metrics.accuracy,
                metrics.up_predictions,
                metrics.up_correct,
                metrics.down_predictions,
                metrics.down_correct,
                metrics.neutral_predictions,
                metrics.neutral_correct,
                metrics.avg_confidence,
            ),
        )
        await self.connection.commit()

    async def get_prediction_accuracy(
        self,
        symbol: str | None = None,
        days: int = 30,
    ) -> dict[str, Any]:
        """Calculate prediction accuracy for the last N days."""
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)

        sql = """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct,
            AVG(confidence) as avg_confidence,
            SUM(CASE WHEN direction = 'UP' THEN 1 ELSE 0 END) as up_total,
            SUM(CASE WHEN direction = 'UP' AND is_correct = 1 THEN 1 ELSE 0 END) as up_correct,
            SUM(CASE WHEN direction = 'DOWN' THEN 1 ELSE 0 END) as down_total,
            SUM(CASE WHEN direction = 'DOWN' AND is_correct = 1 THEN 1 ELSE 0 END) as down_correct,
            SUM(CASE WHEN direction = 'NEUTRAL' THEN 1 ELSE 0 END) as neutral_total,
            SUM(CASE WHEN direction = 'NEUTRAL' AND is_correct = 1 THEN 1 ELSE 0 END) as neutral_correct
        FROM predictions
        WHERE is_correct IS NOT NULL
          AND prediction_time >= ?
        """
        params: list[Any] = [cutoff.isoformat()]

        if symbol:
            sql += " AND symbol = ?"
            params.append(symbol)

        async with self.connection.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            if row:
                total = row["total"] or 0
                correct = row["correct"] or 0
                return {
                    "total": total,
                    "correct": correct,
                    "accuracy": correct / total if total > 0 else 0.0,
                    "avg_confidence": row["avg_confidence"] or 0.0,
                    "up_total": row["up_total"] or 0,
                    "up_correct": row["up_correct"] or 0,
                    "down_total": row["down_total"] or 0,
                    "down_correct": row["down_correct"] or 0,
                    "neutral_total": row["neutral_total"] or 0,
                    "neutral_correct": row["neutral_correct"] or 0,
                }
            return {
                "total": 0,
                "correct": 0,
                "accuracy": 0.0,
                "avg_confidence": 0.0,
            }


@asynccontextmanager
async def get_database(db_path: Path | str | None = None) -> AsyncIterator[Database]:
    """Context manager for database connection.

    Usage:
        async with get_database() as db:
            candles = await db.get_candles("BTCUSDT", "4h")
    """
    db = Database(db_path)
    await db.connect()
    try:
        yield db
    finally:
        await db.close()
