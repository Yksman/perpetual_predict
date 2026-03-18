"""Markdown report generator using Jinja2 templates."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)

# Default template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"


@dataclass
class TechnicalIndicator:
    """Technical indicator data for report."""

    name: str
    value: float
    signal: str = ""


@dataclass
class ReportData:
    """Data structure for analysis report."""

    # Basic info
    report_time: str
    symbol: str
    timeframe: str

    # Price data
    current_price: float
    price_change_24h: float
    high_24h: float
    low_24h: float
    volume_24h: float

    # Technical indicators
    trend_indicators: list[TechnicalIndicator]
    momentum_indicators: list[TechnicalIndicator]
    volatility_indicators: list[TechnicalIndicator]

    # Support/Resistance
    support_levels: list[float]
    resistance_levels: list[float]
    nearest_support: float | None = None
    nearest_resistance: float | None = None

    # Market data
    funding_rate: float = 0.0
    next_funding_time: str = ""
    open_interest: float = 0.0
    oi_change_24h: float = 0.0
    long_short_ratio: float = 1.0

    # Sentiment
    fear_greed_value: int = 50
    fear_greed_classification: str = "Neutral"

    # Summary
    summary: str = ""


class MarkdownReportGenerator:
    """Generates Markdown reports from analysis data."""

    def __init__(
        self,
        template_dir: Path | None = None,
        template_name: str = "analysis_report.md.j2",
    ) -> None:
        """Initialize the report generator.

        Args:
            template_dir: Directory containing Jinja2 templates.
            template_name: Name of the template file.
        """
        self.template_dir = template_dir or TEMPLATE_DIR
        self.template_name = template_name

        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=False,
        )

    def generate(self, data: ReportData) -> str:
        """Generate a Markdown report from data.

        Args:
            data: Report data structure.

        Returns:
            Generated Markdown string.
        """
        template = self.env.get_template(self.template_name)

        # Convert dataclass to dict for template
        context = {
            "report_time": data.report_time,
            "symbol": data.symbol,
            "timeframe": data.timeframe,
            "current_price": data.current_price,
            "price_change_24h": data.price_change_24h,
            "high_24h": data.high_24h,
            "low_24h": data.low_24h,
            "volume_24h": data.volume_24h,
            "trend_indicators": data.trend_indicators,
            "momentum_indicators": data.momentum_indicators,
            "volatility_indicators": data.volatility_indicators,
            "support_levels": data.support_levels,
            "resistance_levels": data.resistance_levels,
            "nearest_support": data.nearest_support,
            "nearest_resistance": data.nearest_resistance,
            "funding_rate": data.funding_rate,
            "next_funding_time": data.next_funding_time,
            "open_interest": data.open_interest,
            "oi_change_24h": data.oi_change_24h,
            "long_short_ratio": data.long_short_ratio,
            "fear_greed_value": data.fear_greed_value,
            "fear_greed_classification": data.fear_greed_classification,
            "summary": data.summary,
        }

        report = template.render(**context)
        logger.debug(f"Generated report for {data.symbol}")
        return report

    def generate_to_file(
        self,
        data: ReportData,
        output_path: Path,
    ) -> Path:
        """Generate a report and save to file.

        Args:
            data: Report data structure.
            output_path: Path to save the report.

        Returns:
            Path to the generated report file.
        """
        report = self.generate(data)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")

        logger.info(f"Report saved to {output_path}")
        return output_path


def create_report_data(
    symbol: str = "BTCUSDT",
    timeframe: str = "4h",
    current_price: float = 0.0,
    price_change_24h: float = 0.0,
    high_24h: float = 0.0,
    low_24h: float = 0.0,
    volume_24h: float = 0.0,
    trend_indicators: list[TechnicalIndicator] | None = None,
    momentum_indicators: list[TechnicalIndicator] | None = None,
    volatility_indicators: list[TechnicalIndicator] | None = None,
    support_levels: list[float] | None = None,
    resistance_levels: list[float] | None = None,
    nearest_support: float | None = None,
    nearest_resistance: float | None = None,
    funding_rate: float = 0.0,
    next_funding_time: str = "",
    open_interest: float = 0.0,
    oi_change_24h: float = 0.0,
    long_short_ratio: float = 1.0,
    fear_greed_value: int = 50,
    fear_greed_classification: str = "Neutral",
    summary: str = "",
) -> ReportData:
    """Create a ReportData instance with sensible defaults.

    Args:
        All report data fields with defaults.

    Returns:
        ReportData instance.
    """
    return ReportData(
        report_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        symbol=symbol,
        timeframe=timeframe,
        current_price=current_price,
        price_change_24h=price_change_24h,
        high_24h=high_24h,
        low_24h=low_24h,
        volume_24h=volume_24h,
        trend_indicators=trend_indicators or [],
        momentum_indicators=momentum_indicators or [],
        volatility_indicators=volatility_indicators or [],
        support_levels=support_levels or [],
        resistance_levels=resistance_levels or [],
        nearest_support=nearest_support,
        nearest_resistance=nearest_resistance,
        funding_rate=funding_rate,
        next_funding_time=next_funding_time,
        open_interest=open_interest,
        oi_change_24h=oi_change_24h,
        long_short_ratio=long_short_ratio,
        fear_greed_value=fear_greed_value,
        fear_greed_classification=fear_greed_classification,
        summary=summary,
    )
