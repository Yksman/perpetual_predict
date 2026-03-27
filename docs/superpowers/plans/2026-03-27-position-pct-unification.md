# Position Pct Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `leverage` + `position_ratio` into a single `position_pct` field (0.0~max_leverage) so the agent decides one number: what fraction of capital to deploy (where >1.0 implies leverage).

**Architecture:** Replace two-field trading parameter system with unified `position_pct`. The field represents capital deployment as a multiplier (e.g., 1.5 = 150% of balance = 1.5x leverage). The trading engine derives `notional_value = balance × position_pct` directly. DB migration converts existing records via `position_ratio × leverage → position_pct`.

**Tech Stack:** Python (aiosqlite, dataclasses), TypeScript/React (dashboard), SQLite migrations

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `perpetual_predict/llm/agent/runner.py` | LLM JSON schema + AgentResult + validation |
| Modify | `perpetual_predict/storage/models.py` | Prediction dataclass: replace leverage+position_ratio with position_pct |
| Modify | `perpetual_predict/trading/models.py` | PaperTrade dataclass: replace leverage+position_ratio with position_pct |
| Modify | `perpetual_predict/trading/engine.py` | Position opening: derive notional from position_pct |
| Modify | `perpetual_predict/storage/database.py` | DB schema migration + SQL statements |
| Modify | `perpetual_predict/scheduler/jobs.py` | Prediction creation + trade logging |
| Modify | `perpetual_predict/notifications/scheduler_alerts.py` | Discord embed formatting |
| Modify | `perpetual_predict/export/exporter.py` | JSON export fields |
| Modify | `dashboard/src/types/index.ts` | TypeScript interfaces |
| Modify | `dashboard/src/components/tables/PredictionTable.tsx` | Display position_pct |
| Modify | `dashboard/src/components/tables/TradeTable.tsx` | Display position_pct |
| Modify | `.claude/agents/predictor.md` | Agent instructions |
| Modify | `CLAUDE.md` | Project documentation |
| Modify | `tests/test_llm/test_runner_validation.py` | Update test fixtures |

---

### Task 1: LLM Schema + AgentResult (`runner.py`)

**Files:**
- Modify: `perpetual_predict/llm/agent/runner.py:69-100` (schema), `:270-296` (validation), `:320-329` (fallback)
- Test: `tests/test_llm/test_runner_validation.py`

- [ ] **Step 1: Update test fixtures to use position_pct**

In `tests/test_llm/test_runner_validation.py`, replace all `"leverage": X, "position_ratio": Y` with `"position_pct": X*Y` (the product). Specifically:

```python
# In every test prediction dict, replace:
#   "leverage": 1.5, "position_ratio": 0.1
# with:
#   "position_pct": 0.15
#
# And for "leverage": 2.0, "position_ratio": 0.3 → "position_pct": 0.6
# And for "leverage": 1.0, "position_ratio": 0.05 → "position_pct": 0.05
# And for "leverage": 1.0, "position_ratio": 0.1 → "position_pct": 0.1
```

Also update `TestAgentResultFields` to check `position_pct` instead of separate fields.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm/test_runner_validation.py -v`
Expected: FAIL (schema still has old fields)

- [ ] **Step 3: Update `_build_prediction_schema()`**

Replace the `leverage` and `position_ratio` fields in the JSON schema with a single `position_pct`:

```python
# runner.py:69-86 — replace leverage + position_ratio + required list
"position_pct": {
    "type": "number",
    "minimum": 0.0,
    "maximum": max_leverage,
    "description": f"투자금 대비 진입 비율 (0.0~{max_leverage}). "
                   f"1.0=투자금 100%, 1.5=투자금 150%(레버리지 1.5x), "
                   f"2.0=투자금 200%(레버리지 2x). "
                   f"NEUTRAL이면 0.0. 시장 확신도에 따라 자유롭게 결정"
},
```

Update the `"required"` list: replace `"leverage", "position_ratio"` with `"position_pct"`.

- [ ] **Step 4: Update `AgentResult` dataclass**

```python
# runner.py:90-100 — replace leverage + position_ratio
@dataclass
class AgentResult:
    direction: str
    confidence: float
    reasoning: str
    key_factors: list[str] = field(default_factory=list)
    position_pct: float = 0.0
    trading_reasoning: str = ""
    # ... rest unchanged
