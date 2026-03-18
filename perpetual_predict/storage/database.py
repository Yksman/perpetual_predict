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
    LongShortRatio,
    OpenInterest,
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

# Index creation for performance
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_candles_symbol_time ON candles(symbol, timeframe, open_time)",
    "CREATE INDEX IF NOT EXISTS idx_funding_symbol_time ON funding_rates(symbol, funding_time)",
    "CREATE INDEX IF NOT EXISTS idx_oi_symbol_time ON open_interest(symbol, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_lsr_symbol_time ON long_short_ratio(symbol, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_fg_time ON fear_greed_index(timestamp)",
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
