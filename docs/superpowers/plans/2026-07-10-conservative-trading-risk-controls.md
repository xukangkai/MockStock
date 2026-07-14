# Conservative Trading Risk Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add conservative execution-layer risk controls that reduce large losses, reject weak/chasing buy picks, and align default sizing with a ¥10,000 account.

**Architecture:** Keep the existing Agent decision architecture in `web_app.py`. Add small pure helper functions for confidence parsing and buy-skip decisions, then call those helpers from the existing buy execution loop and hard-stop section. No schema changes or new dependencies.

**Tech Stack:** Python 3.9, FastAPI, SQLAlchemy, pytest, existing `web_app.py` monolith.

## Global Constraints

- Do not replace the Agent architecture.
- Do not add external dependencies.
- Do not change the database schema.
- Preserve A-share lot-size behavior through existing `LOT_SIZE` / `round_lot` helpers.
- All implementation must be covered by focused pytest tests before changing production logic.
- This project is a simulation/training tool only and must not present output as investment advice.

---

## File Structure

- Modify: `web_app.py`
  - Add pure helpers near existing position-management helpers around `calc_target_delta_amount`, `parse_position_action`, and `should_force_exit`.
  - Update `AutonomousTradingEngine.__init__()` default strategy parameters.
  - Update hard-stop/profit-protection block in `_comprehensive_trade()`.
  - Update new-buy execution loop in `_comprehensive_trade()`.
- Modify: `tests/test_position_management.py`
  - Add unit tests for confidence parsing, buy skip guardrails, and conservative engine defaults.

---

### Task 1: Add Pure Guardrail Helpers

**Files:**
- Modify: `web_app.py`
- Test: `tests/test_position_management.py`

**Interfaces:**
- Produces: `parse_confidence(value) -> Optional[float]`
- Produces: `format_confidence(confidence: Optional[float]) -> str`
- Produces: `should_skip_buy_pick(confidence: Optional[float], quote_pct: float, is_etf: bool, now_time: dtime, min_confidence: float, max_chase_pct: float, late_buy_cutoff: dtime) -> Optional[str]`
- Consumes: existing `dtime` import, existing ETF detection supplied by caller.

- [ ] **Step 1: Write failing tests for confidence parsing**

Add this block to `tests/test_position_management.py` after `test_parse_ai_position_action_uses_target_pct`:

```python
@pytest.mark.parametrize(
    "raw,expected",
    [
        (75, 75.0),
        ("72.5", 72.5),
        (0, 0.0),
    ],
)
def test_parse_confidence_accepts_numeric_values(raw, expected):
    assert web_app.parse_confidence(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "abc", float("nan"), float("inf")])
def test_parse_confidence_rejects_missing_or_invalid_values(raw):
    assert web_app.parse_confidence(raw) is None


def test_format_confidence_shows_unknown_when_missing():
    assert web_app.format_confidence(None) == "unknown"


def test_format_confidence_formats_number():
    assert web_app.format_confidence(72.5) == "72.5%"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_position_management.py::test_parse_confidence_accepts_numeric_values tests/test_position_management.py::test_parse_confidence_rejects_missing_or_invalid_values tests/test_position_management.py::test_format_confidence_shows_unknown_when_missing tests/test_position_management.py::test_format_confidence_formats_number -v
```

Expected: FAIL because `parse_confidence` and `format_confidence` do not exist.

- [ ] **Step 3: Implement confidence helpers**

In `web_app.py`, add `import math` with the other standard-library imports if it is not already present.

Then add this code after `calc_trade_qty_from_delta`:

```python
def parse_confidence(value) -> Optional[float]:
    if value is None:
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(confidence):
        return None
    return round(confidence, 2)


def format_confidence(confidence: Optional[float]) -> str:
    if confidence is None:
        return "unknown"
    if float(confidence).is_integer():
        return f"{int(confidence)}%"
    return f"{confidence}%"
```

- [ ] **Step 4: Run confidence helper tests**

Run:

```bash
pytest tests/test_position_management.py::test_parse_confidence_accepts_numeric_values tests/test_position_management.py::test_parse_confidence_rejects_missing_or_invalid_values tests/test_position_management.py::test_format_confidence_shows_unknown_when_missing tests/test_position_management.py::test_format_confidence_formats_number -v
```

