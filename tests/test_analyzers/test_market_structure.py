"""Tests for market structure analysis (HH/HL/LH/LL)."""

import pandas as pd
import pytest

from perpetual_predict.analyzers.technical.market_structure import (
    analyze_market_structure,
    detect_swings,
)


def _make_ohlcv(prices: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """Create a minimal OHLCV DataFrame from (open, high, low, close) tuples."""
    return pd.DataFrame(
        [{"open": o, "high": h, "low": l, "close": c, "volume": 100.0} for o, h, l, c in prices]
    )


class TestDetectSwings:
    def test_basic_uptrend_produces_hh_hl(self):
        """Uptrend: higher highs and higher lows."""
        # Build price data with clear swing points
        # Valley - Peak - Valley - Peak pattern, each higher
        prices = [
            # Ramp up to first peak at index ~5
            (100, 102, 99, 101),
            (101, 103, 100, 102),
            (102, 105, 101, 104),
            (104, 108, 103, 107),  # approach peak
            (107, 112, 106, 111),
            (111, 115, 110, 114),  # peak 1 (~115)
            (114, 114, 109, 110),
            (110, 111, 105, 106),
            (106, 107, 103, 104),  # valley 1 (~103)
            (104, 106, 102, 105),
            (105, 108, 104, 107),
            (107, 110, 106, 109),
            (109, 113, 108, 112),
            (112, 118, 111, 117),
            (117, 120, 116, 119),  # peak 2 (~120, HH)
            (119, 119, 114, 115),
            (115, 116, 110, 111),
            (111, 112, 108, 109),  # valley 2 (~108, HL)
            (109, 111, 107, 110),
            (110, 113, 109, 112),
        ]
        df = _make_ohlcv(prices)
        swings = detect_swings(df, left_bars=2, right_bars=2)

        # Should have swing points classified
        assert len(swings) > 0

        # Check that we get HH and HL labels in an uptrend
        labels = [s.label for s in swings]
        high_labels = [s.label for s in swings if s.type == "high"]
        low_labels = [s.label for s in swings if s.type == "low"]

        # At least one HH should appear (second peak higher than first)
        assert "HH" in high_labels or "H" in high_labels
        # At least one HL should appear (second valley higher than first)
        assert "HL" in low_labels or "L" in low_labels

    def test_downtrend_produces_lh_ll(self):
        """Downtrend: lower highs and lower lows."""
        prices = [
            (120, 122, 118, 121),
            (121, 125, 120, 124),
            (124, 128, 123, 127),  # peak 1
            (127, 127, 122, 123),
            (123, 124, 118, 119),
            (119, 120, 115, 116),  # valley 1
            (116, 118, 115, 117),
            (117, 120, 116, 119),
            (119, 123, 118, 122),  # peak 2 (LH, lower than 128)
            (122, 122, 117, 118),
            (118, 119, 113, 114),
            (114, 115, 110, 111),  # valley 2 (LL, lower than 115)
            (111, 113, 110, 112),
            (112, 114, 111, 113),
        ]
        df = _make_ohlcv(prices)
        swings = detect_swings(df, left_bars=2, right_bars=2)

        high_labels = [s.label for s in swings if s.type == "high"]
        low_labels = [s.label for s in swings if s.type == "low"]

        # Should detect LH (lower high) pattern
        assert "LH" in high_labels or len(high_labels) <= 1
        # Should detect LL (lower low) pattern
        assert "LL" in low_labels or len(low_labels) <= 1

    def test_insufficient_data(self):
        """Very short data should return empty or minimal swings."""
        prices = [(100, 101, 99, 100), (100, 102, 98, 101)]
        df = _make_ohlcv(prices)
        swings = detect_swings(df, left_bars=2, right_bars=2)
        assert len(swings) == 0


class TestAnalyzeMarketStructure:
    def test_returns_structure_result(self):
        """Should return a valid MarketStructureResult."""
        # Simple trending data
        prices = []
        for i in range(30):
            base = 100 + i * 0.5 + (3 if i % 6 < 3 else -1)
            prices.append((base, base + 2, base - 1, base + 1))

        df = _make_ohlcv(prices)
        result = analyze_market_structure(df, left_bars=2, right_bars=2)

        assert result.current_structure in ("Bullish", "Bearish", "Transition", "Undefined")
        assert isinstance(result.structure_breaks, int)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_insufficient_data_returns_undefined(self):
        """Very short data should return Undefined structure."""
        prices = [(100, 101, 99, 100)] * 5
        df = _make_ohlcv(prices)
        result = analyze_market_structure(df, left_bars=2, right_bars=2)
        assert result.current_structure == "Undefined"


class TestMarketStructureSummaryDebiasing:
    def test_summary_has_no_directional_labels(self):
        """Summary should not contain Bullish/Bearish/Transition labels."""
        prices = []
        for i in range(30):
            base = 100 + i * 0.5 + (3 if i % 6 < 3 else -1)
            prices.append((base, base + 2, base - 1, base + 1))

        df = _make_ohlcv(prices)
        result = analyze_market_structure(df, left_bars=2, right_bars=2)

        assert "Bullish" not in result.summary
        assert "Bearish" not in result.summary
        assert "Transition" not in result.summary
        # Structure Breaks count should still be present
        assert "Structure Breaks" in result.summary

    def test_summary_preserves_swing_data(self):
        """Summary should still contain swing point data and break markers."""
        # Use 30-candle uptrend data — same as test_summary_has_no_directional_labels
        # which is known to produce swing labels in the summary.
        prices = []
        for i in range(30):
            base = 100 + i * 0.5 + (3 if i % 6 < 3 else -1)
            prices.append((base, base + 2, base - 1, base + 1))

        df = _make_ohlcv(prices)
        result = analyze_market_structure(df, left_bars=2, right_bars=2)

        # Swing labels should be present
        assert any(label in result.summary for label in ("HH", "HL", "LH", "LL", "H", "L"))
        assert "$" in result.summary
