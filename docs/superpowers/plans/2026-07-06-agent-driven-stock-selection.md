# Agent-Driven Stock Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand stock selection input from a narrow prefiltered slice to the top 100 active stocks so the Agent, not the prefilter, primarily decides what to buy while execution-layer risk checks remain in place.

**Architecture:** Keep the current single-file `web_app.py` flow, but replace the “top 100 → enrich 10 → show 8” path with a top-100 lightweight candidate-summary path. Update the candidate researcher prompt to consume the broader summary without fixed price-band rules, preserve execution-layer cash/lot/position validation, and add tests that prove the Agent now receives the broader input and that fallback/exposed APIs still work.

**Tech Stack:** Python 3.9+, FastAPI, SQLAlchemy ORM, SQLite/MySQL, NumPy, pytest

---

## File Structure

### Existing files to modify
- `web_app.py`
  - Add a helper that builds lightweight summaries for active candidates.
  - Change `_comprehensive_trade()` so `candidates_ctx` carries the top 100 summarized candidates instead of only the first 10 enriched candidates.
  - Update `run_candidate_research_node()` prompt and candidate rendering so it describes the larger market slice without fixed `5-50 / 0.5-5` price bands.
  - Keep execution-layer checks unchanged, but improve logs so they explain the new broader input and the final filtering result.
- `tests/test_autonomous_agent.py`
  - Add focused tests for candidate context building and researcher prompt behavior.
  - Update sample context assertions where needed to reflect the broader candidate payload.
- `tests/test_agent_api.py`
  - Add a regression test proving agent-cycle API responses can carry the broader candidate debug payload without breaking.

### New files to create
- None.

---

### Task 1: Add failing tests for top-100 candidate summaries

**Files:**
- Modify: `tests/test_autonomous_agent.py`
- Test: `tests/test_autonomous_agent.py`

- [ ] **Step 1: Write failing tests for candidate summarization and context preservation**

Append these tests to `tests/test_autonomous_agent.py`:

```python
def test_summarize_candidate_for_agent_keeps_lightweight_fields():
    raw = {
        "symbol": "000725",
        "name": "京东方A",
        "price": 7.76,
        "pct": 1.8,
        "amount": 15_200_000_000,
        "ma5": 7.6,
        "pe": 18.2,
        "pb": 1.4,
        "net_profit_yoy": 12.5,
        "revenue_yoy": 6.8,
        "is_etf": False,
        "recent_high": 7.95,
        "recent_low": 7.42,
        "extra_noise": "drop me",
    }

    summary = web_app.summarize_candidate_for_agent(raw)

    assert summary == {
        "symbol": "000725",
        "name": "京东方A",
        "price": 7.76,
        "pct": 1.8,
        "amount": 15_200_000_000,
        "ma5": 7.6,
        "pe": 18.2,
        "pb": 1.4,
        "net_profit_yoy": 12.5,
        "revenue_yoy": 6.8,
        "is_etf": False,
        "recent_high": 7.95,
        "recent_low": 7.42,
    }


@pytest.mark.parametrize("field,expected", [("name", ""), ("price", 0.0), ("amount", 0.0)])
def test_summarize_candidate_for_agent_defaults_missing_core_fields(field, expected):
    raw = {"symbol": "300750"}

    summary = web_app.summarize_candidate_for_agent(raw)

    assert summary[field] == expected


def test_build_agent_cycle_context_keeps_candidates_alias_for_full_candidate_list(sample_context):
    extra_candidates = [
        {"symbol": f"600{i:03d}", "name": f"样本{i}", "price": float(i), "amount": i * 1000}
        for i in range(100)
    ]

    context = web_app.build_agent_cycle_context(
        cycle_id=sample_context["cycle_id"],
        timestamp=sample_context["timestamp"],
        account_info=sample_context["account"],
        positions_ctx=sample_context["positions"],
        candidates_ctx=extra_candidates,
        market_sentiment=sample_context["market_snapshot"],
        engine_params=sample_context["engine_params"],
        recent_trades=[],
        recent_decisions=[],
        memory_summary={"notes": []},
    )

    assert len(context["candidate_pool"]) == 100
    assert len(context["candidates"]) == 100
    assert context["candidates"][0]["symbol"] == "600000"
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/test_autonomous_agent.py::test_summarize_candidate_for_agent_keeps_lightweight_fields \
       tests/test_autonomous_agent.py::test_summarize_candidate_for_agent_defaults_missing_core_fields \
       tests/test_autonomous_agent.py::test_build_agent_cycle_context_keeps_candidates_alias_for_full_candidate_list -v
```

