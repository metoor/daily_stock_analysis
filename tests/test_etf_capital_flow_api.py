# -*- coding: utf-8 -*-
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Keep this test runnable when optional LLM runtime deps are not installed.
try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    """Isolate from local .env (e.g. ADMIN_AUTH_ENABLED=true) like other API tests."""
    _reset_auth_globals()
    env_path = tmp_path / ".env"
    db_path = tmp_path / "etf_capital_flow_api_test.db"
    env_path.write_text(
        "\n".join(
            [
                "STOCK_LIST=600519",
                "GEMINI_API_KEY=test",
                "ADMIN_AUTH_ENABLED=false",
                f"DATABASE_PATH={db_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ENV_FILE", str(env_path))
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    Config.reset_instance()
    DatabaseManager.reset_instance()
    app = create_app()
    client = TestClient(app)
    yield client
    DatabaseManager.reset_instance()
    Config.reset_instance()
    _reset_auth_globals()


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


def test_get_latest_returns_snapshot(api_client):
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_latest_snapshot",
               return_value=_sample_payload()):
        response = api_client.get("/api/v1/etf-capital-flow/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["trade_date"] == "2026-07-17"
    assert data["status"] == "ok"
    assert data["market_overview"]["total_net_inflow"] == 1000.0


def test_get_latest_returns_404_when_empty(api_client):
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_latest_snapshot",
               return_value=None):
        response = api_client.get("/api/v1/etf-capital-flow/latest")
    assert response.status_code == 404


def test_get_by_date_returns_snapshot(api_client):
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_snapshot",
               return_value=_sample_payload("2026-07-16")):
        response = api_client.get("/api/v1/etf-capital-flow/2026-07-16")
    assert response.status_code == 200
    assert response.json()["trade_date"] == "2026-07-16"


def test_get_by_date_returns_404_when_missing(api_client):
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_snapshot",
               return_value=None):
        response = api_client.get("/api/v1/etf-capital-flow/2026-01-01")
    assert response.status_code == 404


def test_get_range_returns_list(api_client):
    snapshots = [_sample_payload("2026-07-15"), _sample_payload("2026-07-16"), _sample_payload("2026-07-17")]
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_snapshots_range",
               return_value=snapshots):
        response = api_client.get("/api/v1/etf-capital-flow/range/list?start_date=2026-07-15&end_date=2026-07-17")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["snapshots"]) == 3


def test_refresh_triggers_service_and_returns_snapshot(api_client):
    sample = _sample_payload("2026-07-17")
    with patch(
        "src.services.etf_capital_flow_service.EtfCapitalFlowService.run_daily",
        return_value=sample,
    ) as mock_run:
        response = api_client.post("/api/v1/etf-capital-flow/refresh")
    assert response.status_code == 200
    data = response.json()
    assert data["trade_date"] == "2026-07-17"
    assert data["status"] == "ok"
    assert data["market_overview"]["total_net_inflow"] == 1000.0
    mock_run.assert_called_once()


def test_refresh_with_empty_trade_date_calls_run_daily(api_client):
    sample = _sample_payload("2026-07-17")
    with patch(
        "src.services.etf_capital_flow_service.EtfCapitalFlowService.run_daily",
        return_value=sample,
    ) as mock_run, patch(
        "src.services.etf_capital_flow_service.EtfCapitalFlowService.backfill_for_date"
    ) as mock_backfill:
        response = api_client.post(
            "/api/v1/etf-capital-flow/refresh", json={"trade_date": ""}
        )
    assert response.status_code == 200
    mock_run.assert_called_once()
    mock_backfill.assert_not_called()


def test_refresh_with_past_date_calls_backfill(api_client):
    past_date = "2026-07-15"
    sample = _sample_payload(past_date)
    sample["status"] = "partial"
    with patch(
        "src.services.etf_capital_flow_service.EtfCapitalFlowService.backfill_for_date",
        return_value=sample,
    ) as mock_backfill, patch(
        "src.services.etf_capital_flow_service.EtfCapitalFlowService.run_daily"
    ) as mock_run:
        response = api_client.post(
            "/api/v1/etf-capital-flow/refresh", json={"trade_date": past_date}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["trade_date"] == past_date
    assert data["status"] == "partial"
    mock_backfill.assert_called_once_with(past_date)
    mock_run.assert_not_called()


def test_refresh_with_future_date_returns_400(api_client):
    response = api_client.post(
        "/api/v1/etf-capital-flow/refresh", json={"trade_date": "2030-01-01"}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "bad_request"


def test_refresh_with_invalid_date_format_returns_400(api_client):
    response = api_client.post(
        "/api/v1/etf-capital-flow/refresh", json={"trade_date": "not-a-date"}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "bad_request"


def test_refresh_returns_500_on_service_failure(api_client):
    with patch(
        "src.services.etf_capital_flow_service.EtfCapitalFlowService.run_daily",
        side_effect=RuntimeError("boom"),
    ):
        response = api_client.post("/api/v1/etf-capital-flow/refresh")
    assert response.status_code == 500
