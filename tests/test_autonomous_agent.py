import json
import uuid
from datetime import datetime

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