Expected: FAIL with `AttributeError: module 'web_app' has no attribute 'summarize_candidate_for_agent'`.

- [ ] **Step 3: Add the minimal candidate summarization helper**

In `web_app.py`, near the existing market-data helpers and before `build_agent_cycle_context()`, add:

```python
def summarize_candidate_for_agent(stock: Dict[str, Any]) -> Dict[str, Any]:
    """构造给 Agent 使用的轻量候选摘要，避免在候选池阶段丢失大部分市场视角。"""
    summary = {
        "symbol": stock.get("symbol", ""),
        "name": stock.get("name", ""),
        "price": float(stock.get("price", 0) or 0),
        "pct": float(stock.get("pct", 0) or 0),
        "amount": float(stock.get("amount", 0) or 0),
        "ma5": stock.get("ma5"),
        "pe": stock.get("pe"),
        "pb": stock.get("pb"),
        "net_profit_yoy": stock.get("net_profit_yoy"),
        "revenue_yoy": stock.get("revenue_yoy"),
        "is_etf": bool(stock.get("is_etf", False)),
        "recent_high": stock.get("recent_high"),
        "recent_low": stock.get("recent_low"),
    }
    return summary
```

Do not add extra fields in this task.

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run:

```bash
pytest tests/test_autonomous_agent.py::test_summarize_candidate_for_agent_keeps_lightweight_fields \
       tests/test_autonomous_agent.py::test_summarize_candidate_for_agent_defaults_missing_core_fields \
       tests/test_autonomous_agent.py::test_build_agent_cycle_context_keeps_candidates_alias_for_full_candidate_list -v
```

Expected: PASS for all three tests.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_autonomous_agent.py
git commit -m "feat: add agent candidate summary helper"
```

---

### Task 2: Expand `_comprehensive_trade()` to pass summarized top-100 candidates

**Files:**
- Modify: `web_app.py:2875-2947`
- Modify: `tests/test_autonomous_agent.py`
- Test: `tests/test_autonomous_agent.py`

- [ ] **Step 1: Write a failing regression test for top-100 candidate delivery**

Append this test to `tests/test_autonomous_agent.py`:

```python
def test_comprehensive_trade_passes_top_100_summaries_to_agent(monkeypatch, db):
    acct = web_app.get_account(db)
    acct.cash = 12000
    db.commit()

    engine = web_app.AutonomousTradingEngine()
    captured = {}

    all_stocks = [
        {
            "symbol": f"600{i:03d}",
            "name": f"样本{i}",
            "price": 10 + i * 0.01,
            "pct": i * 0.1,
            "amount": 1_000_000_000 - i,
        }
        for i in range(120)
    ]

    monkeypatch.setattr(web_app, "fetch_all_stocks", lambda: all_stocks)
    monkeypatch.setattr(web_app, "fetch_financial_batch", lambda: {})
    monkeypatch.setattr(web_app, "fetch_history", lambda symbol, days=20: None)
    monkeypatch.setattr(web_app, "fetch_valuation", lambda symbol: None)
    monkeypatch.setattr(web_app, "calculate_market_sentiment", lambda stocks: {"sentiment": "neutral", "score": 50})
    monkeypatch.setattr(web_app, "recall_recent_agent_memory", lambda db, limit=5: {"items": [], "notes": []})

    def fake_run_agent_cycle_with_fallback(db_session, context):
        captured["candidate_count"] = len(context["candidates"])
        captured["first_symbol"] = context["candidates"][0]["symbol"]
        captured["last_symbol"] = context["candidates"][-1]["symbol"]
        return {
            "market_analysis": "ok",
            "risk_level": "low",
            "position_actions": [],
            "buy_picks": [],
            "reasoning": [],
            "candidate_debug": {"input_count": len(context["candidates"]), "selected_count": 0},
        }

    monkeypatch.setattr(web_app, "run_agent_cycle_with_fallback", fake_run_agent_cycle_with_fallback)
    monkeypatch.setattr(web_app, "log_decision", lambda *args, **kwargs: None)

    engine._comprehensive_trade(db)

    assert captured["candidate_count"] == 100
    assert captured["first_symbol"] == "600000"
    assert captured["last_symbol"] == "600099"
