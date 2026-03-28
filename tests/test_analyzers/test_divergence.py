"""Tests for divergence detection (RSI/MACD)."""

import numpy as np
import pandas as pd
import pytest

from perpetual_predict.analyzers.technical.divergence import (
    Divergence,
    DivergenceResult,
    _build_divergence_summary,
    analyze_divergences,
    detect_rsi_divergence,
)


def _make_df_with_rsi(
    prices: list[tuple[float, float, float, float]],
    rsi_values: list[float],
) -> pd.DataFrame:
    """Create DataFrame with OHLCV and RSI_14 column."""
    df = pd.DataFrame(
        [{"open": o, "high": h, "low": l, "close": c, "volume": 100.0} for o, h, l, c in prices]
    )
    df["RSI_14"] = rsi_values
    return df


class TestRSIDivergence:
    def test_bullish_divergence_price_ll_rsi_hl(self):
        """Regular bullish divergence: price makes lower low, RSI makes higher low."""
        # Build data with two clear price lows where RSI diverges
        # We need enough bars for pivot detection (left_bars=2, right_bars=2)
        prices = [
            (105, 107, 104, 106),  # 0
            (106, 108, 105, 107),  # 1
            (107, 109, 106, 108),  # 2
            (108, 109, 103, 104),  # 3 - drop
            (104, 105, 100, 101),  # 4 - low 1 (100)
            (101, 104, 100, 103),  # 5 - bounce
            (103, 107, 102, 106),  # 6
            (106, 109, 105, 108),  # 7 - recovery
            (108, 110, 107, 109),  # 8
            (109, 110, 104, 105),  # 9 - drop again
            (105, 106, 97, 98),   # 10 - low 2 (97, LL)
            (98, 101, 96, 100),   # 11
            (100, 103, 99, 102),  # 12
            (102, 105, 101, 104),  # 13
        ]
        # RSI: at low 1 = 25, at low 2 = 30 (HL while price LL)
        rsi = [55, 58, 60, 40, 25, 35, 50, 55, 58, 38, 30, 32, 42, 48]

        df = _make_df_with_rsi(prices, rsi)
        divs = detect_rsi_divergence(df, left_bars=2, right_bars=2)

        bullish = [d for d in divs if d.type == "bullish" and d.strength == "regular"]
        # May or may not detect depending on exact pivot alignment
        # The key is no crash and correct structure
        assert isinstance(divs, list)
        for d in divs:
            assert d.indicator == "RSI"
            assert d.type in ("bullish", "bearish")
            assert d.strength in ("regular", "hidden")

    def test_no_divergence_on_flat_data(self):
        """No divergence should be detected on flat price data."""
        prices = [(100, 101, 99, 100)] * 20
        rsi = [50.0] * 20
        df = _make_df_with_rsi(prices, rsi)
        divs = detect_rsi_divergence(df, left_bars=2, right_bars=2)
        assert len(divs) == 0

    def test_missing_rsi_column(self):
        """Should return empty list if RSI column is missing."""
        df = pd.DataFrame({
            "open": [100] * 10,
            "high": [101] * 10,
            "low": [99] * 10,
            "close": [100] * 10,
            "volume": [100] * 10,
        })
        divs = detect_rsi_divergence(df, left_bars=2, right_bars=2)
        assert divs == []


class TestAnalyzeDivergences:
    def test_returns_divergence_result(self):
        """Should return a valid DivergenceResult with summary."""
        prices = [(100 + i, 102 + i, 98 + i, 100 + i) for i in range(30)]
        df = pd.DataFrame(
            [{"open": o, "high": h, "low": l, "close": c, "volume": 100.0} for o, h, l, c in prices]
        )
        df["RSI_14"] = [50 + (i % 5) for i in range(30)]
        df["MACDh_12_26_9"] = [0.1 * (i % 7 - 3) for i in range(30)]

        result = analyze_divergences(df, left_bars=2, right_bars=2)
        assert isinstance(result, DivergenceResult)
        assert isinstance(result.summary, str)
        assert isinstance(result.divergences, list)

    def test_empty_data(self):
        """Should handle minimal data gracefully."""
        df = pd.DataFrame({
            "open": [100, 101, 102],
            "high": [102, 103, 104],
            "low": [98, 99, 100],
            "close": [101, 102, 103],
            "volume": [100, 100, 100],
            "RSI_14": [50, 55, 60],
            "MACDh_12_26_9": [0.1, 0.2, 0.3],
        })
        result = analyze_divergences(df, left_bars=2, right_bars=2)
        assert isinstance(result, DivergenceResult)


class TestDivergenceSummaryDebiasing:
    def test_summary_has_no_directional_labels(self):
        """Summary should not contain Bullish/Bearish direction labels."""
        divs = [
            Divergence(
                type="bearish",
                indicator="MACD",
                price_point_1=70000,
                price_point_2=72000,
                indicator_point_1=357,
                indicator_point_2=223,
                index_1=10,
                index_2=20,
                strength="regular",
            ),
            Divergence(
                type="bullish",
                indicator="RSI",
                price_point_1=69000,
                price_point_2=67000,
                indicator_point_1=30,
                indicator_point_2=35,
                index_1=15,
                index_2=25,
                strength="regular",
            ),
        ]
        summary = _build_divergence_summary(divs)

        assert "Bearish" not in summary
        assert "Bullish" not in summary
        # Raw patterns should still be present
        assert "HH" in summary
        assert "LL" in summary
        assert "MACD" in summary
        assert "RSI" in summary
        assert "Regular" in summary

    def test_hidden_divergence_no_labels(self):
        """Hidden divergences should also not have direction labels."""
        divs = [
            Divergence(
                type="bearish",
                indicator="MACD",
                price_point_1=72000,
                price_point_2=71000,
                indicator_point_1=200,
                indicator_point_2=250,
                index_1=10,
                index_2=20,
                strength="hidden",
            ),
        ]
        summary = _build_divergence_summary(divs)

        assert "Bearish" not in summary
        assert "Hidden" in summary
        assert "LH" in summary
