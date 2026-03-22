"""Market context builder for LLM predictions."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from perpetual_predict.analyzers.technical.momentum import add_momentum_indicators
from perpetual_predict.analyzers.technical.price_structure import (
    add_price_structure_indicators,
    interpret_body_ratio,
    interpret_close_in_range,
    interpret_volume_ratio,
)
from perpetual_predict.analyzers.technical.trend import (
    add_trend_indicators,
    interpret_ema_distance,
)
from perpetual_predict.analyzers.technical.volatility import (
    add_volatility_indicators,
    interpret_atr_ratio,
    interpret_bb_squeeze,
)
from perpetual_predict.analyzers.technical.volume import (
    add_volume_indicators,
    interpret_cvd,
)
from perpetual_predict.storage.database import Database
from perpetual_predict.storage.models import (
    Candle,
    OpenInterest,
)
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MarketContext:
    """Complete market context for LLM prediction."""

    # Price data
    current_price: float
    price_change_4h: float
    price_change_24h: float
    high_24h: float
    low_24h: float
    volume_24h: float

    # Price structure (NEW)
    body_ratio: float = 0.0
    upper_wick_ratio: float = 0.0
    lower_wick_ratio: float = 0.0
    close_in_range: float = 0.5
    volume_ratio: float = 1.0

    # Technical indicators
    sma_20: float = 0.0
    sma_50: float = 0.0
    sma_200: float = 0.0
    ema_12: float = 0.0
    ema_26: float = 0.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0
    rsi: float = 50.0
    stoch_rsi_k: float = 50.0
    stoch_rsi_d: float = 50.0
    adx: float = 20.0
    atr: float = 0.0
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0

    # EMA distances (NEW)
    dist_ema_9: float = 0.0
    dist_ema_21: float = 0.0
    dist_ema_55: float = 0.0
    dist_ema_200: float = 0.0

    # Volatility (NEW)
    atr_ratio: float = 1.0
    bb_squeeze: bool = False

    # CVD (NEW)
    cvd: float = 0.0
    cvd_ratio: float = 0.0

    # Liquidation (NEW)
    long_liquidation_volume: float = 0.0
    short_liquidation_volume: float = 0.0
    liquidation_imbalance: float = 0.0

    # Market sentiment
    funding_rate: float = 0.0
    funding_rate_8h_ago: float = 0.0
    open_interest: float = 0.0
    oi_change_24h: float = 0.0
    long_short_ratio: float = 1.0
    fear_greed_value: int = 50
    fear_greed_classification: str = "Neutral"

    # Recent candle summary
    recent_candles_summary: str = ""

    # Metadata
    symbol: str = "BTCUSDT"
    timeframe: str = "4h"
    context_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def format_prompt(self) -> str:
        """Format context as LLM prompt."""
        # Price position relative to MAs
        sma_20_pos = "above" if self.current_price > self.sma_20 else "below"
        sma_50_pos = "above" if self.current_price > self.sma_50 else "below"
        sma_200_pos = "above" if self.current_price > self.sma_200 else "below"

        # RSI interpretation
        if self.rsi > 70:
            rsi_interp = "Overbought"
        elif self.rsi < 30:
            rsi_interp = "Oversold"
        else:
            rsi_interp = "Neutral"

        # ADX interpretation
        if self.adx > 50:
            adx_interp = "Very Strong Trend"
        elif self.adx > 25:
            adx_interp = "Strong Trend"
        else:
            adx_interp = "Weak/No Trend"

        # Funding rate interpretation
        if self.funding_rate > 0.03:
            funding_interp = "Extreme Long Bias (reversal risk)"
        elif self.funding_rate > 0.01:
            funding_interp = "Long Bias"
        elif self.funding_rate < -0.03:
            funding_interp = "Extreme Short Bias (reversal risk)"
        elif self.funding_rate < -0.01:
            funding_interp = "Short Bias"
        else:
            funding_interp = "Neutral"

        # BB position
        bb_range = self.bb_upper - self.bb_lower
        if bb_range > 0:
            bb_pct = (self.current_price - self.bb_lower) / bb_range * 100
            bb_pos = f"{bb_pct:.0f}% from lower band"
        else:
            bb_pos = "N/A"

        # MACD interpretation
        macd_trend = "Bullish" if self.macd > self.macd_signal else "Bearish"
        macd_momentum = "Increasing" if self.macd_histogram > 0 else "Decreasing"

        # New interpretations
        body_interp = interpret_body_ratio(self.body_ratio)
        close_pos_interp = interpret_close_in_range(self.close_in_range)
        volume_interp = interpret_volume_ratio(self.volume_ratio)
        ema9_interp = interpret_ema_distance(self.dist_ema_9, 9)
        ema200_interp = interpret_ema_distance(self.dist_ema_200, 200)
        atr_interp = interpret_atr_ratio(self.atr_ratio)
        squeeze_interp = interpret_bb_squeeze(self.bb_squeeze, self.atr_ratio)
        cvd_interp = interpret_cvd(self.cvd, self.volume_24h / 6 if self.volume_24h > 0 else 1)

        # Liquidation interpretation
        total_liq = self.long_liquidation_volume + self.short_liquidation_volume
        if total_liq < 1.0:
            liq_interp = "Low liquidation activity"
        elif self.liquidation_imbalance > 0.3:
            liq_interp = "More longs liquidated (bearish)"
        elif self.liquidation_imbalance < -0.3:
            liq_interp = "More shorts liquidated (bullish)"
        else:
            liq_interp = "Balanced liquidations"

        prompt = f"""## {self.symbol} {self.timeframe} Market Analysis
