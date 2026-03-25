"""Price structure indicators: body ratio, wick ratios, close position."""

import pandas as pd


def calculate_body_ratio(df: pd.DataFrame) -> pd.Series:
    """Calculate candle body ratio abs(close - open) / (high - low).

    Measures what fraction of the candle range is body vs wicks.
    0.0 = doji (no body), 1.0 = marubozu (all body, no wicks).

    Args:
        df: DataFrame with OHLC columns.

    Returns:
        Series with body ratio values (0.0 to 1.0).
    """
    candle_range = df["high"] - df["low"]
    body = (df["close"] - df["open"]).abs()
    return body / candle_range.replace(0, float("nan"))


def calculate_upper_wick_ratio(df: pd.DataFrame) -> pd.Series:
    """Calculate upper wick ratio relative to candle range.

    Upper wick = high - max(open, close)
    Fraction of the candle range that is upper wick.

    Args:
        df: DataFrame with OHLC data.

    Returns:
        Series with upper wick ratio values (0.0 to 1.0).
    """
    candle_range = df["high"] - df["low"]
    body_top = df[["open", "close"]].max(axis=1)
    upper_wick = df["high"] - body_top
    return upper_wick / candle_range.replace(0, float("nan"))


def calculate_lower_wick_ratio(df: pd.DataFrame) -> pd.Series:
    """Calculate lower wick ratio relative to candle range.

    Lower wick = min(open, close) - low
    Fraction of the candle range that is lower wick.

    Args:
        df: DataFrame with OHLC data.

    Returns:
        Series with lower wick ratio values (0.0 to 1.0).
    """
    candle_range = df["high"] - df["low"]
    body_bottom = df[["open", "close"]].min(axis=1)
    lower_wick = body_bottom - df["low"]
    return lower_wick / candle_range.replace(0, float("nan"))


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


