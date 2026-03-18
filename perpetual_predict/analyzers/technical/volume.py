"""Volume indicators: OBV, VWAP."""

import pandas as pd
import pandas_ta as ta


def calculate_obv(df: pd.DataFrame) -> pd.Series:
    """Calculate On-Balance Volume (OBV).

    Args:
        df: DataFrame with close and volume data.

    Returns:
        Series with OBV values.
    """
    return ta.obv(df["close"], df["volume"])


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculate Volume Weighted Average Price (VWAP).

    Args:
        df: DataFrame with OHLCV data.

    Returns:
        Series with VWAP values.
    """
    return ta.vwap(df["high"], df["low"], df["close"], df["volume"])


def add_volume_indicators(
    df: pd.DataFrame,
    include_obv: bool = True,
    include_vwap: bool = True,
) -> pd.DataFrame:
    """Add volume indicators to DataFrame.

    Args:
        df: DataFrame with OHLCV data.
        include_obv: Whether to include OBV (default True).
        include_vwap: Whether to include VWAP (default True).

    Returns:
        DataFrame with added volume indicator columns.
    """
    result = df.copy()

    # Add OBV
    if include_obv:
        obv = calculate_obv(df)
        if obv is not None:
            result["OBV"] = obv

    # Add VWAP
    if include_vwap:
        vwap = calculate_vwap(df)
        if vwap is not None:
            result["VWAP"] = vwap

    return result
