"""SQLite database connection and operations."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator

if TYPE_CHECKING:
    from perpetual_predict.trading.models import PaperAccount, PaperTrade

import aiosqlite

from perpetual_predict.config import get_settings
from perpetual_predict.storage.models import (
    Candle,
    FearGreedIndex,
    FundingRate,
    Liquidation,
    LongShortRatio,
    MacroIndicator,
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
    predicted_return REAL,
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

CREATE_PAPER_ACCOUNT_TABLE = """
CREATE TABLE IF NOT EXISTS paper_account (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL UNIQUE,
    initial_balance REAL NOT NULL DEFAULT 1000.0,
    current_balance REAL NOT NULL DEFAULT 1000.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_PAPER_TRADES_TABLE = """
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT NOT NULL UNIQUE,
    account_id TEXT NOT NULL DEFAULT 'default',
    prediction_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    leverage REAL NOT NULL,
    position_size REAL NOT NULL,
    position_ratio REAL NOT NULL DEFAULT 1.0,
    notional_value REAL NOT NULL,
    entry_price REAL NOT NULL,
    entry_time TEXT NOT NULL,
    exit_price REAL,
    exit_time TEXT,
    entry_fee REAL,
    exit_fee REAL,
    total_fees REAL,
    gross_pnl REAL,
    net_pnl REAL,
    return_pct REAL,
    balance_before REAL NOT NULL,
    balance_after REAL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    confidence REAL NOT NULL,
    trading_reasoning TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_MACRO_INDICATORS_TABLE = """
CREATE TABLE IF NOT EXISTS macro_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    indicator TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL NOT NULL,
    previous_value REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, indicator, date)
)
"""

CREATE_EXPERIMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    control_modules TEXT NOT NULL,
    variant_modules TEXT NOT NULL,
    min_samples INTEGER DEFAULT 30,
    significance_level REAL DEFAULT 0.05,
    primary_metric TEXT DEFAULT 'net_return',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    winner TEXT
)
"""

