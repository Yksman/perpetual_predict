"""Tests for volume indicators."""

import numpy as np
import pandas as pd
import pytest

from perpetual_predict.analyzers.technical.volume import (
    add_volume_indicators,
    calculate_obv,
    calculate_vwap,
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

    # VWAP requires DatetimeIndex
    dates = pd.date_range(start="2024-01-01", periods=n, freq="4h")

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=dates)


class TestOBV:
    """Tests for OBV calculation."""

    def test_calculate_obv(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test OBV calculation."""
        obv = calculate_obv(sample_ohlcv_df)
        assert obv is not None
        assert len(obv) == len(sample_ohlcv_df)

    def test_obv_changes_with_price(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test that OBV changes based on price direction."""
        obv = calculate_obv(sample_ohlcv_df)
        # OBV should not be constant (unless all price changes are same direction)
        assert obv.std() > 0


class TestVWAP:
    """Tests for VWAP calculation."""

    def test_calculate_vwap(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test VWAP calculation."""
        vwap = calculate_vwap(sample_ohlcv_df)
        assert vwap is not None
        assert len(vwap) == len(sample_ohlcv_df)

    def test_vwap_in_price_range(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test that VWAP is within typical price range."""
        vwap = calculate_vwap(sample_ohlcv_df)
        valid_vwap = vwap.dropna()
        # VWAP should be within the general price range
        assert valid_vwap.min() > 0
        assert valid_vwap.max() < sample_ohlcv_df["high"].max() * 2


class TestAddVolumeIndicators:
    """Tests for add_volume_indicators function."""

    def test_add_all_default_indicators(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test adding all volume indicators with defaults."""
        result = add_volume_indicators(sample_ohlcv_df)

        # Check original columns preserved
        assert "close" in result.columns
        assert "volume" in result.columns

        # Check OBV and VWAP columns
        assert "OBV" in result.columns
        assert "VWAP" in result.columns

    def test_add_obv_only(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test adding only OBV indicator."""
        result = add_volume_indicators(
            sample_ohlcv_df,
            include_obv=True,
            include_vwap=False,
        )

        assert "OBV" in result.columns
        assert "VWAP" not in result.columns

    def test_add_vwap_only(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test adding only VWAP indicator."""
        result = add_volume_indicators(
            sample_ohlcv_df,
            include_obv=False,
            include_vwap=True,
        )

        assert "OBV" not in result.columns
        assert "VWAP" in result.columns

    def test_original_df_unchanged(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test that original DataFrame is not modified."""
        original_cols = list(sample_ohlcv_df.columns)
        add_volume_indicators(sample_ohlcv_df)
        assert list(sample_ohlcv_df.columns) == original_cols
