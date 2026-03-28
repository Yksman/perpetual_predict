# News/Event Sentiment Module Design

## Overview

CryptoPanic API (primary) + RSS fallback을 사용하여 크립토 뉴스/이벤트 데이터를 수집하고, LLM 예측 에이전트에게 시드데이터로 제공하는 모듈.

**목표**: 현재 ~50%인 4H 방향 예측 성공률을 개선하기 위해, LLM이 가장 잘 활용할 수 있는 데이터 유형(뉴스/이벤트 센티먼트)을 추가한다.

**근거**: 학술 연구(Lopez-Lira & Tang, 2023 외 다수)에서 LLM 금융 예측에 가장 큰 개선 폭(+2~5%)을 보인 데이터 유형이 뉴스/이벤트 센티먼트임.

## Data Flow

```
4H Cycle (cron: 0,4,8,12,16,20시)
│
├─ Evaluate (이전 예측 평가)
│
├─ Collect (asyncio.gather - 모두 병렬)
│   ├─ Binance: candles, funding, OI, long_short, liquidations
│   ├─ Sentiment: fear_greed
│   ├─ Macro: FRED, market_indices
│   └─ News: CryptoPanic → (실패 시) RSS fallback
│
└─ Predict
    ├─ build MarketContext (news 포함)
    ├─ format_prompt(enabled_modules)
    │   └─ "news" in modules → _section_news()
    │       ├─ DB에서 직전 4H 구간 기사 쿼리
    │       ├─ total <= 100: 전체 전달
    │       └─ total > 100: 최신순 100건 + 나머지 집계 통계
    └─ claude -p → 예측 → paper trade
```

## Collector Architecture

### File Structure

```
collectors/news/
├── __init__.py
├── cryptopanic_collector.py   # Primary: CryptoPanic REST API
├── rss_collector.py           # Fallback: CoinTelegraph + CoinDesk RSS
└── news_collector.py          # Orchestrator: primary → fallback 전환
```

### NewsCollector (Orchestrator)

수집 진입점. BaseCollector를 상속하며 collect() 호출 시:

1. CryptoPanicCollector.collect() 시도
2. 실패 시 (타임아웃, API 에러, rate limit) → RSSCollector.collect()로 fallback
3. 두 소스 모두 동일한 NewsArticle 데이터클래스로 정규화
4. fallback 발동 여부를 로깅 및 Discord 알림에 포함

### CryptoPanicCollector

- **API**: `GET https://cryptopanic.com/api/v1/posts/?auth_token={key}&kind=news`
- **BTC 필터링 없음**: 크립토 전체 뉴스 수집 (시장 이벤트 포괄)
- **패턴**: aiohttp 세션 (FearGreedCollector와 동일)
  - 세션 소유권 추적 (`_owns_session` flag)
  - lazy session 초기화
  - close()에서 조건부 세션 종료
- **추출 필드**: title, source, published_at, url, votes(positive/negative/important)

### RSSCollector

- **소스**: CoinTelegraph RSS + CoinDesk RSS
- **패턴**: feedparser (sync) → asyncio.run_in_executor() 래핑 (MacroCollector 패턴)
- **BTC 필터링 없음**: 크립토 전체 뉴스 수집
- **투표 데이터**: 없음 → votes 필드 None으로 정규화
- **에러 처리**: 개별 피드 실패 시 나머지 피드로 계속

### 병렬 수집 통합

`cli/collect.py`의 `asyncio.gather()`에 동일 레벨로 추가:

```python
candles, funding, oi, ls, fg, liq, macro, news = await asyncio.gather(
    collect_candles(), collect_funding(), collect_oi(), ..., collect_news(),
    return_exceptions=True
)
```

뉴스는 Binance API와 독립적이므로 완전 병렬 — 수집 시간 추가 없음.

## Data Model

### NewsArticle Dataclass

```python
@dataclass
class NewsArticle:
    timestamp: datetime          # 기사 게시 시간
    title: str                   # 헤드라인
    source: str                  # "CoinDesk", "CoinTelegraph" 등
    url: str                     # 원문 URL
    votes_positive: int | None   # CryptoPanic 투표 (RSS는 None)
    votes_negative: int | None
    votes_important: int | None
    collected_at: datetime       # 수집 시점
    collector_source: str        # "cryptopanic" | "rss"
```

### Database Table

```sql
CREATE TABLE IF NOT EXISTS news_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    votes_positive INTEGER,
    votes_negative INTEGER,
    votes_important INTEGER,
    collected_at TEXT NOT NULL,
    collector_source TEXT NOT NULL,
    UNIQUE(url)
);
```

- UNIQUE(url): 같은 기사 중복 방지
- INSERT OR REPLACE: CryptoPanic 버전(투표 포함)이 RSS 버전보다 우선
- collected_at: 수집 시점 추적, 직전 4H 구간 쿼리에 사용

## Context Builder Integration

### _section_news() Method

프롬프트 전달 포맷 (raw data only, 해석 없음):

