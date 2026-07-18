# tests/test_etf_capital_flow_service.py
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
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


def test_run_daily_fail_open_when_fetcher_raises(isolated_db):
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
    repo = EtfCapitalFlowRepository(db_manager=isolated_db)

    raising_fetcher = MagicMock(side_effect=RuntimeError("boom"))
    service = EtfCapitalFlowService(fetcher=raising_fetcher, repository=repo)
    result = service.run_daily()
    assert result["status"] == "failed"
    assert result["market_overview"]["top_inflow"] == []
    assert result["market_overview"]["top_outflow"] == []
    assert result["market_overview"]["inflow_count"] == 0
    assert result["market_overview"]["outflow_count"] == 0
    assert result["sector_buckets"] == []
    assert result["index_buckets"] == []
    assert result["details"] == []
    assert any("boom" in w for w in result["warnings"])


def test_run_daily_top_inflow_outflow_no_overlap_with_few_items(isolated_db):
    """Regression: with <10 items, top_inflow and top_outflow must not share codes.

    Previously both lists sliced the same sorted array (first 10 vs last 10
    reversed), so a 5-item universe appeared in both charts. The fix filters
    by sign of main_net_inflow before slicing.
    """
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
    repo = EtfCapitalFlowRepository(db_manager=isolated_db)

    fetcher = MagicMock(return_value={
        "status": "ok",
        "data": [
            # 3 inflow ETFs (positive main_net_inflow)
            _batch_item("512000", "券商ETF华泰", scale=500, inflow=10, change=1.0, discount=0.5, shares=1000),
            _batch_item("512880", "证券ETF指数", scale=300, inflow=5, change=0.5, discount=0.3, shares=800),
            _batch_item("510300", "沪深300ETF华泰", scale=2000, inflow=50, change=0.8, discount=-0.1, shares=5000),
            # 2 outflow ETFs (negative main_net_inflow)
            _batch_item("159915", "芯片ETF", scale=400, inflow=-8, change=-1.2, discount=0.2, shares=600),
            _batch_item("588000", "科创50ETF", scale=350, inflow=-3, change=-0.4, discount=0.1, shares=700),
        ],
        "source_chain": [{"provider": "akshare", "result": "ok", "duration_ms": 100}],
        "errors": [],
    })

    service = EtfCapitalFlowService(fetcher=fetcher, repository=repo)
    result = service.run_daily()

    top_inflow = result["market_overview"]["top_inflow"]
    top_outflow = result["market_overview"]["top_outflow"]
    assert len(top_inflow) == 3
    assert len(top_outflow) == 2
    inflow_codes = {item["code"] for item in top_inflow}
    outflow_codes = {item["code"] for item in top_outflow}
    assert inflow_codes.isdisjoint(outflow_codes)
    assert result["market_overview"]["inflow_count"] == 3
    assert result["market_overview"]["outflow_count"] == 2


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


# ---------------------------------------------------------------------------
# backfill_for_date
# ---------------------------------------------------------------------------


def _backfill_universe_item(code, name, scale, turnover=100.0):
    """Today's spot row used as the ranking universe for backfill."""
    return {
        "code": code,
        "name": name,
        "close": 1.0,
        "iopv": None,
        "discount_pct": 0.5,
        "change_pct": 0.5,
        "volume": 1000.0,
        "turnover": turnover,
        "main_net_inflow": 10.0,
        "main_net_inflow_pct": 1.0,
        "latest_shares": 1000,
        "total_market_value": scale,
        "circulating_market_value": scale,
        "trade_date": datetime.now().strftime("%Y-%m-%d"),
    }


def _hist_frame(target_date: str, close=1.05, change_pct=0.5, turnover=1050.0, volume=1000):
    """One-row akshare fund_etf_hist_em DataFrame for target_date."""
    return pd.DataFrame(
        [
            {
                "日期": target_date,
                "开盘": close,
                "收盘": close,
                "最高": close * 1.01,
                "最低": close * 0.99,
                "成交量": volume,
                "成交额": turnover,
                "振幅": 2.0,
                "涨跌幅": change_pct,
                "涨跌额": close - 1.0,
                "换手率": 1.0,
            }
        ]
    )


