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

## Adding New Seed Data

신규 시드데이터 추가 시 반드시 아래 프로세스를 따른다:

1. **수집**: `collectors/` 에 컬렉터 생성 → `cli/collect.py`의 `asyncio.gather()`에 추가
2. **저장**: `storage/models.py`에 데이터클래스 → `storage/database.py`에 테이블/CRUD 추가
3. **무결성 검증**: `reporters/data_integrity.py`의 `LatestDataVerification`에 검증 필드 추가 + `verify_latest_data()`에 검증 로직 추가 (A/B 테스트 여부와 무관하게 항상 적용)
4. **컨텍스트**: `llm/context/builder.py`의 `MarketContext`에 필드 추가 + `_section_*()` 메서드 + `format_prompt()`에 모듈 체크 + `build()`에서 데이터 로드
5. **모듈 등록**: `experiment/models.py`의 `SEED_MODULES`에 추가 + **`EXPERIMENTAL_MODULES`에도 추가** (baseline에서 제외)
6. **알림**: `notifications/scheduler_alerts.py`에 수집 완료/검증 리포트 필드 추가

**중요**: 신규 시드데이터는 `EXPERIMENTAL_MODULES`에 등록하여 baseline 예측에서 제외한다. A/B 테스트(`experiment create --add <module>`)로 효과를 검증한 후, `EXPERIMENTAL_MODULES`에서 제거하면 `DEFAULT_MODULES`에 자동 포함된다. 시드데이터의 `_section_*()` 메서드는 원시 데이터만 제공하고, 해석/시그널은 포함하지 않는다 (에이전트 자율 판단).

## Environment Variables

Required:
- `BINANCE_API_KEY`, `BINANCE_API_SECRET` - Binance Futures API credentials

Optional (see `config/settings.py` for defaults):
- `DISCORD_WEBHOOK_URL`, `DISCORD_ENABLED` - Discord notifications
- `SCHEDULER_CRON_HOUR=0,4,8,12,16,20` - 4H candle close times
- `DATABASE_PATH=data/perpetual_predict.db`

## Database Tables

Predictions are stored with `is_correct` initially NULL, then evaluated when the target candle closes. Query pending evaluations: `SELECT * FROM predictions WHERE is_correct IS NULL`