Expected: PASS.

- [ ] **Step 5: Write failing tests for buy skip helper**

Add this block to `tests/test_position_management.py` after the confidence tests:

```python
def test_should_skip_buy_pick_rejects_missing_confidence():
    reason = web_app.should_skip_buy_pick(
        confidence=None,
        quote_pct=1.2,
        is_etf=False,
        now_time=web_app.dtime(10, 0),
        min_confidence=70.0,
        max_chase_pct=7.0,
        late_buy_cutoff=web_app.dtime(14, 30),
    )
    assert reason == "买入信心缺失"


def test_should_skip_buy_pick_rejects_confidence_at_threshold():
    reason = web_app.should_skip_buy_pick(
        confidence=70.0,
        quote_pct=1.2,
        is_etf=False,
        now_time=web_app.dtime(10, 0),
        min_confidence=70.0,
        max_chase_pct=7.0,
        late_buy_cutoff=web_app.dtime(14, 30),
    )
    assert reason == "买入信心不足: 70% <= 70%"


def test_should_skip_buy_pick_rejects_chasing_non_etf():
    reason = web_app.should_skip_buy_pick(
        confidence=75.0,
        quote_pct=7.8,
        is_etf=False,
        now_time=web_app.dtime(10, 0),
        min_confidence=70.0,
        max_chase_pct=7.0,
        late_buy_cutoff=web_app.dtime(14, 30),
    )
    assert reason == "涨幅过高不追: 7.8% > 7.0%"


def test_should_skip_buy_pick_allows_high_pct_etf():
    reason = web_app.should_skip_buy_pick(
        confidence=75.0,
        quote_pct=7.8,
        is_etf=True,
        now_time=web_app.dtime(10, 0),
        min_confidence=70.0,
        max_chase_pct=7.0,
        late_buy_cutoff=web_app.dtime(14, 30),
    )
    assert reason is None


def test_should_skip_buy_pick_rejects_late_new_buy():
    reason = web_app.should_skip_buy_pick(
        confidence=75.0,
        quote_pct=1.0,
        is_etf=False,
        now_time=web_app.dtime(14, 30),
        min_confidence=70.0,
        max_chase_pct=7.0,
        late_buy_cutoff=web_app.dtime(14, 30),
    )
    assert reason == "尾盘不新开仓: 14:30 >= 14:30"
```

- [ ] **Step 6: Run buy skip helper tests to verify they fail**

Run:

```bash
pytest tests/test_position_management.py::test_should_skip_buy_pick_rejects_missing_confidence tests/test_position_management.py::test_should_skip_buy_pick_rejects_confidence_at_threshold tests/test_position_management.py::test_should_skip_buy_pick_rejects_chasing_non_etf tests/test_position_management.py::test_should_skip_buy_pick_allows_high_pct_etf tests/test_position_management.py::test_should_skip_buy_pick_rejects_late_new_buy -v
```

Expected: FAIL because `should_skip_buy_pick` does not exist.

- [ ] **Step 7: Implement buy skip helper**

Add this code after `format_confidence` in `web_app.py`:

```python
def should_skip_buy_pick(confidence: Optional[float], quote_pct: float, is_etf: bool,
                         now_time: dtime, min_confidence: float, max_chase_pct: float,
                         late_buy_cutoff: dtime) -> Optional[str]:
    if confidence is None:
        return "买入信心缺失"
    if confidence <= min_confidence:
        return f"买入信心不足: {format_confidence(confidence)} <= {format_confidence(min_confidence)}"
    if now_time >= late_buy_cutoff:
        return f"尾盘不新开仓: {now_time.strftime('%H:%M')} >= {late_buy_cutoff.strftime('%H:%M')}"
    if not is_etf and quote_pct > max_chase_pct:
        return f"涨幅过高不追: {quote_pct:.1f}% > {max_chase_pct:.1f}%"
    return None
```

- [ ] **Step 8: Run task tests**

Run:

