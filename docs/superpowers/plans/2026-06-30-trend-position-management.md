# Trend Position Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the trading engine from binary sell/hold behavior to trend-first position management with `add / hold / reduce / exit`, preserving strong trends instead of forcing premature full exits.

**Architecture:** Keep the current single-file `web_app.py` structure, but introduce a thin position-management layer inside the existing comprehensive trade flow. Expand the AI decision contract, add helper functions for target-position math and action validation, then change execution flow to adjust positions by target percentage rather than using full liquidation as the default response.

**Tech Stack:** Python 3.9+, FastAPI, SQLAlchemy ORM, SQLite/MySQL, NumPy, pytest (new test dependency recommended)

---

## File Structure

### Existing files to modify
- `web_app.py`
  - Expand AI decision schema in `ai_comprehensive_decision()`
  - Add helper functions for equity, position percentage, target quantity calculation, and action validation
  - Update `AutoTradeEngine._comprehensive_trade()` to execute `add / hold / reduce / exit`
  - Reinterpret `take_profit_pct` as a profit-management threshold instead of forced full exit
- `requirements.txt`
  - Add `pytest` if no test dependency exists yet
- `README.md`
  - Update strategy description from fixed take-profit selling to trend-first position management

### New files to create
- `tests/test_position_management.py`
  - Focused unit/integration-style tests for new action handling and constraints

---

### Task 1: Add a test harness for trading logic

**Files:**
- Modify: `requirements.txt`
- Create: `tests/test_position_management.py`
- Modify: `README.md`

- [ ] **Step 1: Add pytest to dependencies**

Update `requirements.txt` to include:

```txt
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
sqlalchemy>=2.0.0
python-dotenv>=1.0.0
python-multipart>=0.0.6
akshare>=1.10.0
pandas>=2.0.0
numpy>=1.24.0
pymysql>=1.1.0  # 仅 MySQL 需要，SQLite 用户可删除此行
pytest>=8.0.0
```

- [ ] **Step 2: Create the failing test file skeleton**

Create `tests/test_position_management.py` with this initial content:

```python
import importlib
from pathlib import Path

import pytest

import web_app


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_trader.db"
    monkeypatch.setattr(web_app, "DB_URL", f"sqlite:///{db_file}", raising=False)
    engine = web_app.create_engine(f"sqlite:///{db_file}", echo=False)
    SessionLocal = web_app.sessionmaker(bind=engine)
    web_app.Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_placeholder():
    assert True
```

- [ ] **Step 3: Run the test file to verify the harness works**

Run:

```bash
pytest tests/test_position_management.py -v
```

Expected: PASS with `1 passed`

- [ ] **Step 4: Update README strategy wording**

In `README.md`, replace the risk-control feature bullet:

```md
- **🛡️ 风险控制** — 自动止盈止损、移动止损、单笔风险控制、最大持仓限制
```

with:

```md
- **🛡️ 风险控制** — 趋势优先仓位管理、硬止损、利润管理、单笔风险控制、最大持仓限制
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt README.md tests/test_position_management.py
git commit -m "test: add position management test harness"
```

---

### Task 2: Add helper functions for position sizing and target action math

**Files:**
- Modify: `web_app.py:758-783`
- Test: `tests/test_position_management.py`

- [ ] **Step 1: Write failing tests for position sizing helpers**

Append these tests to `tests/test_position_management.py`:

```python
def test_calc_position_pct_returns_percentage():
    pct = web_app.calc_position_pct(market_value=3200, total_equity=10000)
    assert pct == 32.0


def test_calc_position_pct_handles_zero_equity():
    pct = web_app.calc_position_pct(market_value=3200, total_equity=0)
    assert pct == 0.0


def test_target_delta_amount_positive_for_add():
    delta = web_app.calc_target_delta_amount(current_pct=20, target_pct=35, total_equity=10000)
    assert delta == 1500.0


def test_target_delta_amount_negative_for_reduce():
    delta = web_app.calc_target_delta_amount(current_pct=35, target_pct=20, total_equity=10000)
    assert delta == -1500.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_position_management.py -v
```

Expected: FAIL with `AttributeError` for missing helper functions.

- [ ] **Step 3: Add minimal helper implementations**

In `web_app.py`, near the existing trading helpers after `calc_current_equity()`, add:

```python
def calc_position_pct(market_value: float, total_equity: float) -> float:
    if total_equity <= 0:
        return 0.0
    return round(market_value / total_equity * 100, 2)


def calc_target_delta_amount(current_pct: float, target_pct: float, total_equity: float) -> float:
    if total_equity <= 0:
        return 0.0
    return round((target_pct - current_pct) / 100 * total_equity, 2)
```

