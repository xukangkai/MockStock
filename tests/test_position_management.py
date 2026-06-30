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
