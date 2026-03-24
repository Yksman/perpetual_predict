"""FRED (Federal Reserve Economic Data) collector."""

import asyncio
from datetime import datetime, timedelta, timezone

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.storage.models import MacroIndicator
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)

# FRED series to collect
FRED_SERIES = {
    "DGS10": "10-Year Treasury Yield",
    "DGS2": "2-Year Treasury Yield",
    "DFF": "Federal Funds Rate",
    "T10Y2Y": "10Y-2Y Yield Spread",
}


class FredCollector(BaseCollector):
    """Collector for FRED macroeconomic data.

    Uses fredapi (synchronous) wrapped in run_in_executor for async compatibility.
    Requires a free FRED API key from https://fred.stlouisfed.org/docs/api/api_key.html
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._fred = None

    @property
    def fred(self):
        """Lazy-initialize fredapi client."""
        if self._fred is None:
            from fredapi import Fred

            self._fred = Fred(api_key=self._api_key)
        return self._fred

    async def collect(self, days: int = 5) -> list[MacroIndicator]:
        """Collect FRED data for configured series.

        Args:
            days: Number of days of history to fetch.

        Returns:
            List of MacroIndicator objects.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._collect_sync, days)

    def _collect_sync(self, days: int) -> list[MacroIndicator]:
        """Synchronous collection logic run in executor."""
        results: list[MacroIndicator] = []
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        for series_id in FRED_SERIES:
            try:
                data = self.fred.get_series(
                    series_id,
                    observation_start=start_date.strftime("%Y-%m-%d"),
                    observation_end=end_date.strftime("%Y-%m-%d"),
                )
                if data is None or data.empty:
                    logger.warning(f"No FRED data for {series_id}")
                    continue

                data = data.dropna()
                values = list(data.items())

                for i, (date, value) in enumerate(values):
                    prev_value = float(values[i - 1][1]) if i > 0 else None
                    results.append(MacroIndicator(
                        source="fred",
                        indicator=series_id,
                        date=datetime(date.year, date.month, date.day,
                                      tzinfo=timezone.utc),
                        value=float(value),
                        previous_value=prev_value,
                    ))

                logger.debug(f"Collected {len(values)} records for FRED {series_id}")
            except Exception as e:
                logger.warning(f"Failed to collect FRED {series_id}: {e}")
                continue

        logger.info(f"Collected {len(results)} FRED macro indicators")
        return results

    async def close(self) -> None:
        """No persistent connection to close."""
        self._fred = None