- [ ] **Step 4: Run tests to verify the helpers pass**

Run:

```bash
pytest tests/test_position_management.py -v
```

Expected: PASS for the four new helper tests.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_position_management.py
git commit -m "feat: add target position sizing helpers"
```

---

### Task 3: Add action validation rules for add/hold/reduce/exit

**Files:**
- Modify: `web_app.py`
- Test: `tests/test_position_management.py`

- [ ] **Step 1: Write failing tests for action validation**

Append these tests to `tests/test_position_management.py`:

```python
def test_normalize_position_action_defaults_to_hold():
    action = web_app.normalize_position_action({"action": "weird"})
    assert action == "hold"


def test_normalize_position_action_accepts_known_actions():
    action = web_app.normalize_position_action({"action": "reduce"})
    assert action == "reduce"


def test_allow_add_requires_non_loss_trend_signal():
    allowed = web_app.allow_add_action(
        pnl_pct=-3.5,
        current_pct=15,
        target_pct=25,
        max_position_pct=50,
        trend_ok=False,
    )
    assert allowed is False


def test_allow_add_allows_strong_trend_with_room():
    allowed = web_app.allow_add_action(
        pnl_pct=4.0,
        current_pct=15,
        target_pct=25,
        max_position_pct=50,
        trend_ok=True,
    )
    assert allowed is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_position_management.py -v
```

Expected: FAIL with missing helper function errors.

- [ ] **Step 3: Add action validation helpers**

In `web_app.py`, add these helpers after the position sizing helpers:

```python
def normalize_position_action(item: Dict) -> str:
    action = str(item.get("action", "hold")).lower().strip()
    if action in {"add", "hold", "reduce", "exit"}:
        return action
    return "hold"


def allow_add_action(pnl_pct: float, current_pct: float, target_pct: float,
                     max_position_pct: float, trend_ok: bool) -> bool:
    if not trend_ok:
        return False
    if pnl_pct < 0:
        return False
    if target_pct <= current_pct:
        return False
    if target_pct > max_position_pct:
        return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/test_position_management.py -v
```

Expected: PASS for action validation tests.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_position_management.py
git commit -m "feat: validate trend position actions"
```

---

### Task 4: Expand AI decision schema to target position actions

**Files:**
- Modify: `web_app.py:1226-1355`
- Test: `tests/test_position_management.py`

- [ ] **Step 1: Write a failing parser test for new AI action schema**

Append this test to `tests/test_position_management.py`:

```python
def test_parse_ai_position_action_uses_target_pct():
    item = {
        "symbol": "000725",
        "action": "add",
        "target_pct": 35,
        "change_pct": 10,
        "reason": "趋势增强",
        "confidence": 82,
    }
    parsed = web_app.parse_position_action(item)
    assert parsed["action"] == "add"
    assert parsed["target_pct"] == 35
    assert parsed["change_pct"] == 10
```

- [ ] **Step 2: Run the single test to verify it fails**

Run:

```bash
pytest tests/test_position_management.py::test_parse_ai_position_action_uses_target_pct -v
```

Expected: FAIL with `AttributeError: module 'web_app' has no attribute 'parse_position_action'`.

- [ ] **Step 3: Add parser helper and update the AI JSON contract**

In `web_app.py`, add:

```python
def parse_position_action(item: Dict) -> Dict:
    action = normalize_position_action(item)
    target_pct = float(item.get("target_pct", 0) or 0)
    change_pct = float(item.get("change_pct", 0) or 0)
    return {
        "symbol": normalize_symbol(item.get("symbol", "")),
        "action": action,
        "target_pct": round(max(0.0, target_pct), 2),
        "change_pct": round(change_pct, 2),
        "reason": str(item.get("reason", ""))[:120],
        "confidence": float(item.get("confidence", 0) or 0),
    }
```

Then update the `ai_comprehensive_decision()` prompt so that:

1. `position_actions` examples use `add / hold / reduce / exit`
2. Each action includes `target_pct` and `change_pct`
3. The task instructions explicitly say:

```text
你的首要目标是吃住主升浪。
盈利本身不是清仓理由，趋势破坏才是。
对短线过热但趋势未坏的持仓优先使用 reduce，而不是 exit。
只有趋势强化、仓位不高、且不是逆势补仓时才能使用 add。
```

- [ ] **Step 4: Run the test to verify the parser passes**

Run:

```bash
pytest tests/test_position_management.py::test_parse_ai_position_action_uses_target_pct -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_position_management.py
git commit -m "feat: expand ai decision schema for target positions"
```

---

### Task 5: Replace fixed take-profit exits with profit-management behavior

