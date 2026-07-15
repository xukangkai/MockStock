import pytest

import web_app


@pytest.fixture(autouse=True)
def _stub_market_network_calls(monkeypatch):
    """自动 stub 掉每轮决策会真实联网的函数，避免单元测试触发 akshare 网络请求而挂起。

    autouse fixture 先于测试函数执行；测试函数内若对同一对象再次 monkeypatch.setattr，
    后者会覆盖此处的 stub，因此不影响需要自定义返回值的测试。
    """
    monkeypatch.setattr(web_app, "fetch_market_indices", lambda: {})
    monkeypatch.setattr(web_app, "fetch_market_news", lambda: [])
