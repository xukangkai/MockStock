import json
import uuid
from datetime import date, datetime

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


def test_placeholder_agent_harness(sample_context):
    assert sample_context["account"]["available_cash"] == 6200


def test_agent_tables_are_created(db):
    inspector = inspect(db.bind)
    tables = set(inspector.get_table_names())
    assert "agent_cycle_logs" in tables
    assert "agent_node_logs" in tables
    assert "agent_memories" in tables
    assert "agent_feedback" in tables


def test_agent_tables_use_explicit_autoincrement_ids():
    for model in (
        web_app.AgentCycleLogModel,
        web_app.AgentNodeLogModel,
        web_app.AgentMemoryModel,
        web_app.AgentFeedbackModel,
    ):
        assert model.__table__.c.id.autoincrement is True


def test_agent_memory_model_round_trips_json_content(db):
    payload = {"notes": ["avoid chasing", "wait for pullback"]}
    row = web_app.AgentMemoryModel(
        memory_type="short_term",
        memory_date=datetime(2026, 6, 30, 15, 1),
        tags="defensive,bank",
        content_json=json.dumps(payload, ensure_ascii=False),
        relevance_score=0.8,
    )
    db.add(row)
    db.commit()

    saved = db.query(web_app.AgentMemoryModel).one()
    assert saved.memory_type == "short_term"
    assert json.loads(saved.content_json) == payload
    assert json.loads(saved.content_json)["notes"] == ["avoid chasing", "wait for pullback"]


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
        "ma10": None,
        "ma20": None,
        "trend": None,
        "pe": 18.2,
        "pb": 1.4,
        "net_profit_yoy": 12.5,
        "revenue_yoy": 6.8,
        "is_etf": False,
        "recent_high": 7.95,
        "recent_low": 7.42,
        "rsi6": None,
        "rsi14": None,
        "kdj_k": None,
        "kdj_d": None,
        "kdj_j": None,
        "boll_upper": None,
        "boll_mid": None,
        "boll_lower": None,
        "momentum_5d": None,
        "momentum_10d": None,
        "macd_dif": None,
        "macd_dea": None,
        "macd_hist": None,
        "vol_ratio": None,
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
            "pct": i * 0.04,
            "amount": 1_000_000_000 - i,
            "extra_noise": f"raw-only-{i}",
        }
        for i in range(120)
    ]

    monkeypatch.setattr(web_app, "fetch_all_stocks", lambda: all_stocks)
    monkeypatch.setattr(
        web_app,
        "fetch_financial_batch",
        lambda: {"600000": {"net_profit_yoy": 15.2, "revenue_yoy": 8.4, "eps": 0.91}},
    )
    monkeypatch.setattr(
        web_app,
        "fetch_history",
        lambda symbol, days=20: [
            {"close": 9.8, "high": 10.4, "low": 9.5},
            {"close": 10.0, "high": 10.6, "low": 9.7},
            {"close": 10.2, "high": 10.8, "low": 9.9},
            {"close": 10.4, "high": 11.0, "low": 10.1},
            {"close": 10.6, "high": 11.2, "low": 10.3},
        ]
        if symbol == "600000"
        else None,
    )
    monkeypatch.setattr(web_app, "calculate_indicators", lambda hist: {"ma5": 10.2})
    monkeypatch.setattr(web_app, "fetch_valuation", lambda symbol: {"pe": 11.8, "pb": 1.6, "total_mv": 888000} if symbol == "600000" else None)
    monkeypatch.setattr(web_app, "calculate_market_sentiment", lambda stocks: {"sentiment": "neutral", "score": 50})
    monkeypatch.setattr(web_app, "recall_recent_agent_memory", lambda db, limit=5: {"items": [], "notes": []})
    # mock 新增的真实联网调用，避免测试触发 akshare 网络请求而挂起
    monkeypatch.setattr(
        web_app,
        "fetch_market_indices",
        lambda: {"上证指数": {"name": "上证指数", "price": 3200.0, "pct": 1.23}},
    )
    monkeypatch.setattr(web_app, "fetch_market_news", lambda: [])

    def fake_run_agent_cycle_with_fallback(db_session, context):
        first_candidate = context["candidates"][0]
        captured["candidate_count"] = len(context["candidates"])
        captured["first_symbol"] = first_candidate["symbol"]
        captured["last_symbol"] = context["candidates"][-1]["symbol"]
        captured["first_candidate"] = first_candidate
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

    assert captured["candidate_count"] == 120
    assert captured["first_symbol"] == "600000"
    assert captured["last_symbol"] == "600119"
    assert captured["first_candidate"] == {
        "symbol": "600000",
        "name": "样本0",
        "price": 10.0,
        "pct": 0.0,
        "amount": 1_000_000_000.0,
        "ma5": 10.2,
        "ma10": None,
        "ma20": None,
        "trend": None,
        "pe": 11.8,
        "pb": 1.6,
        "net_profit_yoy": 15.2,
        "revenue_yoy": 8.4,
        "is_etf": False,
        "recent_high": 11.2,
        "recent_low": 9.5,
        "rsi6": None,
        "rsi14": None,
        "kdj_k": None,
        "kdj_d": None,
        "kdj_j": None,
        "boll_upper": None,
        "boll_mid": None,
        "boll_lower": None,
        "momentum_5d": None,
        "momentum_10d": None,
        "macd_dif": None,
        "macd_dea": None,
        "macd_hist": None,
        "vol_ratio": None,
    }
    assert "extra_noise" not in captured["first_candidate"]
    assert "total_mv" not in captured["first_candidate"]
    assert "eps" not in captured["first_candidate"]


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
    assert "成交额前100只活跃股候选摘要，本轮输入 1 只" in captured["prompt"]


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


