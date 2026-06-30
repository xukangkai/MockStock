from types import SimpleNamespace

import web_app


def test_placeholder_agent_api():
    row = SimpleNamespace(cycle_id="cycle-1", summary="防守模式", risk_level="mid")
    assert row.cycle_id == "cycle-1"