```

- [ ] **Step 5: Update validation/clamping logic**

```python
# runner.py:270-280 — replace leverage + position_ratio parsing
# Parse trading parameters (agent-driven, clamped to configured max)
position_pct = float(prediction.get("position_pct", 0.0))
position_pct = max(0.0, min(max_leverage, position_pct))

# Force no position for NEUTRAL
if direction == "NEUTRAL":
    position_pct = 0.0
```

Update the `AgentResult(...)` construction at line ~282:
```python
return AgentResult(
    ...
    position_pct=position_pct,
    trading_reasoning=prediction.get("trading_reasoning", ""),
    ...
)
```

- [ ] **Step 6: Update fallback `_extract_prediction_from_text()`**

```python
# runner.py:320-329 — replace leverage + position_ratio defaults
result = {
    "direction": "NEUTRAL",
    "confidence": 0.5,
    "reasoning": text[:500] if text else "Unable to parse prediction",
    "key_factors": [],
    "position_pct": 0.0,
    "trading_reasoning": "",
}
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_llm/test_runner_validation.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add perpetual_predict/llm/agent/runner.py tests/test_llm/test_runner_validation.py
git commit -m "refactor: unify leverage+position_ratio into position_pct in LLM schema"
```

---

### Task 2: Data Models (`storage/models.py`, `trading/models.py`)

**Files:**
- Modify: `perpetual_predict/storage/models.py:247-283,328-330`
- Modify: `perpetual_predict/trading/models.py:51-54,87-90,117-120`

- [ ] **Step 1: Update Prediction dataclass**

In `storage/models.py`, replace the trading parameters block:

```python
# storage/models.py:247-250 — replace:
#     leverage: float = 1.0
#     position_ratio: float = 0.0
#     trading_reasoning: str = ""
# with:
    position_pct: float = 0.0
    trading_reasoning: str = ""
```

Update `to_dict()` at line ~281:
```python
# Replace leverage + position_ratio entries:
"position_pct": self.position_pct,
"trading_reasoning": self.trading_reasoning,
```

Update `from_dict()` at line ~328:
```python
# Replace:
#     leverage=data.get("leverage", 1.0),
#     position_ratio=data.get("position_ratio", 0.0),
# with:
position_pct=data.get("position_pct", 0.0),
```

- [ ] **Step 2: Update PaperTrade dataclass**

In `trading/models.py`, replace position detail fields:

```python
# trading/models.py:51-54 — replace:
#     leverage: float
#     position_size: float
#     position_ratio: float
#     notional_value: float
# with:
    position_pct: float
    notional_value: float
```

Update `to_dict()`:
```python
# Replace leverage, position_size, position_ratio, notional_value with:
"position_pct": self.position_pct,
"notional_value": self.notional_value,
```

Update `from_dict()`:
```python
# Replace leverage, position_size, position_ratio, notional_value with:
position_pct=data.get("position_pct", 0.0),
notional_value=data["notional_value"],
```

- [ ] **Step 3: Run linter**

Run: `ruff check perpetual_predict/storage/models.py perpetual_predict/trading/models.py`
Expected: PASS (no errors)

- [ ] **Step 4: Commit**

```bash
git add perpetual_predict/storage/models.py perpetual_predict/trading/models.py
git commit -m "refactor: replace leverage+position_ratio with position_pct in data models"
```

---

### Task 3: Trading Engine (`engine.py`)

**Files:**
- Modify: `perpetual_predict/trading/engine.py:48-101,224-226`

- [ ] **Step 1: Update `open_position()`**

```python
# engine.py:48 docstring — update reference
"""Open a paper trade based on prediction.

Returns None if direction is NEUTRAL, position_pct is 0, or balance is 0.
"""

