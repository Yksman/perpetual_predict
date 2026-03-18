"""Tests for trend indicators."""

import numpy as np
import pandas as pd
import pytest

from perpetual_predict.analyzers.technical.trend import (
    add_trend_indicators,
    calculate_adx,
    calculate_ema,
    calculate_macd,
    calculate_sma,
)


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    """Create sample OHLCV DataFrame for testing."""
    np.random.seed(42)
    n = 250  # Enough for SMA_200 calculation

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


class TestSMA:
    """Tests for SMA calculation."""

    def test_calculate_sma_default(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test SMA calculation with default period."""
        sma = calculate_sma(sample_ohlcv_df)
        assert sma is not None
        assert len(sma) == len(sample_ohlcv_df)
        # First 19 values should be NaN for period 20
        assert pd.isna(sma.iloc[:19]).all()
        assert not pd.isna(sma.iloc[19:]).any()

    def test_calculate_sma_custom_period(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test SMA calculation with custom period."""
        sma = calculate_sma(sample_ohlcv_df, period=10)
        assert sma is not None
        # First 9 values should be NaN for period 10
        assert pd.isna(sma.iloc[:9]).all()
        assert not pd.isna(sma.iloc[9:]).any()


class TestEMA:
    """Tests for EMA calculation."""

    def test_calculate_ema_default(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test EMA calculation with default period."""
        ema = calculate_ema(sample_ohlcv_df)
        assert ema is not None
        assert len(ema) == len(sample_ohlcv_df)

    def test_calculate_ema_custom_period(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test EMA calculation with custom period."""
        ema = calculate_ema(sample_ohlcv_df, period=50)
        assert ema is not None
        assert len(ema) == len(sample_ohlcv_df)


class TestMACD:
    """Tests for MACD calculation."""

    def test_calculate_macd_default(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test MACD calculation with default parameters."""
        macd_df = calculate_macd(sample_ohlcv_df)
        assert macd_df is not None
        assert len(macd_df) == len(sample_ohlcv_df)
        # Check columns exist
        assert any("MACD" in col for col in macd_df.columns)

    def test_calculate_macd_custom_params(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test MACD calculation with custom parameters."""
        macd_df = calculate_macd(sample_ohlcv_df, fast=8, slow=21, signal=5)
        assert macd_df is not None
        assert len(macd_df) == len(sample_ohlcv_df)


class TestADX:
    """Tests for ADX calculation."""

    def test_calculate_adx_default(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test ADX calculation with default period."""
        adx_df = calculate_adx(sample_ohlcv_df)
        assert adx_df is not None
        assert len(adx_df) == len(sample_ohlcv_df)
        # Check columns exist
        assert any("ADX" in col for col in adx_df.columns)

    def test_calculate_adx_custom_period(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test ADX calculation with custom period."""
        adx_df = calculate_adx(sample_ohlcv_df, period=20)
        assert adx_df is not None


class TestAddTrendIndicators:
    """Tests for add_trend_indicators function."""

    def test_add_all_default_indicators(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test adding all trend indicators with defaults."""
        result = add_trend_indicators(sample_ohlcv_df)

        # Check original columns preserved
        assert "close" in result.columns
        assert "high" in result.columns

        # Check SMA columns
        assert "SMA_20" in result.columns
        assert "SMA_50" in result.columns
        assert "SMA_200" in result.columns

        # Check EMA columns
        assert "EMA_12" in result.columns
        assert "EMA_26" in result.columns

        # Check MACD columns exist
        macd_cols = [col for col in result.columns if "MACD" in col]
        assert len(macd_cols) >= 1

        # Check ADX columns exist
        adx_cols = [col for col in result.columns if "ADX" in col]
        assert len(adx_cols) >= 1

    def test_add_custom_sma_periods(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test adding trend indicators with custom SMA periods."""
        result = add_trend_indicators(
            sample_ohlcv_df,
            sma_periods=[10, 30],
            ema_periods=[],
        )

        assert "SMA_10" in result.columns
        assert "SMA_30" in result.columns
        assert "SMA_20" not in result.columns

    def test_original_df_unchanged(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test that original DataFrame is not modified."""
        original_cols = list(sample_ohlcv_df.columns)
        add_trend_indicators(sample_ohlcv_df)
        assert list(sample_ohlcv_df.columns) == original_cols
