"""Market index collector via yfinance (no authentication needed)."""

import asyncio
from datetime import datetime, timedelta, timezone

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.storage.models import MacroIndicator
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)

# Yahoo Finance tickers mapped to indicator names
MARKET_TICKERS = {
    "^GSPC": "SPX",
    "^IXIC": "NASDAQ",
    "DX-Y.NYB": "DXY",
    "GC=F": "GOLD",
}


class MarketIndexCollector(BaseCollector):
    """Collector for market indices via yfinance.

    Uses yfinance (synchronous) wrapped in run_in_executor for async compatibility.
    No API key required.
    """

    async def collect(self, days: int = 5) -> list[MacroIndicator]:
        """Collect market index data.

        Args:
            days: Number of days of history to fetch.

        Returns:
            List of MacroIndicator objects.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._collect_sync, days)

    def _collect_sync(self, days: int) -> list[MacroIndicator]:
        """Synchronous collection logic run in executor."""
        import yfinance as yf

        results: list[MacroIndicator] = []
        end_date = datetime.now(timezone.utc)
        # Extra days to account for weekends/holidays
        start_date = end_date - timedelta(days=days + 5)

        for ticker_symbol, indicator_name in MARKET_TICKERS.items():
            try:
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                )

                if hist.empty:
                    logger.warning(f"No yfinance data for {ticker_symbol}")
                    continue

                import math

                rows = list(hist.iterrows())
                for i, (date, row) in enumerate(rows):
                    close_price = float(row["Close"])
                    if math.isnan(close_price):
                        continue
                    prev_close = float(rows[i - 1][1]["Close"]) if i > 0 else None
                    if prev_close is not None and math.isnan(prev_close):
                        prev_close = None
                    results.append(MacroIndicator(
                        source="yfinance",
                        indicator=indicator_name,
                        date=datetime(date.year, date.month, date.day,
                                      tzinfo=timezone.utc),
                        value=close_price,
                        previous_value=prev_close,
                    ))

                logger.debug(f"Collected {len(rows)} records for {indicator_name}")
            except Exception as e:
                logger.warning(f"Failed to collect {ticker_symbol} ({indicator_name}): {e}")
                continue

        logger.info(f"Collected {len(results)} market index indicators")
        return results

    async def close(self) -> None:
        """No persistent connection to close."""
        pass
