import importlib
from datetime import timedelta
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


def test_should_skip_buy_pick_allows_confidence_at_threshold():
    reason = web_app.should_skip_buy_pick(
        confidence=70.0,
        quote_pct=1.2,
        is_etf=False,
        now_time=web_app.dtime(10, 0),
        min_confidence=70.0,
        max_chase_pct=7.0,
        late_buy_cutoff=web_app.dtime(14, 30),
    )
    assert reason is None


def test_should_skip_buy_pick_rejects_confidence_below_threshold():
    reason = web_app.should_skip_buy_pick(
        confidence=69.0,
        quote_pct=1.2,
        is_etf=False,
        now_time=web_app.dtime(10, 0),
        min_confidence=70.0,
        max_chase_pct=7.0,
        late_buy_cutoff=web_app.dtime(14, 30),
    )
    assert reason == "买入信心不足: 69% < 70%"


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


def test_should_force_exit_triggers_at_stop_loss_boundary():
    assert web_app.should_force_exit(pnl_pct=-5.0, stop_loss_pct=5.0, trend_broken=False) is True


def test_comprehensive_trade_sells_hard_stop_before_agent(monkeypatch, db):
    acct = web_app.get_account(db)
    acct.cash = 0.0
    pos = web_app.PositionModel(
        symbol="000001",
        name="平安银行",
        qty=200,
        avg_cost=10.0,
        last_price=9.5,
        stop_loss=9.0,
    )
    lot = web_app.LotModel(
        symbol="000001",
        buy_date=web_app.beijing_now().date() - timedelta(days=1),
        qty=200,
        remaining=200,
        price=10.0,
    )
    db.add_all([pos, lot])
    db.commit()

    monkeypatch.setenv("FORCE_TRADING", "1")
    monkeypatch.setattr(web_app, "fetch_quote", lambda symbol: {"price": 9.5, "pct": -5.0, "amount": 1_000_000})
    monkeypatch.setattr(web_app, "fetch_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_app, "fetch_all_stocks", lambda: [])

    engine = web_app.AutonomousTradingEngine()
    engine._comprehensive_trade(db)

    assert db.query(web_app.PositionModel).filter_by(symbol="000001").first() is None
    trade = db.query(web_app.TradeModel).filter_by(symbol="000001", side="sell").one()
    assert trade.qty == 200
    assert trade.reason == "硬止损: -5.0% <= -5.0%"


def test_comprehensive_trade_logs_hard_stop_blocked_by_t_plus_one(monkeypatch, db):
    pos = web_app.PositionModel(
        symbol="000002",
        name="万科A",
        qty=100,
        avg_cost=10.0,
        last_price=9.5,
        stop_loss=9.0,
    )
    lot = web_app.LotModel(
        symbol="000002",
        buy_date=web_app.beijing_now().date(),
        qty=100,
        remaining=100,
        price=10.0,
    )
    db.add_all([pos, lot])
    db.commit()

    monkeypatch.setenv("FORCE_TRADING", "1")
    monkeypatch.setattr(web_app, "fetch_quote", lambda symbol: {"price": 9.5, "pct": -5.0, "amount": 1_000_000})
    monkeypatch.setattr(web_app, "fetch_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_app, "fetch_all_stocks", lambda: [])

    engine = web_app.AutonomousTradingEngine()
    engine._comprehensive_trade(db)

    assert db.query(web_app.PositionModel).filter_by(symbol="000002").first() is not None
    decision = db.query(web_app.DecisionLogModel).filter_by(symbol="000002", action="skip").one()
    assert decision.reason == "硬止损待执行: T+1限制，当前盈亏-5.0%"


def test_comprehensive_trade_raises_stop_to_cost_after_profit_protection(monkeypatch, db):
    pos = web_app.PositionModel(
        symbol="000003",
        name="测试股票",
        qty=100,
        avg_cost=10.0,
        last_price=10.6,
        stop_loss=9.0,
    )
    lot = web_app.LotModel(
        symbol="000003",
        buy_date=web_app.beijing_now().date() - timedelta(days=1),
        qty=100,
        remaining=100,
        price=10.0,
    )
    db.add_all([pos, lot])
    db.commit()

    monkeypatch.setenv("FORCE_TRADING", "1")
    monkeypatch.setattr(web_app, "fetch_quote", lambda symbol: {"price": 10.6, "pct": 6.0, "amount": 1_000_000})
    monkeypatch.setattr(web_app, "fetch_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_app, "fetch_all_stocks", lambda: [])

    engine = web_app.AutonomousTradingEngine()
    engine._comprehensive_trade(db)

    updated = db.query(web_app.PositionModel).filter_by(symbol="000003").one()
    assert updated.stop_loss == 10.0
    decision = db.query(web_app.DecisionLogModel).filter_by(symbol="000003", action="hold").one()
    assert decision.reason == "盈利保护: 止损上移至成本线 ¥10.000"


def test_comprehensive_trade_blocks_agent_add_for_t_plus_one_hard_stop(monkeypatch, db):
    acct = web_app.get_account(db)
    acct.cash = 10000.0
    pos = web_app.PositionModel(
        symbol="000004",
        name="测试风控股",
        qty=100,
        avg_cost=10.0,
        last_price=9.5,
        stop_loss=9.0,
    )
    lot = web_app.LotModel(
        symbol="000004",
        buy_date=web_app.beijing_now().date(),
        qty=100,
        remaining=100,
        price=10.0,
    )
    db.add_all([pos, lot])
    db.commit()

    monkeypatch.setenv("FORCE_TRADING", "1")
    monkeypatch.setattr(web_app, "fetch_quote", lambda symbol: {"price": 9.5, "pct": -5.0, "amount": 1_000_000})
    monkeypatch.setattr(web_app, "fetch_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_app, "fetch_all_stocks", lambda: [
        {"symbol": "000005", "name": "候选股", "price": 10.0, "pct": 1.0, "amount": 1_000_000}
    ])
    monkeypatch.setattr(web_app, "fetch_financial_batch", lambda: {})
    monkeypatch.setattr(web_app, "fetch_valuation", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_app, "run_agent_cycle_with_fallback", lambda _db, _context: {
        "market_analysis": "测试",
        "risk_level": "mid",
        "position_actions": [{
            "symbol": "000004",
            "action": "add",
            "target_pct": 30,
            "confidence": 90,
            "reason": "测试硬止损后不得加仓",
        }],
        "buy_picks": [],
        "candidate_debug": {"input_count": 1, "selected_count": 0},
    })

    engine = web_app.AutonomousTradingEngine()
    engine._comprehensive_trade(db)

    assert db.query(web_app.TradeModel).filter_by(symbol="000004", side="buy").count() == 0
    risk_skip = db.query(web_app.DecisionLogModel).filter(
        web_app.DecisionLogModel.symbol == "000004",
        web_app.DecisionLogModel.action == "skip",
        web_app.DecisionLogModel.reason.like("%禁止AI加仓%"),
    ).one()
    assert "硬止损待执行" in risk_skip.reason


def test_comprehensive_trade_raises_stop_to_cost_for_non_sellable_profit(monkeypatch, db):
    pos = web_app.PositionModel(
        symbol="000006",
        name="当日盈利股",
        qty=100,
        avg_cost=10.0,
        last_price=10.6,
        stop_loss=9.0,
    )
    lot = web_app.LotModel(
        symbol="000006",
        buy_date=web_app.beijing_now().date(),
        qty=100,
        remaining=100,
        price=10.0,
    )
    db.add_all([pos, lot])
    db.commit()

    monkeypatch.setenv("FORCE_TRADING", "1")
    monkeypatch.setattr(web_app, "fetch_quote", lambda symbol: {"price": 10.6, "pct": 6.0, "amount": 1_000_000})
    monkeypatch.setattr(web_app, "fetch_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_app, "fetch_all_stocks", lambda: [])

    engine = web_app.AutonomousTradingEngine()
    engine._comprehensive_trade(db)

    updated = db.query(web_app.PositionModel).filter_by(symbol="000006").one()
    assert updated.stop_loss == 10.0
    decision = db.query(web_app.DecisionLogModel).filter_by(symbol="000006", action="hold").one()
    assert decision.reason == "盈利保护: 止损上移至成本线 ¥10.000"


def test_comprehensive_trade_skips_new_buy_when_confidence_missing(monkeypatch, db):
    acct = web_app.get_account(db)
    acct.cash = 10000.0
    db.commit()

    monkeypatch.setenv("FORCE_TRADING", "1")
    monkeypatch.setattr(web_app, "fetch_all_stocks", lambda: [
        {"symbol": "000001", "name": "平安银行", "price": 10.0, "pct": 1.0, "amount": 1_000_000}
    ])
    monkeypatch.setattr(web_app, "fetch_financial_batch", lambda: {})
    monkeypatch.setattr(web_app, "fetch_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_app, "fetch_valuation", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_app, "run_agent_cycle_with_fallback", lambda _db, _context: {
        "market_analysis": "测试",
        "risk_level": "mid",
        "position_actions": [],
        "buy_picks": [{
            "symbol": "000001",
            "name": "平安银行",
            "reason": "测试缺失信心",
            "entry_price": 10.0,
            "stop_loss": 9.5,
        }],
        "candidate_debug": {"input_count": 1, "selected_count": 1},
    })
    monkeypatch.setattr(web_app, "fetch_quote", lambda symbol: {"price": 10.0, "pct": 1.0, "amount": 1_000_000})

    engine = web_app.AutonomousTradingEngine()
    engine._comprehensive_trade(db)

    assert db.query(web_app.TradeModel).filter_by(symbol="000001", side="buy").count() == 0
    decision = db.query(web_app.DecisionLogModel).filter_by(symbol="000001", action="skip").one()
    assert decision.score is None
    assert decision.reason == "买入信心缺失"


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
