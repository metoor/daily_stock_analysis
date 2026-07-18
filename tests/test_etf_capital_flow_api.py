# -*- coding: utf-8 -*-
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app


def _sample_payload(trade_date="2026-07-17"):
    return {
        "trade_date": trade_date,
        "status": "ok",
        "source_chain": [{"provider": "akshare", "result": "ok", "duration_ms": 50}],
        "warnings": [],
        "market_overview": {
            "total_net_inflow": 1000.0,
            "inflow_count": 5,
            "outflow_count": 3,
            "top_inflow": [{"code": "510300", "name": "沪深300", "main_net_inflow": 500.0,
                            "change_pct": 0.5, "total_market_value": 1e9, "trade_date": trade_date}],
            "top_outflow": [],
        },
        "sector_buckets": [],
        "index_buckets": [],
        "details": [],
        "created_at": "2026-07-17T18:00:00",
        "updated_at": "2026-07-17T18:00:00",
    }


def test_get_latest_returns_snapshot():
    app = create_app()
    client = TestClient(app)
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_latest_snapshot",
               return_value=_sample_payload()):
        response = client.get("/api/v1/etf-capital-flow/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["trade_date"] == "2026-07-17"
    assert data["status"] == "ok"
    assert data["market_overview"]["total_net_inflow"] == 1000.0


def test_get_latest_returns_404_when_empty():
    app = create_app()
    client = TestClient(app)
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_latest_snapshot",
               return_value=None):
        response = client.get("/api/v1/etf-capital-flow/latest")
    assert response.status_code == 404


def test_get_by_date_returns_snapshot():
    app = create_app()
    client = TestClient(app)
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_snapshot",
               return_value=_sample_payload("2026-07-16")):
        response = client.get("/api/v1/etf-capital-flow/2026-07-16")
    assert response.status_code == 200
    assert response.json()["trade_date"] == "2026-07-16"


def test_get_by_date_returns_404_when_missing():
    app = create_app()
    client = TestClient(app)
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_snapshot",
               return_value=None):
        response = client.get("/api/v1/etf-capital-flow/2026-01-01")
    assert response.status_code == 404


def test_get_range_returns_list():
    app = create_app()
    client = TestClient(app)
    snapshots = [_sample_payload("2026-07-15"), _sample_payload("2026-07-16"), _sample_payload("2026-07-17")]
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_snapshots_range",
               return_value=snapshots):
        response = client.get("/api/v1/etf-capital-flow/range/list?start_date=2026-07-15&end_date=2026-07-17")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["snapshots"]) == 3