```

- [ ] **Step 2: Run the regression test to verify it fails**

Run:

```bash
pytest tests/test_autonomous_agent.py::test_comprehensive_trade_passes_top_100_summaries_to_agent -v
```

Expected: FAIL because `candidate_count` is `10`, not `100`.

- [ ] **Step 3: Replace the top-10 enriched candidate path with top-100 summaries**

In `web_app.py`, change the candidate-building block inside `_comprehensive_trade()` to this shape:

```python
        candidates = sorted(all_stocks, key=lambda s: s.get("amount", 0), reverse=True)[:100]
        add_realtime_log("info", f"🧺 候选池初筛: 从 {len(all_stocks)} 只股票中按成交额选出 {len(candidates)} 只活跃股")
        fin_data = fetch_financial_batch()
        candidates_ctx = []
        for stock in candidates:
            enriched = dict(stock)
            try:
                hist = fetch_history(enriched["symbol"], days=20)
                if hist:
                    indicators = calculate_indicators(hist)
                    enriched.update(indicators)
                    closes = [h["close"] for h in hist[-5:]]
                    enriched["ma5"] = round(float(np.mean(closes)), 2) if closes else enriched["price"]
                    enriched["recent_high"] = max(h["high"] for h in hist[-5:])
                    enriched["recent_low"] = min(h["low"] for h in hist[-5:])
                enriched["is_etf"] = is_etf_code(enriched["symbol"])
                if not enriched["is_etf"]:
                    try:
                        val = fetch_valuation(enriched["symbol"])
                        if val:
                            enriched["pe"] = val.get("pe")
                            enriched["pb"] = val.get("pb")
                            enriched["total_mv"] = val.get("total_mv")
                    except Exception:
                        pass
                fin = fin_data.get(enriched["symbol"], {})
                if fin:
                    enriched["net_profit_yoy"] = fin.get("net_profit_yoy")
                    enriched["revenue_yoy"] = fin.get("revenue_yoy")
                    enriched["eps"] = fin.get("eps")
            except Exception:
                pass
            candidates_ctx.append(summarize_candidate_for_agent(enriched))
```

Also update the comment immediately above this block from “取成交额前10只活跃股” to “取成交额前100只活跃股并生成轻量摘要”.

- [ ] **Step 4: Update the preview log to reflect the broader input and rerun the regression test**

Keep the existing preview log, but make sure it now describes the top-100 summarized set:

```python
        candidate_preview = "，".join([f"{s.get('symbol','')}{s.get('name','')}" for s in candidates_ctx[:5]]) or "无"
        add_realtime_log("info", f"🔎 候选池精筛完成: 保留 {len(candidates_ctx)} 只候选，前5只: {candidate_preview}")
```

Run:

```bash
pytest tests/test_autonomous_agent.py::test_comprehensive_trade_passes_top_100_summaries_to_agent -v
```

Expected: PASS with `candidate_count == 100`.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_autonomous_agent.py
git commit -m "feat: pass top 100 candidates into agent selection"
```

---

### Task 3: Remove fixed price-band bias from the candidate researcher prompt

**Files:**
- Modify: `web_app.py:1130-1218`
- Modify: `tests/test_autonomous_agent.py`
- Test: `tests/test_autonomous_agent.py`

- [ ] **Step 1: Write failing tests for the new researcher prompt contract**

Append these tests to `tests/test_autonomous_agent.py`:

```python
def test_run_candidate_research_node_uses_all_candidates_in_prompt(monkeypatch):
    captured = {}
    candidates = [
        {"symbol": f"600{i:03d}", "name": f"样本{i}", "price": 10.0 + i, "amount": 1_000_000_000 - i}
        for i in range(12)
    ]
    state = {
        "context": {
            "candidates": candidates,
            "account": {"available_cash": 10000, "max_positions": 3, "current_positions": 0},
        },
        "market_assessment": {"regime": "neutral"},
    }

    def fake_agent_ai_call(agent_key, prompt, stage_label):
        captured["prompt"] = prompt
        return json.dumps({"assessments": [], "reasoning": "无合适标的"})

    monkeypatch.setattr(web_app, "_agent_ai_call", fake_agent_ai_call)

    result = web_app.run_candidate_research_node(state)

    assert result["candidate_debug"]["input_count"] == 12
    assert "600011 样本11" in captured["prompt"]


def test_run_candidate_research_node_prompt_drops_fixed_price_band_language(monkeypatch):
    captured = {}
    state = {
        "context": {
            "candidates": [{"symbol": "000725", "name": "京东方A", "price": 7.76, "amount": 1_000_000_000}],
            "account": {"available_cash": 10000, "max_positions": 3, "current_positions": 0},
        },
        "market_assessment": {"regime": "defensive"},
    }

    def fake_agent_ai_call(agent_key, prompt, stage_label):
        captured["prompt"] = prompt
        return json.dumps({"assessments": [], "reasoning": "无合适标的"})

    monkeypatch.setattr(web_app, "_agent_ai_call", fake_agent_ai_call)

    web_app.run_candidate_research_node(state)

    assert "股票5-50元" not in captured["prompt"]
    assert "ETF 0.5-5元" not in captured["prompt"]
    assert "价格×100 ≤ 可用现金" not in captured["prompt"]
    assert "前100只活跃股候选摘要" in captured["prompt"]
```