```bash
pytest tests/test_position_management.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit task**

Run:

```bash
git add web_app.py tests/test_position_management.py
git commit -m "feat: add conservative buy guardrail helpers"
```

---

### Task 2: Update Conservative Engine Defaults

**Files:**
- Modify: `web_app.py`
- Test: `tests/test_position_management.py`

**Interfaces:**
- Consumes: `AutonomousTradingEngine` constructor.
- Produces: new engine attributes `min_buy_confidence`, `max_chase_pct`, `late_buy_cutoff`, `profit_protect_pct`.

- [ ] **Step 1: Write failing default-parameter test**

Add this test near the existing strategy helper tests in `tests/test_position_management.py`:

```python
def test_autonomous_engine_uses_conservative_risk_defaults():
    engine = web_app.AutonomousTradingEngine()

    assert engine.max_position_pct == 30.0
    assert engine.max_buy_per_day == 5000.0
    assert engine.single_buy_min == 2000.0
    assert engine.single_buy_max == 3000.0
    assert engine.min_buy_confidence == 70.0
    assert engine.max_chase_pct == 7.0
    assert engine.late_buy_cutoff == web_app.dtime(14, 30)
    assert engine.profit_protect_pct == 6.0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_position_management.py::test_autonomous_engine_uses_conservative_risk_defaults -v
```

Expected: FAIL because defaults still use the old aggressive values or new attributes do not exist.

- [ ] **Step 3: Update engine defaults**

In `web_app.py`, replace the strategy parameter block in `AutonomousTradingEngine.__init__()` with:

```python
        # 策略参数 - 保守增强型（控制大亏、减少追高，适配1万元账户）
        self.initial_cash = 10000.0              # 初始资金1万元
        self.target_annual_return = 0.18         # 目标年化18%（优先稳定性）
        self.max_positions = 3                   # 最大持仓3只
        self.take_profit_pct = 12.0              # 利润管理区12%
        self.stop_loss_pct = 5.0                 # 硬止损线5%
        self.trailing_stop_pct = 8.0             # 移动止损8%（保护盈利）
        self.max_position_pct = 30.0             # 单标的最大仓位30%
        self.risk_per_trade_pct = 1.5            # 单笔风险1.5%
        self.min_score_to_buy = 68.0             # 保留旧评分字段兼容
        self.min_buy_confidence = 70.0           # 买入信心必须大于70%
        self.max_chase_pct = 7.0                 # 非ETF当日涨幅超过7%不追
        self.late_buy_cutoff = dtime(14, 30)     # 14:30后不新开仓
        self.profit_protect_pct = 6.0            # 盈利6%后保护成本线
        self.max_buy_per_day = 5000.0            # 每日最大买入5000元
        self.top_picks_count = 25                # 选股池25只
        self.scan_interval = 180                 # 扫描间隔3分钟
        self.min_cash_reserve = 1000.0           # 最低保留现金1000元
        self.single_buy_min = 2000.0             # 单笔买入最低2000元
        self.single_buy_max = 3000.0             # 单笔买入最高3000元
```

- [ ] **Step 4: Run default test**

Run:

```bash
pytest tests/test_position_management.py::test_autonomous_engine_uses_conservative_risk_defaults -v
```

Expected: PASS.

- [ ] **Step 5: Commit task**

Run:

```bash
git add web_app.py tests/test_position_management.py
git commit -m "feat: tune conservative trading defaults"
```

---

### Task 3: Enforce Hard Stop and Profit Protection

**Files:**
- Modify: `web_app.py`
- Test: `tests/test_position_management.py`

**Interfaces:**
- Consumes: existing `should_force_exit(pnl_pct, stop_loss_pct, trend_broken=False)`.
- Consumes: existing `exec_sell`, `calc_available_to_sell`, `log_decision`, `add_realtime_log`.
- Produces: sellable positions at or below `-stop_loss_pct` are sold before Agent actions.

- [ ] **Step 1: Add/confirm pure hard-stop test**

`tests/test_position_management.py` already contains:

```python
def test_should_force_exit_on_stop_loss_returns_true():
    force_exit = web_app.should_force_exit(
        pnl_pct=-5.1,
        stop_loss_pct=5.0,
        trend_broken=False,
    )
    assert force_exit is True
