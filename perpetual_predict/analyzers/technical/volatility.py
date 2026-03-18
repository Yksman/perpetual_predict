"""Volatility indicators: Bollinger Bands, ATR."""

import pandas as pd
import pandas_ta as ta


def calculate_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
    column: str = "close",
) -> pd.DataFrame:
    """Calculate Bollinger Bands.

    Args:
        df: DataFrame with price data.
        period: Moving average period (default 20).
        std_dev: Standard deviation multiplier (default 2.0).
        column: Column to use for calculation (default "close").

    Returns:
        DataFrame with BBL (lower), BBM (middle), BBU (upper), BBB (bandwidth), BBP (percent) columns.
    """
    return ta.bbands(df[column], length=period, std=std_dev)


def calculate_atr(
    df: pd.DataFrame,
    period: int = 14,
) -> pd.Series:
    """Calculate Average True Range (ATR).

    Args:
        df: DataFrame with OHLC data.
        period: ATR period (default 14).

    Returns:
        Series with ATR values.
    """
    return ta.atr(df["high"], df["low"], df["close"], length=period)


def add_volatility_indicators(
    df: pd.DataFrame,
    bb_periods: list[int] | None = None,
    bb_std_dev: float = 2.0,
    atr_periods: list[int] | None = None,
) -> pd.DataFrame:
    """Add volatility indicators to DataFrame.

    Args:
        df: DataFrame with OHLCV data.
        bb_periods: List of Bollinger Bands periods (default [20]).
        bb_std_dev: Standard deviation multiplier for BB (default 2.0).
        atr_periods: List of ATR periods (default [14]).

    Returns:
        DataFrame with added volatility indicator columns.
    """
    if bb_periods is None:
        bb_periods = [20]

    if atr_periods is None:
        atr_periods = [14]

    result = df.copy()

    # Add Bollinger Bands for each period
    for period in bb_periods:
        bb = calculate_bollinger_bands(df, period=period, std_dev=bb_std_dev)
        if bb is not None:
            for col in bb.columns:
                # Rename columns to include period
                new_col_name = col.replace(f"_{period}", f"_{period}")
                result[new_col_name] = bb[col]

    # Add ATR for each period
    for period in atr_periods:
        atr = calculate_atr(df, period=period)
        if atr is not None:
            result[f"ATR_{period}"] = atr

    return result
