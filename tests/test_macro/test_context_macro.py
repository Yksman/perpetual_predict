"""Tests for _section_macro() in MarketContext."""

from perpetual_predict.llm.context.builder import MarketContext


class TestSectionMacro:
    """Tests for macro section output formatting."""

    def test_full_data(self):
        ctx = MarketContext(
            current_price=67000.0,
            price_change_4h=1.5,
            price_change_24h=3.2,
            high_24h=68000.0,
            low_24h=65000.0,
            volume_24h=50000.0,
            sma_20=66000.0,
            sma_50=64000.0,
            sma_200=60000.0,
            ema_12=66500.0,
            ema_26=65000.0,
            macd=1500.0,
            macd_signal=1200.0,
            macd_histogram=300.0,
            bb_upper=69000.0,
            bb_middle=66000.0,
            bb_lower=63000.0,
            treasury_10y=4.35,
            treasury_2y=4.65,
            treasury_10y_change=0.05,
            yield_spread_10y2y=-0.30,
            fed_funds_rate=5.33,
            spx_value=5800.0,
            spx_change_pct=1.2,
            nasdaq_change_pct=1.5,
            dxy_value=104.52,
            dxy_change_pct=-0.3,
            gold_value=2350.0,
            gold_change_pct=0.8,
        )
        section = ctx._section_macro()

        assert "### Macroeconomic Environment" in section
        assert "4.350%" in section
        assert "4.650%" in section
        assert "-0.300%" in section
        assert "5.33%" in section
        assert "5,800.00" in section
        assert "+1.20%" in section
        assert "+1.50%" in section
        assert "104.52" in section
        assert "-0.30%" in section
        assert "2,350.00" in section
        assert "+0.80%" in section
        # No interpretation text
        assert "bearish" not in section.lower()
        assert "bullish" not in section.lower()
        assert "risk-on" not in section.lower()

    def test_all_none(self):
        ctx = MarketContext(
            current_price=67000.0,
            price_change_4h=1.5,
            price_change_24h=3.2,
            high_24h=68000.0,
            low_24h=65000.0,
            volume_24h=50000.0,
            sma_20=66000.0,
            sma_50=64000.0,
            sma_200=60000.0,
            ema_12=66500.0,
            ema_26=65000.0,
            macd=1500.0,
            macd_signal=1200.0,
            macd_histogram=300.0,
            bb_upper=69000.0,
            bb_middle=66000.0,
            bb_lower=63000.0,
        )
        section = ctx._section_macro()
        # Returns empty string when no macro data
        assert section == ""

    def test_yfinance_only(self):
        """When FRED_API_KEY is not set, only yfinance data is available."""
        ctx = MarketContext(
            current_price=67000.0,
            price_change_4h=1.5,
            price_change_24h=3.2,
            high_24h=68000.0,
            low_24h=65000.0,
            volume_24h=50000.0,
            sma_20=66000.0,
            sma_50=64000.0,
            sma_200=60000.0,
            ema_12=66500.0,
            ema_26=65000.0,
            macd=1500.0,
            macd_signal=1200.0,
            macd_histogram=300.0,
            bb_upper=69000.0,
            bb_middle=66000.0,
            bb_lower=63000.0,
            # Only yfinance data
            spx_value=5800.0,
            spx_change_pct=1.2,
            dxy_value=104.52,
            dxy_change_pct=-0.3,
            gold_value=2350.0,
            gold_change_pct=0.8,
        )
        section = ctx._section_macro()

        assert "### Macroeconomic Environment" in section
        assert "S&P 500" in section
        assert "DXY" in section
        assert "Gold" in section
        # No FRED data
        assert "Treasury" not in section
        assert "Fed Funds" not in section

    def test_module_in_format_prompt(self):
        """Verify 'macro' module is included in format_prompt."""
        ctx = MarketContext(
            current_price=67000.0,
            price_change_4h=1.5,
            price_change_24h=3.2,
            high_24h=68000.0,
            low_24h=65000.0,
            volume_24h=50000.0,
            sma_20=66000.0,
            sma_50=64000.0,
            sma_200=60000.0,
            ema_12=66500.0,
            ema_26=65000.0,
            macd=1500.0,
            macd_signal=1200.0,
            macd_histogram=300.0,
            bb_upper=69000.0,
            bb_middle=66000.0,
            bb_lower=63000.0,
            dxy_value=104.52,
            dxy_change_pct=-0.3,
        )
        # With macro module enabled
        prompt_with = ctx.format_prompt(enabled_modules=["macro"])
        assert "DXY" in prompt_with

        # Without macro module
        prompt_without = ctx.format_prompt(enabled_modules=["price_action"])
        assert "DXY" not in prompt_without
