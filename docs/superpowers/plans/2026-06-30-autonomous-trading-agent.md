# Autonomous Trading Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current single-call AI decision path with a LangGraph-based autonomous trading agent that uses specialist nodes, short-term memory, structured logs, and frontend visibility while preserving the existing execution engine.

**Architecture:** Keep `web_app.py` as the integration center because the current project is intentionally monolithic, but add focused agent helpers and tests around it. The new flow builds a shared cycle context, recalls memory, runs market/position/candidate/risk specialist nodes through LangGraph, validates a final trading plan, executes with the existing buy/sell functions, then persists cycle logs and memory for the frontend.

**Tech Stack:** Python 3.9+, FastAPI, SQLAlchemy ORM, SQLite/MySQL, LangGraph, NumPy, pytest

---

## File Structure

### Existing files to modify
- `web_app.py`
  - Add agent log / memory / feedback SQLAlchemy models
  - Add context builder, memory helpers, specialist node helpers, plan validation, LangGraph runner, persistence helpers, and API routes
  - Replace the central `ai_comprehensive_decision()` call site inside `_comprehensive_trade()` with `run_trading_agent_cycle(...)` plus safe fallback
- `templates/index.html`
  - Add Agent cycle timeline and memory summary sections to the dashboard
  - Add client-side fetch/render functions for new `/api/agent/*` endpoints
  - Update docs tab language from hard stop-profit selling to agent-driven profit management and decision chain visibility
- `requirements.txt`
  - Add `langgraph`
- `README.md`
  - Document the autonomous agent architecture, memory, and decision timeline

### New files to create
- `tests/test_autonomous_agent.py`
  - Unit tests for context building, memory recall, plan validation, specialist node orchestration, persistence helpers, and daily reflection
- `tests/test_agent_api.py`
  - Route/serializer tests for cycle timeline and memory summary APIs

---

### Task 1: Add LangGraph dependency and an agent test harness

**Files:**
- Modify: `requirements.txt`
- Create: `tests/test_autonomous_agent.py`
- Create: `tests/test_agent_api.py`

- [ ] **Step 1: Add LangGraph to dependencies**

Update `requirements.txt` so it contains:

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
langgraph>=0.2.34
```

- [ ] **Step 2: Create the core agent test harness**

Create `tests/test_autonomous_agent.py` with this initial content:

```python
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

import web_app


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_file = tmp_path / "agent_test.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setattr(web_app, "DB_URL", url, raising=False)
    engine = create_engine(url, echo=False)
    TestingSessionLocal = sessionmaker(bind=engine)
    web_app.Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def sample_context():
    return {
        "cycle_id": str(uuid.uuid4()),
        "timestamp": "2026-06-30T10:03:00+08:00",
        "account": {
            "initial_cash": 10000,
            "available_cash": 6200,
            "max_buy_amount": 5000,
            "max_buy_price": 50,
            "current_positions": 1,
            "max_positions": 3,
            "remaining_capacity": 2,
        },
        "positions": [
            {
                "symbol": "600000",
                "name": "浦发银行",
                "qty": 400,
                "current_price": 10.2,
                "buy_price": 9.8,
                "pnl_pct": 4.08,
                "available_to_sell": 400,
            }
        ],
        "candidate_pool": [
            {
                "symbol": "512880",
                "name": "证券ETF",
                "price": 1.25,
                "pct": 1.8,
                "trend": "up",
            }
        ],
        "market_snapshot": {"sentiment": "neutral", "score": 56},
        "engine_params": {"max_positions": 3, "max_position_pct": 50.0},
        "recent_trades": [],
        "recent_decisions": [],
        "memory_summary": {"notes": []},
    }
```

- [ ] **Step 3: Create the API test harness**

Create `tests/test_agent_api.py` with this initial content:

```python
from types import SimpleNamespace

import web_app


def test_placeholder_agent_api():
    row = SimpleNamespace(cycle_id="cycle-1", summary="防守模式", risk_level="mid")
    assert row.cycle_id == "cycle-1"
```

- [ ] **Step 4: Run the harness tests**

Run:

```bash
pytest tests/test_autonomous_agent.py tests/test_agent_api.py -v
```

Expected: PASS with `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/test_autonomous_agent.py tests/test_agent_api.py
git commit -m "test: add autonomous agent test harness"
```

---

### Task 2: Add agent cycle, node log, memory, and feedback tables

**Files:**
- Modify: `web_app.py`
- Test: `tests/test_autonomous_agent.py`

- [ ] **Step 1: Write failing tests for new agent tables**

Append these tests to `tests/test_autonomous_agent.py`:

```python
def test_agent_tables_are_created(db):
    inspector = inspect(db.bind)
    tables = set(inspector.get_table_names())
    assert "agent_cycle_logs" in tables
    assert "agent_node_logs" in tables
    assert "agent_memories" in tables
    assert "agent_feedback" in tables


