"""Support and Resistance level analysis."""

import numpy as np
import pandas as pd


def find_pivot_points(
    df: pd.DataFrame,
    left_bars: int = 5,
    right_bars: int = 5,
) -> tuple[pd.Series, pd.Series]:
    """Find pivot highs and lows in price data.

    Args:
        df: DataFrame with OHLC data.
        left_bars: Number of bars to the left for pivot confirmation.
        right_bars: Number of bars to the right for pivot confirmation.

    Returns:
        Tuple of (pivot_highs, pivot_lows) Series with values at pivot points.
    """
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)

    pivot_highs = pd.Series(np.nan, index=df.index)
    pivot_lows = pd.Series(np.nan, index=df.index)

    for i in range(left_bars, n - right_bars):
        # Check pivot high
        is_pivot_high = True
        for j in range(1, left_bars + 1):
            if highs[i] <= highs[i - j]:
                is_pivot_high = False
                break
        if is_pivot_high:
            for j in range(1, right_bars + 1):
                if highs[i] <= highs[i + j]:
                    is_pivot_high = False
                    break
        if is_pivot_high:
            pivot_highs.iloc[i] = highs[i]

        # Check pivot low
        is_pivot_low = True
        for j in range(1, left_bars + 1):
            if lows[i] >= lows[i - j]:
                is_pivot_low = False
                break
        if is_pivot_low:
            for j in range(1, right_bars + 1):
                if lows[i] >= lows[i + j]:
                    is_pivot_low = False
                    break
        if is_pivot_low:
            pivot_lows.iloc[i] = lows[i]

    return pivot_highs, pivot_lows


def find_support_resistance_levels(
    df: pd.DataFrame,
    left_bars: int = 5,
    right_bars: int = 5,
    tolerance_pct: float = 0.5,
    min_touches: int = 2,
) -> dict[str, list[float]]:
    """Find support and resistance levels from pivot points.

    Args:
        df: DataFrame with OHLC data.
        left_bars: Number of bars for pivot detection.
        right_bars: Number of bars for pivot detection.
        tolerance_pct: Percentage tolerance for grouping similar levels.
        min_touches: Minimum number of touches to confirm a level.

    Returns:
        Dictionary with 'support' and 'resistance' level lists.
    """
    pivot_highs, pivot_lows = find_pivot_points(df, left_bars, right_bars)

    # Get valid pivot values
    resistance_points = pivot_highs.dropna().values
    support_points = pivot_lows.dropna().values

    def cluster_levels(points: np.ndarray, tolerance_pct: float, min_touches: int) -> list[float]:
        """Cluster nearby price levels."""
        if len(points) == 0:
            return []

        sorted_points = np.sort(points)
        clusters: list[list[float]] = []
        current_cluster = [sorted_points[0]]

        for point in sorted_points[1:]:
            # Check if point is within tolerance of cluster mean
            cluster_mean = np.mean(current_cluster)
            if abs(point - cluster_mean) / cluster_mean * 100 <= tolerance_pct:
                current_cluster.append(point)
            else:
                clusters.append(current_cluster)
                current_cluster = [point]

        clusters.append(current_cluster)

        # Filter by minimum touches and return means
        return [float(np.mean(c)) for c in clusters if len(c) >= min_touches]

    resistance_levels = cluster_levels(resistance_points, tolerance_pct, min_touches)
    support_levels = cluster_levels(support_points, tolerance_pct, min_touches)

    return {
        "support": sorted(support_levels),
        "resistance": sorted(resistance_levels),
    }


def calculate_nearest_levels(
    current_price: float,
    levels: dict[str, list[float]],
) -> dict[str, float | None]:
    """Find the nearest support and resistance levels to current price.

    Args:
        current_price: Current market price.
        levels: Dictionary with 'support' and 'resistance' lists.

    Returns:
        Dictionary with 'nearest_support' and 'nearest_resistance'.
    """
    nearest_support: float | None = None
    nearest_resistance: float | None = None

    # Find nearest support (below current price)
    supports_below = [s for s in levels["support"] if s < current_price]
    if supports_below:
        nearest_support = max(supports_below)

    # Find nearest resistance (above current price)
    resistances_above = [r for r in levels["resistance"] if r > current_price]
    if resistances_above:
        nearest_resistance = min(resistances_above)

    return {
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
    }


def add_support_resistance_indicators(
    df: pd.DataFrame,
    left_bars: int = 5,
    right_bars: int = 5,
) -> pd.DataFrame:
    """Add support/resistance indicators to DataFrame.

    Args:
        df: DataFrame with OHLCV data.
        left_bars: Number of bars for pivot detection.
        right_bars: Number of bars for pivot detection.

    Returns:
        DataFrame with added pivot_high and pivot_low columns.
    """
    result = df.copy()

    pivot_highs, pivot_lows = find_pivot_points(df, left_bars, right_bars)

    result["pivot_high"] = pivot_highs
    result["pivot_low"] = pivot_lows

    return result
