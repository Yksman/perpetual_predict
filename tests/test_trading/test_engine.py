"""Tests for the paper trading engine."""

import uuid
from datetime import datetime, timezone

import pytest

from perpetual_predict.storage.database import Database
from perpetual_predict.storage.models import Prediction
from perpetual_predict.trading.engine import PaperTradingEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_prediction(
    direction: str = "UP",
    position_pct: float = 1.0,
    confidence: float = 0.7,
) -> Prediction:
    """Return a minimal Prediction dataclass for testing."""
    now = datetime.now(timezone.utc)
    return Prediction(
        prediction_id=str(uuid.uuid4()),
        prediction_time=now,
        target_candle_open=now,
        target_candle_close=now,
        symbol="BTCUSDT",
        timeframe="4h",
        direction=direction,  # type: ignore[arg-type]
        confidence=confidence,
        reasoning="test",
        position_pct=position_pct,
        trading_reasoning="test",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db(tmp_path):
    """In-memory SQLite database with all tables created."""
    db_file = tmp_path / "test.db"
    database = Database(db_file)
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
async def engine(db):
    """PaperTradingEngine wired to the test database with a funded account."""
    eng = PaperTradingEngine(db, account_id="test")
    await eng.ensure_account(initial_balance=1000.0)
    return eng


# ---------------------------------------------------------------------------
# open_position tests
# ---------------------------------------------------------------------------

class TestOpenPosition:
    """Tests for PaperTradingEngine.open_position()."""

    async def test_up_direction_opens_long(self, engine):
        """UP prediction should open a LONG trade."""
        pred = make_prediction(direction="UP", position_pct=1.0)
        trade = await engine.open_position(pred, entry_price=50_000.0)

        assert trade is not None
        assert trade.side == "LONG"

    async def test_down_direction_opens_short(self, engine):
        """DOWN prediction should open a SHORT trade."""
        pred = make_prediction(direction="DOWN", position_pct=1.0)
        trade = await engine.open_position(pred, entry_price=50_000.0)

        assert trade is not None
        assert trade.side == "SHORT"

    async def test_neutral_direction_returns_none(self, engine):
        """NEUTRAL prediction must return None — no trade opened."""
        pred = make_prediction(direction="NEUTRAL", position_pct=1.0)
        trade = await engine.open_position(pred, entry_price=50_000.0)

        assert trade is None

    async def test_zero_position_pct_returns_none(self, engine):
        """position_pct=0 should skip trade and return None."""
        pred = make_prediction(direction="UP", position_pct=0.0)
        trade = await engine.open_position(pred, entry_price=50_000.0)

        assert trade is None

    async def test_notional_value_equals_balance_times_position_pct(self, engine):
        """notional_value must equal current_balance * position_pct."""
        pred = make_prediction(direction="UP", position_pct=2.0)
        trade = await engine.open_position(pred, entry_price=50_000.0)

        assert trade is not None
        assert trade.notional_value == pytest.approx(1000.0 * 2.0)

    async def test_position_pct_clamped_to_max_leverage(self, engine):
        """position_pct above max_leverage (3.0) should be clamped to 3.0."""
        pred = make_prediction(direction="UP", position_pct=10.0)
        trade = await engine.open_position(pred, entry_price=50_000.0)

        assert trade is not None
        # Default max_leverage is 3.0; notional = 1000 * 3.0
        assert trade.position_pct == pytest.approx(3.0)
        assert trade.notional_value == pytest.approx(1000.0 * 3.0)

    async def test_zero_balance_returns_none(self, db):
        """Engine with a zero-balance account should return None."""
        engine_zero = PaperTradingEngine(db, account_id="zero_balance_test")
        await engine_zero.ensure_account(initial_balance=1000.0)
        # Drain account to zero
        await db.update_paper_account_balance("zero_balance_test", 0.0)

        pred = make_prediction(direction="UP", position_pct=1.0)
        trade = await engine_zero.open_position(pred, entry_price=50_000.0)

        assert trade is None


# ---------------------------------------------------------------------------
# close_position tests
# ---------------------------------------------------------------------------

class TestClosePosition:
    """Tests for PaperTradingEngine.close_position()."""

    async def _open_and_close(
        self,
        engine,
        direction: str,
        entry_price: float,
        exit_price: float,
        position_pct: float = 1.0,
    ):
        """Helper: open then close a position and return the closed trade."""
        pred = make_prediction(direction=direction, position_pct=position_pct)
        trade = await engine.open_position(pred, entry_price=entry_price)
        assert trade is not None
        closed = await engine.close_position(pred.prediction_id, exit_price=exit_price)
        return closed

    async def test_long_profit(self, engine):
        """LONG trade with rising price should yield positive net PnL."""
        closed = await self._open_and_close(
            engine,
            direction="UP",
            entry_price=50_000.0,
            exit_price=51_000.0,
            position_pct=1.0,
        )

        assert closed is not None
        assert closed.gross_pnl is not None
        assert closed.gross_pnl > 0
        # gross_pnl = notional * (exit - entry) / entry = 1000 * 1000/50000 = 20.0
        assert closed.gross_pnl == pytest.approx(1000.0 * (51_000 - 50_000) / 50_000)

    async def test_short_profit(self, engine):
        """SHORT trade with falling price should yield positive net PnL."""
        closed = await self._open_and_close(
            engine,
            direction="DOWN",
            entry_price=50_000.0,
            exit_price=49_000.0,
            position_pct=1.0,
        )

        assert closed is not None
        assert closed.gross_pnl is not None
        assert closed.gross_pnl > 0
        # gross_pnl = notional * -(exit - entry) / entry = 1000 * 1000/50000 = 20.0
        assert closed.gross_pnl == pytest.approx(1000.0 * (50_000 - 49_000) / 50_000)

    async def test_long_loss(self, engine):
        """LONG trade with falling price should yield negative net PnL."""
        closed = await self._open_and_close(
            engine,
            direction="UP",
            entry_price=50_000.0,
            exit_price=49_000.0,
            position_pct=1.0,
        )

        assert closed is not None
        assert closed.net_pnl is not None
        assert closed.net_pnl < 0

    async def test_fees_are_deducted(self, engine):
        """net_pnl must be gross_pnl minus entry + exit fees."""
        closed = await self._open_and_close(
            engine,
            direction="UP",
            entry_price=50_000.0,
            exit_price=51_000.0,
            position_pct=1.0,
        )

        assert closed is not None
        notional = 1000.0 * 1.0  # balance * position_pct
        entry_fee = notional * 0.001  # 0.1%
        exit_fee = notional * 0.001   # 0.1%
        expected_total_fees = entry_fee + exit_fee

        assert closed.total_fees == pytest.approx(expected_total_fees)
        assert closed.net_pnl == pytest.approx(closed.gross_pnl - expected_total_fees)

    async def test_return_pct_formula(self, engine):
        """return_pct must equal net_pnl / balance_before * 100."""
        closed = await self._open_and_close(
            engine,
            direction="UP",
            entry_price=50_000.0,
            exit_price=51_000.0,
            position_pct=1.0,
        )

        assert closed is not None
        assert closed.return_pct == pytest.approx(
            closed.net_pnl / closed.balance_before * 100
        )

    async def test_no_open_trade_returns_none(self, engine):
        """close_position on an unknown prediction_id should return None."""
        result = await engine.close_position("nonexistent-id", exit_price=50_000.0)
        assert result is None


# ---------------------------------------------------------------------------
# get_portfolio_context tests
# ---------------------------------------------------------------------------

class TestGetPortfolioContext:
    """Tests for PaperTradingEngine.get_portfolio_context()."""

    async def test_returns_empty_dict_when_no_account(self, db):
        """Engine with no account created should return empty dict."""
        engine_no_account = PaperTradingEngine(db, account_id="ghost")
        ctx = await engine_no_account.get_portfolio_context()
        assert ctx == {}

    async def test_returns_balance_fields(self, engine):
        """Context should include balance and initial_balance from the account."""
        ctx = await engine.get_portfolio_context()

        assert "balance" in ctx
        assert "initial_balance" in ctx
        assert ctx["balance"] == pytest.approx(1000.0)
        assert ctx["initial_balance"] == pytest.approx(1000.0)

    async def test_returns_trade_summary_when_no_trades(self, engine):
        """Context should have recent_trades_summary even with no closed trades."""
        ctx = await engine.get_portfolio_context()

        assert "recent_trades_summary" in ctx
        assert "no trades" in ctx["recent_trades_summary"]
