"""Tests for volatility indicators."""

import numpy as np
import pandas as pd
import pytest

from perpetual_predict.analyzers.technical.volatility import (
    add_volatility_indicators,
    calculate_atr,
    calculate_bollinger_bands,
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


class TestBollingerBands:
    """Tests for Bollinger Bands calculation."""

    def test_calculate_bb_default(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test Bollinger Bands calculation with default parameters."""
        bb = calculate_bollinger_bands(sample_ohlcv_df)
        assert bb is not None
        assert len(bb) == len(sample_ohlcv_df)
        # Check columns exist
        assert any("BBL" in col for col in bb.columns)  # Lower band
        assert any("BBM" in col for col in bb.columns)  # Middle band
        assert any("BBU" in col for col in bb.columns)  # Upper band

    def test_calculate_bb_custom_params(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test Bollinger Bands calculation with custom parameters."""
        bb = calculate_bollinger_bands(sample_ohlcv_df, period=10, std_dev=1.5)
        assert bb is not None
        assert len(bb) == len(sample_ohlcv_df)

    def test_bb_band_order(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test that lower < middle < upper band."""
        bb = calculate_bollinger_bands(sample_ohlcv_df)
        # Get valid (non-NaN) rows
        bb_clean = bb.dropna()

        lower_col = [col for col in bb.columns if "BBL" in col][0]
        middle_col = [col for col in bb.columns if "BBM" in col][0]
        upper_col = [col for col in bb.columns if "BBU" in col][0]

        assert (bb_clean[lower_col] <= bb_clean[middle_col]).all()
        assert (bb_clean[middle_col] <= bb_clean[upper_col]).all()


class TestATR:
    """Tests for ATR calculation."""

    def test_calculate_atr_default(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test ATR calculation with default period."""
        atr = calculate_atr(sample_ohlcv_df)
        assert atr is not None
        assert len(atr) == len(sample_ohlcv_df)
        # ATR should be positive
        valid_atr = atr.dropna()
        assert (valid_atr >= 0).all()

    def test_calculate_atr_custom_period(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test ATR calculation with custom period."""
        atr = calculate_atr(sample_ohlcv_df, period=7)
        assert atr is not None
        assert len(atr) == len(sample_ohlcv_df)


class TestAddVolatilityIndicators:
    """Tests for add_volatility_indicators function."""

    def test_add_all_default_indicators(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test adding all volatility indicators with defaults."""
        result = add_volatility_indicators(sample_ohlcv_df)

        # Check original columns preserved
        assert "close" in result.columns
        assert "high" in result.columns

        # Check Bollinger Bands columns exist
        bb_cols = [col for col in result.columns if "BB" in col]
        assert len(bb_cols) >= 3  # At least lower, middle, upper

        # Check ATR columns
        assert "ATR_14" in result.columns

    def test_add_custom_periods(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test adding volatility indicators with custom periods."""
        result = add_volatility_indicators(
            sample_ohlcv_df,
            bb_periods=[10],
            atr_periods=[7, 21],
        )

        # Check custom ATR periods
        assert "ATR_7" in result.columns
        assert "ATR_21" in result.columns
        assert "ATR_14" not in result.columns

    def test_original_df_unchanged(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test that original DataFrame is not modified."""
        original_cols = list(sample_ohlcv_df.columns)
        add_volatility_indicators(sample_ohlcv_df)
        assert list(sample_ohlcv_df.columns) == original_cols