@pytest.mark.parametrize("content_json", ['["not", "a", "dict"]', '"freeform"', "123", "null"])
def test_recall_recent_agent_memory_coerces_non_dict_payloads(content_json, db):
    db.add(
        web_app.AgentMemoryModel(
            memory_type="short_term",
            memory_date=datetime(2026, 6, 30, 15, 5),
            tags="edge-case",
            content_json=content_json,
            relevance_score=0.4,
        )
    )
    db.commit()

    summary = web_app.recall_recent_agent_memory(db, limit=1)

    assert summary["items"][0]["content"] == {}
    assert summary["notes"] == []


def test_recall_recent_agent_memory_handles_malformed_json_and_aggregates_notes(db):
    db.add_all(
        [
            web_app.AgentMemoryModel(
                memory_type="short_term",
                memory_date=datetime(2026, 6, 30, 15, 3),
                tags="latest",
                content_json='{"notes": ["latest-a", "latest-b"]}',
                relevance_score=0.9,
            ),
            web_app.AgentMemoryModel(
                memory_type="short_term",
                memory_date=datetime(2026, 6, 30, 15, 2),
                tags="bad-json",
                content_json='{"notes": ["missing bracket"}',
                relevance_score=0.2,
            ),
            web_app.AgentMemoryModel(
                memory_type="short_term",
                memory_date=datetime(2026, 6, 30, 15, 1),
                tags="older",
                content_json='{"notes": ["older-a", "older-b", "older-c", "older-d"]}',
                relevance_score=0.7,
            ),
        ]
    )
    db.commit()

    summary = web_app.recall_recent_agent_memory(db, limit=3)

    assert [item["tags"] for item in summary["items"]] == ["latest", "bad-json", "older"]
    assert summary["items"][1]["content"] == {}
    assert summary["notes"] == ["latest-a", "latest-b", "older-a", "older-b", "older-c"]