- [ ] **Step 2: Run the prompt tests to verify they fail**

Run:

```bash
pytest tests/test_autonomous_agent.py::test_run_candidate_research_node_uses_all_candidates_in_prompt \
       tests/test_autonomous_agent.py::test_run_candidate_research_node_prompt_drops_fixed_price_band_language -v
```

Expected: FAIL because the prompt currently only includes the first 8 candidates and still contains the fixed price-band lines.

- [ ] **Step 3: Update `run_candidate_research_node()` to describe the full summarized set**

In `web_app.py`, replace the candidate rendering and prompt block with this version:

```python
    cand_lines = []
    for c in candidates:
        tech = []
        if c.get("ma5"):
            tech.append(f"MA5={c['ma5']}")
        if c.get("pe"):
            tech.append(f"PE={c['pe']}")
        if c.get("net_profit_yoy") is not None:
            tech.append(f"净利增速={c['net_profit_yoy']}%")
        tech_str = " ".join(tech)
        cand_lines.append(
            f"- {c['symbol']} {c.get('name','')}: ¥{c.get('price',0):.2f} "
            f"涨跌幅{c.get('pct',0):+.2f}% 成交额¥{c.get('amount',0)/1e8:.1f}亿 {tech_str}".strip()
        )
    cand_text = "\n".join(cand_lines)

    prompt = f"""你是A股短线选股专家。

## 候选标的（成交额前100只活跃股候选摘要）
{cand_text}

## 账户信息
- 可用现金: ¥{acct.get('available_cash', 0):,.0f}
- 最大持仓: {acct.get('max_positions', 3)} 只
- 当前持仓: {acct.get('current_positions', 0)} 只
- 市场格局: {market.get('regime', 'neutral')}

## 选股要求
- 从以上候选中找出当前最值得买入的 0-3 只标的。
- 优先考虑趋势质量、流动性、风险收益比、基本面支撑与当前市场格局的匹配度。
- 结合账户规模判断哪些标的更适合当前资金体量，但不要机械套用固定价格区间。
- 如果没有足够有把握的标的，可以返回空数组。

## 输出JSON（严格）
{{
  "assessments": [
    {{
      "symbol": "代码",
      "name": "名称",
      "kind": "stock / etf",
      "reason": "推荐理由（80字内，含技术面分析）",
      "entry_price": 0.00,
      "stop_loss": 0.00,
      "target_price": 0.00,
      "confidence": 70,
      "time_horizon": "3-30天"
    }}
  ],
  "reasoning": "你的筛选逻辑和推理过程（100字内）"
}}"""
```

Keep the existing `candidate_debug` return structure.

- [ ] **Step 4: Run the prompt tests to verify they pass**

Run:

```bash
pytest tests/test_autonomous_agent.py::test_run_candidate_research_node_uses_all_candidates_in_prompt \
       tests/test_autonomous_agent.py::test_run_candidate_research_node_prompt_drops_fixed_price_band_language -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_autonomous_agent.py
git commit -m "feat: let researcher choose from top 100 candidates"
```

---

### Task 4: Add API-level regression coverage for broader candidate debug payloads

**Files:**
- Modify: `tests/test_agent_api.py`
- Test: `tests/test_agent_api.py`

- [ ] **Step 1: Write a failing API regression test for candidate debug passthrough**

Append this test to `tests/test_agent_api.py`:

```python
def test_agent_cycles_expose_candidate_debug_payload(client):
    cycle_id = "candidate-debug-001"
    with web_app.SessionLocal() as db:
        cycle = AgentCycleLogModel(
            cycle_id=cycle_id,
            status="ok",
            risk_level="low",
            summary="agent picked none",
            plan_json=json.dumps({
                "reasoning": ["等待机会"],
                "position_actions": [],
                "buy_picks": [],
                "candidate_debug": {
                    "input_count": 100,
                    "selected_count": 0,
                    "rejected_by": "researcher",
                    "rejected_reasons": ["当前没有足够高把握标的"],
                },
            }, ensure_ascii=False),
        )
        db.add(cycle)
        db.commit()

    resp = client.get("/api/agent/cycles")
    assert resp.status_code == 200
    rows = [row for row in resp.json() if row["cycle_id"] == cycle_id]
    assert len(rows) == 1
    assert rows[0]["plan"]["candidate_debug"]["input_count"] == 100
    assert rows[0]["plan"]["candidate_debug"]["rejected_by"] == "researcher"
```

