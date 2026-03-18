"""Report generation CLI command."""

import argparse
import asyncio
from pathlib import Path

import pandas as pd

from perpetual_predict.analyzers.technical.momentum import calculate_rsi
from perpetual_predict.analyzers.technical.support_resistance import (
    calculate_nearest_levels,
    find_support_resistance_levels,
)
from perpetual_predict.analyzers.technical.trend import calculate_ema, calculate_sma
from perpetual_predict.analyzers.technical.volatility import calculate_atr
from perpetual_predict.reporters.markdown_generator import (
    MarkdownReportGenerator,
    TechnicalIndicator,
    create_report_data,
)
from perpetual_predict.storage.database import get_database
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


async def generate_report(
    symbol: str = "BTCUSDT",
    timeframe: str = "4h",
    output_path: Path | None = None,
) -> str:
    """Generate analysis report from collected data.

    Args:
        symbol: Trading symbol.
        timeframe: Candle timeframe.
        output_path: Optional path to save the report.

    Returns:
        Generated report as string.
    """
    async with get_database() as db:
        # Get candles
        candles = await db.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=500,
        )

        if not candles:
            raise ValueError(f"No candle data found for {symbol} {timeframe}")

        # Convert to DataFrame
        df = pd.DataFrame([c.to_dict() for c in candles])
        df["open_time"] = pd.to_datetime(df["open_time"])
        df = df.set_index("open_time").sort_index()

        # Get latest candle for current price
        latest_candle = candles[-1]
        current_price = latest_candle.close

        # Calculate 24h stats (6 candles for 4h timeframe)
        recent_candles = candles[-6:] if len(candles) >= 6 else candles
        high_24h = max(c.high for c in recent_candles)
        low_24h = min(c.low for c in recent_candles)
        volume_24h = sum(c.volume for c in recent_candles)
        first_close = recent_candles[0].close
        price_change_24h = ((current_price - first_close) / first_close) * 100

        # Calculate technical indicators
        trend_indicators: list[TechnicalIndicator] = []

        sma_20 = calculate_sma(df, period=20)
        if sma_20 is not None and not sma_20.empty:
            sma_val = sma_20.iloc[-1]
            signal = "Bullish" if current_price > sma_val else "Bearish"
            trend_indicators.append(
                TechnicalIndicator(name="SMA_20", value=float(sma_val), signal=signal)
            )

        sma_50 = calculate_sma(df, period=50)
        if sma_50 is not None and not sma_50.empty:
            sma_val = sma_50.iloc[-1]
            signal = "Bullish" if current_price > sma_val else "Bearish"
            trend_indicators.append(
                TechnicalIndicator(name="SMA_50", value=float(sma_val), signal=signal)
            )

        ema_12 = calculate_ema(df, period=12)
        if ema_12 is not None and not ema_12.empty:
            ema_val = ema_12.iloc[-1]
            signal = "Bullish" if current_price > ema_val else "Bearish"
            trend_indicators.append(
                TechnicalIndicator(name="EMA_12", value=float(ema_val), signal=signal)
            )

        # Momentum indicators
        momentum_indicators: list[TechnicalIndicator] = []

        rsi_14 = calculate_rsi(df, period=14)
        if rsi_14 is not None and not rsi_14.empty:
            rsi_val = rsi_14.iloc[-1]
            if rsi_val > 70:
                signal = "Overbought"
            elif rsi_val < 30:
                signal = "Oversold"
            else:
                signal = "Neutral"
            momentum_indicators.append(
                TechnicalIndicator(name="RSI_14", value=float(rsi_val), signal=signal)
            )

        # Volatility indicators
        volatility_indicators: list[TechnicalIndicator] = []

        atr_14 = calculate_atr(df, period=14)
        if atr_14 is not None and not atr_14.empty:
            atr_val = atr_14.iloc[-1]
            volatility_indicators.append(
                TechnicalIndicator(name="ATR_14", value=float(atr_val))
            )

        # Support/Resistance levels
        levels = find_support_resistance_levels(df, min_touches=1)
        support_levels = levels["support"][-3:] if levels["support"] else []
        resistance_levels = levels["resistance"][:3] if levels["resistance"] else []

        nearest = calculate_nearest_levels(current_price, levels)

        # Get funding rate
        funding_rate = 0.0
        next_funding_time = ""
        funding_rates = await db.get_funding_rates(symbol=symbol, limit=1)
        if funding_rates:
            funding_rate = funding_rates[-1].funding_rate * 100
            next_funding_time = funding_rates[-1].funding_time.strftime(
                "%Y-%m-%d %H:%M UTC"
            )

        # Get open interest
        open_interest = 0.0
        oi_change_24h = 0.0
        oi_records = await db.get_open_interests(symbol=symbol, limit=7)
        if oi_records:
            open_interest = oi_records[-1].sum_open_interest
            if len(oi_records) >= 2:
                old_oi = oi_records[0].sum_open_interest
                if old_oi > 0:
                    oi_change_24h = ((open_interest - old_oi) / old_oi) * 100

        # Get long/short ratio
        long_short_ratio = 1.0
        ls_ratios = await db.get_long_short_ratios(symbol=symbol, limit=1)
        if ls_ratios:
            long_short_ratio = ls_ratios[-1].long_short_ratio

        # Get Fear & Greed Index
        fear_greed_value = 50
        fear_greed_classification = "Neutral"
        fgi_records = await db.get_fear_greed_records(limit=1)
        if fgi_records:
            fear_greed_value = fgi_records[-1].value
            fear_greed_classification = fgi_records[-1].classification

        # Create report data
        report_data = create_report_data(
            symbol=symbol,
            timeframe=timeframe,
            current_price=current_price,
            price_change_24h=price_change_24h,
            high_24h=high_24h,
            low_24h=low_24h,
            volume_24h=volume_24h,
            trend_indicators=trend_indicators,
            momentum_indicators=momentum_indicators,
            volatility_indicators=volatility_indicators,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            nearest_support=nearest["nearest_support"],
            nearest_resistance=nearest["nearest_resistance"],
            funding_rate=funding_rate,
            next_funding_time=next_funding_time,
            open_interest=open_interest,
            oi_change_24h=oi_change_24h,
            long_short_ratio=long_short_ratio,
            fear_greed_value=fear_greed_value,
            fear_greed_classification=fear_greed_classification,
        )

        # Generate report
        generator = MarkdownReportGenerator()
        report = generator.generate(report_data)

        if output_path:
            generator.generate_to_file(report_data, output_path)
            logger.info(f"Report saved to {output_path}")

        return report


def run_report(args: argparse.Namespace) -> int:
    """Run the report command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success).
    """
    logger.info(f"Generating report for {args.symbol}...")

    try:
        output_path = Path(args.output) if args.output else None

        report = asyncio.run(
            generate_report(
                symbol=args.symbol,
                timeframe=args.timeframe,
                output_path=output_path,
            )
        )

        if not output_path:
            print(report)
        else:
            print(f"Report saved to: {output_path}")

        return 0

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        print(f"Error: {e}")
        return 1


def setup_parser(subparsers: argparse._SubParsersAction) -> None:
    """Setup the report subcommand parser.

    Args:
        subparsers: Parent subparsers action.
    """
    parser = subparsers.add_parser(
        "report",
        help="Generate analysis report from collected data",
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
        "-o",
        "--output",
        help="Output file path (prints to stdout if not specified)",
    )
    parser.set_defaults(func=run_report)
