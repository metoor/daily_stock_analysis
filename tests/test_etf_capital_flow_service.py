# tests/test_etf_capital_flow_service.py
# -*- coding: utf-8 -*-
from unittest.mock import MagicMock

import pytest

from src.services.etf_capital_flow_service import EtfCapitalFlowService


def _batch_item(code, name, scale, inflow, change, discount, shares, turnover=100.0):
    return {
        "code": code, "name": name, "close": 1.0,
        "iopv": None, "discount_pct": discount, "change_pct": change,
        "volume": 1000.0, "turnover": turnover,
        "main_net_inflow": inflow, "main_net_inflow_pct": None,
        "latest_shares": shares, "share_change": None,
        "total_market_value": scale, "circulating_market_value": scale,
        "trade_date": "2026-07-17",
    }


@pytest.fixture
def fake_fetcher():
    fetcher = MagicMock()
    fetcher.return_value = {
        "status": "ok",
        "data": [
            # 券商 bucket
            _batch_item("512000", "券商ETF华泰", scale=500, inflow=10, change=1.0, discount=0.5, shares=1000),
            _batch_item("512880", "证券ETF指数", scale=300, inflow=5, change=0.5, discount=0.3, shares=800),
            # 沪深300 bucket
            _batch_item("510300", "沪深300ETF华泰", scale=2000, inflow=50, change=0.8, discount=-0.1, shares=5000),
            # 未分类
            _batch_item("588888", "新主题ETF", scale=10, inflow=1, change=2.0, discount=None, shares=100),
        ],
        "source_chain": [{"provider": "akshare", "result": "ok", "duration_ms": 100}],
        "errors": [],
    }
    return fetcher


def test_run_daily_persists_and_returns_payload(fake_fetcher, isolated_db):
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
    repo = EtfCapitalFlowRepository(db_manager=isolated_db)

    service = EtfCapitalFlowService(fetcher=fake_fetcher, repository=repo)
    result = service.run_daily()

    assert result["status"] == "ok"
    assert result["trade_date"] == "2026-07-17"
    # Sector bucket "券商" should have 2 members
    sector_names = [b["bucket_name"] for b in result["sector_buckets"]]
    assert "券商" in sector_names
    broker_bucket = next(b for b in result["sector_buckets"] if b["bucket_name"] == "券商")
    assert broker_bucket["member_count"] == 2
    assert broker_bucket["net_inflow_sum"] == 15
    # Index bucket "沪深300"
    index_names = [b["bucket_name"] for b in result["index_buckets"]]
    assert "沪深300" in index_names
    # C view: total net inflow = 10+5+50+1 = 66
    assert result["market_overview"]["total_net_inflow"] == 66
    assert result["market_overview"]["inflow_count"] == 4
    # Persisted
    persisted = repo.get_snapshot("2026-07-17")
    assert persisted is not None
    assert persisted["trade_date"] == "2026-07-17"


def test_run_daily_marks_share_change_missing_when_no_history(fake_fetcher, isolated_db):
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
    repo = EtfCapitalFlowRepository(db_manager=isolated_db)

    service = EtfCapitalFlowService(fetcher=fake_fetcher, repository=repo)
    result = service.run_daily()
    broker_bucket = next(b for b in result["sector_buckets"] if b["bucket_name"] == "券商")
    # No previous snapshot -> share_change_sum should be None
    assert broker_bucket["share_change_sum"] is None
    assert any("share_change" in w for w in result["warnings"])


def test_run_daily_computes_share_change_from_previous_snapshot(fake_fetcher, isolated_db):
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
    repo = EtfCapitalFlowRepository(db_manager=isolated_db)

    # Seed previous day snapshot with shares
    prev_payload = {
        "trade_date": "2026-07-16",
        "status": "ok",
        "warnings": [],
        "market_overview": {},
        "sector_buckets": [],
        "index_buckets": [],
        "details": [
            {"code": "512000", "latest_shares": 950},
            {"code": "510300", "latest_shares": 4900},
        ],
    }
    repo.save_snapshot("2026-07-16", prev_payload)

    service = EtfCapitalFlowService(fetcher=fake_fetcher, repository=repo)
    result = service.run_daily()
    # share_change for 512000 = 1000 - 950 = 50
    detail_512000 = next(d for d in result["details"] if d["code"] == "512000")
    assert detail_512000["share_change"] == 50


def test_run_daily_fail_open_when_fetcher_fails(isolated_db):
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
    repo = EtfCapitalFlowRepository(db_manager=isolated_db)

    failing_fetcher = MagicMock(return_value={
        "status": "failed",
        "data": [],
        "source_chain": [{"provider": "akshare", "result": "failed", "duration_ms": 0}],
        "errors": ["network down"],
    })
    service = EtfCapitalFlowService(fetcher=failing_fetcher, repository=repo)
    result = service.run_daily()
    assert result["status"] == "failed"
    assert "network down" in result["warnings"]
    assert result["sector_buckets"] == []
    assert result["index_buckets"] == []


# Add this fixture at the bottom of the test file (mirror tests/test_decision_signal_repo.py):
@pytest.fixture()
def isolated_db(tmp_path):
    import os
    from src.config import Config
    from src.storage import DatabaseManager
    old_database_path = os.environ.get("DATABASE_PATH")
    db_path = tmp_path / "etf_capital_flow_service.db"
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