def test_run_trading_agent_cycle_returns_valid_plan(sample_context, monkeypatch):
    # Mock _make_tracked_node to pass through raw functions (no status tracking in tests)
    monkeypatch.setattr(web_app, "_make_tracked_node", lambda name, fn: fn)
    # Mock ai_call to return predictable JSON for each sub-agent
    call_count = [0]
    ai_responses = [
        # market analyst
        json.dumps({"regime": "defensive", "risk_bias": "conservative",
                    "reasoning": "防守优先", "sector_focus": ["ETF"], "warnings": ["高位分歧扩大"]}),
        # position review
        json.dumps({"assessments": [{"symbol": "600000", "action": "hold", "target_pct": 18,
                    "confidence": 72, "thesis": "趋势未破", "risks": [], "supports": ["量能稳定"]}]}),
        # candidate research
        json.dumps({"assessments": [], "reasoning": "无合适候选"}),
        # risk review
        json.dumps({"overall_pass": True, "risk_level": "medium", "blocked_actions": [],
                    "adjustments": [], "notes": ["保留现金"], "reasoning": "风控通过"}),
        # synthesizer
        json.dumps({"market_analysis": "防守模式", "risk_level": "medium", "portfolio_bias": "balanced",
                    "cash_reserve_target": 0.35, "confidence": 0.74, "summary": "防守模式，继续持有",
                    "position_actions": [{"symbol": "600000", "action": "hold", "target_pct": 18}],
                    "buy_picks": [], "reasoning": ["防守优先"]}),
    ]
    def mock_ai_call(messages, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        return ai_responses[idx] if idx < len(ai_responses) else "{}"
    monkeypatch.setattr(web_app, "ai_call", mock_ai_call)

    plan = web_app.run_trading_agent_cycle(sample_context)
    assert plan["portfolio_bias"] == "balanced"
    assert plan["position_actions"][0]["action"] == "hold"
    assert plan["risk_level"] == "medium"


def test_run_market_analysis_node_bullish(monkeypatch, sample_context):
    sample_context["market_snapshot"]["score"] = 75
    monkeypatch.setattr(web_app, "ai_call", lambda msgs, **kw: json.dumps({
        "regime": "bullish", "risk_bias": "aggressive",
        "reasoning": "市场看涨", "sector_focus": [], "warnings": []
    }))
    state = {"context": sample_context}
    result = web_app.run_market_analysis_node(state)
    assessment = result["market_assessment"]
    assert assessment["regime"] == "bullish"
    assert assessment["risk_bias"] == "aggressive"


def test_run_market_analysis_node_defensive(monkeypatch, sample_context):
    sample_context["market_snapshot"]["score"] = 40
    monkeypatch.setattr(web_app, "ai_call", lambda msgs, **kw: json.dumps({
        "regime": "defensive", "risk_bias": "conservative",
        "reasoning": "市场防御", "sector_focus": [], "warnings": ["风险高"]
    }))
    state = {"context": sample_context}
    result = web_app.run_market_analysis_node(state)
    assessment = result["market_assessment"]
    assert assessment["regime"] == "defensive"
    assert assessment["risk_bias"] == "conservative"


def test_run_market_analysis_node_neutral(monkeypatch, sample_context):
    sample_context["market_snapshot"]["score"] = 55
    monkeypatch.setattr(web_app, "ai_call", lambda msgs, **kw: json.dumps({
        "regime": "neutral", "risk_bias": "balanced",
        "reasoning": "市场中性", "sector_focus": [], "warnings": []
    }))
    state = {"context": sample_context}
    result = web_app.run_market_analysis_node(state)
    assessment = result["market_assessment"]
    assert assessment["regime"] == "neutral"
    assert assessment["risk_bias"] == "balanced"


# ═════════════════════════════════════════════════════
#  validate_final_trading_plan tests
# ═════════════════════════════════════════════════════

def test_validate_final_trading_plan_valid_passes_through():
    plan = {
        "market_analysis": "市场震荡",
        "position_actions": [{"symbol": "600000", "action": "hold"}],
        "buy_picks": [{"symbol": "512880", "price": 1.25}],
        "reasoning": ["防守为主"],
    }
    result = web_app.validate_final_trading_plan(plan)
    assert result is plan
    assert result["market_analysis"] == "市场震荡"
    assert len(result["position_actions"]) == 1
    assert len(result["buy_picks"]) == 1
    assert result["reasoning"] == ["防守为主"]


def test_validate_final_trading_plan_missing_keys_get_defaults():
    plan = {}
    result = web_app.validate_final_trading_plan(plan)
    assert result["market_analysis"] == ""
    assert result["position_actions"] == []
    assert result["buy_picks"] == []
    assert result["reasoning"] == []


def test_validate_final_trading_plan_non_dict_returns_safe_empty():
    for bad_input in [None, "string", 42, [1, 2, 3]]:
        result = web_app.validate_final_trading_plan(bad_input)
        assert result == {"market_analysis": "", "position_actions": [], "buy_picks": [], "reasoning": []}


def test_validate_final_trading_plan_non_list_position_actions_coerced():
    plan = {"position_actions": "not a list", "buy_picks": None, "reasoning": 99}
    result = web_app.validate_final_trading_plan(plan)
    assert result["position_actions"] == []
    assert result["buy_picks"] == []
    assert result["reasoning"] == []


def test_validate_final_trading_plan_filters_non_dict_items_in_lists():
    plan = {
        "position_actions": [{"symbol": "600000", "action": "hold"}, "bad", 42, None],
        "buy_picks": [{"symbol": "512880"}, "invalid", 3.14],
    }
    result = web_app.validate_final_trading_plan(plan)
    assert len(result["position_actions"]) == 1
    assert result["position_actions"][0]["symbol"] == "600000"
    assert len(result["buy_picks"]) == 1
    assert result["buy_picks"][0]["symbol"] == "512880"


def test_validate_final_trading_plan_extra_keys_preserved():
    plan = {
        "market_analysis": "bull",
        "position_actions": [],
        "buy_picks": [],
        "reasoning": [],
        "confidence": 0.8,
        "risk_level": "low",
        "summary": "看多",
    }
    result = web_app.validate_final_trading_plan(plan)
    assert result["confidence"] == 0.8
    assert result["risk_level"] == "low"
    assert result["summary"] == "看多"


# ═════════════════════════════════════════════════════
#  run_agent_cycle_with_fallback tests
# ═════════════════════════════════════════════════════

def test_run_agent_cycle_with_fallback_success_path(monkeypatch, db, sample_context):
    expected_plan = {
        "market_analysis": "Agent 分析完毕",
        "position_actions": [{"symbol": "600000", "action": "hold", "target_pct": 15}],
        "buy_picks": [],
        "reasoning": ["防守模式"],
        "risk_level": "medium",
        "confidence": 0.7,
    }
    monkeypatch.setattr(web_app, "run_trading_agent_cycle", lambda ctx: expected_plan)
    monkeypatch.setattr(web_app, "log_agent_cycle", lambda *a, **kw: None)
    monkeypatch.setattr(web_app, "store_agent_memory", lambda *a, **kw: None)

    result = web_app.run_agent_cycle_with_fallback(db, sample_context)
    assert result["market_analysis"] == "Agent 分析完毕"
    assert result["position_actions"][0]["action"] == "hold"
    assert result["risk_level"] == "medium"


def test_run_agent_cycle_with_fallback_falls_back_on_agent_exception(monkeypatch, db, sample_context):
    monkeypatch.setattr(web_app, "run_trading_agent_cycle", lambda ctx: (_ for _ in ()).throw(RuntimeError("agent boom")))
    legacy_plan = {
        "market_analysis": "传统AI分析",
        "position_actions": [{"symbol": "600000", "action": "reduce", "target_pct": 10}],
        "buy_picks": [],
        "reasoning": ["回退决策"],
    }
    monkeypatch.setattr(web_app, "ai_comprehensive_decision", lambda *a, **kw: legacy_plan)

    result = web_app.run_agent_cycle_with_fallback(db, sample_context)
    assert result["market_analysis"] == "传统AI分析"
    assert result["position_actions"][0]["action"] == "reduce"


def test_run_agent_cycle_with_fallback_passes_correct_args_to_legacy(monkeypatch, db, sample_context):
    """Verify that the fallback extracts the right context keys for the legacy function."""
    captured = {}

    def fake_agent_cycle(ctx):
        raise ValueError("fail")

    def fake_legacy(positions, candidates, account, market):
        captured["positions"] = positions
        captured["candidates"] = candidates
        captured["account"] = account
        captured["market"] = market
        return {"market_analysis": "ok", "position_actions": [], "buy_picks": [], "reasoning": []}

    monkeypatch.setattr(web_app, "run_trading_agent_cycle", fake_agent_cycle)
    monkeypatch.setattr(web_app, "ai_comprehensive_decision", fake_legacy)

    result = web_app.run_agent_cycle_with_fallback(db, sample_context)
    assert captured["account"]["available_cash"] == 6200
    assert captured["positions"][0]["symbol"] == "600000"
    assert captured["market"]["sentiment"] == "neutral"


# ═════════════════════════════════════════════════════
#  Cycle log & memory persistence tests (Task 6)
# ═════════════════════════════════════════════════════

def test_log_agent_cycle_persists_to_db(db):
    cycle_id = str(uuid.uuid4())
    context = {"account": {"available_cash": 5000}, "market_snapshot": {"sentiment": "neutral"}}
    plan = {
        "position_actions": [{"symbol": "600000", "action": "hold"}],
        "buy_picks": [],
        "reasoning": ["防守"],
        "risk_level": "medium",
        "summary": "继续持有",
    }
    web_app.log_agent_cycle(db, cycle_id, context, plan)
    db.commit()

    saved = db.query(web_app.AgentCycleLogModel).filter_by(cycle_id=cycle_id).one()
    assert saved.status == "success"
    assert saved.risk_level == "medium"
    assert saved.summary == "继续持有"
    assert saved.triggered_trade is True
    parsed = json.loads(saved.plan_json)
    assert parsed["position_actions"][0]["symbol"] == "600000"


def test_log_agent_node_persists_to_db(db):
    cycle_id = str(uuid.uuid4())
    state = {
        "context": {"cycle_id": cycle_id},
        "market_assessment": {"regime": "bullish"},
        "memory_summary": {"notes": ["skip"]},
    }
    web_app.log_agent_node(db, cycle_id, "analyze_market", state)
    db.commit()

    saved = db.query(web_app.AgentNodeLogModel).filter_by(cycle_id=cycle_id, node_name="analyze_market").one()
    assert saved.node_name == "analyze_market"
    # input_summary should NOT contain memory_summary
    input_data = json.loads(saved.input_summary)
    assert "memory_summary" not in input_data
    # output_summary should NOT contain context or memory_summary
    output_data = json.loads(saved.output_summary)
    assert "context" not in output_data
    assert "memory_summary" not in output_data
    assert "market_assessment" in output_data


def test_store_agent_memory_persists_to_db(db):
    ref_date = datetime(2026, 6, 30, 15, 0)
    content = {"lesson": "避免追高", "confidence": 0.9}
    web_app.store_agent_memory(db, "short_term", ref_date, "追高教训", content, source="agent_review")
    db.commit()

    saved = db.query(web_app.AgentMemoryModel).filter_by(memory_type="short_term").one()
    assert saved.tags == "agent_review:追高教训"
    parsed = json.loads(saved.content_json)
    assert parsed["lesson"] == "避免追高"
    assert parsed["confidence"] == 0.9


def test_write_daily_reflection_memory_creates_note(db):
    # Insert a fake cycle log for today
    cycle = web_app.AgentCycleLogModel(
        cycle_id=str(uuid.uuid4()),
        status="success",
        risk_level="medium",
        summary="hold 600000",
        triggered_trade=True,
        plan_json=json.dumps({
            "position_actions": [{"symbol": "600000", "action": "hold"}],
            "buy_picks": [{"symbol": "512880"}],
        }, ensure_ascii=False),
    )
    db.add(cycle)
    db.commit()

    web_app.write_daily_reflection_memory(db)
    db.commit()

    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    reflection = db.query(web_app.AgentMemoryModel).filter(
        web_app.AgentMemoryModel.memory_type == "reflection",
        web_app.AgentMemoryModel.memory_date >= today_start,
        web_app.AgentMemoryModel.memory_date <= today_end,
    ).one()
    assert "日终总结" in reflection.tags
    parsed = json.loads(reflection.content_json)
    assert parsed["cycle_count"] == 1
    assert any("600000" in a for a in parsed["actions"])
    assert any("512880" in a for a in parsed["actions"])


def test_write_daily_reflection_memory_skips_if_exists(db):
    # Pre-create a reflection for today
    today_start = datetime.combine(date.today(), datetime.min.time())
    db.add(web_app.AgentMemoryModel(
        memory_type="reflection",
        memory_date=today_start,
        tags="existing",
        content_json='{"cycle_count": 0}',
    ))
    db.commit()

    # Also add a cycle so it would normally create one
    db.add(web_app.AgentCycleLogModel(
        cycle_id=str(uuid.uuid4()),
        plan_json='{"position_actions": []}',
    ))
    db.commit()

    # Should not create a duplicate
    web_app.write_daily_reflection_memory(db)
    db.commit()

    today_end = datetime.combine(date.today(), datetime.max.time())
    reflections = db.query(web_app.AgentMemoryModel).filter(
        web_app.AgentMemoryModel.memory_type == "reflection",
        web_app.AgentMemoryModel.memory_date >= today_start,
        web_app.AgentMemoryModel.memory_date <= today_end,
    ).all()
    assert len(reflections) == 1
    assert reflections[0].tags == "existing"
