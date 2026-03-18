"""Tests for Markdown report generator."""

from pathlib import Path

import pytest

from perpetual_predict.reporters.markdown_generator import (
    MarkdownReportGenerator,
    ReportData,
    TechnicalIndicator,
    create_report_data,
)


@pytest.fixture
def sample_report_data() -> ReportData:
    """Create sample report data for testing."""
    return ReportData(
        report_time="2024-01-01 12:00:00 UTC",
        symbol="BTCUSDT",
        timeframe="4h",
        current_price=42000.0,
        price_change_24h=2.5,
        high_24h=42500.0,
        low_24h=41000.0,
        volume_24h=1000000.0,
        trend_indicators=[
            TechnicalIndicator(name="SMA_20", value=41500.0, signal="Bullish"),
            TechnicalIndicator(name="EMA_12", value=41800.0, signal="Bullish"),
        ],
        momentum_indicators=[
            TechnicalIndicator(name="RSI_14", value=55.0, signal="Neutral"),
        ],
        volatility_indicators=[
            TechnicalIndicator(name="ATR_14", value=500.0),
        ],
        support_levels=[40000.0, 39000.0],
        resistance_levels=[43000.0, 44000.0],
        nearest_support=40000.0,
        nearest_resistance=43000.0,
        funding_rate=0.01,
        next_funding_time="2024-01-01 16:00:00 UTC",
        open_interest=50000.0,
        oi_change_24h=5.0,
        long_short_ratio=1.2,
        fear_greed_value=45,
        fear_greed_classification="Fear",
        summary="Market is showing bullish momentum.",
    )


class TestMarkdownReportGenerator:
    """Tests for MarkdownReportGenerator."""

    def test_generate_returns_string(self, sample_report_data: ReportData) -> None:
        """Test that generate returns a string."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_contains_symbol(self, sample_report_data: ReportData) -> None:
        """Test that report contains symbol."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        assert "BTCUSDT" in result

    def test_generate_contains_price(self, sample_report_data: ReportData) -> None:
        """Test that report contains current price."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        assert "42000.00" in result

    def test_generate_contains_indicators(
        self, sample_report_data: ReportData
    ) -> None:
        """Test that report contains technical indicators."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        assert "SMA_20" in result
        assert "RSI_14" in result
        assert "ATR_14" in result

    def test_generate_contains_support_resistance(
        self, sample_report_data: ReportData
    ) -> None:
        """Test that report contains S/R levels."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        assert "40000.00" in result
        assert "43000.00" in result

    def test_generate_contains_sentiment(
        self, sample_report_data: ReportData
    ) -> None:
        """Test that report contains sentiment data."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        assert "45" in result
        assert "Fear" in result

    def test_generate_to_file(
        self, sample_report_data: ReportData, tmp_path: Path
    ) -> None:
        """Test saving report to file."""
        generator = MarkdownReportGenerator()
        output_path = tmp_path / "report.md"

        result_path = generator.generate_to_file(sample_report_data, output_path)

        assert result_path == output_path
        assert output_path.exists()
        content = output_path.read_text()
        assert "BTCUSDT" in content

    def test_generate_to_file_creates_directory(
        self, sample_report_data: ReportData, tmp_path: Path
    ) -> None:
        """Test that generate_to_file creates parent directory."""
        generator = MarkdownReportGenerator()
        output_path = tmp_path / "subdir" / "report.md"

        generator.generate_to_file(sample_report_data, output_path)

        assert output_path.exists()


class TestCreateReportData:
    """Tests for create_report_data helper."""

    def test_creates_with_defaults(self) -> None:
        """Test creating report data with defaults."""
        data = create_report_data()
        assert data.symbol == "BTCUSDT"
        assert data.timeframe == "4h"
        assert data.current_price == 0.0
        assert len(data.trend_indicators) == 0

    def test_creates_with_custom_values(self) -> None:
        """Test creating report data with custom values."""
        data = create_report_data(
            symbol="ETHUSDT",
            current_price=2000.0,
            fear_greed_value=75,
        )
        assert data.symbol == "ETHUSDT"
        assert data.current_price == 2000.0
        assert data.fear_greed_value == 75

    def test_report_time_is_set(self) -> None:
        """Test that report_time is automatically set."""
        data = create_report_data()
        assert data.report_time
        assert "UTC" in data.report_time


class TestTechnicalIndicator:
    """Tests for TechnicalIndicator dataclass."""

    def test_create_with_signal(self) -> None:
        """Test creating indicator with signal."""
        indicator = TechnicalIndicator(
            name="RSI_14",
            value=65.5,
            signal="Overbought",
        )
        assert indicator.name == "RSI_14"
        assert indicator.value == 65.5
        assert indicator.signal == "Overbought"

    def test_create_without_signal(self) -> None:
        """Test creating indicator without signal."""
        indicator = TechnicalIndicator(name="ATR_14", value=100.0)
        assert indicator.name == "ATR_14"
        assert indicator.value == 100.0
        assert indicator.signal == ""
