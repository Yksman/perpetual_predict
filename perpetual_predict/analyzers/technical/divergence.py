"""Divergence detection: RSI and MACD divergences against price."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from perpetual_predict.analyzers.technical.support_resistance import find_pivot_points


@dataclass
class Divergence:
    """A detected divergence between price and an indicator."""

    type: str  # "bullish" or "bearish"
    indicator: str  # "RSI" or "MACD"
    price_point_1: float  # Earlier price pivot
    price_point_2: float  # Later price pivot
    indicator_point_1: float  # Earlier indicator value
    indicator_point_2: float  # Later indicator value
    index_1: int  # DataFrame index of first pivot
    index_2: int  # DataFrame index of second pivot
    strength: str  # "regular" or "hidden"


@dataclass
class DivergenceResult:
    """Result of divergence analysis."""

    divergences: list[Divergence]
    summary: str  # Human-readable summary for LLM prompt


def detect_rsi_divergence(
    df: pd.DataFrame,
    left_bars: int = 3,
    right_bars: int = 3,
    lookback: int = 30,
) -> list[Divergence]:
    """Detect RSI divergences against price.

    Bullish Regular: Price makes LL, RSI makes HL (reversal up expected)
    Bearish Regular: Price makes HH, RSI makes LH (reversal down expected)
    Bullish Hidden: Price makes HL, RSI makes LL (continuation up)
    Bearish Hidden: Price makes LH, RSI makes HH (continuation down)

    Args:
        df: DataFrame with OHLCV data and RSI_14 column.
        left_bars: Bars for pivot detection.
        right_bars: Bars for pivot detection.
        lookback: Max bars between two pivots for divergence.

    Returns:
        List of detected RSI divergences.
    """
    rsi_col = "RSI_14"
    if rsi_col not in df.columns:
        return []

    return _detect_divergences(
        df=df,
        indicator_col=rsi_col,
        indicator_name="RSI",
        left_bars=left_bars,
        right_bars=right_bars,
        lookback=lookback,
    )


def detect_macd_divergence(
    df: pd.DataFrame,
    left_bars: int = 3,
    right_bars: int = 3,
    lookback: int = 30,
) -> list[Divergence]:
    """Detect MACD histogram divergences against price.

    Uses MACD histogram for more sensitive divergence detection.

    Args:
        df: DataFrame with OHLCV data and MACDh_12_26_9 column.
        left_bars: Bars for pivot detection.
        right_bars: Bars for pivot detection.
        lookback: Max bars between two pivots for divergence.

    Returns:
        List of detected MACD divergences.
    """
    macd_col = "MACDh_12_26_9"
    if macd_col not in df.columns:
        return []

    return _detect_divergences(
        df=df,
        indicator_col=macd_col,
        indicator_name="MACD",
        left_bars=left_bars,
        right_bars=right_bars,
        lookback=lookback,
    )


def _detect_divergences(
    df: pd.DataFrame,
    indicator_col: str,
    indicator_name: str,
    left_bars: int,
    right_bars: int,
    lookback: int,
) -> list[Divergence]:
    """Generic divergence detection between price pivots and indicator pivots.

    Args:
        df: DataFrame with OHLCV and indicator data.
        indicator_col: Column name of the indicator to check.
        indicator_name: Human-readable name ("RSI", "MACD").
        left_bars: Bars for pivot detection.
        right_bars: Bars for pivot detection.
        lookback: Max bars between two pivots.

    Returns:
        List of detected divergences.
    """
    divergences: list[Divergence] = []

    # Find price pivots
    price_highs, price_lows = find_pivot_points(df, left_bars, right_bars)

    # Get pivot indices and values
    price_high_idx = price_highs.dropna().index.tolist()
    price_low_idx = price_lows.dropna().index.tolist()

    # Check bullish divergences (price lows vs indicator lows)
    for i in range(len(price_low_idx) - 1):
        idx1 = price_low_idx[i]
        idx2 = price_low_idx[i + 1]

        # Check lookback window
        pos1 = df.index.get_loc(idx1)
        pos2 = df.index.get_loc(idx2)
        if pos2 - pos1 > lookback:
            continue

        price1 = float(price_lows.loc[idx1])
        price2 = float(price_lows.loc[idx2])
        ind1 = float(df[indicator_col].iloc[pos1])
        ind2 = float(df[indicator_col].iloc[pos2])

        if np.isnan(ind1) or np.isnan(ind2):
            continue

        # Regular Bullish: Price LL, Indicator HL
        if price2 < price1 and ind2 > ind1:
            divergences.append(Divergence(
                type="bullish",
                indicator=indicator_name,
                price_point_1=price1,
                price_point_2=price2,
                indicator_point_1=ind1,
                indicator_point_2=ind2,
                index_1=int(pos1),
                index_2=int(pos2),
                strength="regular",
            ))
        # Hidden Bullish: Price HL, Indicator LL
        elif price2 > price1 and ind2 < ind1:
            divergences.append(Divergence(
                type="bullish",
                indicator=indicator_name,
                price_point_1=price1,
                price_point_2=price2,
                indicator_point_1=ind1,
                indicator_point_2=ind2,
                index_1=int(pos1),
                index_2=int(pos2),
                strength="hidden",
            ))

    # Check bearish divergences (price highs vs indicator highs)
    for i in range(len(price_high_idx) - 1):
        idx1 = price_high_idx[i]
        idx2 = price_high_idx[i + 1]

        pos1 = df.index.get_loc(idx1)
        pos2 = df.index.get_loc(idx2)
        if pos2 - pos1 > lookback:
            continue

        price1 = float(price_highs.loc[idx1])
        price2 = float(price_highs.loc[idx2])
        ind1 = float(df[indicator_col].iloc[pos1])
        ind2 = float(df[indicator_col].iloc[pos2])

        if np.isnan(ind1) or np.isnan(ind2):
            continue

        # Regular Bearish: Price HH, Indicator LH
        if price2 > price1 and ind2 < ind1:
            divergences.append(Divergence(
                type="bearish",
                indicator=indicator_name,
                price_point_1=price1,
                price_point_2=price2,
                indicator_point_1=ind1,
                indicator_point_2=ind2,
                index_1=int(pos1),
                index_2=int(pos2),
                strength="regular",
            ))
        # Hidden Bearish: Price LH, Indicator HH
        elif price2 < price1 and ind2 > ind1:
            divergences.append(Divergence(
                type="bearish",
                indicator=indicator_name,
                price_point_1=price1,
                price_point_2=price2,
                indicator_point_1=ind1,
                indicator_point_2=ind2,
                index_1=int(pos1),
                index_2=int(pos2),
                strength="hidden",
            ))

    return divergences


def analyze_divergences(
    df: pd.DataFrame,
    left_bars: int = 3,
    right_bars: int = 3,
    lookback: int = 30,
    recent_only: int = 10,
) -> DivergenceResult:
    """Run full divergence analysis on price data.

    Args:
        df: DataFrame with OHLCV, RSI_14, and MACDh_12_26_9 columns.
        left_bars: Bars for pivot detection.
        right_bars: Bars for pivot detection.
        lookback: Max bars between pivots for divergence detection.
        recent_only: Only report divergences where the second pivot
            is within this many bars of the latest candle.

    Returns:
        DivergenceResult with detected divergences and summary.
    """
    all_divergences: list[Divergence] = []

    rsi_divs = detect_rsi_divergence(df, left_bars, right_bars, lookback)
    macd_divs = detect_macd_divergence(df, left_bars, right_bars, lookback)

    all_divergences.extend(rsi_divs)
    all_divergences.extend(macd_divs)

    # Filter to recent divergences only
    latest_idx = len(df) - 1
    recent_divs = [
        d for d in all_divergences
        if (latest_idx - d.index_2) <= recent_only
    ]

    summary = _build_divergence_summary(recent_divs)

    return DivergenceResult(
        divergences=recent_divs,
        summary=summary,
    )


def _build_divergence_summary(divergences: list[Divergence]) -> str:
    """Build human-readable divergence summary for LLM prompt."""
    if not divergences:
        return "  No divergences detected in recent candles"

    lines = []
    for d in divergences:
        strength_label = "Regular" if d.strength == "regular" else "Hidden"

        if d.type == "bullish":
            price_pattern = "LL" if d.strength == "regular" else "HL"
            ind_pattern = "HL" if d.strength == "regular" else "LL"
        else:
            price_pattern = "HH" if d.strength == "regular" else "LH"
            ind_pattern = "LH" if d.strength == "regular" else "HH"

        lines.append(
            f"  - {d.indicator} {strength_label}: "
            f"Price {price_pattern} (${d.price_point_1:,.0f}→${d.price_point_2:,.0f}), "
            f"{d.indicator} {ind_pattern} ({d.indicator_point_1:.1f}→{d.indicator_point_2:.1f})"
        )

    return "\n".join(lines)