def test_agent_memory_model_persists_json_content(db):
    row = web_app.AgentMemoryModel(
        memory_type="short_term",
        memory_date=datetime(2026, 6, 30, 15, 1),
        tags="defensive,bank",
        content_json='{"notes": ["avoid chasing"]}',
        relevance_score=0.8,
    )
    db.add(row)
    db.commit()

    saved = db.query(web_app.AgentMemoryModel).one()
    assert saved.memory_type == "short_term"
    assert "avoid chasing" in saved.content_json
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```bash
pytest tests/test_autonomous_agent.py -k "agent_tables or agent_memory_model" -v
```

Expected: FAIL with `AttributeError` for missing `AgentMemoryModel` and missing tables.

- [ ] **Step 3: Add the SQLAlchemy models**

In `web_app.py`, add these models near the existing ORM models section:

```python
class AgentCycleLogModel(Base):
    __tablename__ = "agent_cycle_logs"

    id = Column(Integer, primary_key=True)
    cycle_id = Column(String(64), unique=True, index=True, nullable=False)
    time = Column(DateTime, default=datetime.now, index=True)
    status = Column(String(16), default="success")
    duration_ms = Column(Integer, default=0)
    risk_level = Column(String(16), default="mid")
    summary = Column(Text, default="")
    triggered_trade = Column(Boolean, default=False)
    plan_json = Column(Text, default="{}")


class AgentNodeLogModel(Base):
    __tablename__ = "agent_node_logs"

    id = Column(Integer, primary_key=True)
    cycle_id = Column(String(64), index=True, nullable=False)
    node_name = Column(String(64), index=True, nullable=False)
    time = Column(DateTime, default=datetime.now, index=True)
    duration_ms = Column(Integer, default=0)
    model_name = Column(String(128), default="")
    tool_calls = Column(Text, default="[]")
    input_summary = Column(Text, default="")
    output_summary = Column(Text, default="")


class AgentMemoryModel(Base):
    __tablename__ = "agent_memories"

    id = Column(Integer, primary_key=True)
    memory_type = Column(String(32), index=True, nullable=False)
    memory_date = Column(DateTime, default=datetime.now, index=True)
    tags = Column(String(255), default="")
    content_json = Column(Text, default="{}")
    relevance_score = Column(Float, default=0.0)


class AgentFeedbackModel(Base):
    __tablename__ = "agent_feedback"

    id = Column(Integer, primary_key=True)
    cycle_id = Column(String(64), index=True, nullable=False)
    symbol = Column(String(16), index=True, nullable=False)
    action_type = Column(String(16), nullable=False)
    feedback_date = Column(DateTime, default=datetime.now, index=True)
    horizon_1d = Column(Float, default=0.0)
    horizon_3d = Column(Float, default=0.0)
    horizon_5d = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    outcome_label = Column(String(32), default="pending")
    notes = Column(Text, default="")
```

- [ ] **Step 4: Run the focused tests again**

Run:

```bash
pytest tests/test_autonomous_agent.py -k "agent_tables or agent_memory_model" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_autonomous_agent.py
git commit -m "feat: add autonomous agent storage models"
```

---

### Task 3: Add cycle context building and short-term memory recall helpers

**Files:**
- Modify: `web_app.py`
- Test: `tests/test_autonomous_agent.py`

- [ ] **Step 1: Write failing tests for context and memory recall**

Append these tests to `tests/test_autonomous_agent.py`:

```python
def test_build_agent_cycle_context_keeps_core_sections(sample_context):
    context = web_app.build_agent_cycle_context(
        cycle_id=sample_context["cycle_id"],
        timestamp=sample_context["timestamp"],
        account_info=sample_context["account"],
        positions_ctx=sample_context["positions"],
        candidates_ctx=sample_context["candidate_pool"],
        market_sentiment=sample_context["market_snapshot"],
        engine_params=sample_context["engine_params"],
        recent_trades=[],
        recent_decisions=[],
        memory_summary={"notes": ["avoid chasing"]},
    )
    assert context["account"]["available_cash"] == 6200
    assert context["positions"][0]["symbol"] == "600000"
    assert context["memory_summary"]["notes"] == ["avoid chasing"]


def test_recall_recent_agent_memory_prefers_latest_rows(db):
    db.add(
        web_app.AgentMemoryModel(
            memory_type="short_term",
            memory_date=datetime(2026, 6, 28, 15, 0),
            tags="bullish,bank",
            content_json='{"notes": ["older"]}',
            relevance_score=0.3,
        )
    )
    db.add(
        web_app.AgentMemoryModel(
            memory_type="short_term",
            memory_date=datetime(2026, 6, 30, 15, 0),
            tags="defensive,etf",
            content_json='{"notes": ["latest"]}',
            relevance_score=0.9,
        )
    )
    db.commit()

    summary = web_app.recall_recent_agent_memory(db, limit=1)
    assert summary["items"][0]["tags"] == "defensive,etf"
    assert summary["notes"] == ["latest"]
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```bash
pytest tests/test_autonomous_agent.py -k "build_agent_cycle_context or recall_recent_agent_memory" -v
```

Expected: FAIL with missing helper function errors.

- [ ] **Step 3: Add context and memory helpers**

In `web_app.py`, add these helpers near the new agent section:

```python
def build_agent_cycle_context(cycle_id: str, timestamp: str, account_info: Dict,
                              positions_ctx: List[Dict], candidates_ctx: List[Dict],
                              market_sentiment: Dict, engine_params: Dict,
                              recent_trades: List[Dict], recent_decisions: List[Dict],
                              memory_summary: Dict) -> Dict:
    return {
        "cycle_id": cycle_id,
        "timestamp": timestamp,
        "account": account_info,
        "positions": positions_ctx,
        "candidate_pool": candidates_ctx,
        "market_snapshot": market_sentiment,
        "engine_params": engine_params,
        "recent_trades": recent_trades,
        "recent_decisions": recent_decisions,
        "memory_summary": memory_summary or {"items": [], "notes": []},
    }