def _past_date(days_ago: int = 3) -> str:
    return (datetime.now().date() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def test_backfill_for_date_produces_partial_snapshot(isolated_db):
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository

    repo = EtfCapitalFlowRepository(db_manager=isolated_db)
    target_date = _past_date(3)

    fetcher = MagicMock(return_value={
        "status": "ok",
        "data": [
            _backfill_universe_item("512000", "券商ETF华泰", scale=500),
            _backfill_universe_item("510300", "沪深300ETF华泰", scale=2000),
        ],
        "source_chain": [{"provider": "akshare", "result": "ok", "duration_ms": 100}],
        "errors": [],
    })

    def _fake_hist_em(symbol, period, start_date, end_date, adjust):
        return _hist_frame(target_date, close=1.05, change_pct=0.8)

    service = EtfCapitalFlowService(fetcher=fetcher, repository=repo)
    with patch("akshare.fund_etf_hist_em", side_effect=_fake_hist_em):
        result = service.backfill_for_date(target_date)

    assert result["trade_date"] == target_date
    assert result["status"] == "partial"
    assert any("backfill" in w for w in result["warnings"])
    # Details: capital flow / share fields must be null for every row.
    assert result["details"], "expected at least one detail row"
    for detail in result["details"]:
        assert detail["main_net_inflow"] is None
        assert detail["discount_pct"] is None
        assert detail["latest_shares"] is None
        assert detail["share_change"] is None
    # close / change_pct come from the hist row, not from today's spot.
    for detail in result["details"]:
        assert detail["close"] == 1.05
        assert detail["change_pct"] == 0.8
    # total_net_inflow is 0.0 because all main_net_inflow are None.
    assert result["market_overview"]["total_net_inflow"] == 0.0
    # inflow_count/outflow_count come from change_pct sign (both positive).
    assert result["market_overview"]["inflow_count"] == len(result["details"])
    assert result["market_overview"]["outflow_count"] == 0


def test_backfill_for_date_persists_snapshot(isolated_db):
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository

    repo = EtfCapitalFlowRepository(db_manager=isolated_db)
    target_date = _past_date(5)

    fetcher = MagicMock(return_value={
        "status": "ok",
        "data": [
            _backfill_universe_item("512000", "券商ETF华泰", scale=500),
        ],
        "source_chain": [{"provider": "akshare", "result": "ok", "duration_ms": 100}],
        "errors": [],
    })

    with patch("akshare.fund_etf_hist_em", side_effect=lambda **kw: _hist_frame(target_date)):
        service = EtfCapitalFlowService(fetcher=fetcher, repository=repo)
        service.backfill_for_date(target_date)

    persisted = repo.get_snapshot(target_date)
    assert persisted is not None
    assert persisted["trade_date"] == target_date
    assert persisted["status"] == "partial"


def test_backfill_for_date_today_delegates_to_run_daily(isolated_db):
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository

    repo = EtfCapitalFlowRepository(db_manager=isolated_db)
    today = datetime.now().strftime("%Y-%m-%d")

    fetcher = MagicMock(return_value={
        "status": "ok",
        "data": [],
        "source_chain": [],
        "errors": [],
    })

    service = EtfCapitalFlowService(fetcher=fetcher, repository=repo)
    delegated = {
        "trade_date": today,
        "status": "ok",
        "source_chain": [],
        "warnings": [],
        "market_overview": {
            "total_net_inflow": 1.0,
            "inflow_count": 1,
            "outflow_count": 0,
            "top_inflow": [],
            "top_outflow": [],
        },
        "sector_buckets": [],
        "index_buckets": [],
        "details": [],
    }
    with patch.object(service, "run_daily", return_value=delegated) as mock_run:
        result = service.backfill_for_date(today)

    mock_run.assert_called_once()
    assert result["trade_date"] == today
    assert result["status"] == "ok"


def test_backfill_for_date_marks_failed_when_majority_fetches_fail(isolated_db):
    """If >50% of per-ETF hist fetches raise, status must be 'failed'."""
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository

    repo = EtfCapitalFlowRepository(db_manager=isolated_db)
    target_date = _past_date(2)

    fetcher = MagicMock(return_value={
        "status": "ok",
        "data": [
            _backfill_universe_item("512000", "券商ETF华泰", scale=500),
            _backfill_universe_item("510300", "沪深300ETF华泰", scale=2000),
            _backfill_universe_item("510500", "中证500ETF", scale=1500),
        ],
        "source_chain": [{"provider": "akshare", "result": "ok", "duration_ms": 100}],
        "errors": [],
    })

    def _flaky_hist_em(symbol, **kwargs):
        # Only one of three ETFs returns data; >50% fail -> status='failed'.
        if symbol == "510300":
            return _hist_frame(target_date)
        raise RuntimeError("akshare boom")

    with patch("akshare.fund_etf_hist_em", side_effect=_flaky_hist_em):
        service = EtfCapitalFlowService(fetcher=fetcher, repository=repo)
        result = service.backfill_for_date(target_date)

    assert result["trade_date"] == target_date
    assert result["status"] == "failed"
    assert any("510500" in w or "512000" in w for w in result["warnings"])
