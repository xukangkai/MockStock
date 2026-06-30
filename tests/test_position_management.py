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
