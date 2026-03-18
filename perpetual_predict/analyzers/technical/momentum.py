"""Momentum indicators: RSI, Stochastic RSI."""

import pandas as pd
import pandas_ta as ta


def calculate_rsi(
    df: pd.DataFrame,
    period: int = 14,
    column: str = "close",
) -> pd.Series:
    """Calculate Relative Strength Index (RSI).

    Args:
        df: DataFrame with price data.
        period: RSI period (default 14).
        column: Column to use for calculation (default "close").

    Returns:
        Series with RSI values.
    """
    return ta.rsi(df[column], length=period)


def calculate_stoch_rsi(
    df: pd.DataFrame,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_period: int = 3,
    d_period: int = 3,
    column: str = "close",
) -> pd.DataFrame:
    """Calculate Stochastic RSI.

    Args:
        df: DataFrame with price data.
        rsi_period: RSI calculation period.
        stoch_period: Stochastic period.
        k_period: %K smoothing period.
        d_period: %D smoothing period.
        column: Column to use for calculation (default "close").

    Returns:
        DataFrame with STOCHRSIk and STOCHRSId columns.
    """
    result = ta.stochrsi(
        df[column],
        length=rsi_period,
        rsi_length=rsi_period,
        k=k_period,
        d=d_period,
    )
    return result


def add_momentum_indicators(
    df: pd.DataFrame,
    rsi_periods: list[int] | None = None,
    stoch_rsi_params: dict | None = None,
) -> pd.DataFrame:
    """Add momentum indicators to DataFrame.

    Args:
        df: DataFrame with OHLCV data.
        rsi_periods: List of RSI periods (default [14]).
        stoch_rsi_params: Stochastic RSI parameters (default standard params).

    Returns:
        DataFrame with added momentum indicator columns.
    """
    if rsi_periods is None:
        rsi_periods = [14]

    if stoch_rsi_params is None:
        stoch_rsi_params = {
            "rsi_period": 14,
            "stoch_period": 14,
            "k_period": 3,
            "d_period": 3,
        }

    result = df.copy()

    # Add RSI for each period
    for period in rsi_periods:
        rsi = calculate_rsi(df, period=period)
        if rsi is not None:
            result[f"RSI_{period}"] = rsi

    # Add Stochastic RSI
    stoch_rsi = calculate_stoch_rsi(df, **stoch_rsi_params)
    if stoch_rsi is not None:
        for col in stoch_rsi.columns:
            result[col] = stoch_rsi[col]

    return result
