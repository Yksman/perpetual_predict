# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Perpetual Predict is a cryptocurrency futures prediction system for BTCUSDT.P on 4H timeframes. Phase 1 MVP focuses on data collection automation and analysis report generation for manual Claude Code analysis.

## Commands

```bash
# Install dependencies
uv sync  # or pip install -e .

# Run linter
ruff check .

# Run tests
pytest

# Run single test file
pytest tests/test_collectors/test_market_data.py

# CLI commands (after implementation)
python -m perpetual_predict collect   # Collect market data
python -m perpetual_predict report    # Generate analysis report
```

## Architecture

```
perpetual_predict/
├── collectors/           # Async data collectors
│   ├── base_collector.py    # Abstract base class
│   ├── binance/             # Binance Futures API
│   │   ├── client.py           # API client with retry logic
│   │   ├── market_data.py      # OHLCV & long/short ratio
│   │   ├── funding.py          # Funding rate collector
│   │   └── open_interest.py    # Open interest collector
│   └── sentiment/           # External sentiment sources
│       └── fear_greed.py       # Fear & Greed Index
├── analyzers/            # Technical analysis
│   └── technical/
│       ├── trend.py         # SMA, EMA, MACD, ADX
│       ├── momentum.py      # RSI, Stochastic RSI
│       ├── volatility.py    # Bollinger Bands, ATR
│       ├── volume.py        # OBV, VWAP
│       └── support_resistance.py
├── storage/              # Data persistence
│   ├── database.py          # SQLite connection/operations
│   └── models.py            # Data models
├── reporters/            # Report generation
│   ├── markdown_generator.py
│   └── templates/
│       └── analysis_report.md.j2
├── config/               # Configuration
│   ├── __init__.py
│   └── settings.py          # Env vars & settings
└── utils/
    ├── logger.py            # Logging setup
    └── retry.py             # Retry decorator for API calls
```

## Key Patterns

- **Async collectors**: All Binance API collectors use `asyncio` and `aiohttp`
- **Retry logic**: API calls wrapped with exponential backoff via `utils/retry.py`
- **SQLite storage**: Single `storage/database.py` handles all DB operations
- **Jinja2 reports**: Markdown templates in `reporters/templates/`

## Tech Stack

- Python 3.12+
- `aiohttp` for async HTTP
- `pandas` for data manipulation
- `ta` or `pandas-ta` for technical indicators
- `SQLite` for local storage
- `Jinja2` for report templates
- `ruff` for linting
- `pytest` for testing

## Out of Scope (Do Not Implement)

- Auto-trading (order_manager.py, position_tracker.py)
- Claude API auto-analysis integration
- Telegram Bot notifications
- Backtesting system
- WebSocket real-time data
- Liquidation data collection
- On-chain exchange flow/whale alerts
- CryptoPanic news collection
- Scheduler automation

## Ralph Agent System

This project uses `ralph.sh` for autonomous task execution:
- Tasks defined in `.ralph/current/PRD.md`
- Progress logged to `.ralph/current/progress.txt`
- Each task = one commit with format: `feat: US-XX - [task name]`
- Run `./ralph.sh` to start autonomous development loop
