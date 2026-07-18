# -*- coding: utf-8 -*-
import os

import pytest

from src.config import Config
from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
from src.storage import DatabaseManager, EtfCapitalFlowSnapshot


@pytest.fixture()
def isolated_db(tmp_path):
    """Mirror tests/test_decision_signal_repo.py:isolate_db pattern."""
    old_database_path = os.environ.get("DATABASE_PATH")
    db_path = tmp_path / "etf_capital_flow_repo.db"
    os.environ["DATABASE_PATH"] = str(db_path)
    Config.reset_instance()
    DatabaseManager.reset_instance()
    db = DatabaseManager.get_instance()
    try:
        yield db
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        if old_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = old_database_path


@pytest.fixture
def repo(isolated_db):
    return EtfCapitalFlowRepository(db_manager=isolated_db)


def test_save_and_get_snapshot(repo):
    payload = {"trade_date": "2026-07-17", "buckets": [], "status": "ok"}
    repo.save_snapshot("2026-07-17", payload)
    result = repo.get_snapshot("2026-07-17")
    assert result is not None
    assert result["trade_date"] == "2026-07-17"
    assert result["status"] == "ok"


def test_save_snapshot_upserts_same_date(repo):
    repo.save_snapshot("2026-07-17", {"status": "ok", "v": 1})
    repo.save_snapshot("2026-07-17", {"status": "ok", "v": 2})
    result = repo.get_snapshot("2026-07-17")
    assert result["v"] == 2


def test_get_snapshot_missing_returns_none(repo):
    assert repo.get_snapshot("2026-01-01") is None


def test_get_latest_snapshot(repo):
    repo.save_snapshot("2026-07-16", {"status": "ok", "trade_date": "2026-07-16"})
    repo.save_snapshot("2026-07-17", {"status": "ok", "trade_date": "2026-07-17"})
    repo.save_snapshot("2026-07-15", {"status": "ok", "trade_date": "2026-07-15"})
    result = repo.get_latest_snapshot()
    assert result["trade_date"] == "2026-07-17"


def test_get_snapshots_range(repo):
    for d in ["2026-07-15", "2026-07-16", "2026-07-17", "2026-07-18"]:
        repo.save_snapshot(d, {"trade_date": d, "status": "ok"})
    result = repo.get_snapshots_range("2026-07-16", "2026-07-17")
    assert len(result) == 2
    assert {r["trade_date"] for r in result} == {"2026-07-16", "2026-07-17"}