Time: {self.context_time.strftime("%Y-%m-%d %H:%M UTC")}

### Price Action
- Current Price: ${self.current_price:,.2f}
- 4H Change: {self.price_change_4h:+.2f}%
- 24H Change: {self.price_change_24h:+.2f}%
- 24H High: ${self.high_24h:,.2f}
- 24H Low: ${self.low_24h:,.2f}
- 24H Volume: ${self.volume_24h:,.0f}

### Candle Structure (Latest)
- Body Ratio: {self.body_ratio:.4f} ({body_interp})
- Upper Wick: {self.upper_wick_ratio:.4f}
- Lower Wick: {self.lower_wick_ratio:.4f}
- Close Position: {self.close_in_range:.1%} ({close_pos_interp})
- Volume vs Prev: {self.volume_ratio:.2f}x ({volume_interp})

### EMA Distance (Trend Strength)
- EMA 9: {self.dist_ema_9:+.2f}% ({ema9_interp})
- EMA 21: {self.dist_ema_21:+.2f}%
- EMA 55: {self.dist_ema_55:+.2f}%
- EMA 200: {self.dist_ema_200:+.2f}% ({ema200_interp})

### Trend Indicators
- SMA 20: ${self.sma_20:,.2f} (Price {sma_20_pos})
- SMA 50: ${self.sma_50:,.2f} (Price {sma_50_pos})
- SMA 200: ${self.sma_200:,.2f} (Price {sma_200_pos})
- EMA 12/26: ${self.ema_12:,.2f} / ${self.ema_26:,.2f}
- MACD: {self.macd:.2f} | Signal: {self.macd_signal:.2f} | Histogram: {self.macd_histogram:.2f}
- MACD Status: {macd_trend}, momentum {macd_momentum}
- ADX: {self.adx:.1f} ({adx_interp})

### Momentum Indicators
- RSI (14): {self.rsi:.1f} ({rsi_interp})
- Stochastic RSI: K={self.stoch_rsi_k:.1f}, D={self.stoch_rsi_d:.1f}

### Volatility
- ATR (14): ${self.atr:,.2f} ({self.atr / self.current_price * 100:.2f}% of price)
- ATR Ratio: {self.atr_ratio:.2f} ({atr_interp})
- BB Squeeze: {"YES" if self.bb_squeeze else "No"} ({squeeze_interp})
- Bollinger Bands: Upper ${self.bb_upper:,.2f} | Middle ${self.bb_middle:,.2f} | Lower ${self.bb_lower:,.2f}
- Price Position: {bb_pos}

### CVD (Buy/Sell Pressure)
- CVD 4H: {self.cvd:+,.2f} BTC
- CVD Ratio: {self.cvd_ratio:+.2f} ({cvd_interp})

### Liquidation Pressure
- Long Liquidations: {self.long_liquidation_volume:.4f} BTC
- Short Liquidations: {self.short_liquidation_volume:.4f} BTC
- Imbalance: {self.liquidation_imbalance:+.2f} ({liq_interp})

### Market Sentiment
- Funding Rate: {self.funding_rate * 100:.4f}% ({funding_interp})
- Funding 8H Ago: {self.funding_rate_8h_ago * 100:.4f}%
- Funding Change: {(self.funding_rate - self.funding_rate_8h_ago) * 100:+.4f}%
- Open Interest: ${self.open_interest:,.0f}
- OI 24H Change: {self.oi_change_24h:+.2f}%
- Long/Short Ratio: {self.long_short_ratio:.2f} ({"Longs dominate" if self.long_short_ratio > 1 else "Shorts dominate" if self.long_short_ratio < 1 else "Balanced"})
- Fear & Greed Index: {self.fear_greed_value} ({self.fear_greed_classification})