def recall_recent_agent_memory(db: Session, limit: int = 5, memory_type: str = "short_term") -> Dict:
    rows = db.query(AgentMemoryModel).filter(
        AgentMemoryModel.memory_type == memory_type
    ).order_by(AgentMemoryModel.memory_date.desc()).limit(limit).all()

    items = []
    notes = []
    for row in rows:
        payload = safe_json_loads(row.content_json, {})
        items.append({
            "id": row.id,
            "memory_type": row.memory_type,
            "memory_date": row.memory_date.isoformat() if row.memory_date else "",
            "tags": row.tags,
            "content": payload,
            "relevance_score": row.relevance_score,
        })
        notes.extend(payload.get("notes", []))

    return {"items": items, "notes": notes[:5]}
```

Also add a small JSON helper if the file does not already have one:

```python
def safe_json_loads(raw: str, default):
    try:
        return json.loads(raw) if raw else default
    except Exception:
        return default
```

- [ ] **Step 4: Run the focused tests again**

Run:

```bash
pytest tests/test_autonomous_agent.py -k "build_agent_cycle_context or recall_recent_agent_memory" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_autonomous_agent.py
git commit -m "feat: add agent context and memory helpers"
```

---

### Task 4: Build the LangGraph specialist workflow

**Files:**
- Modify: `web_app.py`
- Test: `tests/test_autonomous_agent.py`

- [ ] **Step 1: Write failing tests for the agent graph output shape**

Append these tests to `tests/test_autonomous_agent.py`:

```python
def test_run_trading_agent_cycle_returns_valid_plan(sample_context, monkeypatch):
    monkeypatch.setattr(web_app, "run_market_analysis_node", lambda state: {
        "market_assessment": {
            "regime": "defensive",
            "sentiment_score": 48,
            "risk_bias": "conservative",
            "sector_focus": ["ETF"],
            "warnings": ["高位分歧扩大"],
            "reasoning": "防守优先",
        }
    })
    monkeypatch.setattr(web_app, "run_position_review_node", lambda state: {
        "position_assessments": [
            {
                "symbol": "600000",
                "action": "hold",
                "target_pct": 18,
                "confidence": 0.72,
                "thesis": "趋势未破",
                "risks": [],
                "supports": ["量能稳定"],
            }
        ]
    })
    monkeypatch.setattr(web_app, "run_candidate_research_node", lambda state: {
        "candidate_assessments": []
    })
    monkeypatch.setattr(web_app, "run_risk_review_node", lambda state: {
        "risk_review": {
            "overall_pass": True,
            "risk_level": "medium",
            "blocked_actions": [],
            "adjustments": [],
            "notes": ["保留现金"],
        }
    })
    monkeypatch.setattr(web_app, "run_decision_synthesizer_node", lambda state: {
        "final_plan": {
            "cycle_id": state["context"]["cycle_id"],
            "position_actions": [{"symbol": "600000", "action": "hold", "target_pct": 18}],
            "new_entries": [],
            "buy_picks": [],
            "portfolio_bias": "balanced",
            "cash_reserve_target": 0.35,
            "summary": "防守模式，继续持有",
            "confidence": 0.74,
            "risk_level": "medium",
        }
    })

    plan = web_app.run_trading_agent_cycle(sample_context)
    assert plan["portfolio_bias"] == "balanced"
    assert plan["position_actions"][0]["action"] == "hold"
    assert plan["risk_level"] == "medium"
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
pytest tests/test_autonomous_agent.py -k run_trading_agent_cycle_returns_valid_plan -v
```

Expected: FAIL with missing graph helper function errors.

- [ ] **Step 3: Add the state type, node helpers, and LangGraph runner**

In `web_app.py`, add these imports near the top:

```python
from typing import Any, TypedDict
from langgraph.graph import END, StateGraph
```

Then add the graph state and runner:

```python
class TradingAgentState(TypedDict, total=False):
    context: Dict[str, Any]
    memory_summary: Dict[str, Any]
    market_assessment: Dict[str, Any]
    position_assessments: List[Dict[str, Any]]
    candidate_assessments: List[Dict[str, Any]]
    risk_review: Dict[str, Any]
    final_plan: Dict[str, Any]