```

Add this boundary test after it:

```python
def test_should_force_exit_triggers_at_stop_loss_boundary():
    assert web_app.should_force_exit(pnl_pct=-5.0, stop_loss_pct=5.0, trend_broken=False) is True
```

- [ ] **Step 2: Run hard-stop helper tests**

Run:

```bash
pytest tests/test_position_management.py::test_should_force_exit_on_stop_loss_returns_true tests/test_position_management.py::test_should_force_exit_triggers_at_stop_loss_boundary -v
```

Expected: PASS. If the boundary test fails, adjust `should_force_exit` to use `<= -abs(stop_loss_pct)`.

- [ ] **Step 3: Replace extreme-only stop block with hard stop and profit protection**

In `web_app.py`, inside `_comprehensive_trade()`, replace lines currently beginning with:

```python
            # 极端止损兜底（-20%），防止AI决策失效时的灾难性亏损
            if pnl_pct <= -20:
```

through the normal stop/profit logging block with:

```python
            if pnl_pct >= self.profit_protect_pct:
                protected_stop = round(max(pos.stop_loss or 0, pos.avg_cost), 3)
                if protected_stop > (pos.stop_loss or 0):
                    pos.stop_loss = protected_stop
                    add_realtime_log("info", f"🛡️ 盈利保护: {pos.symbol} 止损上移至成本线 ¥{protected_stop:.3f}")
                    log_decision(db, "hold", pos.symbol, pos.name, price, reason=f"盈利保护: 止损上移至成本线 ¥{protected_stop:.3f}")

            hit_config_stop = should_force_exit(pnl_pct, self.stop_loss_pct)
            hit_price_stop = bool(pos.stop_loss and price <= pos.stop_loss)
            if hit_config_stop or hit_price_stop:
                stop_reason = f"硬止损: {pnl_pct:.1f}% <= -{self.stop_loss_pct:.1f}%" if hit_config_stop else f"跌破止损价: ¥{price:.2f} <= ¥{pos.stop_loss:.2f}"
                add_realtime_log("warning", f"🚨 {stop_reason}，准备退出 {pos.symbol}")
                result = exec_sell(db, pos.symbol, price, avails,
                                   reason=stop_reason,
                                   is_etf=is_etf_code(pos.symbol))
                if result["ok"]:
                    add_realtime_log("success", f"✅ 风控卖出: {pos.symbol} {avails}股 @ ¥{price:.2f}")
                    sold_symbols.add(pos.symbol)
                continue

            if pnl_pct >= self.take_profit_pct:
                add_realtime_log("info", f"📌 利润管理区: {pos.symbol} {pnl_pct:.1f}% >= {self.take_profit_pct:.1f}%（交由Agent决策）")
```

Also change the earlier `if avails <= 0:` branch in this loop from:

```python
            if avails <= 0:
                continue
```

to:

```python
            if avails <= 0:
                if should_force_exit(pnl_pct, self.stop_loss_pct):
                    add_realtime_log("warning", f"⏳ {pos.symbol} 触发硬止损但受T+1限制暂无可卖数量")
                    log_decision(db, "skip", pos.symbol, pos.name, price, reason=f"硬止损待执行: T+1限制，当前盈亏{pnl_pct:.1f}%")
                continue
```

- [ ] **Step 4: Run position-management tests**

Run:

```bash
pytest tests/test_position_management.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit task**

Run:

```bash
git add web_app.py tests/test_position_management.py
git commit -m "feat: enforce hard stop loss before agent actions"
```

---

### Task 4: Enforce Buy Guardrails in Execution Loop

**Files:**
- Modify: `web_app.py`
- Test: `tests/test_position_management.py`

**Interfaces:**
- Consumes: `parse_confidence`, `format_confidence`, `should_skip_buy_pick` from Task 1.
- Consumes: engine attributes from Task 2.
- Produces: new buy picks are skipped before sizing when confidence/chase/time rules fail.

- [ ] **Step 1: Run helper tests before integration**

Run:

```bash
pytest tests/test_position_management.py::test_should_skip_buy_pick_rejects_missing_confidence tests/test_position_management.py::test_should_skip_buy_pick_rejects_confidence_at_threshold tests/test_position_management.py::test_should_skip_buy_pick_rejects_chasing_non_etf tests/test_position_management.py::test_should_skip_buy_pick_allows_high_pct_etf tests/test_position_management.py::test_should_skip_buy_pick_rejects_late_new_buy -v
```

