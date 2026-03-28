"""Tests for directional label removal from context builder."""

from perpetual_predict.llm.context.builder import MarketContext


class TestTrendSectionDebiasing:
    """Verify _section_trend uses only numbers, no above/below labels."""

    def test_no_above_below_labels(self):
        ctx = MarketContext(
            current_price=70000.0,
            price_change_4h=1.0,
            price_change_24h=2.0,
            high_24h=71000.0,
            low_24h=69000.0,
            volume_24h=50000.0,
            sma_20=69000.0,
            sma_50=68000.0,
            sma_200=65000.0,
            ema_12=69500.0,
            ema_26=69000.0,
            macd=500.0,
            macd_signal=400.0,
            macd_histogram=100.0,
            bb_upper=72000.0,
            bb_middle=70000.0,
            bb_lower=68000.0,
        )
        section = ctx._section_trend()
        assert "above" not in section.lower()
        assert "below" not in section.lower()
        assert "%" in section
        assert "69,000" in section
        assert "68,000" in section
        assert "65,000" in section

    def test_shows_distance_percentages(self):
        ctx = MarketContext(
            current_price=70000.0,
            price_change_4h=0.0,
            price_change_24h=0.0,
            high_24h=70000.0,
            low_24h=70000.0,
            volume_24h=0.0,
            sma_20=69000.0,
            sma_50=68000.0,
            sma_200=65000.0,
            ema_12=69500.0,
            ema_26=69000.0,
            macd=500.0,
            macd_signal=400.0,
            macd_histogram=100.0,
            bb_upper=72000.0,
            bb_middle=70000.0,
            bb_lower=68000.0,
        )
        section = ctx._section_trend()
        assert "+1.45%" in section
        assert "+2.94%" in section
        assert "+7.69%" in section


class TestRecentCandlesDebiasing:
    """Verify _summarize_recent_candles uses neutral pattern names."""

    def _make_summary(self, candle_data):
        import pandas as pd

        from perpetual_predict.llm.context.builder import MarketContextBuilder
        df = pd.DataFrame(candle_data)
        builder = MarketContextBuilder.__new__(MarketContextBuilder)
        return builder._summarize_recent_candles(df)

    def test_no_bullish_bearish_labels(self):
        candles = [
            {"open": 100, "high": 110, "low": 95, "close": 108, "volume": 1000},
            {"open": 108, "high": 112, "low": 100, "close": 102, "volume": 1200},
            {"open": 102, "high": 105, "low": 98, "close": 104, "volume": 900},
        ]
        summary = self._make_summary(candles)
        assert "bullish" not in summary.lower()
        assert "bearish" not in summary.lower()

    def test_no_shooting_star_hanging_man(self):
        candles = [
            {"open": 100, "high": 120, "low": 99, "close": 98, "volume": 1000},
            {"open": 100, "high": 101, "low": 80, "close": 98, "volume": 1000},
        ]
        summary = self._make_summary(candles)
        assert "shooting star" not in summary.lower()
        assert "hanging man" not in summary.lower()

    def test_uses_neutral_pattern_names(self):
        candles = [
            {"open": 100, "high": 110, "low": 90, "close": 100.5, "volume": 1000},
        ]
        summary = self._make_summary(candles)
        assert "Doji" in summary

    def test_wick_descriptions_are_structural(self):
        # body=4, upper_wick=15, body_pct=25% → triggers Long Upper Wick
        candles = [
            {"open": 100, "high": 115, "low": 99, "close": 96, "volume": 1000},
        ]
        summary = self._make_summary(candles)
        assert "Upper Wick" in summary or "Long Upper" in summary

    def test_body_descriptions_are_structural(self):
        candles = [
            {"open": 100, "high": 112, "low": 99, "close": 110, "volume": 1000},
        ]
        summary = self._make_summary(candles)
        assert "+" in summary


class TestEmaDistanceIntegration:
    """Verify EMA distances are integrated into trend section, not separate."""

    def test_trend_section_includes_ema_distances(self):
        ctx = MarketContext(
            current_price=70000.0,
            price_change_4h=0.0,
            price_change_24h=0.0,
            high_24h=70000.0,
            low_24h=70000.0,
            volume_24h=0.0,
            sma_20=69000.0,
            sma_50=68000.0,
            sma_200=65000.0,
            ema_12=69500.0,
            ema_26=69000.0,
            macd=500.0,
            macd_signal=400.0,
            macd_histogram=100.0,
            bb_upper=72000.0,
            bb_middle=70000.0,
            bb_lower=68000.0,
            dist_ema_9=0.45,
            dist_ema_21=-1.22,
            dist_ema_55=-4.82,
            dist_ema_200=-0.12,
        )
        section = ctx._section_trend()

        assert "EMA 9" in section
        assert "EMA 21" in section
        assert "EMA 55" in section
        assert "EMA 200" in section
        assert "+0.45%" in section
        assert "-1.22%" in section

    def test_format_prompt_no_ema_distance_section(self):
        ctx = MarketContext(
            current_price=70000.0,
            price_change_4h=0.0,
            price_change_24h=0.0,
            high_24h=70000.0,
            low_24h=70000.0,
            volume_24h=0.0,
            sma_20=69000.0,
            sma_50=68000.0,
            sma_200=65000.0,
            ema_12=69500.0,
            ema_26=69000.0,
            macd=500.0,
            macd_signal=400.0,
            macd_histogram=100.0,
            bb_upper=72000.0,
            bb_middle=70000.0,
            bb_lower=68000.0,
        )
        prompt = ctx.format_prompt()

        assert "### EMA Distance" not in prompt
        assert "### Trend Indicators" in prompt