# engine.py:53-54 — replace position_ratio check:
if prediction.position_pct <= 0:
    logger.info("Agent chose position_pct=0, skipping trade")
    return None

# engine.py:64-70 — replace leverage/position_ratio calculation:
# Use agent-decided position_pct, clamped to configured max
position_pct = max(0.0, min(settings.max_leverage, prediction.position_pct))

side = "LONG" if prediction.direction == "UP" else "SHORT"
notional_value = account.current_balance * position_pct

# Entry fee on notional
entry_fee = notional_value * (settings.entry_fee_pct / 100)
```

Update PaperTrade construction:
```python
# engine.py:75-92 — replace trade construction:
trade = PaperTrade(
    trade_id=str(uuid.uuid4()),
    account_id=self.account_id,
    prediction_id=prediction.prediction_id,
    symbol=prediction.symbol,
    side=side,
    position_pct=position_pct,
    notional_value=notional_value,
    entry_price=entry_price,
    entry_time=datetime.now(timezone.utc),
    balance_before=account.current_balance,
    confidence=prediction.confidence,
    status="OPEN",
    trading_reasoning=prediction.trading_reasoning,
    entry_fee=entry_fee,
)
```

Update log message:
```python
# engine.py:96-101
logger.info(
    f"Paper trade opened: {side} "
    f"position_pct={position_pct:.2f}x "
    f"notional=${notional_value:.2f} "
    f"@ ${entry_price:,.2f}"
)
```

- [ ] **Step 2: Update `close_position()` return_pct calculation**

```python
# engine.py:137 — replace position_size with notional/position_pct:
# return_pct is based on the actual capital at risk (balance_before)
return_pct = (net_pnl / trade.balance_before * 100) if trade.balance_before > 0 else 0.0
```

Note: Previously `return_pct = net_pnl / position_size * 100`. Now there's no `position_size` field. We use `balance_before` as the reference since `notional_value = balance_before × position_pct`. So `net_pnl / balance_before` gives the actual account return percentage (not the leveraged return).

- [ ] **Step 3: Update portfolio context formatting**

```python
# engine.py:224-226 — replace trade summary line:
trade_lines.append(
    f"  {t.side} {ret_str} (position {t.position_pct:.2f}x) → PnL {pnl_str}"
)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -v --timeout=30 -x`
Expected: PASS (or expected failures from DB migration not yet done)

- [ ] **Step 5: Commit**

```bash
git add perpetual_predict/trading/engine.py
git commit -m "refactor: simplify trading engine to use position_pct directly"
```

---

### Task 4: Database Migration (`database.py`)

**Files:**
- Modify: `perpetual_predict/storage/database.py:170-196,331-340,395-412,954-983,1207-1234`

- [ ] **Step 1: Update `CREATE_PAPER_TRADES_TABLE` schema**

```python
# database.py:170-196 — replace leverage, position_size, position_ratio with position_pct:
CREATE_PAPER_TRADES_TABLE = """
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT NOT NULL UNIQUE,
    account_id TEXT NOT NULL DEFAULT 'default',
    prediction_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    position_pct REAL NOT NULL DEFAULT 0.0,
    notional_value REAL NOT NULL,
    entry_price REAL NOT NULL,
    entry_time TEXT NOT NULL,
    exit_price REAL,
    exit_time TEXT,
    entry_fee REAL,
    exit_fee REAL,
    total_fees REAL,
    gross_pnl REAL,
    net_pnl REAL,
    return_pct REAL,
    balance_before REAL NOT NULL,
    balance_after REAL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    confidence REAL NOT NULL,
    trading_reasoning TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""
```

- [ ] **Step 2: Add migration for predictions table**

In the migration section (~line 331), replace the existing leverage/position_ratio migration:

```python
# database.py:331-340 — replace existing migration block:
# Migration: Add position_pct field (replaces leverage + position_ratio)
if "position_pct" not in columns:
    if "leverage" in columns and "position_ratio" in columns:
        # Convert existing data: position_pct = leverage * position_ratio
        await self._connection.execute(
            "ALTER TABLE predictions ADD COLUMN position_pct REAL DEFAULT 0.0"
        )
        await self._connection.execute(
            "UPDATE predictions SET position_pct = leverage * position_ratio"
        )
    else:
        await self._connection.execute(
            "ALTER TABLE predictions ADD COLUMN position_pct REAL DEFAULT 0.0"
        )

# Keep trading_reasoning migration as-is
if "trading_reasoning" not in columns:
    await self._connection.execute(
        "ALTER TABLE predictions ADD COLUMN trading_reasoning TEXT DEFAULT ''"
    )
```

- [ ] **Step 3: Add migration for paper_trades table**

Add a similar migration for `paper_trades` in the `_ensure_paper_trades_table` method (or wherever paper_trades migrations live). After the table is created, check and migrate:

```python
# Add position_pct column and migrate from leverage * position_ratio
paper_columns = set()
async with self._connection.execute("PRAGMA table_info(paper_trades)") as cursor:
    async for row in cursor:
        paper_columns.add(row[1])

if "position_pct" not in paper_columns:
    await self._connection.execute(
        "ALTER TABLE paper_trades ADD COLUMN position_pct REAL DEFAULT 0.0"
    )
    if "leverage" in paper_columns and "position_ratio" in paper_columns:
        await self._connection.execute(
            "UPDATE paper_trades SET position_pct = leverage * position_ratio"
        )
```

- [ ] **Step 4: Update predictions table recreation SQL**

```python
# database.py:395-412 — update the predictions_new CREATE TABLE:
# Replace:
#   "  leverage REAL DEFAULT 1.0,"
#   "  position_ratio REAL DEFAULT 0.0,"
# With:
#   "  position_pct REAL DEFAULT 0.0,"
```

- [ ] **Step 5: Update INSERT statements**

For predictions insert (~line 954-983):
```python
# Replace leverage, position_ratio in column list and values:
sql = """
INSERT OR REPLACE INTO predictions
(prediction_id, prediction_time, target_candle_open, target_candle_close,
 symbol, timeframe, direction, confidence, reasoning, key_factors,
 session_id, duration_ms, model_usage,
 position_pct, trading_reasoning,
 bull_case, bear_case,
 actual_direction, actual_price_change, is_correct, predicted_return, evaluated_at,
 experiment_id, arm)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
