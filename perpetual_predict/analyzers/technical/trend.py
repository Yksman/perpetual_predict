"""Trend indicators: SMA, EMA, MACD, ADX."""

import pandas as pd
import pandas_ta as ta


def calculate_sma(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.Series:
    """Calculate Simple Moving Average.

    Args:
        df: DataFrame with OHLCV data.
        period: SMA period (default 20).
        column: Column to use for calculation (default "close").

    Returns:
        Series with SMA values.
    """
    return ta.sma(df[column], length=period)


def calculate_ema(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.Series:
    """Calculate Exponential Moving Average.

    Args:
        df: DataFrame with OHLCV data.
        period: EMA period (default 20).
        column: Column to use for calculation (default "close").

    Returns:
        Series with EMA values.
    """
    return ta.ema(df[column], length=period)


def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "close",
) -> pd.DataFrame:
    """Calculate MACD (Moving Average Convergence Divergence).

    Args:
        df: DataFrame with OHLCV data.
        fast: Fast EMA period (default 12).
        slow: Slow EMA period (default 26).
        signal: Signal line period (default 9).
        column: Column to use for calculation (default "close").

    Returns:
        DataFrame with columns: MACD, MACDh (histogram), MACDs (signal).
    """
    macd_df = ta.macd(df[column], fast=fast, slow=slow, signal=signal)
    if macd_df is None:
        return pd.DataFrame(columns=["MACD", "MACDh", "MACDs"])
    return macd_df


def calculate_adx(
    df: pd.DataFrame, period: int = 14
) -> pd.DataFrame:
    """Calculate ADX (Average Directional Index).

    Args:
        df: DataFrame with OHLCV data (must have high, low, close columns).
        period: ADX period (default 14).

    Returns:
        DataFrame with columns: ADX, DMP (DI+), DMN (DI-).
    """
    adx_df = ta.adx(df["high"], df["low"], df["close"], length=period)
    if adx_df is None:
        return pd.DataFrame(columns=["ADX", "DMP", "DMN"])
    return adx_df


def add_trend_indicators(
    df: pd.DataFrame,
    sma_periods: list[int] | None = None,
    ema_periods: list[int] | None = None,
    macd_params: tuple[int, int, int] | None = None,
    adx_period: int = 14,
) -> pd.DataFrame:
    """Add all trend indicators to a DataFrame.

    Args:
        df: DataFrame with OHLCV data.
        sma_periods: List of SMA periods to calculate (default [20, 50, 200]).
        ema_periods: List of EMA periods to calculate (default [12, 26]).
        macd_params: MACD parameters (fast, slow, signal) (default (12, 26, 9)).
        adx_period: ADX period (default 14).

    Returns:
        DataFrame with added indicator columns.
    """
    result = df.copy()

    # Default values
    sma_periods = sma_periods or [20, 50, 200]
    ema_periods = ema_periods or [12, 26]
    macd_params = macd_params or (12, 26, 9)

    # Add SMAs
    for period in sma_periods:
        sma = calculate_sma(result, period)
        if sma is not None:
            result[f"SMA_{period}"] = sma

    # Add EMAs
    for period in ema_periods:
        ema = calculate_ema(result, period)
        if ema is not None:
            result[f"EMA_{period}"] = ema

    # Add MACD
    macd_df = calculate_macd(result, *macd_params)
    if not macd_df.empty:
        for col in macd_df.columns:
            result[col] = macd_df[col]

    # Add ADX
    adx_df = calculate_adx(result, adx_period)
    if not adx_df.empty:
        for col in adx_df.columns:
            result[col] = adx_df[col]

    return result
