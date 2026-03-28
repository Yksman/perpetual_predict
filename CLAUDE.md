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

# A/B experiment management
uv run python -m perpetual_predict experiment create --name "test_macro" --add macro
uv run python -m perpetual_predict experiment list                                    # List experiments
uv run python -m perpetual_predict experiment status <experiment_id>                  # Show results
uv run python -m perpetual_predict experiment pause <experiment_id>
uv run python -m perpetual_predict experiment resume <experiment_id>
uv run python -m perpetual_predict experiment merge <experiment_id>                   # Promote winner

# Dashboard data export
uv run python -m perpetual_predict export                    # Export to JSON
uv run python -m perpetual_predict export --push             # Export and push to git data branch
```

## Architecture

**Data Flow**: Binance API → Collectors → SQLite → LLM Context Builder → Claude CLI → Predictions → Evaluator → Discord

**Key Modules**:
- `cli/` - Command entry points: `collect.py`, `cycle.py`, `daemon.py`, `report.py`, `experiment.py`, `export.py`
- `collectors/binance/` - Async collectors sharing a `BinanceClient` session
- `collectors/macro/` - Macroeconomic data: `fred_collector.py` (FRED API), `market_index_collector.py` (yfinance: SPX, NASDAQ, DXY, GOLD)
- `collectors/news/` - News collection: `news_collector.py` (RSS primary), `rss_collector.py` (feedparser, CoinTelegraph + CoinDesk)
- `llm/agent/runner.py` - Invokes `claude -p --output-format json --json-schema` for structured predictions
- `llm/context/builder.py` - Builds market context prompt from collected data
- `llm/evaluation/evaluator.py` - Compares predictions against actual candle outcomes
- `experiment/` - A/B testing framework: `models.py` (multi-variant `Experiment.variants: dict`, SEED_MODULES, EXPERIMENTAL_MODULES), `analyzer.py` (per-variant VariantResult, statistical significance)
- `trading/` - Paper trading engine: `engine.py` (positions from predictions), `metrics.py` (accuracy, PnL, Sharpe)
- `export/exporter.py` - Exports predictions, trades, metrics to JSON for dashboard consumption
- `scheduler/scheduler.py` - APScheduler-based cron (4H intervals)
- `storage/database.py` - Async SQLite via `aiosqlite`, context manager pattern: `async with get_database() as db:`
- `notifications/discord_webhook.py` - Discord embeds for scheduler status and predictions

## Prediction Cycle (`scheduler/jobs.py`)

`cycle` 명령은 3단계를 순차 실행하며, `fcntl.flock()`으로 동시 실행을 방지한다:

1. **Evaluate**: 대상 캔들이 마감된 미평가 예측(is_correct=NULL)을 찾아 실제 방향과 비교. NEUTRAL 임계값 ±0.2% (수수료 손익분기)
2. **Collect + Verify**: `collect_with_verification()` — 수집 후 데이터 무결성 검증. 실패 시 5회 재시도 (2s~10s 지수 백오프). 각 재시도마다 Discord 알림
3. **Predict**: baseline 예측 실행 → 활성 실험이 있으면 모든 variant arm을 **병렬 실행** (max 4 concurrent, `asyncio.gather`). Control arm은 baseline 예측을 복사 재사용. 각 variant는 독립 paper trading 계좌(`{experiment_id}_variant_{name}`)에 거래 오픈. 에이전트는 `position_pct`(0.0~max_leverage)로 투자금 대비 진입 비율을 결정

## Context Builder Module System

`llm/context/builder.py`의 `MarketContextBuilder.build()`:
1. Binance에서 250개 캔들 fetch → pandas DataFrame 변환
2. `analyzers/technical/` 8개 모듈로 지표 계산 (trend, momentum, volatility, price_structure, volume, market_structure, divergence, support_resistance)
3. 추가 데이터 fetch: funding_rates, OI, long_short, fear_greed, liquidations, macro, news (RSS)
4. `MarketContext` dataclass (~126 fields) 조립
5. `format_prompt(enabled_modules)`: 모듈 이름 → `_section_*()` 매핑으로 프롬프트 생성. `None`이면 `DEFAULT_MODULES` 사용

## Dashboard (`dashboard/`)

React 19 + Vite + TypeScript 정적 앱. 백엔드 API 없이 `export` 명령이 생성한 JSON 파일(`dashboard/data/*.json`)을 fetch하여 렌더링. Vercel 배포.

- `predictions.json`, `trades.json`, `metrics.json`, `meta.json`, `experiments.json`
- Tabs: Predictions (적중률, 신뢰도), Trading (PnL, 승률, 드로다운), Experiments (control vs multi-variant, 각 variant별 카드)

## Key Patterns

- **Async context managers**: Database uses `async with get_database() as db:` pattern
- **Parallel API calls**: Collectors use `asyncio.gather(..., return_exceptions=True)` for concurrent requests
- **Sync library wrapping**: yfinance, fredapi 등 동기 라이브러리는 `asyncio.get_running_loop().run_in_executor(None, sync_method, args)` 패턴으로 래핑
- **Structured LLM output**: Predictions use JSON schema validation with fallback text parsing
- **Settings singleton**: `get_settings()` lazily loads from env vars, use `reload_settings()` to refresh
- **Unified position sizing**: Agent outputs single `position_pct` (0.0~max_leverage). Values >1.0 imply leverage (e.g., 1.5 = 150% of balance = 1.5x leverage). Trading engine derives `notional_value = balance × position_pct` directly.

## Adding New Seed Data

신규 시드데이터 추가 시 반드시 아래 프로세스를 따른다:

1. **수집**: `collectors/` 에 컬렉터 생성 → `cli/collect.py`의 `asyncio.gather()`에 추가
2. **저장**: `storage/models.py`에 데이터클래스 → `storage/database.py`에 테이블/CRUD 추가
3. **무결성 검증**: `reporters/data_integrity.py`의 `LatestDataVerification`에 검증 필드 추가 + `verify_latest_data()`에 검증 로직 추가 (A/B 테스트 여부와 무관하게 항상 적용)
4. **컨텍스트**: `llm/context/builder.py`의 `MarketContext`에 필드 추가 + `_section_*()` 메서드 + `format_prompt()`에 모듈 체크 + `build()`에서 데이터 로드
5. **모듈 등록**: `experiment/models.py`의 `SEED_MODULES`에 추가 + **`EXPERIMENTAL_MODULES`에도 추가** (baseline에서 제외)
6. **알림**: `notifications/scheduler_alerts.py`에 수집 완료/검증 리포트 필드 추가

**중요**: 신규 시드데이터는 `EXPERIMENTAL_MODULES`에 등록하여 baseline 예측에서 제외한다. A/B 테스트(`experiment create --add <module>`)로 효과를 검증한 후, `EXPERIMENTAL_MODULES`에서 제거하면 `DEFAULT_MODULES`에 자동 포함된다. 시드데이터의 `_section_*()` 메서드는 원시 데이터만 제공하고, 해석/시그널은 포함하지 않는다 (에이전트 자율 판단).

## A/B Testing Framework

실험 시스템은 control(baseline 모듈) vs 하나 이상의 named variant 구성을 비교한다.

**Multi-variant 구조**: `Experiment.variants: dict[str, list[str]]` — 키는 variant 이름, 값은 해당 arm의 모듈 목록. CLI: `experiment create --name <name> --variant macro --variant news --variant macro,news`

**모듈 라이프사이클**:
1. 신규 모듈 → `EXPERIMENTAL_MODULES` 등록 → `DEFAULT_MODULES`에서 자동 제외
2. `experiment create --variant <modules>` → control + N개 variant arm 생성, 각 arm별 독립 paper trading 계좌 (`{experiment_id}_variant_{name}`)
3. `min_samples`(기본 30) 이상 예측 누적 후 variant별 통계적 유의성 검정 (p-value < 0.05)
4. `experiment merge [--variant <name>]` → 승리 variant의 모듈을 `EXPERIMENTAL_MODULES`에서 제거하여 baseline에 포함

**Variant 병렬 실행**: 모든 variant가 `asyncio.gather`로 병렬 실행 (max 4 concurrent). `claude -p`는 독립 subprocess이므로 완전한 프로세스 격리.

**Control 재사용 최적화**: baseline 예측은 모든 활성 실험의 control arm으로 복사 저장. `claude -p` 호출은 1회만 실행.

**평가 지표**: `accuracy` (방향 적중률), `net_return` (누적 수익률%), `sharpe` (위험 조정 수익률)

**현재 실험 모듈**: `news` (RSS 뉴스 헤드라인, CoinTelegraph + CoinDesk)

**Sentiment 모듈 분리**: `sentiment` (legacy) → `sentiment_market` (funding rate, OI, long/short ratio) + `fear_greed` (Alternative.me index). Legacy `"sentiment"` 키는 두 모듈 모두 활성화하는 backward-compat 경로로 유지됨.

## Environment Variables

Required:
- `BINANCE_API_KEY`, `BINANCE_API_SECRET` - Binance Futures API credentials

Optional (see `config/settings.py` for defaults):
- `DISCORD_WEBHOOK_URL`, `DISCORD_ENABLED` - Discord notifications
- `SCHEDULER_CRON_HOUR=0,4,8,12,16,20` - 4H candle close times
- `DATABASE_PATH=data/perpetual_predict.db`
- `FRED_API_KEY` - FRED API key for macroeconomic data (fred.stlouisfed.org)
- `MACRO_ENABLED=true` - Enable/disable macro data collection
- `NEWS_ENABLED=true` - Enable/disable news collection
- `NEWS_MAX_HEADLINES=100` - Maximum headlines to include in prompt context
- `NEWS_RSS_FEEDS` - Comma-separated RSS feed URLs (default: CoinTelegraph + CoinDesk)
- `EXPERIMENT_ENABLED=false` - Enable A/B experiment arms in cycle
- `EXPERIMENT_MIN_SAMPLES=30` - Minimum samples before significance test
- `EXPERIMENT_SIGNIFICANCE=0.05` - p-value threshold
- `EXPERIMENT_PRIMARY_METRIC=net_return` - Primary metric: `accuracy | net_return | sharpe`
- `PAPER_TRADING_ENABLED=true`, `PAPER_TRADING_INITIAL_BALANCE=1000.0`, `PAPER_TRADING_MAX_LEVERAGE=3.0`
- `DASHBOARD_EXPORT_ENABLED=false`, `DASHBOARD_AUTO_PUSH=false`, `DASHBOARD_GIT_DATA_BRANCH=data`

## Database Tables

Predictions are stored with `is_correct` initially NULL, then evaluated when the target candle closes. Query pending evaluations: `SELECT * FROM predictions WHERE is_correct IS NULL`
