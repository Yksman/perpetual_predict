"""Volatility indicators: Bollinger Bands, ATR, BB Squeeze, ATR Ratio."""

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


def calculate_bb_squeeze(
    df: pd.DataFrame,
    bb_period: int = 20,
    bb_std_dev: float = 2.0,
    squeeze_lookback: int = 20,
    squeeze_percentile: float = 0.1,
) -> pd.Series:
    """Detect Bollinger Band squeeze (low volatility compression).

    Squeeze occurs when BB width is at historical lows, often preceding
    significant price moves.

    Args:
        df: DataFrame with OHLCV data.
        bb_period: BB period (default 20).
        bb_std_dev: BB standard deviation (default 2.0).
        squeeze_lookback: Lookback period for percentile (default 20).
        squeeze_percentile: Percentile threshold for squeeze (default 0.1 = 10%).

    Returns:
        Series with boolean squeeze detection.
    """
    bb = calculate_bollinger_bands(df, period=bb_period, std_dev=bb_std_dev)
    if bb is None:
        return pd.Series([False] * len(df), index=df.index)

    # pandas_ta uses format: BBB_20_2.0_2.0 (period_stddev_stddev)
    # Try to find the BB width column (BBB = Bandwidth)
    bb_width = None
    for col in bb.columns:
        if col.startswith("BBB_"):
            bb_width = bb[col]
            break

    if bb_width is None:
        # Calculate width manually: (upper - lower) / middle
        upper_col = middle_col = lower_col = None
        for col in bb.columns:
            if col.startswith("BBU_"):
                upper_col = col
            elif col.startswith("BBM_"):
                middle_col = col
            elif col.startswith("BBL_"):
                lower_col = col

        if upper_col and lower_col and middle_col:
            bb_width = (bb[upper_col] - bb[lower_col]) / bb[middle_col]
        else:
            return pd.Series([False] * len(df), index=df.index)

    # Squeeze = current width is below the Nth percentile of recent values
    threshold = bb_width.rolling(squeeze_lookback).quantile(squeeze_percentile)
    return bb_width < threshold


def calculate_atr_ratio(
    df: pd.DataFrame,
    atr_period: int = 14,
    ratio_lookback: int = 20,
) -> pd.Series:
    """Calculate ATR ratio compared to recent average.

    > 1 = Higher than average volatility
    < 1 = Lower than average volatility

    Args:
        df: DataFrame with OHLCV data.
        atr_period: ATR period (default 14).
        ratio_lookback: Lookback for average (default 20).

    Returns:
        Series with ATR ratio values.
    """
    atr = calculate_atr(df, period=atr_period)
    if atr is None:
        return pd.Series([float("nan")] * len(df), index=df.index)

    atr_avg = atr.rolling(ratio_lookback).mean()
    return atr / atr_avg.replace(0, float("nan"))


def interpret_bb_squeeze(is_squeeze: bool, atr_ratio: float) -> str:
    """Interpret BB squeeze for LLM context.

    Args:
        is_squeeze: Whether squeeze is detected.
        atr_ratio: ATR ratio value.

    Returns:
        Human-readable interpretation.
    """
    if is_squeeze:
        return "SQUEEZE DETECTED - Expect volatility expansion"
    elif atr_ratio < 0.7:
        return "Low volatility - potential squeeze forming"
    elif atr_ratio > 1.5:
        return "High volatility"
    else:
        return "Normal volatility"


def interpret_atr_ratio(atr_ratio: float) -> str:
    """Interpret ATR ratio for LLM context.

    Args:
        atr_ratio: ATR ratio value.

    Returns:
        Human-readable interpretation.
    """
    if atr_ratio > 2.0:
        return "Extreme volatility"
    elif atr_ratio > 1.5:
        return "High volatility"
    elif atr_ratio > 1.0:
        return "Above average"
    elif atr_ratio > 0.7:
        return "Below average"
    else:
        return "Low volatility"


def add_volatility_indicators(
    df: pd.DataFrame,
    bb_periods: list[int] | None = None,
    bb_std_dev: float = 2.0,
    atr_periods: list[int] | None = None,
    include_squeeze: bool = True,
    include_atr_ratio: bool = True,
) -> pd.DataFrame:
    """Add volatility indicators to DataFrame.

    Args:
        df: DataFrame with OHLCV data.
        bb_periods: List of Bollinger Bands periods (default [20]).
        bb_std_dev: Standard deviation multiplier for BB (default 2.0).
        atr_periods: List of ATR periods (default [14]).
        include_squeeze: Whether to detect BB squeeze (default True).
        include_atr_ratio: Whether to calculate ATR ratio (default True).

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

        # Add BB Squeeze detection
        if include_squeeze:
            result[f"BB_squeeze_{period}"] = calculate_bb_squeeze(
                df, bb_period=period, bb_std_dev=bb_std_dev
            )

    # Add ATR for each period
    for period in atr_periods:
        atr = calculate_atr(df, period=period)
        if atr is not None:
            result[f"ATR_{period}"] = atr

        # Add ATR ratio
        if include_atr_ratio:
            result[f"ATR_ratio_{period}"] = calculate_atr_ratio(df, atr_period=period)

    return result