### Recent Candles (Last 5)
{self.recent_candles_summary}

---
Based on this analysis, predict the direction of the NEXT {self.timeframe} candle.

**중요: 모든 응답(reasoning, key_factors)은 반드시 한국어로 작성하세요.**"""

        return prompt


class MarketContextBuilder:
    """Builds market context from database data."""

    def __init__(
        self,
        db: Database,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
    ):
        self.db = db
        self.symbol = symbol
        self.timeframe = timeframe

    async def build(self, lookback_candles: int = 250) -> MarketContext:
        """Build complete market context.

        Args:
            lookback_candles: Number of historical candles for technical analysis.
                Default 250 for SMA200 calculation + buffer.

        Returns:
            MarketContext with all market data.
        """
        # Fetch candles
        candles = await self.db.get_candles(
            self.symbol, self.timeframe, limit=lookback_candles
        )

        if not candles or len(candles) < 10:
            raise ValueError(f"Insufficient candle data for {self.symbol} {self.timeframe}")

        # Convert to DataFrame and sort chronologically
        df = self._candles_to_df(candles)
        df = df.sort_values("open_time").reset_index(drop=True)

        # Add technical indicators
        df = add_trend_indicators(df)
        df = add_momentum_indicators(df)
        df = add_volatility_indicators(df)
        df = add_price_structure_indicators(df)
        df = add_volume_indicators(df)

        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        # Fetch additional market data
        funding_rates = await self.db.get_funding_rates(self.symbol, limit=3)
        open_interests = await self.db.get_open_interests(self.symbol, limit=7)
        long_short = await self.db.get_long_short_ratios(self.symbol, limit=1)
        fear_greed = await self.db.get_fear_greeds(limit=1)
        liquidations = await self.db.get_liquidations(self.symbol, limit=1)

        # Calculate derived values
        price_change_4h = self._pct_change(latest["close"], prev["close"])
        price_change_24h = self._calculate_24h_change(df)
        oi_change_24h = self._calculate_oi_change(open_interests)

        # Recent candles summary
        recent_summary = self._summarize_recent_candles(df.tail(5))

        # Extract liquidation data
        liq = liquidations[0] if liquidations else None

        return MarketContext(
            current_price=float(latest["close"]),
            price_change_4h=price_change_4h,
            price_change_24h=price_change_24h,
            high_24h=float(df.tail(6)["high"].max()),
            low_24h=float(df.tail(6)["low"].min()),
            volume_24h=float(df.tail(6)["volume"].sum()),

            # Price structure (NEW)
            body_ratio=self._safe_get(latest, "body_ratio", 0.0),
            upper_wick_ratio=self._safe_get(latest, "upper_wick_ratio", 0.0),
            lower_wick_ratio=self._safe_get(latest, "lower_wick_ratio", 0.0),
            close_in_range=self._safe_get(latest, "close_in_range", 0.5),
            volume_ratio=self._safe_get(latest, "volume_ratio", 1.0),

            sma_20=self._safe_get(latest, "SMA_20", latest["close"]),
            sma_50=self._safe_get(latest, "SMA_50", latest["close"]),
            sma_200=self._safe_get(latest, "SMA_200", latest["close"]),
            ema_12=self._safe_get(latest, "EMA_12", latest["close"]),
            ema_26=self._safe_get(latest, "EMA_26", latest["close"]),
            macd=self._safe_get(latest, "MACD_12_26_9", 0),
            macd_signal=self._safe_get(latest, "MACDs_12_26_9", 0),
            macd_histogram=self._safe_get(latest, "MACDh_12_26_9", 0),
            rsi=self._safe_get(latest, "RSI_14", 50),
            stoch_rsi_k=self._safe_get(latest, "STOCHRSIk_14_14_3_3", 50),
            stoch_rsi_d=self._safe_get(latest, "STOCHRSId_14_14_3_3", 50),
            adx=self._safe_get(latest, "ADX_14", 20),
            atr=self._safe_get(latest, "ATRr_14", 0),
            bb_upper=self._safe_get(latest, "BBU_20_2.0", latest["close"] * 1.02),
            bb_middle=self._safe_get(latest, "BBM_20_2.0", latest["close"]),
            bb_lower=self._safe_get(latest, "BBL_20_2.0", latest["close"] * 0.98),

            # EMA distances (NEW)
            dist_ema_9=self._safe_get(latest, "dist_EMA_9", 0.0),
            dist_ema_21=self._safe_get(latest, "dist_EMA_21", 0.0),
            dist_ema_55=self._safe_get(latest, "dist_EMA_55", 0.0),
            dist_ema_200=self._safe_get(latest, "dist_EMA_200", 0.0),

            # Volatility (NEW)
            atr_ratio=self._safe_get(latest, "ATR_ratio_14", 1.0),
            bb_squeeze=bool(self._safe_get(latest, "BB_squeeze_20", False)),

            # CVD (NEW)
            cvd=self._safe_get(latest, "CVD", 0.0),
            cvd_ratio=self._safe_get(latest, "CVD_ratio", 0.0),

            # Liquidation (NEW)
            long_liquidation_volume=liq.long_liquidation_volume if liq else 0.0,
            short_liquidation_volume=liq.short_liquidation_volume if liq else 0.0,
            liquidation_imbalance=liq.imbalance if liq else 0.0,

            funding_rate=funding_rates[0].funding_rate if funding_rates else 0.0,
            funding_rate_8h_ago=funding_rates[1].funding_rate if len(funding_rates) > 1 else 0.0,
            open_interest=open_interests[0].open_interest_value if open_interests else 0.0,
            oi_change_24h=oi_change_24h,
            long_short_ratio=long_short[0].long_short_ratio if long_short else 1.0,
            fear_greed_value=fear_greed[0].value if fear_greed else 50,
            fear_greed_classification=fear_greed[0].classification if fear_greed else "Neutral",

            recent_candles_summary=recent_summary,

            symbol=self.symbol,
            timeframe=self.timeframe,
            context_time=datetime.now(timezone.utc),
        )

    def _candles_to_df(self, candles: list[Candle]) -> pd.DataFrame:
        """Convert candles to pandas DataFrame."""
        data = []
        for c in candles:
            data.append({
                "open_time": c.open_time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
                "taker_buy_base": c.taker_buy_base,  # For CVD calculation
            })
        return pd.DataFrame(data)

    def _pct_change(self, current: float, previous: float) -> float:
        """Calculate percentage change."""
        if previous == 0:
            return 0.0
        return ((current - previous) / previous) * 100

    def _calculate_24h_change(self, df: pd.DataFrame) -> float:
        """Calculate 24H price change (6 x 4H candles)."""
        if len(df) < 7:
            return 0.0
        current = df.iloc[-1]["close"]
        past = df.iloc[-7]["close"]  # 6 candles ago = 24H
        return self._pct_change(current, past)

    def _calculate_oi_change(self, ois: list[OpenInterest]) -> float:
        """Calculate 24H open interest change."""
        if len(ois) < 7:
            return 0.0
        current = ois[0].open_interest_value
        past = ois[6].open_interest_value if len(ois) > 6 else ois[-1].open_interest_value
        return self._pct_change(current, past)

    def _safe_get(self, row: pd.Series, key: str, default: float) -> float:
        """Safely get a value from a pandas Series."""
        val = row.get(key)
        if val is None or pd.isna(val):
            return default
        return float(val)

    def _summarize_recent_candles(self, df: pd.DataFrame) -> str:
        """Generate human-readable summary of recent candles."""
        lines = []
        for i, (_, row) in enumerate(df.iterrows(), 1):
            change = self._pct_change(row["close"], row["open"])
            direction = "+" if change >= 0 else ""
            candle_type = "Bullish" if change >= 0 else "Bearish"

            # Simple pattern detection
            body = abs(row["close"] - row["open"])
            upper_wick = row["high"] - max(row["close"], row["open"])
            lower_wick = min(row["close"], row["open"]) - row["low"]
            total_range = row["high"] - row["low"]

            if total_range > 0:
                body_pct = body / total_range * 100
                if body_pct < 20:
                    pattern = "Doji"
                elif upper_wick > body * 2:
                    pattern = "Shooting Star" if change < 0 else "Inverted Hammer"
                elif lower_wick > body * 2:
                    pattern = "Hammer" if change >= 0 else "Hanging Man"
                else:
                    pattern = candle_type
            else:
                pattern = "Flat"

            lines.append(
                f"  {i}. {direction}{change:.2f}% | "
                f"O: ${row['open']:,.0f} H: ${row['high']:,.0f} "
                f"L: ${row['low']:,.0f} C: ${row['close']:,.0f} | {pattern}"
            )

        return "\n".join(lines)