# In the values tuple, replace:
#   prediction.leverage,
#   prediction.position_ratio,
# with:
#   prediction.position_pct,
```

For paper_trades insert (~line 1207-1234):
```python
# Replace leverage, position_size, position_ratio in column list:
sql = """
INSERT INTO paper_trades
(trade_id, account_id, prediction_id, symbol,
 side, position_pct, notional_value,
 entry_price, entry_time,
 exit_price, exit_time,
 entry_fee, exit_fee, total_fees,
 gross_pnl, net_pnl, return_pct,
 balance_before, balance_after,
 status, confidence, trading_reasoning,
 experiment_id, arm)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
# In the values tuple, replace:
#   d["leverage"], d["position_size"], d["position_ratio"],
# with:
#   d["position_pct"],
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/ -v --timeout=30`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add perpetual_predict/storage/database.py
git commit -m "refactor: migrate DB schema from leverage+position_ratio to position_pct"
```

---

### Task 5: Scheduler Jobs (`jobs.py`)

**Files:**
- Modify: `perpetual_predict/scheduler/jobs.py:411-461,564-636`

- [ ] **Step 1: Update prediction construction**

```python
# jobs.py:411-413 — replace:
#   leverage=agent_result.leverage,
#   position_ratio=agent_result.position_ratio,
# with:
position_pct=agent_result.position_pct,
```

- [ ] **Step 2: Update trade open check**

```python
# jobs.py:427 — replace:
#   and prediction.position_ratio > 0
# with:
and prediction.position_pct > 0
```

- [ ] **Step 3: Update log messages**

```python
# jobs.py:445-447 — replace:
#   f"leverage={trade.leverage:.1f}x "
#   f"ratio={trade.position_ratio:.0%} "
# with:
f"position_pct={trade.position_pct:.2f}x "
```

```python
# jobs.py:457-462 — replace:
f"(confidence: {prediction.confidence:.0%}, "
f"position_pct: {prediction.position_pct:.2f}x) "
```

- [ ] **Step 4: Update control prediction copy**

```python
# jobs.py:564-566 — replace:
#   leverage=prediction.leverage,
#   position_ratio=prediction.position_ratio,
# with:
position_pct=prediction.position_pct,
```

- [ ] **Step 5: Update control trade open check**

```python
# jobs.py:578 — replace:
#   and control_pred.position_ratio > 0
# with:
and control_pred.position_pct > 0
```

- [ ] **Step 6: Update health status details**

```python
# jobs.py:635-636 — replace:
#   "leverage": prediction.leverage if prediction else 0,
#   "position_ratio": prediction.position_ratio if prediction else 0,
# with:
"position_pct": prediction.position_pct if prediction else 0,
```

- [ ] **Step 7: Commit**

```bash
git add perpetual_predict/scheduler/jobs.py
git commit -m "refactor: update scheduler jobs to use position_pct"
```

---

### Task 6: Discord Notifications (`scheduler_alerts.py`)

**Files:**
- Modify: `perpetual_predict/notifications/scheduler_alerts.py:274-278,744-748`

- [ ] **Step 1: Update baseline prediction embed**

```python
# scheduler_alerts.py:274-279 — replace:
.add_field(
    name="💰 트레이딩 파라미터",
    value=(
        f"• 투입 비중: `{prediction.position_pct:.2f}x` "
        f"({prediction.position_pct * 100:.0f}%)"
    ),
    inline=True,
)
```

- [ ] **Step 2: Update variant prediction embed**

```python
# scheduler_alerts.py:744-748 — replace:
.add_field(
    name="💰 트레이딩 파라미터",
    value=(
        f"• 투입 비중: `{prediction.position_pct:.2f}x` "
        f"({prediction.position_pct * 100:.0f}%)"
    ),
    inline=True,
)
```

- [ ] **Step 3: Commit**

```bash
git add perpetual_predict/notifications/scheduler_alerts.py
git commit -m "refactor: update Discord embeds for position_pct"
```

---

### Task 7: Export (`exporter.py`)

**Files:**
- Modify: `perpetual_predict/export/exporter.py:134-155,360-370`

- [ ] **Step 1: Update prediction export**

```python
# exporter.py:134-135 — replace:
#   "leverage": p.leverage,
#   "position_ratio": p.position_ratio,
# with:
"position_pct": p.position_pct,
```

- [ ] **Step 2: Update trade export**

```python
# exporter.py:153-155 — replace:
#   "leverage": t.leverage,
#   "position_size": t.position_size,
#   "position_ratio": t.position_ratio,
# with:
"position_pct": t.position_pct,
```

- [ ] **Step 3: Update experiment arm export**

```python
# exporter.py:360-370 — replace _pred_arm():
def _pred_arm(p) -> dict:
    return {
        "direction": p.direction,
        "confidence": p.confidence,
        "position_pct": p.position_pct,
        "is_correct": p.is_correct,
        "actual_direction": p.actual_direction,
        "actual_price_change": p.actual_price_change,
    }
```

- [ ] **Step 4: Commit**

```bash
git add perpetual_predict/export/exporter.py
git commit -m "refactor: update export to use position_pct"
```

---

### Task 8: Dashboard TypeScript + Components

**Files:**
- Modify: `dashboard/src/types/index.ts:12-13,29-31,102-103`
- Modify: `dashboard/src/components/tables/PredictionTable.tsx:78-84,170-175`
- Modify: `dashboard/src/components/tables/TradeTable.tsx:79-80,167`

- [ ] **Step 1: Update TypeScript types**

```typescript
// types/index.ts — Prediction interface:
// Replace leverage + position_ratio with:
position_pct: number;

// Trade interface:
// Replace leverage + position_size + position_ratio with:
position_pct: number;

// ExperimentPredictionArm interface:
// Replace leverage + position_ratio with:
position_pct: number;
```

- [ ] **Step 2: Update PredictionTable**

```tsx
// PredictionTable.tsx:78-84 (mobile card) — replace Lev + Size lines:
<span>
  <span style={{ color: 'var(--text-muted)' }}>Pos </span>
  <span style={{ color: 'var(--text-secondary)' }}>{p.position_pct.toFixed(2)}x</span>
</span>

// PredictionTable.tsx:170-175 (desktop table) — replace leverage and position_ratio cells:
// Remove the separate leverage column, update position_ratio column to:
<td style={cellStyle('right')}>
  <span className="mono" style={{ fontSize: 'var(--table-font)' }}>
    {p.position_pct.toFixed(2)}x
  </span>
</td>
```

Note: Remove the "Lev" column header and cell, rename "Size" to "Pos" (or "Position").

- [ ] **Step 3: Update TradeTable**

```tsx
// TradeTable.tsx:79-80 (mobile card) — replace Lev line:
<span>
  <span style={{ color: 'var(--text-muted)' }}>Pos </span>
  <span style={{ color: 'var(--text-secondary)' }}>{t.position_pct.toFixed(2)}x</span>
</span>

// TradeTable.tsx:167 (desktop table) — replace leverage cell:
<td style={cellStyle('right')}>{t.position_pct.toFixed(2)}x</td>
```

- [ ] **Step 4: Verify build**

Run: `cd /Users/kevin.brave/perpetual_predict/dashboard && npm run build`
Expected: Build succeeds with no type errors

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/types/index.ts dashboard/src/components/tables/PredictionTable.tsx dashboard/src/components/tables/TradeTable.tsx
git commit -m "refactor: update dashboard to display position_pct"
```

---

### Task 9: Agent Prompt + Documentation

**Files:**
- Modify: `.claude/agents/predictor.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update predictor.md**

Replace the Output section:

```markdown
## Output

- `bull_case`: Your upside scenario — probability and reasoning
- `bear_case`: Your downside scenario — probability and reasoning
- `direction`: Follows whichever case has higher probability (or NEUTRAL if too close)
- `confidence`: Must equal the probability of your chosen direction
- `position_pct`: How much of the account to deploy, as a multiplier of account balance (0.0–MAX_LEVERAGE). 0.5 = 50% of balance (conservative, no leverage). 1.0 = 100% of balance. 1.5 = 150% of balance (1.5x leverage). NEUTRAL means 0.0 — there's no edge in entering when you see no clear direction (fees alone make it negative EV).
- `reasoning`: Walk through your thinking — how bull and bear cases led to your final call
- `key_factors`: The decisive factors that tipped the balance
- `trading_reasoning`: Why this specific position size for this specific setup
```

Also update the "How You Trade" section:
```markdown
- Your position size is entirely your judgment. There are no preset formulas or scaling rules — you decide what the data warrants. A higher `position_pct` means more conviction and more capital at risk.
```

- [ ] **Step 2: Update CLAUDE.md**

In the "Prediction Cycle" section, update the bullet about predict phase:
```markdown
3. **Predict**: baseline 예측 실행 → 활성 실험이 있으면 variant arm 별도 실행 (10초 쿨다운). 에이전트는 `position_pct`(0.0~max_leverage)로 투자금 대비 진입 비율을 결정. 예측 결과로 paper trade 자동 오픈
```

In the "Key Patterns" section, add or update:
```markdown
- **Unified position sizing**: Agent outputs single `position_pct` (0.0~max_leverage). Values >1.0 imply leverage (e.g., 1.5 = 150% of balance = 1.5x leverage). Trading engine derives `notional_value = balance × position_pct` directly.
```

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/predictor.md CLAUDE.md
git commit -m "docs: update agent prompt and CLAUDE.md for position_pct"
```

---

### Task 10: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --timeout=60`
Expected: All tests pass

- [ ] **Step 2: Run linter**

Run: `ruff check .`
Expected: No errors

- [ ] **Step 3: Verify dashboard builds**

Run: `cd /Users/kevin.brave/perpetual_predict/dashboard && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "refactor: complete position_pct unification"
```
