"""Report generation utilities."""

from perpetual_predict.reporters.data_integrity import (
    DataIntegrityResult,
    FearGreedIntegrityResult,
    IntegrityReport,
    verify_data_integrity,
)
from perpetual_predict.reporters.discord_report import create_integrity_report_embed
from perpetual_predict.reporters.markdown_generator import (
    MarkdownReportGenerator,
    ReportData,
    TechnicalIndicator,
    create_report_data,
)

__all__ = [
    # Data integrity
    "DataIntegrityResult",
    "FearGreedIntegrityResult",
    "IntegrityReport",
    "verify_data_integrity",
    "create_integrity_report_embed",
    # Markdown report
    "MarkdownReportGenerator",
    "ReportData",
    "TechnicalIndicator",
    "create_report_data",
]
