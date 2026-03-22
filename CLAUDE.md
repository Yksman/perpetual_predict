# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Perpetual Predict is a cryptocurrency futures prediction system for BTCUSDT.P on 4H timeframes. The system collects market data, runs technical analysis, makes predictions via Claude Code CLI (`claude -p`), evaluates past predictions, and sends Discord notifications.

## Commands

```bash
# Install dependencies
uv sync

# Run linter
ruff check .

# Run tests (async mode auto-enabled via pyproject.toml)
pytest
pytest tests/test_notifications/test_scheduler_alerts.py  # Single file

# CLI commands
uv run python -m perpetual_predict collect                  # Collect market data
uv run python -m perpetual_predict report                   # Generate analysis report
uv run python -m perpetual_predict cycle                    # Full cycle: evaluate → collect → predict
uv run python -m perpetual_predict cycle --phase predict    # Run single phase
uv run python -m perpetual_predict daemon --run-once        # Single collection
```

## Architecture

**Data Flow**: Binance API → Collectors → SQLite → LLM Context Builder → Claude CLI → Predictions → Evaluator → Discord

**Key Modules**:
- `cli/` - Command entry points: `collect.py`, `cycle.py`, `daemon.py`, `report.py`
- `collectors/binance/` - Async collectors sharing a `BinanceClient` session
- `llm/agent/runner.py` - Invokes `claude -p --output-format json --json-schema` for structured predictions
- `llm/context/builder.py` - Builds market context prompt from collected data
- `llm/evaluation/evaluator.py` - Compares predictions against actual candle outcomes
- `scheduler/scheduler.py` - APScheduler-based cron (4H intervals)
- `storage/database.py` - Async SQLite via `aiosqlite`, context manager pattern: `async with get_database() as db:`
- `notifications/discord_webhook.py` - Discord embeds for scheduler status and predictions

## Key Patterns

- **Async context managers**: Database uses `async with get_database() as db:` pattern
- **Parallel API calls**: Collectors use `asyncio.gather(..., return_exceptions=True)` for concurrent requests
- **File locking**: `cycle` command uses `fcntl.flock()` to prevent concurrent execution
- **Structured LLM output**: Predictions use JSON schema validation with fallback text parsing
- **Settings singleton**: `get_settings()` lazily loads from env vars, use `reload_settings()` to refresh

## Environment Variables

Required:
- `BINANCE_API_KEY`, `BINANCE_API_SECRET` - Binance Futures API credentials

Optional (see `config/settings.py` for defaults):
- `DISCORD_WEBHOOK_URL`, `DISCORD_ENABLED` - Discord notifications
- `SCHEDULER_CRON_HOUR=0,4,8,12,16,20` - 4H candle close times
- `DATABASE_PATH=data/perpetual_predict.db`

## Database Tables

Predictions are stored with `is_correct` initially NULL, then evaluated when the target candle closes. Query pending evaluations: `SELECT * FROM predictions WHERE is_correct IS NULL`
