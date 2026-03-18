"""Tests for momentum indicators."""

import numpy as np
import pandas as pd
import pytest

from perpetual_predict.analyzers.technical.momentum import (
    add_momentum_indicators,
    calculate_rsi,
    calculate_stoch_rsi,
)


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    """Create sample OHLCV DataFrame for testing."""
    np.random.seed(42)
    n = 100

    # Generate realistic price data
    close = 42000 + np.cumsum(np.random.randn(n) * 100)
    high = close + np.abs(np.random.randn(n) * 50)
    low = close - np.abs(np.random.randn(n) * 50)
    open_ = close + np.random.randn(n) * 30
    volume = np.random.randint(1000, 10000, n).astype(float)

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


class TestRSI:
    """Tests for RSI calculation."""

    def test_calculate_rsi_default(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test RSI calculation with default period."""
        rsi = calculate_rsi(sample_ohlcv_df)
        assert rsi is not None
        assert len(rsi) == len(sample_ohlcv_df)
        # RSI values should be between 0 and 100
        valid_rsi = rsi.dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

    def test_calculate_rsi_custom_period(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test RSI calculation with custom period."""
        rsi = calculate_rsi(sample_ohlcv_df, period=7)
        assert rsi is not None
        assert len(rsi) == len(sample_ohlcv_df)


class TestStochRSI:
    """Tests for Stochastic RSI calculation."""

    def test_calculate_stoch_rsi_default(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test Stochastic RSI calculation with default parameters."""
        stoch_rsi = calculate_stoch_rsi(sample_ohlcv_df)
        assert stoch_rsi is not None
        assert len(stoch_rsi) == len(sample_ohlcv_df)
        # Check columns exist
        assert any("STOCHRSI" in col for col in stoch_rsi.columns)

    def test_calculate_stoch_rsi_custom_params(
        self, sample_ohlcv_df: pd.DataFrame
    ) -> None:
        """Test Stochastic RSI calculation with custom parameters."""
        stoch_rsi = calculate_stoch_rsi(
            sample_ohlcv_df,
            rsi_period=10,
            stoch_period=10,
            k_period=5,
            d_period=5,
        )
        assert stoch_rsi is not None
        assert len(stoch_rsi) == len(sample_ohlcv_df)


class TestAddMomentumIndicators:
    """Tests for add_momentum_indicators function."""

    def test_add_all_default_indicators(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test adding all momentum indicators with defaults."""
        result = add_momentum_indicators(sample_ohlcv_df)

        # Check original columns preserved
        assert "close" in result.columns
        assert "high" in result.columns

        # Check RSI columns
        assert "RSI_14" in result.columns

        # Check Stochastic RSI columns exist
        stoch_cols = [col for col in result.columns if "STOCHRSI" in col]
        assert len(stoch_cols) >= 1

    def test_add_custom_rsi_periods(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test adding momentum indicators with custom RSI periods."""
        result = add_momentum_indicators(
            sample_ohlcv_df,
            rsi_periods=[7, 21],
        )

        assert "RSI_7" in result.columns
        assert "RSI_21" in result.columns
        assert "RSI_14" not in result.columns

    def test_original_df_unchanged(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test that original DataFrame is not modified."""
        original_cols = list(sample_ohlcv_df.columns)
        add_momentum_indicators(sample_ohlcv_df)
        assert list(sample_ohlcv_df.columns) == original_cols
