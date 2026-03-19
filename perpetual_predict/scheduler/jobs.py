"""Scheduled job definitions for data collection and reporting."""

from typing import TYPE_CHECKING

from perpetual_predict.collectors.binance import (
    FundingRateCollector,
    LiquidationCollector,
    LongShortRatioCollector,
    OHLCVCollector,
    OpenInterestCollector,
)
from perpetual_predict.collectors.news import CryptoPanicCollector
from perpetual_predict.collectors.onchain import WhaleAlertCollector
from perpetual_predict.collectors.sentiment import FearGreedCollector
from perpetual_predict.reporters.markdown_generator import MarkdownReportGenerator
from perpetual_predict.storage.database import Database
from perpetual_predict.utils import get_logger

if TYPE_CHECKING:
    from perpetual_predict.scheduler.scheduler import SchedulerManager

logger = get_logger(__name__)


async def collection_job(database: Database) -> None:
    """Run all data collectors and store results.

    Args:
        database: Database instance for storing collected data.
    """
    logger.info("Starting scheduled data collection")

    collectors = [
        ("OHLCV", OHLCVCollector()),
        ("FundingRate", FundingRateCollector()),
        ("OpenInterest", OpenInterestCollector()),
        ("LongShortRatio", LongShortRatioCollector()),
        ("Liquidation", LiquidationCollector()),
        ("FearGreed", FearGreedCollector()),
        ("WhaleAlert", WhaleAlertCollector()),
        ("CryptoPanic", CryptoPanicCollector()),
    ]

    for name, collector in collectors:
        try:
            logger.info(f"Collecting {name} data...")
            data = await collector.collect()

            if data:
                # Store data based on collector type
                if name == "OHLCV":
                    await database.insert_candles(data)
                elif name == "FundingRate":
                    await database.insert_funding_rates(data)
                elif name == "OpenInterest":
                    await database.insert_open_interests(data)
                elif name == "LongShortRatio":
                    await database.insert_long_short_ratios(data)
                elif name == "Liquidation":
                    await database.insert_liquidations(data)
                elif name == "FearGreed":
                    await database.insert_fear_greeds(data)
                elif name == "WhaleAlert":
                    await database.insert_whale_transactions(data)
                elif name == "CryptoPanic":
                    await database.insert_news_items(data)

                logger.info(f"Stored {len(data)} {name} records")
            else:
                logger.info(f"No {name} data collected")

        except Exception as e:
            logger.error(f"Failed to collect {name}: {e}")

        finally:
            await collector.close()

    logger.info("Scheduled data collection completed")


async def report_job(database: Database, output_dir: str = "reports") -> str | None:
    """Generate analysis report.

    Args:
        database: Database instance for reading data.
        output_dir: Directory for report output.

    Returns:
        Path to generated report or None on failure.
    """
    logger.info("Starting scheduled report generation")

    try:
        generator = MarkdownReportGenerator(database)
        report_path = await generator.generate(output_dir=output_dir)

        logger.info(f"Report generated: {report_path}")
        return report_path

    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        return None


def setup_collection_job(
    scheduler: "SchedulerManager",  # type: ignore
    database: Database,
    interval_hours: int = 4,
) -> None:
    """Register the data collection job with the scheduler.

    Args:
        scheduler: SchedulerManager instance.
        database: Database instance.
        interval_hours: Collection interval in hours.
    """
    scheduler.add_interval_job(
        func=collection_job,
        job_id="data_collection",
        hours=interval_hours,
        database=database,
    )
    logger.info(f"Collection job registered (every {interval_hours}h)")


def setup_report_job(
    scheduler: "SchedulerManager",  # type: ignore
    database: Database,
    interval_hours: int = 4,
    output_dir: str = "reports",
) -> None:
    """Register the report generation job with the scheduler.

    Args:
        scheduler: SchedulerManager instance.
        database: Database instance.
        interval_hours: Report interval in hours.
        output_dir: Directory for report output.
    """
    scheduler.add_interval_job(
        func=report_job,
        job_id="report_generation",
        hours=interval_hours,
        database=database,
        output_dir=output_dir,
    )
    logger.info(f"Report job registered (every {interval_hours}h)")


def setup_all_jobs(
    scheduler: "SchedulerManager",  # type: ignore
    database: Database,
    collection_interval: int = 4,
    report_interval: int = 4,
) -> None:
    """Register all scheduled jobs.

    Args:
        scheduler: SchedulerManager instance.
        database: Database instance.
        collection_interval: Collection interval in hours.
        report_interval: Report interval in hours.
    """
    setup_collection_job(scheduler, database, collection_interval)
    setup_report_job(scheduler, database, report_interval)