**Files:**
- Modify: `web_app.py:1679-1711`
- Test: `tests/test_position_management.py`

- [ ] **Step 1: Write a failing test for profit management gating**

Append this test to `tests/test_position_management.py`:

```python
def test_should_force_exit_on_profit_returns_false_for_take_profit_only():
    force_exit = web_app.should_force_exit(
        pnl_pct=12.5,
        stop_loss_pct=5.0,
        trend_broken=False,
    )
    assert force_exit is False


def test_should_force_exit_on_stop_loss_returns_true():
    force_exit = web_app.should_force_exit(
        pnl_pct=-5.1,
        stop_loss_pct=5.0,
        trend_broken=False,
    )
    assert force_exit is True
```

- [ ] **Step 2: Run the single test group to verify it fails**

Run:

```bash
pytest tests/test_position_management.py -k force_exit -v
```

Expected: FAIL with missing helper function errors.

- [ ] **Step 3: Add the helper and update hard-risk flow**

In `web_app.py`, add:

```python
def should_force_exit(pnl_pct: float, stop_loss_pct: float, trend_broken: bool = False) -> bool:
    if pnl_pct <= -abs(stop_loss_pct):
        return True
    if trend_broken:
        return True
    return False
```

Then update `_comprehensive_trade()` so that:
- stop-loss continues to call `exec_sell()` for full available quantity
- fixed take-profit no longer directly calls `exec_sell()`
- when `pnl_pct >= self.take_profit_pct`, log that the symbol entered the profit-management zone instead of selling immediately

Use a log message shaped like:

```python
add_realtime_log("info", f"📌 利润管理区: {pos.symbol} {pnl_pct:.1f}% >= {self.take_profit_pct:.1f}%")
```

- [ ] **Step 4: Run the focused test again**

Run:

```bash
pytest tests/test_position_management.py -k force_exit -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_position_management.py
git commit -m "feat: replace hard take-profit exits with profit management"
```

---

### Task 6: Execute add/hold/reduce/exit inside comprehensive trading

**Files:**
- Modify: `web_app.py:1784-1812`
- Test: `tests/test_position_management.py`

- [ ] **Step 1: Write failing tests for reduce and add quantity handling**

Append these tests to `tests/test_position_management.py`:

```python
def test_calc_trade_qty_for_reduce_uses_target_delta():
    qty = web_app.calc_trade_qty_from_delta(delta_amount=-1500, price=5.0)
    assert qty == 300


def test_calc_trade_qty_for_add_uses_target_delta():
    qty = web_app.calc_trade_qty_from_delta(delta_amount=1500, price=5.0)
    assert qty == 300


def test_calc_trade_qty_returns_zero_for_small_delta():
    qty = web_app.calc_trade_qty_from_delta(delta_amount=200, price=5.0)
    assert qty == 0
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```bash
pytest tests/test_position_management.py -k trade_qty -v
```

Expected: FAIL with missing helper function errors.

- [ ] **Step 3: Add the quantity helper and refactor action execution**

In `web_app.py`, add:

```python
def calc_trade_qty_from_delta(delta_amount: float, price: float) -> int:
    if price <= 0:
        return 0
    raw_qty = int(abs(delta_amount) / price)
    return round_lot(raw_qty)
```

Then refactor the AI position-action loop in `_comprehensive_trade()` so that:

- `hold` only logs a hold decision
- `exit` sells all available quantity
- `reduce` computes current position percentage, target delta amount, converts to quantity, then sells that quantity if `qty > 0`
- `add` computes target delta amount, quantity, validates with `allow_add_action(...)`, then buys via `exec_buy()` if `qty > 0`
- if `qty == 0`, log a `skip` decision with reason `目标仓位变化不足一手`

Use this control flow pattern:

```python
parsed = parse_position_action(pa)
action = parsed["action"]

if action == "hold":
    ...
elif action == "exit":
    ...
elif action == "reduce":
    ...
elif action == "add":
    ...
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run:

```bash
pytest tests/test_position_management.py -k trade_qty -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_position_management.py
git commit -m "feat: execute target-based add reduce exit actions"
```

---

### Task 7: Guard against over-concentration and noisy micro-trades

**Files:**
- Modify: `web_app.py`
- Test: `tests/test_position_management.py`

- [ ] **Step 1: Write failing tests for over-concentration guards**

Append these tests to `tests/test_position_management.py`:

