# Perpetual Predict

Cryptocurrency futures prediction system for BTCUSDT.P on 4H timeframes.

## Features

- Automated data collection from Binance Futures API
- Technical analysis indicators (SMA, EMA, RSI, MACD, etc.)
- LLM-based price direction prediction via Claude CLI
- Discord notifications for scheduler status and predictions

## Quick Start

```bash
# Install dependencies
uv sync

# Run data collection
uv run python -m perpetual_predict collect

# Run scheduler (single execution)
uv run python -m perpetual_predict daemon --run-once
```

