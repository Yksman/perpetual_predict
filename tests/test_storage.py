"""Tests for storage module."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from perpetual_predict.storage import (
    Candle,
    Database,
    FearGreedIndex,
    FundingRate,
    LongShortRatio,
    OpenInterest,
    get_database,
)


class TestModels:
    """Tests for data models."""

    def test_candle_to_dict(self) -> None:
        """Test Candle to_dict conversion."""
        candle = Candle(
            symbol="BTCUSDT",
            timeframe="4h",
            open_time=datetime(2024, 1, 1, 0, 0, 0),
            open=42000.0,
            high=43000.0,
            low=41000.0,
            close=42500.0,
            volume=1000.0,
            close_time=datetime(2024, 1, 1, 4, 0, 0),
            quote_volume=42500000.0,
            trades=5000,
            taker_buy_base=500.0,
            taker_buy_quote=21250000.0,
        )
        data = candle.to_dict()
        assert data["symbol"] == "BTCUSDT"
        assert data["open"] == 42000.0
        assert data["open_time"] == "2024-01-01T00:00:00"

    def test_candle_from_dict(self) -> None:
        """Test Candle from_dict conversion."""
        data = {
            "symbol": "BTCUSDT",
            "timeframe": "4h",
            "open_time": "2024-01-01T00:00:00",
            "open": 42000.0,
            "high": 43000.0,
            "low": 41000.0,
            "close": 42500.0,
            "volume": 1000.0,
            "close_time": "2024-01-01T04:00:00",
            "quote_volume": 42500000.0,
            "trades": 5000,
            "taker_buy_base": 500.0,
            "taker_buy_quote": 21250000.0,
        }
        candle = Candle.from_dict(data)
        assert candle.symbol == "BTCUSDT"
        assert candle.open == 42000.0
        assert candle.open_time == datetime(2024, 1, 1, 0, 0, 0)

    def test_funding_rate_roundtrip(self) -> None:
        """Test FundingRate to_dict and from_dict roundtrip."""
        rate = FundingRate(
            symbol="BTCUSDT",
            funding_time=datetime(2024, 1, 1, 8, 0, 0),
            funding_rate=0.0001,
            mark_price=42000.0,
        )
        data = rate.to_dict()
        restored = FundingRate.from_dict(data)
        assert restored.symbol == rate.symbol
        assert restored.funding_rate == rate.funding_rate

    def test_open_interest_roundtrip(self) -> None:
        """Test OpenInterest to_dict and from_dict roundtrip."""
        oi = OpenInterest(
            symbol="BTCUSDT",
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
            open_interest=100000.0,
            open_interest_value=4200000000.0,
        )
        data = oi.to_dict()
        restored = OpenInterest.from_dict(data)
        assert restored.symbol == oi.symbol
        assert restored.open_interest == oi.open_interest

    def test_long_short_ratio_roundtrip(self) -> None:
        """Test LongShortRatio to_dict and from_dict roundtrip."""
        ratio = LongShortRatio(
            symbol="BTCUSDT",
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
            long_ratio=0.55,
            short_ratio=0.45,
            long_short_ratio=1.22,
        )
        data = ratio.to_dict()
        restored = LongShortRatio.from_dict(data)
        assert restored.long_ratio == ratio.long_ratio
        assert restored.long_short_ratio == ratio.long_short_ratio

    def test_fear_greed_roundtrip(self) -> None:
        """Test FearGreedIndex to_dict and from_dict roundtrip."""
        fg = FearGreedIndex(
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
            value=75,
            classification="Greed",
        )
        data = fg.to_dict()
        restored = FearGreedIndex.from_dict(data)
        assert restored.value == fg.value
        assert restored.classification == fg.classification


class TestDatabase:
    """Tests for Database class."""

    @pytest.fixture
    def temp_db_path(self) -> Path:
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test.db"

    @pytest.mark.asyncio
    async def test_connect_creates_tables(self, temp_db_path: Path) -> None:
        """Test database connection creates tables."""
        db = Database(temp_db_path)
        await db.connect()

        # Check tables exist
        async with db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ) as cursor:
            rows = await cursor.fetchall()
            table_names = [row[0] for row in rows]

        assert "candles" in table_names
        assert "funding_rates" in table_names
        assert "open_interest" in table_names
        assert "long_short_ratio" in table_names
        assert "fear_greed_index" in table_names

        await db.close()

    @pytest.mark.asyncio
    async def test_insert_and_get_candle(self, temp_db_path: Path) -> None:
        """Test inserting and retrieving candles."""
        async with get_database(temp_db_path) as db:
            candle = Candle(
                symbol="BTCUSDT",
                timeframe="4h",
                open_time=datetime(2024, 1, 1, 0, 0, 0),
                open=42000.0,
                high=43000.0,
                low=41000.0,
                close=42500.0,
                volume=1000.0,
                close_time=datetime(2024, 1, 1, 4, 0, 0),
                quote_volume=42500000.0,
                trades=5000,
                taker_buy_base=500.0,
                taker_buy_quote=21250000.0,
            )
            await db.insert_candle(candle)

            candles = await db.get_candles("BTCUSDT", "4h")
            assert len(candles) == 1
            assert candles[0].symbol == "BTCUSDT"
            assert candles[0].close == 42500.0

    @pytest.mark.asyncio
    async def test_insert_candles_batch(self, temp_db_path: Path) -> None:
        """Test batch inserting candles."""
        async with get_database(temp_db_path) as db:
            candles = [
                Candle(
                    symbol="BTCUSDT",
                    timeframe="4h",
                    open_time=datetime(2024, 1, 1, i * 4, 0, 0),
                    open=42000.0 + i * 100,
                    high=43000.0,
                    low=41000.0,
                    close=42500.0,
                    volume=1000.0,
                    close_time=datetime(2024, 1, 1, (i + 1) * 4, 0, 0),
                    quote_volume=42500000.0,
                    trades=5000,
                    taker_buy_base=500.0,
                    taker_buy_quote=21250000.0,
                )
                for i in range(5)
            ]
            await db.insert_candles(candles)

            result = await db.get_candles("BTCUSDT", "4h")
            assert len(result) == 5

    @pytest.mark.asyncio
    async def test_insert_and_get_funding_rate(self, temp_db_path: Path) -> None:
        """Test inserting and retrieving funding rates."""
        async with get_database(temp_db_path) as db:
            rate = FundingRate(
                symbol="BTCUSDT",
                funding_time=datetime(2024, 1, 1, 8, 0, 0),
                funding_rate=0.0001,
                mark_price=42000.0,
            )
            await db.insert_funding_rate(rate)

            rates = await db.get_funding_rates("BTCUSDT")
            assert len(rates) == 1
            assert rates[0].funding_rate == 0.0001

    @pytest.mark.asyncio
    async def test_insert_and_get_open_interest(self, temp_db_path: Path) -> None:
        """Test inserting and retrieving open interest."""
        async with get_database(temp_db_path) as db:
            oi = OpenInterest(
                symbol="BTCUSDT",
                timestamp=datetime(2024, 1, 1, 0, 0, 0),
                open_interest=100000.0,
                open_interest_value=4200000000.0,
            )
            await db.insert_open_interest(oi)

            ois = await db.get_open_interests("BTCUSDT")
            assert len(ois) == 1
            assert ois[0].open_interest == 100000.0

    @pytest.mark.asyncio
    async def test_insert_and_get_long_short_ratio(self, temp_db_path: Path) -> None:
        """Test inserting and retrieving long/short ratio."""
        async with get_database(temp_db_path) as db:
            ratio = LongShortRatio(
                symbol="BTCUSDT",
                timestamp=datetime(2024, 1, 1, 0, 0, 0),
                long_ratio=0.55,
                short_ratio=0.45,
                long_short_ratio=1.22,
            )
            await db.insert_long_short_ratio(ratio)

            ratios = await db.get_long_short_ratios("BTCUSDT")
            assert len(ratios) == 1
            assert ratios[0].long_short_ratio == 1.22

    @pytest.mark.asyncio
    async def test_insert_and_get_fear_greed(self, temp_db_path: Path) -> None:
        """Test inserting and retrieving Fear & Greed index."""
        async with get_database(temp_db_path) as db:
            fg = FearGreedIndex(
                timestamp=datetime(2024, 1, 1, 0, 0, 0),
                value=75,
                classification="Greed",
            )
            await db.insert_fear_greed(fg)

            fgs = await db.get_fear_greeds()
            assert len(fgs) == 1
            assert fgs[0].value == 75

    @pytest.mark.asyncio
    async def test_get_candles_with_time_filter(self, temp_db_path: Path) -> None:
        """Test getting candles with time filter."""
        async with get_database(temp_db_path) as db:
            candles = [
                Candle(
                    symbol="BTCUSDT",
                    timeframe="4h",
                    open_time=datetime(2024, 1, day, 0, 0, 0),
                    open=42000.0,
                    high=43000.0,
                    low=41000.0,
                    close=42500.0,
                    volume=1000.0,
                    close_time=datetime(2024, 1, day, 4, 0, 0),
                    quote_volume=42500000.0,
                    trades=5000,
                    taker_buy_base=500.0,
                    taker_buy_quote=21250000.0,
                )
                for day in range(1, 11)
            ]
            await db.insert_candles(candles)

            # Filter by start time
            result = await db.get_candles(
                "BTCUSDT",
                "4h",
                start_time=datetime(2024, 1, 5, 0, 0, 0),
            )
            assert len(result) == 6  # Days 5-10

    @pytest.mark.asyncio
    async def test_get_candles_with_limit(self, temp_db_path: Path) -> None:
        """Test getting candles with limit."""
        async with get_database(temp_db_path) as db:
            candles = [
                Candle(
                    symbol="BTCUSDT",
                    timeframe="4h",
                    open_time=datetime(2024, 1, day, 0, 0, 0),
                    open=42000.0,
                    high=43000.0,
                    low=41000.0,
                    close=42500.0,
                    volume=1000.0,
                    close_time=datetime(2024, 1, day, 4, 0, 0),
                    quote_volume=42500000.0,
                    trades=5000,
                    taker_buy_base=500.0,
                    taker_buy_quote=21250000.0,
                )
                for day in range(1, 11)
            ]
            await db.insert_candles(candles)

            result = await db.get_candles("BTCUSDT", "4h", limit=3)
            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_upsert_on_duplicate(self, temp_db_path: Path) -> None:
        """Test that duplicate records are updated (upsert)."""
        async with get_database(temp_db_path) as db:
            candle1 = Candle(
                symbol="BTCUSDT",
                timeframe="4h",
                open_time=datetime(2024, 1, 1, 0, 0, 0),
                open=42000.0,
                high=43000.0,
                low=41000.0,
                close=42500.0,
                volume=1000.0,
                close_time=datetime(2024, 1, 1, 4, 0, 0),
                quote_volume=42500000.0,
                trades=5000,
                taker_buy_base=500.0,
                taker_buy_quote=21250000.0,
            )
            await db.insert_candle(candle1)

            # Insert same timestamp with different close
            candle2 = Candle(
                symbol="BTCUSDT",
                timeframe="4h",
                open_time=datetime(2024, 1, 1, 0, 0, 0),
                open=42000.0,
                high=43000.0,
                low=41000.0,
                close=43000.0,  # Different close
                volume=1000.0,
                close_time=datetime(2024, 1, 1, 4, 0, 0),
                quote_volume=42500000.0,
                trades=5000,
                taker_buy_base=500.0,
                taker_buy_quote=21250000.0,
            )
            await db.insert_candle(candle2)

            candles = await db.get_candles("BTCUSDT", "4h")
            assert len(candles) == 1
            assert candles[0].close == 43000.0  # Updated value


class TestGetDatabaseContextManager:
    """Tests for get_database context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_closes_connection(self) -> None:
        """Test that context manager properly closes connection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            async with get_database(db_path) as db:
                assert db._connection is not None

            # After context, connection should be closed
            assert db._connection is None
