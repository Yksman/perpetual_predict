"""Market structure analysis: Swing Highs/Lows and HH/HL/LH/LL classification."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from perpetual_predict.analyzers.technical.support_resistance import find_pivot_points


@dataclass
class SwingPoint:
    """A swing high or low point."""

    index: int
    price: float
    type: str  # "high" or "low"
    label: str  # "HH", "HL", "LH", "LL", or "H"/"L" for first points


@dataclass
class MarketStructureResult:
    """Result of market structure analysis."""

    swings: list[SwingPoint]
    current_structure: str  # "Bullish", "Bearish", "Transition", "Undefined"
    structure_breaks: int  # Number of structure breaks in the lookback
    summary: str  # Human-readable summary for LLM prompt


def detect_swings(
    df: pd.DataFrame,
    left_bars: int = 3,
    right_bars: int = 3,
) -> list[SwingPoint]:
    """Detect swing highs and lows, then classify as HH/HL/LH/LL.

    Args:
        df: DataFrame with OHLCV data (sorted chronologically).
        left_bars: Bars to the left for pivot confirmation.
        right_bars: Bars to the right for pivot confirmation.

    Returns:
        List of SwingPoints in chronological order with HH/HL/LH/LL labels.
    """
    pivot_highs, pivot_lows = find_pivot_points(df, left_bars, right_bars)

    # Collect all swing points
    raw_swings: list[SwingPoint] = []

    for i in range(len(df)):
        if not np.isnan(pivot_highs.iloc[i]):
            raw_swings.append(SwingPoint(
                index=i,
                price=float(pivot_highs.iloc[i]),
                type="high",
                label="H",
            ))
        if not np.isnan(pivot_lows.iloc[i]):
            raw_swings.append(SwingPoint(
                index=i,
                price=float(pivot_lows.iloc[i]),
                type="low",
                label="L",
            ))

    # Sort by index (chronological)
    raw_swings.sort(key=lambda s: s.index)

    if len(raw_swings) < 2:
        return raw_swings

    # Classify: compare each swing to the previous swing of the same type
    last_high: float | None = None
    last_low: float | None = None

    for swing in raw_swings:
        if swing.type == "high":
            if last_high is None:
                swing.label = "H"  # First high, no comparison
            elif swing.price > last_high:
                swing.label = "HH"
            else:
                swing.label = "LH"
            last_high = swing.price
        else:  # low
            if last_low is None:
                swing.label = "L"  # First low, no comparison
            elif swing.price > last_low:
                swing.label = "HL"
            else:
                swing.label = "LL"
            last_low = swing.price

    return raw_swings


def analyze_market_structure(
    df: pd.DataFrame,
    left_bars: int = 3,
    right_bars: int = 3,
    lookback_swings: int = 8,
) -> MarketStructureResult:
    """Analyze market structure from price data.

    Args:
        df: DataFrame with OHLCV data (sorted chronologically).
        left_bars: Bars for pivot detection.
        right_bars: Bars for pivot detection.
        lookback_swings: Number of recent swings to include in analysis.

    Returns:
        MarketStructureResult with swing classification and structure state.
    """
    swings = detect_swings(df, left_bars, right_bars)

    if len(swings) < 4:
        return MarketStructureResult(
            swings=swings,
            current_structure="Undefined",
            structure_breaks=0,
            summary="Insufficient swing data for structure analysis",
        )

    # Take the most recent swings
    recent = swings[-lookback_swings:] if len(swings) > lookback_swings else swings

    # Determine current structure from recent high/low labels
    recent_highs = [s for s in recent if s.type == "high" and s.label in ("HH", "LH")]
    recent_lows = [s for s in recent if s.type == "low" and s.label in ("HL", "LL")]

    # Count bullish vs bearish signals
    bullish_signals = sum(1 for s in recent_highs if s.label == "HH") + \
                      sum(1 for s in recent_lows if s.label == "HL")
    bearish_signals = sum(1 for s in recent_highs if s.label == "LH") + \
                      sum(1 for s in recent_lows if s.label == "LL")

    total = bullish_signals + bearish_signals
    if total == 0:
        current_structure = "Undefined"
    elif bullish_signals > bearish_signals * 1.5:
        current_structure = "Bullish"
    elif bearish_signals > bullish_signals * 1.5:
        current_structure = "Bearish"
    else:
        current_structure = "Transition"

    # Count structure breaks (transitions from HH→LH or LL→HL)
    structure_breaks = _count_structure_breaks(recent)

    # Build summary
    summary = _build_summary(recent, current_structure, structure_breaks)

    return MarketStructureResult(
        swings=recent,
        current_structure=current_structure,
        structure_breaks=structure_breaks,
        summary=summary,
    )


def _count_structure_breaks(swings: list[SwingPoint]) -> int:
    """Count structure breaks in swing sequence.

    A structure break occurs when:
    - Bullish→Bearish: HH followed by LH, or HL followed by LL
    - Bearish→Bullish: LH followed by HH, or LL followed by HL
    """
    breaks = 0
    highs = [s for s in swings if s.type == "high" and s.label in ("HH", "LH")]
    lows = [s for s in swings if s.type == "low" and s.label in ("HL", "LL")]

    for i in range(1, len(highs)):
        prev, curr = highs[i - 1].label, highs[i].label
        if (prev == "HH" and curr == "LH") or (prev == "LH" and curr == "HH"):
            breaks += 1

    for i in range(1, len(lows)):
        prev, curr = lows[i - 1].label, lows[i].label
        if (prev == "HL" and curr == "LL") or (prev == "LL" and curr == "HL"):
            breaks += 1

    return breaks


def _build_summary(
    swings: list[SwingPoint],
    structure: str,
    breaks: int,
) -> str:
    """Build human-readable market structure summary."""
    lines = []

    # Show recent swing sequence
    for i, swing in enumerate(swings, 1):
        marker = " ← Break" if _is_break_point(swings, i - 1) else ""
        lines.append(
            f"  {i}. ${swing.price:,.0f} ({swing.label}){marker}"
        )

    lines.append(f"  Current Structure: {structure}")
    lines.append(f"  Structure Breaks: {breaks}")

    return "\n".join(lines)


def _is_break_point(swings: list[SwingPoint], idx: int) -> bool:
    """Check if a swing point represents a structure break."""
    if idx < 1:
        return False

    curr = swings[idx]
    # Find previous swing of same type
    for i in range(idx - 1, -1, -1):
        prev = swings[i]
        if prev.type == curr.type:
            if curr.type == "high":
                return (prev.label == "HH" and curr.label == "LH") or \
                       (prev.label == "LH" and curr.label == "HH")
            else:
                return (prev.label == "HL" and curr.label == "LL") or \
                       (prev.label == "LL" and curr.label == "HL")
    return False
