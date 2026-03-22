"""Volume indicators: OBV, VWAP, CVD."""

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


def calculate_cvd(df: pd.DataFrame) -> pd.Series:
    """Calculate Cumulative Volume Delta (CVD) for single candle.

    CVD = Taker Buy Volume - Taker Sell Volume
    Where: Taker Sell Volume = Total Volume - Taker Buy Volume

    Positive CVD = More aggressive buying (bullish pressure)
    Negative CVD = More aggressive selling (bearish pressure)

    Args:
        df: DataFrame with volume and taker_buy_base columns.
            taker_buy_base is provided by Binance API.

    Returns:
        Series with CVD values (in base asset units, e.g., BTC).
    """
    if "taker_buy_base" not in df.columns:
        # Fallback: cannot calculate CVD without taker data
        return pd.Series([float("nan")] * len(df), index=df.index)

    taker_buy = df["taker_buy_base"]
    taker_sell = df["volume"] - taker_buy
    return taker_buy - taker_sell


def calculate_cvd_ratio(df: pd.DataFrame) -> pd.Series:
    """Calculate CVD as ratio of total volume.

    Range: -1 (all selling) to +1 (all buying)
    0 = balanced buying/selling

    Args:
        df: DataFrame with volume and taker_buy_base columns.

    Returns:
        Series with CVD ratio values (-1 to +1).
    """
    if "taker_buy_base" not in df.columns:
        return pd.Series([float("nan")] * len(df), index=df.index)

    cvd = calculate_cvd(df)
    # Normalize by total volume
    return cvd / df["volume"].replace(0, float("nan"))


def interpret_cvd(cvd_value: float, volume: float) -> str:
    """Interpret CVD value for LLM context.

    Args:
        cvd_value: Raw CVD value.
        volume: Total volume for context.

    Returns:
        Human-readable interpretation.
    """
    if volume == 0:
        return "No Volume"

    cvd_ratio = cvd_value / volume

    if cvd_ratio > 0.3:
        return "Strong Buy Pressure"
    elif cvd_ratio > 0.1:
        return "Buy Pressure"
    elif cvd_ratio < -0.3:
        return "Strong Sell Pressure"
    elif cvd_ratio < -0.1:
        return "Sell Pressure"
    else:
        return "Balanced"


def add_volume_indicators(
    df: pd.DataFrame,
    include_obv: bool = True,
    include_vwap: bool = True,
    include_cvd: bool = True,
) -> pd.DataFrame:
    """Add volume indicators to DataFrame.

    Args:
        df: DataFrame with OHLCV data.
        include_obv: Whether to include OBV (default True).
        include_vwap: Whether to include VWAP (default True).
        include_cvd: Whether to include CVD (default True).

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

    # Add CVD (Cumulative Volume Delta)
    if include_cvd and "taker_buy_base" in df.columns:
        result["CVD"] = calculate_cvd(df)
        result["CVD_ratio"] = calculate_cvd_ratio(df)

    return result