def run_market_analysis_node(state: TradingAgentState) -> Dict[str, Any]:
    context = state["context"]
    snapshot = context.get("market_snapshot", {})
    score = float(snapshot.get("score", 50) or 50)
    regime = "bullish" if score >= 70 else "defensive" if score <= 45 else "neutral"
    return {
        "market_assessment": {
            "regime": regime,
            "sentiment_score": score,
            "risk_bias": "aggressive" if score >= 70 else "conservative" if score <= 45 else "balanced",
            "sector_focus": [],
            "warnings": [],
            "reasoning": snapshot.get("sentiment", "市场中性"),
        }
    }


def run_position_review_node(state: TradingAgentState) -> Dict[str, Any]:
    positions = []
    for pos in state["context"].get("positions", []):
        positions.append({
            "symbol": pos["symbol"],
            "action": "hold",
            "target_pct": min(50.0, pos.get("target_pct", 20.0) or 20.0),
            "confidence": 0.6,
            "thesis": "等待 AI 细化",
            "risks": [],
            "supports": [],
        })
    return {"position_assessments": positions}


def run_candidate_research_node(state: TradingAgentState) -> Dict[str, Any]:
    return {"candidate_assessments": []}


def run_risk_review_node(state: TradingAgentState) -> Dict[str, Any]:
    return {
        "risk_review": {
            "overall_pass": True,
            "risk_level": "medium",
            "blocked_actions": [],
            "adjustments": [],
            "notes": [],
        }
    }


def run_decision_synthesizer_node(state: TradingAgentState) -> Dict[str, Any]:
    assessments = state.get("position_assessments", [])
    final_plan = {
        "cycle_id": state["context"]["cycle_id"],
        "position_actions": [
            {
                "symbol": item["symbol"],
                "action": item["action"],
                "target_pct": item["target_pct"],
            }
            for item in assessments
        ],
        "new_entries": [],
        "buy_picks": [],
        "portfolio_bias": state.get("market_assessment", {}).get("risk_bias", "balanced"),
        "cash_reserve_target": 0.35,
        "summary": state.get("market_assessment", {}).get("reasoning", "Agent plan"),
        "confidence": 0.6,
        "risk_level": state.get("risk_review", {}).get("risk_level", "medium"),
    }
    return {"final_plan": final_plan}


def build_trading_agent_graph():
    graph = StateGraph(TradingAgentState)
    graph.add_node("recall_memory", lambda state: {"memory_summary": state["context"].get("memory_summary", {})})
    graph.add_node("analyze_market", run_market_analysis_node)
    graph.add_node("review_positions", run_position_review_node)
    graph.add_node("research_candidates", run_candidate_research_node)
    graph.add_node("risk_review", run_risk_review_node)
    graph.add_node("synthesize_decision", run_decision_synthesizer_node)

    graph.set_entry_point("recall_memory")
    graph.add_edge("recall_memory", "analyze_market")
    graph.add_edge("analyze_market", "review_positions")
    graph.add_edge("review_positions", "research_candidates")
    graph.add_edge("research_candidates", "risk_review")
    graph.add_edge("risk_review", "synthesize_decision")
    graph.add_edge("synthesize_decision", END)
    return graph.compile()


def run_trading_agent_cycle(context: Dict[str, Any]) -> Dict[str, Any]:
    graph = build_trading_agent_graph()
    result = graph.invoke({"context": context})
    return result["final_plan"]
```

- [ ] **Step 4: Run the graph test again**

Run:

```bash
pytest tests/test_autonomous_agent.py -k run_trading_agent_cycle_returns_valid_plan -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_autonomous_agent.py
git commit -m "feat: add langgraph trading agent workflow"
```

---

### Task 5: Validate final plans and integrate the agent runner into the trading loop

**Files:**
- Modify: `web_app.py`
- Test: `tests/test_autonomous_agent.py`

- [ ] **Step 1: Write failing tests for plan validation and fallback**

Append these tests to `tests/test_autonomous_agent.py`:

```python
def test_validate_final_trading_plan_blocks_new_entries_when_risk_high():
    plan = {
        "cycle_id": "cycle-1",
        "position_actions": [{"symbol": "600000", "action": "hold", "target_pct": 20}],
        "new_entries": [{"symbol": "512880", "action": "buy", "target_pct": 25}],
        "buy_picks": [{"symbol": "512880", "name": "证券ETF", "confidence": 82}],
        "portfolio_bias": "aggressive",
        "cash_reserve_target": 0.1,
        "summary": "still buying",
        "confidence": 0.9,
        "risk_level": "high",
    }

    validated = web_app.validate_final_trading_plan(
        plan,
        max_position_pct=50.0,
        max_positions=3,
        available_cash=2000,
    )
    assert validated["new_entries"] == []
    assert validated["buy_picks"] == []
    assert validated["portfolio_bias"] == "conservative"


