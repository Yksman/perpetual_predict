"""Data collection CLI command."""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone

from perpetual_predict.collectors.binance.client import BinanceClient
from perpetual_predict.collectors.binance.funding import FundingRateCollector
from perpetual_predict.collectors.binance.market_data import (
    LongShortRatioCollector,
    OHLCVCollector,
)
from perpetual_predict.collectors.binance.open_interest import OpenInterestCollector
from perpetual_predict.collectors.sentiment.fear_greed import FearGreedCollector
from perpetual_predict.config import get_settings
from perpetual_predict.storage.database import get_database
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


async def collect_data(
    symbol: str = "BTCUSDT",
    timeframe: str = "4h",
    days: int = 7,
) -> dict[str, int]:
    """Collect all market data and save to database.

    Args:
        symbol: Trading symbol (default BTCUSDT).
        timeframe: Candle timeframe (default 4h).
        days: Number of days of historical data to collect.

    Returns:
        Dictionary with counts of collected records.
    """
    settings = get_settings()
    results: dict[str, int] = {}

    # Calculate time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)

    # Create shared client
    client = BinanceClient(
        api_key=settings.binance.api_key,
        api_secret=settings.binance.api_secret,
        use_testnet=settings.binance.use_testnet,
    )

    try:
        async with get_database() as db:
            # Collect OHLCV data
            logger.info(f"Collecting OHLCV data for {symbol} {timeframe}...")
            ohlcv_collector = OHLCVCollector(
                client=client, symbol=symbol, timeframe=timeframe
            )
            candles = await ohlcv_collector.collect(
                start_time=start_time, end_time=end_time
            )
            for candle in candles:
                await db.insert_candle(candle)
            results["candles"] = len(candles)
            logger.info(f"Collected {len(candles)} candles")

            # Collect funding rate
            logger.info(f"Collecting funding rate for {symbol}...")
            funding_collector = FundingRateCollector(client=client, symbol=symbol)
            funding_rates = await funding_collector.collect(
                start_time=start_time, end_time=end_time
            )
            for rate in funding_rates:
                await db.insert_funding_rate(rate)
            results["funding_rates"] = len(funding_rates)
            logger.info(f"Collected {len(funding_rates)} funding rates")

            # Collect open interest
            logger.info(f"Collecting open interest for {symbol}...")
            oi_collector = OpenInterestCollector(client=client, symbol=symbol)
            open_interests = await oi_collector.collect(
                start_time=start_time, end_time=end_time
            )
            for oi in open_interests:
                await db.insert_open_interest(oi)
            results["open_interests"] = len(open_interests)
            logger.info(f"Collected {len(open_interests)} open interest records")

            # Collect long/short ratio
            logger.info(f"Collecting long/short ratio for {symbol}...")
            ls_collector = LongShortRatioCollector(client=client, symbol=symbol)
            ratios = await ls_collector.collect(
                start_time=start_time, end_time=end_time
            )
            for ratio in ratios:
                await db.insert_long_short_ratio(ratio)
            results["long_short_ratios"] = len(ratios)
            logger.info(f"Collected {len(ratios)} long/short ratios")

            # Collect Fear & Greed Index
            logger.info("Collecting Fear & Greed Index...")
            fgi_collector = FearGreedCollector()
            try:
                fgi_data = await fgi_collector.collect(limit=days)
                for fgi in fgi_data:
                    await db.insert_fear_greed(fgi)
                results["fear_greed"] = len(fgi_data)
                logger.info(f"Collected {len(fgi_data)} Fear & Greed Index records")
            finally:
                await fgi_collector.close()

    finally:
        await client.close()

    return results


def run_collect(args: argparse.Namespace) -> int:
    """Run the collect command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success).
    """
    logger.info(f"Starting data collection for {args.symbol}...")

    try:
        results = asyncio.run(
            collect_data(
                symbol=args.symbol,
                timeframe=args.timeframe,
                days=args.days,
            )
        )

        print("\nCollection Results:")
        print(f"  Candles: {results.get('candles', 0)}")
        print(f"  Funding Rates: {results.get('funding_rates', 0)}")
        print(f"  Open Interests: {results.get('open_interests', 0)}")
        print(f"  Long/Short Ratios: {results.get('long_short_ratios', 0)}")
        print(f"  Fear & Greed: {results.get('fear_greed', 0)}")

        total = sum(results.values())
        print(f"\nTotal records collected: {total}")

        return 0

    except Exception as e:
        logger.error(f"Collection failed: {e}")
        print(f"Error: {e}")
        return 1


def setup_parser(subparsers: argparse._SubParsersAction) -> None:
    """Setup the collect subcommand parser.

    Args:
        subparsers: Parent subparsers action.
    """
    parser = subparsers.add_parser(
        "collect",
        help="Collect market data from Binance and external sources",
    )
    parser.add_argument(
        "--symbol",
        default="BTCUSDT",
        help="Trading symbol (default: BTCUSDT)",
    )
    parser.add_argument(
        "--timeframe",
        default="4h",
        help="Candle timeframe (default: 4h)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Days of historical data to collect (default: 7)",
    )
    parser.set_defaults(func=run_collect)
