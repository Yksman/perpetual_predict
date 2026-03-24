"""Macroeconomic data collectors."""

from perpetual_predict.collectors.macro.fred_collector import FredCollector
from perpetual_predict.collectors.macro.market_index_collector import MarketIndexCollector

__all__ = ["FredCollector", "MarketIndexCollector"]