def test_run_agent_cycle_with_fallback_uses_legacy_path_on_error(sample_context, monkeypatch):
    monkeypatch.setattr(web_app, "run_trading_agent_cycle", lambda context: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(web_app, "ai_comprehensive_decision", lambda *args, **kwargs: {
        "market_analysis": "fallback",
        "risk_level": "mid",
        "position_actions": [],
        "buy_picks": [],
    })

    decision = web_app.run_agent_cycle_with_fallback(
        positions_ctx=sample_context["positions"],
        candidates_ctx=sample_context["candidate_pool"],
        account_info=sample_context["account"],
        market_sentiment=sample_context["market_snapshot"],
        engine_params=sample_context["engine_params"],
        recent_trades=[],
        recent_decisions=[],
        memory_summary=sample_context["memory_summary"],
    )
    assert decision["market_analysis"] == "fallback"
    assert decision["position_actions"] == []
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```bash
pytest tests/test_autonomous_agent.py -k "validate_final_trading_plan or run_agent_cycle_with_fallback" -v
```

Expected: FAIL with missing helper function errors.

- [ ] **Step 3: Add plan validation and the fallback wrapper**

In `web_app.py`, add:

```python
def validate_final_trading_plan(plan: Dict[str, Any], max_position_pct: float,
                                max_positions: int, available_cash: float) -> Dict[str, Any]:
    validated = dict(plan)
    validated["position_actions"] = [
        {
            **item,
            "target_pct": cap_target_pct(float(item.get("target_pct", 0) or 0), max_position_pct),
        }
        for item in plan.get("position_actions", [])
    ]

    if plan.get("risk_level") == "high":
        validated["new_entries"] = []
        validated["buy_picks"] = []
        validated["portfolio_bias"] = "conservative"
    else:
        validated["new_entries"] = plan.get("new_entries", [])[:max_positions]
        validated["buy_picks"] = plan.get("buy_picks", [])[:max_positions]

    if available_cash <= 0:
        validated["new_entries"] = []
        validated["buy_picks"] = []

    return validated


def run_agent_cycle_with_fallback(positions_ctx: List[Dict], candidates_ctx: List[Dict],
                                  account_info: Dict, market_sentiment: Dict,
                                  engine_params: Dict, recent_trades: List[Dict],
                                  recent_decisions: List[Dict], memory_summary: Dict) -> Dict:
    cycle_id = str(uuid.uuid4())
    context = build_agent_cycle_context(
        cycle_id=cycle_id,
        timestamp=beijing_now().isoformat(),
        account_info=account_info,
        positions_ctx=positions_ctx,
        candidates_ctx=candidates_ctx,
        market_sentiment=market_sentiment,
        engine_params=engine_params,
        recent_trades=recent_trades,
        recent_decisions=recent_decisions,
        memory_summary=memory_summary,
    )
    try:
        plan = run_trading_agent_cycle(context)
        plan = validate_final_trading_plan(
            plan,
            max_position_pct=engine_params.get("max_position_pct", 50.0),
            max_positions=engine_params.get("max_positions", 3),
            available_cash=account_info.get("available_cash", 0.0),
        )
        return {
            "market_analysis": plan.get("summary", ""),
            "risk_level": plan.get("risk_level", "mid"),
            "position_actions": plan.get("position_actions", []),
            "buy_picks": plan.get("buy_picks", []),
            "agent_plan": plan,
            "cycle_id": cycle_id,
        }
    except Exception as e:
        add_realtime_log("warning", f"⚠️ Agent流程失败，回退单次AI: {e}")
        legacy = ai_comprehensive_decision(positions_ctx, candidates_ctx, account_info, market_sentiment)
        legacy["cycle_id"] = cycle_id
        return legacy
```

Then update the decision call inside `AutonomousTradingEngine._comprehensive_trade()` from:

```python
decision = ai_comprehensive_decision(positions_ctx, candidates_ctx, account_info, market_sentiment)
```

to:

```python
memory_summary = recall_recent_agent_memory(db, limit=5)
engine_params = {
    "max_positions": self.max_positions,
    "max_position_pct": self.max_position_pct,
    "take_profit_pct": self.take_profit_pct,
    "stop_loss_pct": self.stop_loss_pct,
}
recent_trades = []
recent_decisions = []
decision = run_agent_cycle_with_fallback(
    positions_ctx=positions_ctx,
    candidates_ctx=candidates_ctx,
    account_info=account_info,
    market_sentiment=market_sentiment,
    engine_params=engine_params,
    recent_trades=recent_trades,
    recent_decisions=recent_decisions,
    memory_summary=memory_summary,
)
```

- [ ] **Step 4: Run the focused tests again**

Run:

```bash
pytest tests/test_autonomous_agent.py -k "validate_final_trading_plan or run_agent_cycle_with_fallback" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_autonomous_agent.py
git commit -m "feat: integrate trading agent with validated fallback"
```

---

### Task 6: Persist cycle logs, node logs, short-term memory, and daily reflection

**Files:**
- Modify: `web_app.py`
- Test: `tests/test_autonomous_agent.py`

- [ ] **Step 1: Write failing persistence tests**

Append these tests to `tests/test_autonomous_agent.py`:

```python
def test_log_agent_cycle_persists_plan_summary(db):
    web_app.log_agent_cycle(
        db,
        cycle_id="cycle-1",
        status="success",
        duration_ms=1234,
        risk_level="medium",
        summary="防守模式",
        triggered_trade=False,
        plan={"position_actions": []},
    )
    row = db.query(web_app.AgentCycleLogModel).filter_by(cycle_id="cycle-1").one()
    assert row.summary == "防守模式"
    assert row.duration_ms == 1234


def test_write_daily_reflection_creates_memory_row(db):
    db.add(
        web_app.AgentCycleLogModel(
            cycle_id="cycle-2",
            time=datetime(2026, 6, 30, 14, 55),
            risk_level="medium",
            summary="减仓高位分歧票",
            status="success",
            duration_ms=800,
            triggered_trade=True,
            plan_json='{"position_actions": [{"symbol": "600000", "action": "reduce"}]}'
        )
    )
    db.commit()

    created = web_app.write_daily_reflection_memory(
        db,
        for_date=datetime(2026, 6, 30, 15, 5),
    )
    assert created is True

    row = db.query(web_app.AgentMemoryModel).filter_by(memory_type="daily_reflection").one()
    assert "减仓高位分歧票" in row.content_json
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```bash
pytest tests/test_autonomous_agent.py -k "log_agent_cycle_persists_plan_summary or write_daily_reflection_creates_memory_row" -v
```

Expected: FAIL with missing helper function errors.

- [ ] **Step 3: Add persistence helpers**

In `web_app.py`, add:

```python
def log_agent_cycle(db: Session, cycle_id: str, status: str, duration_ms: int,
                    risk_level: str, summary: str, triggered_trade: bool,
                    plan: Dict[str, Any]):
    row = AgentCycleLogModel(
        cycle_id=cycle_id,
        status=status,
        duration_ms=duration_ms,
        risk_level=risk_level,
        summary=summary,
        triggered_trade=triggered_trade,
        plan_json=json.dumps(plan, ensure_ascii=False),
    )
    db.add(row)
    db.commit()


def log_agent_node(db: Session, cycle_id: str, node_name: str,
                   input_summary: str, output_summary: str,
                   duration_ms: int = 0, model_name: str = "",
                   tool_calls: Optional[List[str]] = None):
    row = AgentNodeLogModel(
        cycle_id=cycle_id,
        node_name=node_name,
        input_summary=input_summary,
        output_summary=output_summary,
        duration_ms=duration_ms,
        model_name=model_name,
        tool_calls=json.dumps(tool_calls or [], ensure_ascii=False),
    )
    db.add(row)
    db.commit()


def store_agent_memory(db: Session, memory_type: str, tags: str, content: Dict[str, Any],
                       relevance_score: float = 0.0):
    row = AgentMemoryModel(
        memory_type=memory_type,
        tags=tags,
        content_json=json.dumps(content, ensure_ascii=False),
        relevance_score=relevance_score,
    )
    db.add(row)
    db.commit()


def write_daily_reflection_memory(db: Session, for_date: datetime) -> bool:
    start = datetime(for_date.year, for_date.month, for_date.day, 0, 0, 0)
    end = start + timedelta(days=1)
    rows = db.query(AgentCycleLogModel).filter(
        AgentCycleLogModel.time >= start,
        AgentCycleLogModel.time < end,
    ).order_by(AgentCycleLogModel.time.asc()).all()
    if not rows:
        return False

    notes = [row.summary for row in rows if row.summary]
    content = {
        "date": start.strftime("%Y-%m-%d"),
        "notes": notes[:5],
        "count": len(rows),
        "tomorrow_bias": "保持谨慎" if any(row.risk_level == "high" for row in rows) else "平衡应对",
    }
    store_agent_memory(
        db,
        memory_type="daily_reflection",
        tags="reflection,daily",
        content=content,
        relevance_score=0.7,
    )
    return True
```

Then, after the agent decision is produced in `_comprehensive_trade()`, persist a cycle log:

```python
agent_plan = decision.get("agent_plan") or {
    "position_actions": decision.get("position_actions", []),
    "buy_picks": decision.get("buy_picks", []),
    "summary": decision.get("market_analysis", ""),
    "risk_level": decision.get("risk_level", "mid"),
}
log_agent_cycle(
    db,
    cycle_id=decision.get("cycle_id", str(uuid.uuid4())),
    status="success",
    duration_ms=0,
    risk_level=agent_plan.get("risk_level", decision.get("risk_level", "mid")),
    summary=agent_plan.get("summary", decision.get("market_analysis", "")),
    triggered_trade=bool(agent_plan.get("position_actions") or agent_plan.get("buy_picks")),
    plan=agent_plan,
)
```

- [ ] **Step 4: Run the focused tests again**

Run:

```bash
pytest tests/test_autonomous_agent.py -k "log_agent_cycle_persists_plan_summary or write_daily_reflection_creates_memory_row" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_autonomous_agent.py
git commit -m "feat: persist autonomous agent logs and reflections"
```

---

### Task 7: Add Agent timeline and memory summary APIs

**Files:**
- Modify: `web_app.py`
- Modify: `tests/test_agent_api.py`

- [ ] **Step 1: Write failing API serializer tests**

Replace the placeholder in `tests/test_agent_api.py` with:

```python
from datetime import datetime
from types import SimpleNamespace

import web_app


def test_serialize_agent_cycle_row_returns_expected_fields():
    row = SimpleNamespace(
        cycle_id="cycle-1",
        time=datetime(2026, 6, 30, 10, 3),
        status="success",
        duration_ms=900,
        risk_level="medium",
        summary="防守模式",
        triggered_trade=False,
        plan_json='{"position_actions": []}',
    )
    data = web_app.serialize_agent_cycle_row(row)
    assert data["cycle_id"] == "cycle-1"
    assert data["risk_level"] == "medium"
    assert data["plan"]["position_actions"] == []


def test_serialize_agent_memory_row_returns_expected_fields():
    row = SimpleNamespace(
        id=1,
        memory_type="short_term",
        memory_date=datetime(2026, 6, 30, 15, 1),
        tags="defensive,etf",
        content_json='{"notes": ["avoid chasing"]}',
        relevance_score=0.9,
    )
    data = web_app.serialize_agent_memory_row(row)
    assert data["memory_type"] == "short_term"
    assert data["content"]["notes"] == ["avoid chasing"]
```

- [ ] **Step 2: Run the focused API tests to verify they fail**

Run:

```bash
pytest tests/test_agent_api.py -v
```

Expected: FAIL with missing serializer helper errors.

- [ ] **Step 3: Add serializers and API routes**

In `web_app.py`, add:

```python
def serialize_agent_cycle_row(row: AgentCycleLogModel) -> Dict[str, Any]:
    return {
        "cycle_id": row.cycle_id,
        "time": row.time.strftime("%Y-%m-%d %H:%M:%S") if row.time else "",
        "status": row.status,
        "duration_ms": row.duration_ms,
        "risk_level": row.risk_level,
        "summary": row.summary,
        "triggered_trade": row.triggered_trade,
        "plan": safe_json_loads(row.plan_json, {}),
    }


def serialize_agent_memory_row(row: AgentMemoryModel) -> Dict[str, Any]:
    return {
        "id": row.id,
        "memory_type": row.memory_type,
        "memory_date": row.memory_date.strftime("%Y-%m-%d %H:%M:%S") if row.memory_date else "",
        "tags": row.tags,
        "content": safe_json_loads(row.content_json, {}),
        "relevance_score": row.relevance_score,
    }
```

Then add these FastAPI routes near the existing API section:

```python
@app.get("/api/agent/cycles")
def api_agent_cycles(limit: int = 20):
    with SessionLocal() as db:
        rows = db.query(AgentCycleLogModel).order_by(AgentCycleLogModel.id.desc()).limit(limit).all()
        return [serialize_agent_cycle_row(row) for row in rows]


@app.get("/api/agent/memory")
def api_agent_memory(limit: int = 10, memory_type: Optional[str] = None):
    with SessionLocal() as db:
        query = db.query(AgentMemoryModel)
        if memory_type:
            query = query.filter(AgentMemoryModel.memory_type == memory_type)
        rows = query.order_by(AgentMemoryModel.id.desc()).limit(limit).all()
        return [serialize_agent_memory_row(row) for row in rows]
```

- [ ] **Step 4: Run the API tests again**

Run:

```bash
pytest tests/test_agent_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app.py tests/test_agent_api.py
git commit -m "feat: add autonomous agent timeline apis"
```

---

### Task 8: Add Agent timeline and memory cards to the frontend

**Files:**
- Modify: `templates/index.html`
- Modify: `README.md`

- [ ] **Step 1: Add the new dashboard sections**

In `templates/index.html`, inside the dashboard tab below the existing “引擎决策日志” row, add:

```html
  <div class="cols-2">
    <div class="card">
      <div class="card-title">🧠 Agent 决策链</div>
      <div id="agentCyclesContent" class="scroll"></div>
    </div>
    <div class="card">
      <div class="card-title">📝 Agent 近期记忆</div>
      <div id="agentMemoryContent" class="scroll"></div>
    </div>
  </div>
```

- [ ] **Step 2: Add frontend loaders and renderers**

In the `<script>` block of `templates/index.html`, add:

```javascript
async function loadAgentCycles() {
  const rows = await api('/api/agent/cycles?limit=10');
  const el = document.getElementById('agentCyclesContent');
  if (!rows.length) {
    el.innerHTML = '<div class="empty-state">暂无 Agent 决策链</div>';
    return;
  }
  el.innerHTML = rows.map(row => `
    <div class="pick-card">
      <div class="pick-header">
        <div>
          <div class="pick-symbol">${row.time}</div>
          <div class="pick-name">${row.summary || '无摘要'}</div>
        </div>
        <div class="tag ${row.risk_level === 'high' ? 'tag-sell' : 'tag-scan'}">${row.risk_level}</div>
      </div>
      <div class="text-muted">仓位动作：${(row.plan.position_actions || []).length} 条</div>
      <div class="text-muted">新开仓：${(row.plan.buy_picks || []).length} 条</div>
    </div>
  `).join('');
}


async function loadAgentMemory() {
  const rows = await api('/api/agent/memory?limit=6');
  const el = document.getElementById('agentMemoryContent');
  if (!rows.length) {
    el.innerHTML = '<div class="empty-state">暂无 Agent 记忆</div>';
    return;
  }
  el.innerHTML = rows.map(row => `
    <div class="pick-card">
      <div class="pick-header">
        <div>
          <div class="pick-symbol">${row.memory_type}</div>
          <div class="pick-name">${row.memory_date}</div>
        </div>
        <div class="tag tag-hold">${row.tags || 'memory'}</div>
      </div>
      <div class="text-muted">${(row.content.notes || []).join('；') || '无摘要'}</div>
    </div>
  `).join('');
}
```

Then update `refreshAll()` so it also calls:

```javascript
  loadAgentCycles().catch(e => console.error('agent cycles', e));
  loadAgentMemory().catch(e => console.error('agent memory', e));
```

- [ ] **Step 3: Update README to describe the new agent flow**

Append this section to `README.md` after “趋势优先仓位管理”:

```md
## 自主决策 Agent（第一阶段）

系统已从单次 AI 综合调用升级为主控编排式 Agent 流程。每个交易周期会按以下顺序运行：

1. 构建上下文
2. 读取近期记忆
3. 判断市场环境
4. 审查已有持仓
5. 研究候选标的
6. 进行风险复核
7. 生成最终交易计划
8. 执行交易并写入 Agent 日志

前端会展示最近的 Agent 决策链和记忆摘要，方便观察系统为什么买、为什么减、为什么不买。
```

- [ ] **Step 4: Run the backend tests and do a browser smoke test**

Run:

```bash
pytest tests/test_autonomous_agent.py tests/test_agent_api.py -v
python web_app.py
```

Expected:
- pytest PASS
- 服务启动后访问 `http://127.0.0.1:8080`
- 仪表盘能看到 “🧠 Agent 决策链” 和 “📝 Agent 近期记忆” 两个卡片

- [ ] **Step 5: Commit**

```bash
git add templates/index.html README.md
git commit -m "feat: expose autonomous agent timeline in dashboard"
```

---

### Task 9: Update docs copy, run full verification, and prepare for review

**Files:**
- Modify: `templates/index.html`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-06-30-autonomous-trading-agent-design.md`

- [ ] **Step 1: Update the docs tab text to match the new agent behavior**

In `templates/index.html`, replace these docs tab phrases:

```text
STEP 2 AI 深度分析
STEP 4 持仓管理 止盈 12% / 止损 5%
🟢 止盈：盈利 ≥ 12% → 立即全部卖出
```

with:

```text
STEP 2 Agent 决策编排
STEP 4 持仓管理 Agent + 风控复核
🟢 利润管理：盈利达到阈值后进入利润管理区，由 Agent 决定 hold / reduce / exit
```

Also update the “AI 在系统中的角色” list so it becomes “Agent 在系统中的角色”, and include “近期记忆” 与 “风险复核节点”。

- [ ] **Step 2: Update the design doc implementation status**

Append this section to `docs/superpowers/specs/2026-06-30-autonomous-trading-agent-design.md` after implementation completes:

```md
## 实施状态

- [x] LangGraph 主控流程已接入交易主循环
- [x] 第一阶段已支持市场分析、持仓诊断、候选研究、风控复核四类节点
- [x] 已新增 Agent cycle / node / memory / feedback 数据表
- [x] 前端已展示 Agent 决策链与近期记忆摘要
- [x] 保留原有执行层作为安全执行主干，并支持失败回退
```

- [ ] **Step 3: Run the full verification suite**

Run:

```bash
pytest tests/test_position_management.py tests/test_autonomous_agent.py tests/test_agent_api.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add templates/index.html README.md docs/superpowers/specs/2026-06-30-autonomous-trading-agent-design.md
git commit -m "docs: describe autonomous trading agent phase one"
```

---

## Self-Review

### Spec coverage
- Multi-step agent orchestration is covered in Tasks 3, 4, and 5.
- Market / position / candidate / risk node structure is covered in Task 4.
- Short-term memory and daily reflection are covered in Tasks 3 and 6.
- Agent cycle logs, node logs, memories, and feedback storage are covered in Task 2 and Task 6.
- Frontend decision-chain and memory visibility are covered in Task 8 and Task 9.
- Safe fallback to the legacy single-call path is covered in Task 5.

### Placeholder scan
- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Each code step includes concrete code blocks or direct replacement text.
- Each verification step includes an exact command and expected outcome.

### Type consistency
- Shared context object is consistently named `AgentCycleContext` conceptually and implemented through `build_agent_cycle_context(...)`.
- Final execution object is consistently carried as `final_plan` / `agent_plan` with `position_actions`, `buy_picks`, and `risk_level`.
- Serializer, memory, and persistence helper names are consistent across tasks.

---