CREATE_EXPERIMENT_ACCOUNTS_TABLE = """
CREATE TABLE IF NOT EXISTS experiment_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT NOT NULL,
    arm TEXT NOT NULL,
    initial_balance REAL DEFAULT 1000.0,
    current_balance REAL DEFAULT 1000.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(experiment_id, arm)
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
    "CREATE INDEX IF NOT EXISTS idx_paper_trades_status ON paper_trades(status)",
    "CREATE INDEX IF NOT EXISTS idx_paper_trades_prediction ON paper_trades(prediction_id)",
    "CREATE INDEX IF NOT EXISTS idx_paper_trades_account ON paper_trades(account_id, entry_time DESC)",
    "CREATE INDEX IF NOT EXISTS idx_macro_source_indicator_date ON macro_indicators(source, indicator, date DESC)",
]

# Experiment-related indexes (created after migration adds columns)
EXPERIMENT_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status)",
    "CREATE INDEX IF NOT EXISTS idx_predictions_experiment ON predictions(experiment_id, arm)",
    "CREATE INDEX IF NOT EXISTS idx_paper_trades_experiment ON paper_trades(experiment_id, arm)",
    "CREATE INDEX IF NOT EXISTS idx_experiment_accounts_exp ON experiment_accounts(experiment_id)",
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
        await self._connection.execute(CREATE_PAPER_ACCOUNT_TABLE)
        await self._connection.execute(CREATE_PAPER_TRADES_TABLE)
        await self._connection.execute(CREATE_MACRO_INDICATORS_TABLE)
        await self._connection.execute(CREATE_EXPERIMENTS_TABLE)
        await self._connection.execute(CREATE_EXPERIMENT_ACCOUNTS_TABLE)

        # Create indexes
        for index_sql in CREATE_INDEXES:
            await self._connection.execute(index_sql)

        # Run migrations for existing databases
        await self._run_migrations()

        # Create experiment indexes (after migration adds columns)
        for index_sql in EXPERIMENT_INDEXES:
            await self._connection.execute(index_sql)

        await self._connection.commit()

    async def _run_migrations(self) -> None:
        """Run database migrations for schema updates."""
        cursor = await self._connection.execute(
            "PRAGMA table_info(predictions)"
        )
        columns = [row[1] for row in await cursor.fetchall()]

        # Migration: Add predicted_return column
        if "predicted_return" not in columns:
            await self._connection.execute(
                "ALTER TABLE predictions ADD COLUMN predicted_return REAL"
            )

        # Migration: Add paper trading fields to predictions
        for col, col_type, default in [
            ("leverage", "REAL", "1.0"),
            ("position_ratio", "REAL", "0.0"),
            ("trading_reasoning", "TEXT", "''"),
        ]:
            if col not in columns:
                await self._connection.execute(
                    f"ALTER TABLE predictions ADD COLUMN {col} {col_type} DEFAULT {default}"
                )

        # Migration: Add experiment fields to predictions
        for col, col_type, default in [
            ("experiment_id", "TEXT", "NULL"),
            ("arm", "TEXT", "'baseline'"),
        ]:
            if col not in columns:
                await self._connection.execute(
                    f"ALTER TABLE predictions ADD COLUMN {col} {col_type} DEFAULT {default}"
                )

        # Migration: Add experiment fields to paper_trades
        trades_cursor = await self._connection.execute(
            "PRAGMA table_info(paper_trades)"
        )
        trades_columns = [row[1] for row in await trades_cursor.fetchall()]

        for col, col_type, default in [
            ("experiment_id", "TEXT", "NULL"),
            ("arm", "TEXT", "'baseline'"),
        ]:
            if col not in trades_columns:
                await self._connection.execute(
                    f"ALTER TABLE paper_trades ADD COLUMN {col} {col_type} DEFAULT {default}"
                )

        # Migration: Update UNIQUE constraint on predictions to allow experiment arms
        # Drop old unique index and create new one that includes experiment_id and arm
        await self._connection.execute(
            "DROP INDEX IF EXISTS idx_predictions_unique_experiment"
        )
        await self._connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_unique_experiment "
            "ON predictions(symbol, timeframe, target_candle_open, "
            "COALESCE(experiment_id, ''), COALESCE(arm, 'baseline'))"
        )

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

    # Macro indicator operations
    async def insert_macro_indicator(self, mi: MacroIndicator) -> None:
        """Insert a macro indicator record."""
        sql = """
        INSERT OR REPLACE INTO macro_indicators
        (source, indicator, date, value, previous_value)
        VALUES (?, ?, ?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (mi.source, mi.indicator, mi.date.strftime("%Y-%m-%d"),
             mi.value, mi.previous_value),
        )
        await self.connection.commit()

    async def insert_macro_indicators(self, mis: list[MacroIndicator]) -> None:
        """Insert multiple macro indicator records."""
        sql = """
        INSERT OR REPLACE INTO macro_indicators
        (source, indicator, date, value, previous_value)
        VALUES (?, ?, ?, ?, ?)
        """
        data = [
            (m.source, m.indicator, m.date.strftime("%Y-%m-%d"),
             m.value, m.previous_value)
            for m in mis
        ]
        await self.connection.executemany(sql, data)
        await self.connection.commit()

    async def get_macro_indicators(
        self,
        source: str | None = None,
        indicator: str | None = None,
        limit: int | None = None,
    ) -> list[MacroIndicator]:
        """Get macro indicator records with optional filters."""
        sql = "SELECT * FROM macro_indicators WHERE 1=1"
        params: list[Any] = []

        if source:
            sql += " AND source = ?"
            params.append(source)
        if indicator:
            sql += " AND indicator = ?"
            params.append(indicator)

        sql += " ORDER BY date DESC"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [MacroIndicator.from_dict(dict(row)) for row in rows]

    async def get_latest_macro_snapshot(self) -> dict[str, MacroIndicator]:
        """Get the most recent value for each indicator.

        Returns:
            Dict mapping indicator name to its latest MacroIndicator.
        """
        sql = """
        SELECT m.* FROM macro_indicators m
        INNER JOIN (
            SELECT source, indicator, MAX(date) as max_date
            FROM macro_indicators
            GROUP BY source, indicator
        ) latest ON m.source = latest.source
            AND m.indicator = latest.indicator
            AND m.date = latest.max_date
        """
        async with self.connection.execute(sql) as cursor:
            rows = await cursor.fetchall()
            return {
                row["indicator"]: MacroIndicator.from_dict(dict(row))
                for row in rows
            }

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
    async def insert_prediction(
        self,
        prediction: Prediction,
        experiment_id: str | None = None,
        arm: str = "baseline",
    ) -> None:
        """Insert a prediction record."""
        import json

        sql = """
        INSERT OR REPLACE INTO predictions
        (prediction_id, prediction_time, target_candle_open, target_candle_close,
         symbol, timeframe, direction, confidence, reasoning, key_factors,
         session_id, duration_ms, model_usage,
         leverage, position_ratio, trading_reasoning,
         actual_direction, actual_price_change, is_correct, predicted_return, evaluated_at,
         experiment_id, arm)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                prediction.leverage,
                prediction.position_ratio,
                prediction.trading_reasoning,
                prediction.actual_direction,
                prediction.actual_price_change,
                prediction.is_correct,
                prediction.predicted_return,
                prediction.evaluated_at.isoformat() if prediction.evaluated_at else None,
                experiment_id,
                arm,
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
        predicted_return: float,
        evaluated_at: datetime,
    ) -> None:
        """Update a prediction with evaluation results."""
        sql = """
        UPDATE predictions
        SET actual_direction = ?, actual_price_change = ?,
            is_correct = ?, predicted_return = ?, evaluated_at = ?
        WHERE prediction_id = ?
        """
        await self.connection.execute(
            sql,
            (
                actual_direction,
                actual_price_change,
                is_correct,
                predicted_return,
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

    # Paper trading operations
    async def insert_paper_account(self, account: PaperAccount) -> None:
        """Insert a paper trading account (ignore if exists)."""
        sql = """
        INSERT OR IGNORE INTO paper_account
        (account_id, initial_balance, current_balance, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (
                account.account_id,
                account.initial_balance,
                account.current_balance,
                account.created_at.isoformat(),
                account.updated_at.isoformat(),
            ),
        )
        await self.connection.commit()

    async def get_paper_account(self, account_id: str) -> PaperAccount | None:
        """Get a paper trading account by ID."""
        from perpetual_predict.trading.models import PaperAccount

        sql = "SELECT * FROM paper_account WHERE account_id = ?"
        async with self.connection.execute(sql, (account_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return PaperAccount.from_dict(dict(row))
            return None

    async def update_paper_account_balance(
        self, account_id: str, new_balance: float
    ) -> None:
        """Update paper account balance."""
        sql = """
        UPDATE paper_account
        SET current_balance = ?, updated_at = ?
        WHERE account_id = ?
        """
        await self.connection.execute(
            sql,
            (new_balance, datetime.utcnow().isoformat(), account_id),
        )
        await self.connection.commit()

    async def insert_paper_trade(self, trade: PaperTrade) -> None:
        """Insert a paper trade record."""
        d = trade.to_dict()
        sql = """
        INSERT INTO paper_trades
        (trade_id, account_id, prediction_id, symbol,
         side, leverage, position_size, position_ratio, notional_value,
         entry_price, entry_time,
         exit_price, exit_time,
         entry_fee, exit_fee, total_fees,
         gross_pnl, net_pnl, return_pct,
         balance_before, balance_after,
         status, confidence, trading_reasoning)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (
                d["trade_id"], d["account_id"], d["prediction_id"], d["symbol"],
                d["side"], d["leverage"], d["position_size"], d["position_ratio"],
                d["notional_value"],
                d["entry_price"], d["entry_time"],
                d["exit_price"], d["exit_time"],
                d["entry_fee"], d["exit_fee"], d["total_fees"],
                d["gross_pnl"], d["net_pnl"], d["return_pct"],
                d["balance_before"], d["balance_after"],
                d["status"], d["confidence"], d["trading_reasoning"],
            ),
        )
        await self.connection.commit()

    async def get_open_trade(self, prediction_id: str) -> PaperTrade | None:
        """Get an open paper trade by prediction ID."""
        from perpetual_predict.trading.models import PaperTrade

        sql = "SELECT * FROM paper_trades WHERE prediction_id = ? AND status = 'OPEN'"
        async with self.connection.execute(sql, (prediction_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return PaperTrade.from_dict(dict(row))
            return None

    async def update_paper_trade_close(self, trade: PaperTrade) -> None:
        """Update a paper trade with close data."""
        sql = """
        UPDATE paper_trades
        SET exit_price = ?, exit_time = ?,
            entry_fee = ?, exit_fee = ?, total_fees = ?,
            gross_pnl = ?, net_pnl = ?, return_pct = ?,
            balance_after = ?, status = 'CLOSED'
        WHERE trade_id = ?
        """
        await self.connection.execute(
            sql,
            (
                trade.exit_price,
                trade.exit_time.isoformat() if trade.exit_time else None,
                trade.entry_fee,
                trade.exit_fee,
                trade.total_fees,
                trade.gross_pnl,
                trade.net_pnl,
                trade.return_pct,
                trade.balance_after,
                trade.trade_id,
            ),
        )
        await self.connection.commit()

    async def get_paper_trades(
        self,
        account_id: str = "default",
        status: str | None = None,
        limit: int | None = None,
    ) -> list[PaperTrade]:
        """Get paper trades with optional filters."""
        from perpetual_predict.trading.models import PaperTrade

        sql = "SELECT * FROM paper_trades WHERE account_id = ?"
        params: list[Any] = [account_id]

        if status:
            sql += " AND status = ?"
            params.append(status)

        sql += " ORDER BY entry_time DESC"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [PaperTrade.from_dict(dict(row)) for row in rows]

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


    # Experiment operations

    async def insert_experiment(self, experiment: Any) -> None:
        """Insert an experiment record."""
        d = experiment.to_dict()
        sql = """
        INSERT INTO experiments
        (experiment_id, name, description, status, control_modules, variant_modules,
         min_samples, significance_level, primary_metric, created_at, completed_at, winner)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (
                d["experiment_id"], d["name"], d["description"], d["status"],
                d["control_modules"], d["variant_modules"],
                d["min_samples"], d["significance_level"], d["primary_metric"],
                d["created_at"], d["completed_at"], d["winner"],
            ),
        )
        await self.connection.commit()

    async def get_experiment(self, experiment_id: str) -> Any:
        """Get an experiment by ID."""
        from perpetual_predict.experiment.models import Experiment

        sql = "SELECT * FROM experiments WHERE experiment_id = ?"
        async with self.connection.execute(sql, (experiment_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return Experiment.from_dict(dict(row))
            return None

    async def get_active_experiments(self) -> list[Any]:
        """Get all active experiments."""
        from perpetual_predict.experiment.models import Experiment

        sql = "SELECT * FROM experiments WHERE status = 'active' ORDER BY created_at ASC"
        async with self.connection.execute(sql) as cursor:
            rows = await cursor.fetchall()
            return [Experiment.from_dict(dict(row)) for row in rows]

    async def get_experiments(
        self, status: str | None = None
    ) -> list[Any]:
        """Get experiments with optional status filter."""
        from perpetual_predict.experiment.models import Experiment

        sql = "SELECT * FROM experiments"
        params: list[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC"

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [Experiment.from_dict(dict(row)) for row in rows]

    async def update_experiment_status(
        self,
        experiment_id: str,
        status: str,
        winner: str | None = None,
    ) -> None:
        """Update experiment status and optionally set winner."""
        sql = "UPDATE experiments SET status = ?"
        params: list[Any] = [status]

        if status == "completed":
            sql += ", completed_at = ?"
            params.append(datetime.utcnow().isoformat())

        if winner is not None:
            sql += ", winner = ?"
            params.append(winner)

        sql += " WHERE experiment_id = ?"
        params.append(experiment_id)

        await self.connection.execute(sql, params)
        await self.connection.commit()

    async def insert_experiment_account(
        self,
        experiment_id: str,
        arm: str,
        initial_balance: float = 1000.0,
    ) -> None:
        """Create an experiment arm account."""
        sql = """
        INSERT OR IGNORE INTO experiment_accounts
        (experiment_id, arm, initial_balance, current_balance)
        VALUES (?, ?, ?, ?)
        """
        await self.connection.execute(
            sql, (experiment_id, arm, initial_balance, initial_balance)
        )
        await self.connection.commit()

    async def get_experiment_account(
        self, experiment_id: str, arm: str
    ) -> Any:
        """Get an experiment arm account."""
        from perpetual_predict.experiment.models import ExperimentAccount

        sql = "SELECT * FROM experiment_accounts WHERE experiment_id = ? AND arm = ?"
        async with self.connection.execute(sql, (experiment_id, arm)) as cursor:
            row = await cursor.fetchone()
            if row:
                d = dict(row)
                return ExperimentAccount(
                    experiment_id=d["experiment_id"],
                    arm=d["arm"],
                    initial_balance=d["initial_balance"],
                    current_balance=d["current_balance"],
                )
            return None

    async def update_experiment_account_balance(
        self, experiment_id: str, arm: str, new_balance: float
    ) -> None:
        """Update experiment arm account balance."""
        sql = """
        UPDATE experiment_accounts
        SET current_balance = ?
        WHERE experiment_id = ? AND arm = ?
        """
        await self.connection.execute(sql, (new_balance, experiment_id, arm))
        await self.connection.commit()

    async def get_predictions_by_experiment(
        self,
        experiment_id: str,
        arm: str | None = None,
        evaluated_only: bool = False,
    ) -> list[Prediction]:
        """Get predictions for a specific experiment."""
        sql = "SELECT * FROM predictions WHERE experiment_id = ?"
        params: list[Any] = [experiment_id]

        if arm:
            sql += " AND arm = ?"
            params.append(arm)

        if evaluated_only:
            sql += " AND is_correct IS NOT NULL"

        sql += " ORDER BY prediction_time ASC"

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [Prediction.from_dict(dict(row)) for row in rows]

    async def get_paper_trades_by_experiment(
        self,
        experiment_id: str,
        arm: str | None = None,
    ) -> list[Any]:
        """Get paper trades for a specific experiment."""
        from perpetual_predict.trading.models import PaperTrade

        sql = "SELECT * FROM paper_trades WHERE experiment_id = ?"
        params: list[Any] = [experiment_id]

        if arm:
            sql += " AND arm = ?"
            params.append(arm)

        sql += " ORDER BY entry_time ASC"

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [PaperTrade.from_dict(dict(row)) for row in rows]


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
