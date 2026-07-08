import json
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import web_app
from web_app import (
    AgentCycleLogModel,
    AgentMemoryModel,
    AgentNodeLogModel,
    Base,
)


@pytest.fixture(autouse=True)
def _patch_db(tmp_path, monkeypatch):
    """Use a temporary SQLite database for every test."""
    db_file = tmp_path / "test_agent_api.db"
    url = f"sqlite:///{db_file}"
    engine = create_engine(url, echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    monkeypatch.setattr(web_app, "engine", engine, raising=False)
    monkeypatch.setattr(web_app, "SessionLocal", TestingSessionLocal, raising=False)
    yield
    engine.dispose()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    return TestClient(web_app.app)


# ── /api/agent/cycles ───────────────────────────────────────────

def test_agent_cycles_empty(client):
    """Agent cycles endpoint returns empty list when no data."""
    resp = client.get("/api/agent/cycles")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert resp.json() == []


def test_agent_cycles_with_data(client):
    """Agent cycles endpoint returns cycle with nodes."""
    cycle_id = "test-cycle-001"
    with web_app.SessionLocal() as db:
        cycle = AgentCycleLogModel(
            cycle_id=cycle_id,
            status="ok",
            risk_level="mid",
            summary="test cycle",
            plan_json=json.dumps({
                "reasoning": ["test reason"],
                "position_actions": [],
                "buy_picks": [],
            }),
        )
        db.add(cycle)
        node = AgentNodeLogModel(
            cycle_id=cycle_id,
            node_name="analyze_market",
            input_summary="test input",
            output_summary="test output",
        )
        db.add(node)
        db.commit()

    resp = client.get("/api/agent/cycles")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    found = [c for c in data if c["cycle_id"] == cycle_id]
    assert len(found) == 1
    assert found[0]["risk_level"] == "mid"
    assert found[0]["summary"] == "test cycle"
    assert found[0]["reasoning"] == ["test reason"]
    assert found[0]["nodes"][0]["node_name"] == "analyze_market"


def test_agent_cycles_limit(client):
    """Agent cycles endpoint respects limit parameter."""
    with web_app.SessionLocal() as db:
        for i in range(5):
            db.add(AgentCycleLogModel(
                cycle_id=f"cycle-limit-{i}",
                status="ok",
                risk_level="low",
                summary=f"cycle {i}",
            ))
        db.commit()

    resp = client.get("/api/agent/cycles?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


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


# ── /api/agent/memory ───────────────────────────────────────────

def test_agent_memory_empty(client):
    """Agent memory endpoint returns empty list when no data."""
    resp = client.get("/api/agent/memory")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert resp.json() == []


def test_agent_memory_filter_by_scope(client):
    """Agent memory endpoint can filter by scope/type."""
    with web_app.SessionLocal() as db:
        db.add(AgentMemoryModel(
            memory_type="reflection",
            memory_date=date.today(),
            tags="test:tag",
            content_json=json.dumps({"test": True}),
        ))
        db.add(AgentMemoryModel(
            memory_type="lesson",
            memory_date=date.today(),
            tags="other:tag",
            content_json=json.dumps({"lesson": "buy low"}),
        ))
        db.commit()

    resp = client.get("/api/agent/memory", params={"scope": "reflection"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(m["memory_type"] == "reflection" for m in data)
    assert any(m.get("content", {}).get("test") is True for m in data)


def test_agent_memory_all_types(client):
    """Agent memory endpoint returns all types when no scope filter."""
    with web_app.SessionLocal() as db:
        db.add(AgentMemoryModel(
            memory_type="reflection",
            memory_date=date.today(),
            tags="t:1",
            content_json=json.dumps({"a": 1}),
        ))
        db.add(AgentMemoryModel(
            memory_type="lesson",
            memory_date=date.today(),
            tags="t:2",
            content_json=json.dumps({"b": 2}),
        ))
        db.commit()

    resp = client.get("/api/agent/memory")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    types = {m["memory_type"] for m in data}
    assert "reflection" in types
    assert "lesson" in types


def test_agent_memory_limit(client):
    """Agent memory endpoint respects limit parameter."""
    with web_app.SessionLocal() as db:
        for i in range(5):
            db.add(AgentMemoryModel(
                memory_type="reflection",
                memory_date=date.today(),
                tags=f"tag:{i}",
                content_json=json.dumps({"i": i}),
            ))
        db.commit()

    resp = client.get("/api/agent/memory", params={"limit": 3})
    assert resp.status_code == 200
    assert len(resp.json()) == 3