```python
def test_cap_target_pct_respects_max_position_limit():
    capped = web_app.cap_target_pct(target_pct=65, max_position_pct=50)
    assert capped == 50


def test_cap_target_pct_keeps_lower_value():
    capped = web_app.cap_target_pct(target_pct=35, max_position_pct=50)
    assert capped == 35
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run:

```bash
pytest tests/test_position_management.py -k cap_target_pct -v
```

Expected: FAIL with missing helper errors.

- [ ] **Step 3: Add guard helper and use it before action execution**

In `web_app.py`, add:

```python
def cap_target_pct(target_pct: float, max_position_pct: float) -> float:
    return round(max(0.0, min(target_pct, max_position_pct)), 2)
```

Then ensure parsed actions are capped before calculating delta amounts:

```python
parsed["target_pct"] = cap_target_pct(parsed["target_pct"], self.max_position_pct)
```

Also treat deltas under one lot as no-op actions that create a `skip` decision instead of a trade.

- [ ] **Step 4: Run the focused tests again**

Run:

```bash
pytest tests/test_position_management.py -k cap_target_pct -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_position_management.py
git commit -m "feat: cap target position size and suppress micro trades"
```

---

### Task 8: Add end-to-end tests for the new action semantics

**Files:**
- Modify: `tests/test_position_management.py`
- Modify: `web_app.py` (only if test seams are needed)

- [ ] **Step 1: Write failing end-to-end-style tests for semantic behavior**

Append these tests to `tests/test_position_management.py`:

```python
def test_parse_unknown_action_falls_back_to_hold():
    parsed = web_app.parse_position_action({"symbol": "000725", "action": "strange"})
    assert parsed["action"] == "hold"


def test_allow_add_rejects_target_over_limit():
    allowed = web_app.allow_add_action(
        pnl_pct=6.0,
        current_pct=30.0,
        target_pct=55.0,
        max_position_pct=50.0,
        trend_ok=True,
    )
    assert allowed is False


def test_should_force_exit_allows_hold_when_profitable_and_trend_not_broken():
    assert web_app.should_force_exit(pnl_pct=14.0, stop_loss_pct=5.0, trend_broken=False) is False
```

- [ ] **Step 2: Run the full test file**

Run:

```bash
pytest tests/test_position_management.py -v
```

Expected: PASS after previous tasks, or FAIL only on missing seams introduced by refactoring.

- [ ] **Step 3: Fill any missing seams introduced by the refactor**

If the test file exposes friction points, keep changes minimal. Only add helper seams if they directly support:
- isolated action parsing
- isolated target percentage math
- isolated force-exit checks

Do not add abstractions that are not exercised by tests.

- [ ] **Step 4: Run the full test file again**

Run:

```bash
pytest tests/test_position_management.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_position_management.py
git commit -m "test: cover trend position management behavior"
```

---

### Task 9: Update documentation to match the implemented behavior

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-06-30-trend-position-management-design.md`

- [ ] **Step 1: Update README feature and behavior descriptions**

Add a short section under features or configuration describing the new behavior:

```md
## 趋势优先仓位管理

系统会优先判断每只持仓应当 `add / hold / reduce / exit`，而不是简单地“卖出或继续持有”。

- **hold**：趋势未坏，继续持有
- **add**：趋势强化且仓位仍有空间时顺势加仓
- **reduce**：短线过热或仓位过重时部分减仓
- **exit**：趋势破坏或止损触发时清仓

固定止盈阈值不再直接触发全卖，而是作为利润管理区的参考信号。
```

- [ ] **Step 2: Update the design doc implementation status note**

Append this section to `docs/superpowers/specs/2026-06-30-trend-position-management-design.md` after implementation completes:

```md
## 实施状态

- [x] AI 持仓动作升级为 `add / hold / reduce / exit`
- [x] 固定止盈改造为利润管理区
- [x] 执行层支持按目标仓位加减仓
- [x] 第一版约束包含整手规则、最大仓位限制与禁止逆势补仓
```

- [ ] **Step 3: Run tests one last time as a doc safety check**

Run:

```bash
pytest tests/test_position_management.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/superpowers/specs/2026-06-30-trend-position-management-design.md
git commit -m "docs: describe trend-first position management"
```

---

## Self-Review

### Spec coverage
- New action model (`add / hold / reduce / exit`) is covered in Tasks 3, 4, and 6.
- Profit-management replacement for hard take-profit is covered in Task 5.
- Position-target execution and concentration controls are covered in Tasks 2, 6, and 7.
- Documentation updates are covered in Task 9.
- Tests exist for helper math, action parsing, force-exit gating, and action guards across Tasks 1-8.

### Placeholder scan
- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every code step includes concrete code blocks or exact update instructions.
- Every verification step includes an exact command and expected result.

### Type consistency
- Action vocabulary is consistently `add / hold / reduce / exit`.
- Target size field is consistently `target_pct`.
- Delta helper naming is consistently `calc_target_delta_amount` and `calc_trade_qty_from_delta`.

---