```
## News (Recent 4H)

Articles: 24 total (showing all), source: cryptopanic
Sentiment votes: +145 positive, -32 negative, 68 important

Headlines:
- [2026-03-28 08:15] "Bitcoin ETF sees record $2.1B inflow" (src: CoinDesk, +18/-2, important: 5)
- [2026-03-28 07:30] "Fed signals rate pause through Q2" (src: CoinTelegraph, +12/-3, important: 8)
- [2026-03-28 06:45] "Whale moves 5000 BTC to exchange" (src: CryptoSlate, +3/-15, important: 4)
- ...
```

100건 초과 시:

```
## News (Recent 4H)

Articles: 152 total (showing 100 most recent, 52 older summarized)
Sentiment votes (all 152): +520 positive, -189 negative, 245 important

Headlines (100 most recent):
- [2026-03-28 08:15] "..." (src: ..., +18/-2, important: 5)
- ...

Older articles (52): +180 positive, -60 negative, 90 important
```

RSS fallback 기사는 투표 없이 표시:

```
- [2026-03-28 07:00] "..." (src: CoinTelegraph, via RSS)
```

### Module Registration

```python
# experiment/models.py
SEED_MODULES = [..., "news"]
EXPERIMENTAL_MODULES = {"macro", "news"}
```

`format_prompt()`에서:

```python
if "news" in modules:
    sections.append(self._section_news())
```

## Configuration

### Settings (config/settings.py)

```python
@dataclass
class NewsConfig:
    enabled: bool = True
    cryptopanic_api_key: str = ""
    max_headlines: int = 100
    rss_feeds: list[str] = field(
        default_factory=lambda: [
            "https://cointelegraph.com/rss",
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
        ]
    )
```

### Environment Variables

```bash
NEWS_ENABLED=true                    # 뉴스 수집 활성화
CRYPTOPANIC_API_KEY=<api_key>        # CryptoPanic 무료 API 키
NEWS_MAX_HEADLINES=100               # 프롬프트 최대 전달 건수
```

## Data Integrity & Notifications

### Data Integrity (reporters/data_integrity.py)

기존 패턴 따라 뉴스 수집 검증 추가:
- 수집 건수 확인 (0건 = warning, 에러 아님 — 뉴스 없는 구간 존재 가능)
- collector_source 확인 (cryptopanic vs rss → fallback 발동 추적)

### Discord Alerts (notifications/scheduler_alerts.py)

수집 완료 리포트에 추가:

```
News: 24 articles (cryptopanic)     # 정상
News: 8 articles (rss fallback)     # fallback 발동
News: 0 articles                    # 뉴스 없음 (warning)
```

## A/B Testing Strategy

1. `news` 모듈을 `EXPERIMENTAL_MODULES`에 등록
2. `experiment create --add news` → control(기존 모듈) vs variant(기존+news) 비교
3. min_samples(기본 30) 이상 누적 후 통계적 유의성 검정
4. 유의미한 개선 확인 시 `experiment merge` → baseline 포함

**평가 지표**: accuracy (방향 적중률), net_return (누적 수익률%), sharpe (위험 조정 수익률)

## File Changes Summary

| File | Change |
|------|--------|
| `collectors/news/__init__.py` | NEW |
| `collectors/news/cryptopanic_collector.py` | NEW |
| `collectors/news/rss_collector.py` | NEW |
| `collectors/news/news_collector.py` | NEW |
| `storage/models.py` | + NewsArticle dataclass |
| `storage/database.py` | + news_articles 테이블, insert_news_articles(), get_recent_news() |
| `config/settings.py` | + NewsConfig |
| `llm/context/builder.py` | + _section_news(), MarketContext.news 필드 |
| `experiment/models.py` | SEED_MODULES += "news", EXPERIMENTAL_MODULES += "news" |
| `cli/collect.py` | + news collector를 asyncio.gather()에 추가 |
| `reporters/data_integrity.py` | + 뉴스 수집 검증 |
| `notifications/scheduler_alerts.py` | + 뉴스 수집 결과 리포트 |

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary 소스 | CryptoPanic API (무료) | 안정성(2017~), 투표 센티먼트, BTC 필터, 4H 6회/일 << 100회/일 한도 |
| Fallback | RSS (CoinTelegraph + CoinDesk) | API 의존 없는 백업, 무료, rate limit 없음 |
| BTC 필터링 | 안 함 | 시장 전체 이벤트(규제, 매크로) 포괄 위해 |
| 본문 수집 | 안 함 (헤드라인만) | 연구상 헤드라인만으로 충분, 토큰 효율, 무료 tier 제한 |
| 프롬프트 전달 | 직전 4H 전체, >100건 시 최신 100건 + 나머지 집계 | 에이전트 자율 판단 + 토큰 안전장치 |
| 데이터 원칙 | raw data only | 기존 시스템 원칙 준수 — 에이전트 자율 판단 |
| 모듈 구조 | 독립 "news" 모듈 | A/B 테스트로 순수 효과 분리 측정 |
| 수집 타이밍 | collect 단계 asyncio.gather() 병렬 | 수집 시간 추가 없음, 아키텍처 변경 없음 |