Expected: PASS.

- [ ] **Step 2: Parse confidence without defaulting to zero**

In `web_app.py`, inside the new-buy loop, replace:

```python
            confidence = pick.get("confidence", 0)
```

with:

```python
            confidence = parse_confidence(pick.get("confidence"))
```

- [ ] **Step 3: Apply guardrail after quote fetch and ETF detection**

After these existing lines:

```python
            price = quote["price"]
            is_etf = is_etf_code(sym)
```

add:

```python
            quote_pct = float(quote.get("pct", 0) or 0)
            skip_reason = should_skip_buy_pick(
                confidence=confidence,
                quote_pct=quote_pct,
                is_etf=is_etf,
                now_time=beijing_now().time(),
                min_confidence=self.min_buy_confidence,
                max_chase_pct=self.max_chase_pct,
                late_buy_cutoff=self.late_buy_cutoff,
            )
            if skip_reason:
                add_realtime_log("warning", f"🚫 跳过 {sym} {name}: {skip_reason}")
                log_decision(db, "skip", sym, name, price, score=confidence, reason=skip_reason)
                continue
```

- [ ] **Step 4: Use formatted confidence in logs and reasons**

Replace:

```python
            add_realtime_log("ai", f"🚀 AI综合决策买入 {sym} {name} (信心{confidence}%)")
            reason_str = f"AI决策(信心{confidence}%): {reason[:100]}"
```

with:

```python
            confidence_text = format_confidence(confidence)
            add_realtime_log("ai", f"🚀 AI综合决策买入 {sym} {name} (信心{confidence_text})")
            reason_str = f"AI决策(信心{confidence_text}): {reason[:100]}"
```

Replace the non-trading log decision reason:

```python
                log_decision(db, "skip", sym, name, price, score=confidence, reason=f"[非交易时段记录] AI计划开仓{qty}股(信心{confidence}%): {reason[:100]}")
```

with:

```python
                log_decision(db, "skip", sym, name, price, score=confidence, reason=f"[非交易时段记录] AI计划开仓{qty}股(信心{confidence_text}): {reason[:100]}")
```

Replace the print line:

```python
                print(f"[AI] 买入 {sym} {name} {qty}股 @ {price} 止损{sl} AI信心{confidence}%")
```

with:

```python
                print(f"[AI] 买入 {sym} {name} {qty}股 @ {price} 止损{sl} AI信心{confidence_text}")
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/test_position_management.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit task**

Run:

```bash
git add web_app.py tests/test_position_management.py
git commit -m "feat: enforce conservative buy guardrails"
```

---

### Task 5: Full Verification

**Files:**
- No planned source modifications unless verification exposes a defect.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: verified conservative risk-control implementation.

- [ ] **Step 1: Run focused tests**

Run:

```bash
pytest tests/test_position_management.py -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run full test suite**

Run:

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 3: Verify server imports**

Run:

```bash
python3 -m py_compile web_app.py
```

Expected: command exits with status 0 and no syntax errors.

- [ ] **Step 4: Optional local API smoke test**

If a server is already running, run:

```bash
python3 - <<'PY'
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8080/api/metrics', timeout=10) as r:
    data = json.load(r)
print(data['win_rate'])
PY
```

Expected: prints a numeric win rate. If no server is running, skip this smoke test and record that it was skipped.

- [ ] **Step 5: Commit verification note if needed**

If Task 5 required any source/test changes, commit them:

```bash
git add web_app.py tests/test_position_management.py
git commit -m "test: verify conservative trading controls"
```

If no files changed, do not create an empty commit.

---

## Self-Review

- Spec coverage: covered conservative sizing, confidence enforcement, chase filter, late buy cutoff, hard stop, profit protection metadata, and skip logging.
- Placeholder scan: no placeholder tasks remain; every task has explicit code and commands.
- Type consistency: `parse_confidence` returns `Optional[float]`; `should_skip_buy_pick` accepts `Optional[float]`; engine buy loop logs `score=confidence`, compatible with existing optional score handling.