- [ ] **Step 2: Run the API regression test to verify it fails only if the payload is dropped**

Run:

```bash
pytest tests/test_agent_api.py::test_agent_cycles_expose_candidate_debug_payload -v
```

Expected: If the API already preserves `plan_json` payloads, PASS immediately. If it fails, inspect the returned JSON and make the minimal fix in the next step.

- [ ] **Step 3: If needed, make the minimal API fix to keep `candidate_debug` in `plan`**

Only if Step 2 fails, update the `api_agent_cycles()` response builder in `web_app.py` so it returns the parsed `plan_json` unchanged inside the `plan` field, including nested `candidate_debug` data.

Use this response shape if a fix is required:

```python
        result.append({
            "cycle_id": row.cycle_id,
            "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else "",
            "status": row.status,
            "risk_level": row.risk_level,
            "summary": row.summary,
            "triggered_trade": bool(row.triggered_trade),
            "plan": plan,
            "reasoning": plan.get("reasoning", []),
            "nodes": nodes,
        })
```

If Step 2 already passes, skip this step and note that no code change was required.

- [ ] **Step 4: Run the agent API test file**

Run:

```bash
pytest tests/test_agent_api.py -v
```

Expected: PASS for the full file.

- [ ] **Step 5: Commit**

If only the test changed:

```bash
git add tests/test_agent_api.py
git commit -m "test: cover candidate debug in agent cycles api"
```

If both test and `web_app.py` changed:

```bash
git add tests/test_agent_api.py web_app.py
git commit -m "fix: preserve candidate debug in agent cycles api"
```

---

### Task 5: Run the focused verification suite and smoke-check the runtime behavior

**Files:**
- Modify: `web_app.py`
- Modify: `tests/test_autonomous_agent.py`
- Modify: `tests/test_agent_api.py`

- [ ] **Step 1: Run the focused autonomous-agent tests**

Run:

```bash
pytest tests/test_autonomous_agent.py -v
```

Expected: PASS with no failures.

- [ ] **Step 2: Run the focused agent API tests**

Run:

```bash
pytest tests/test_agent_api.py -v
```

Expected: PASS with no failures.

- [ ] **Step 3: Restart the app and verify the broader candidate logs**

Run:

```bash
lsof -ti tcp:8080 -sTCP:LISTEN | xargs kill 2>/dev/null || true
cd /Users/a1234/Desktop/A股模拟短线交易训练器
PORT=8080 python3 web_app.py
```

Expected in startup logs: `Uvicorn running on http://0.0.0.0:8080`.

- [ ] **Step 4: Trigger a cycle and verify the new candidate breadth**

With the app running, inspect:

```bash
curl -s 'http://127.0.0.1:8080/api/logs?limit=20'
curl -s 'http://127.0.0.1:8080/api/agent/status'
```

Expected evidence:

- realtime logs contain `候选池初筛: 从 ... 按成交额选出 100 只活跃股`
- realtime logs contain `候选池精筛完成: 保留 100 只候选`
- agent status researcher text no longer references the fixed `5-50元 / 0.5-5元` rule

- [ ] **Step 5: Commit the final implementation**

```bash
git add web_app.py tests/test_autonomous_agent.py tests/test_agent_api.py
git commit -m "feat: let agent drive stock selection from top 100"
```

---

## Self-Review

### Spec coverage
- **Top 100 candidate input:** Covered by Task 2.
- **Remove fixed price-band bias:** Covered by Task 3.
- **Keep execution-layer risk checks:** Verified implicitly in Task 2 and explicitly preserved by not changing execution rules; runtime smoke check in Task 5 confirms behavior still flows through the existing executor.
- **Improve explainability/logs:** Covered by Task 2 preview/log expectations and Task 5 smoke check.
- **API/debug visibility:** Covered by Task 4.

### Placeholder scan
- No `TODO` / `TBD` placeholders remain.
- Commands, test code, and code snippets are concrete for every code-changing step.
- The one conditional step in Task 4 includes the exact fallback code and explicitly says to skip it if not needed.

### Type consistency
- The new helper is consistently named `summarize_candidate_for_agent` in tests, implementation, and later tasks.
- Candidate debug keys stay `input_count`, `selected_count`, `rejected_by`, `rejected_reasons` everywhere.
- Candidate summary fields used by the researcher prompt (`symbol`, `name`, `price`, `pct`, `amount`, `ma5`, `pe`, `net_profit_yoy`) match the helper output.
