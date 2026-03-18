"""Tests for support/resistance analysis."""

import numpy as np
import pandas as pd
import pytest

from perpetual_predict.analyzers.technical.support_resistance import (
    add_support_resistance_indicators,
    calculate_nearest_levels,
    find_pivot_points,
    find_support_resistance_levels,
)


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    """Create sample OHLCV DataFrame for testing."""
    np.random.seed(42)
    n = 100

    # Generate price data with clear swing highs/lows
    base = 42000
    trend = np.cumsum(np.random.randn(n) * 50)
    # Add some oscillation to create pivots
    oscillation = 200 * np.sin(np.linspace(0, 4 * np.pi, n))
    close = base + trend + oscillation

    high = close + np.abs(np.random.randn(n) * 30)
    low = close - np.abs(np.random.randn(n) * 30)
    open_ = close + np.random.randn(n) * 20
    volume = np.random.randint(1000, 10000, n).astype(float)

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


class TestFindPivotPoints:
    """Tests for pivot point detection."""

    def test_find_pivot_points_returns_series(
        self, sample_ohlcv_df: pd.DataFrame
    ) -> None:
        """Test that pivot points returns two series."""
        pivot_highs, pivot_lows = find_pivot_points(sample_ohlcv_df)
        assert isinstance(pivot_highs, pd.Series)
        assert isinstance(pivot_lows, pd.Series)
        assert len(pivot_highs) == len(sample_ohlcv_df)
        assert len(pivot_lows) == len(sample_ohlcv_df)

    def test_find_pivot_points_detects_pivots(
        self, sample_ohlcv_df: pd.DataFrame
    ) -> None:
        """Test that pivot points are detected."""
        pivot_highs, pivot_lows = find_pivot_points(sample_ohlcv_df)
        # Should detect some pivot points
        assert pivot_highs.notna().sum() > 0
        assert pivot_lows.notna().sum() > 0

    def test_find_pivot_points_custom_bars(
        self, sample_ohlcv_df: pd.DataFrame
    ) -> None:
        """Test pivot detection with custom bar settings."""
        pivot_highs, pivot_lows = find_pivot_points(
            sample_ohlcv_df, left_bars=3, right_bars=3
        )
        # More pivots with smaller window
        assert pivot_highs.notna().sum() > 0


class TestFindSupportResistanceLevels:
    """Tests for support/resistance level detection."""

    def test_returns_dict_with_keys(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test that result has correct structure."""
        levels = find_support_resistance_levels(sample_ohlcv_df)
        assert isinstance(levels, dict)
        assert "support" in levels
        assert "resistance" in levels
        assert isinstance(levels["support"], list)
        assert isinstance(levels["resistance"], list)

    def test_levels_are_sorted(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test that levels are sorted ascending."""
        levels = find_support_resistance_levels(sample_ohlcv_df, min_touches=1)
        if levels["support"]:
            assert levels["support"] == sorted(levels["support"])
        if levels["resistance"]:
            assert levels["resistance"] == sorted(levels["resistance"])

    def test_min_touches_filtering(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test that min_touches filters out weak levels."""
        levels_1 = find_support_resistance_levels(sample_ohlcv_df, min_touches=1)
        levels_2 = find_support_resistance_levels(sample_ohlcv_df, min_touches=2)
        # Stricter filtering should result in fewer or equal levels
        assert len(levels_2["support"]) <= len(levels_1["support"])
        assert len(levels_2["resistance"]) <= len(levels_1["resistance"])


class TestCalculateNearestLevels:
    """Tests for nearest level calculation."""

    def test_finds_nearest_support(self) -> None:
        """Test finding nearest support level."""
        levels = {
            "support": [40000.0, 41000.0, 41500.0],
            "resistance": [43000.0, 44000.0],
        }
        result = calculate_nearest_levels(42000.0, levels)
        assert result["nearest_support"] == 41500.0

    def test_finds_nearest_resistance(self) -> None:
        """Test finding nearest resistance level."""
        levels = {
            "support": [40000.0, 41000.0],
            "resistance": [42500.0, 43000.0, 44000.0],
        }
        result = calculate_nearest_levels(42000.0, levels)
        assert result["nearest_resistance"] == 42500.0

    def test_handles_no_levels_below(self) -> None:
        """Test when no support levels exist below price."""
        levels = {
            "support": [43000.0, 44000.0],
            "resistance": [45000.0],
        }
        result = calculate_nearest_levels(42000.0, levels)
        assert result["nearest_support"] is None

    def test_handles_no_levels_above(self) -> None:
        """Test when no resistance levels exist above price."""
        levels = {
            "support": [40000.0],
            "resistance": [41000.0, 41500.0],
        }
        result = calculate_nearest_levels(42000.0, levels)
        assert result["nearest_resistance"] is None


class TestAddSupportResistanceIndicators:
    """Tests for add_support_resistance_indicators function."""

    def test_adds_pivot_columns(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test adding pivot columns to DataFrame."""
        result = add_support_resistance_indicators(sample_ohlcv_df)

        assert "pivot_high" in result.columns
        assert "pivot_low" in result.columns

    def test_preserves_original_columns(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test that original columns are preserved."""
        result = add_support_resistance_indicators(sample_ohlcv_df)

        assert "close" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns

    def test_original_df_unchanged(self, sample_ohlcv_df: pd.DataFrame) -> None:
        """Test that original DataFrame is not modified."""
        original_cols = list(sample_ohlcv_df.columns)
        add_support_resistance_indicators(sample_ohlcv_df)
        assert list(sample_ohlcv_df.columns) == original_cols
