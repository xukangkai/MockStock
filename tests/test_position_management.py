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


def test_normalize_position_action_defaults_to_hold():
    action = web_app.normalize_position_action({"action": "weird"})
    assert action == "hold"


def test_normalize_position_action_accepts_known_actions():
    action = web_app.normalize_position_action({"action": "reduce"})
    assert action == "reduce"


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


def test_allow_reduce_rejects_inverted_target_pct():
    allowed = web_app.allow_reduce_action(current_pct=20.0, target_pct=30.0)
    assert allowed is False


def test_has_remaining_position_capacity_blocks_when_none_left():
    allowed = web_app.has_remaining_position_capacity(open_count=3, max_positions=3, remaining_capacity=0)
    assert allowed is False


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


def test_calc_trade_qty_for_reduce_uses_target_delta():
    qty = web_app.calc_trade_qty_from_delta(delta_amount=-1500, price=5.0)
    assert qty == 300


def test_calc_trade_qty_for_add_uses_target_delta():
    qty = web_app.calc_trade_qty_from_delta(delta_amount=1500, price=5.0)
    assert qty == 300


def test_calc_trade_qty_returns_zero_for_small_delta():
    qty = web_app.calc_trade_qty_from_delta(delta_amount=200, price=5.0)
    assert qty == 0


def test_cap_target_pct_respects_max_position_limit():
    capped = web_app.cap_target_pct(target_pct=65, max_position_pct=50)
    assert capped == 50


def test_cap_target_pct_keeps_lower_value():
    capped = web_app.cap_target_pct(target_pct=35, max_position_pct=50)
    assert capped == 35


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
