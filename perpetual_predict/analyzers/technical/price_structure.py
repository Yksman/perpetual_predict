"""Price structure indicators: body ratio, wick ratios, close position."""

import pandas as pd


def calculate_body_ratio(df: pd.DataFrame) -> pd.Series:
    """Calculate candle body ratio (close - open) / open.

    Positive = bullish candle, negative = bearish candle.
    Magnitude indicates strength of the move.

    Args:
        df: DataFrame with open and close columns.

    Returns:
        Series with body ratio values.
    """
    return (df["close"] - df["open"]) / df["open"]


def calculate_upper_wick_ratio(df: pd.DataFrame) -> pd.Series:
    """Calculate upper wick ratio relative to close price.

    Upper wick = high - max(open, close)
    Large upper wick suggests selling pressure / rejection.

    Args:
        df: DataFrame with OHLC data.

    Returns:
        Series with upper wick ratio values.
    """
    body_top = df[["open", "close"]].max(axis=1)
    upper_wick = df["high"] - body_top
    return upper_wick / df["close"]


def calculate_lower_wick_ratio(df: pd.DataFrame) -> pd.Series:
    """Calculate lower wick ratio relative to close price.

    Lower wick = min(open, close) - low
    Large lower wick suggests buying pressure / support.

    Args:
        df: DataFrame with OHLC data.

    Returns:
        Series with lower wick ratio values.
    """
    body_bottom = df[["open", "close"]].min(axis=1)
    lower_wick = body_bottom - df["low"]
    return lower_wick / df["close"]


def calculate_close_in_range(df: pd.DataFrame) -> pd.Series:
    """Calculate where close sits within the candle range (0 to 1).

    0 = closed at low (bearish)
    1 = closed at high (bullish)
    0.5 = closed at middle (indecision)

    Args:
        df: DataFrame with high, low, close columns.

    Returns:
        Series with close position values (0 to 1).
    """
    candle_range = df["high"] - df["low"]
    # Avoid division by zero for flat candles
    return (df["close"] - df["low"]) / candle_range.replace(0, float("nan"))


def calculate_volume_ratio(df: pd.DataFrame) -> pd.Series:
    """Calculate volume ratio compared to previous candle.

    > 1 = increasing volume
    < 1 = decreasing volume

    Args:
        df: DataFrame with volume column.

    Returns:
        Series with volume ratio values.
    """
    prev_volume = df["volume"].shift(1)
    return df["volume"] / prev_volume.replace(0, float("nan"))


def calculate_gap_ratio(df: pd.DataFrame) -> pd.Series:
    """Calculate gap ratio (open vs previous close).

    Gap up = positive
    Gap down = negative

    Args:
        df: DataFrame with open and close columns.

    Returns:
        Series with gap ratio values.
    """
    prev_close = df["close"].shift(1)
    return (df["open"] - prev_close) / prev_close


def add_price_structure_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all price structure indicators to DataFrame.

    Args:
        df: DataFrame with OHLCV data.

    Returns:
        DataFrame with added price structure columns.
    """
    result = df.copy()

    result["body_ratio"] = calculate_body_ratio(df)
    result["upper_wick_ratio"] = calculate_upper_wick_ratio(df)
    result["lower_wick_ratio"] = calculate_lower_wick_ratio(df)
    result["close_in_range"] = calculate_close_in_range(df)
    result["volume_ratio"] = calculate_volume_ratio(df)
    result["gap_ratio"] = calculate_gap_ratio(df)

    return result


def interpret_body_ratio(body_ratio: float) -> str:
    """Interpret body ratio value for LLM context."""
    if body_ratio > 0.02:
        return "Strong Bullish"
    elif body_ratio > 0.005:
        return "Bullish"
    elif body_ratio < -0.02:
        return "Strong Bearish"
    elif body_ratio < -0.005:
        return "Bearish"
    else:
        return "Doji/Indecision"


def interpret_close_in_range(close_in_range: float) -> str:
    """Interpret close position for LLM context."""
    if close_in_range > 0.8:
        return "Near High (Bullish Control)"
    elif close_in_range > 0.6:
        return "Upper Half"
    elif close_in_range < 0.2:
        return "Near Low (Bearish Control)"
    elif close_in_range < 0.4:
        return "Lower Half"
    else:
        return "Middle (Indecision)"


def interpret_volume_ratio(volume_ratio: float) -> str:
    """Interpret volume ratio for LLM context."""
    if volume_ratio > 2.0:
        return "Very High Volume"
    elif volume_ratio > 1.5:
        return "High Volume"
    elif volume_ratio > 1.0:
        return "Increasing Volume"
    elif volume_ratio > 0.7:
        return "Decreasing Volume"
    else:
        return "Low Volume"
