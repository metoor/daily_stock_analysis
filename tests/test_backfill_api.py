# -*- coding: utf-8 -*-
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import src.auth as auth
from server import app


@pytest.fixture(autouse=True)
def disable_auth():
    auth._auth_enabled = None
    with patch("api.middlewares.auth.is_auth_enabled", return_value=False), \
         patch("src.auth.is_auth_enabled", return_value=False):
        yield
    auth._auth_enabled = None


client = TestClient(app)


def test_backfill_rejects_future_date():
    future = (date.today() + timedelta(days=1)).isoformat()
    resp = client.post("/api/v1/analysis/backfill", json={
        "stock_codes": ["600519"], "target_date": future,
    })
    assert resp.status_code == 400


def test_backfill_rejects_empty_codes():
    resp = client.post("/api/v1/analysis/backfill", json={
        "stock_codes": [], "target_date": "2026-06-10",
    })
    assert resp.status_code == 400


def test_backfill_accepts_valid_request():
    with patch("src.services.analysis_service.AnalysisService.backfill_as_of_date") as m:
        m.return_value = {"processed": 1, "saved": 1, "skipped": 0, "errors": 0, "message": "ok", "diagnostics": {}}
        resp = client.post("/api/v1/analysis/backfill", json={
            "stock_codes": ["600519"], "target_date": "2026-06-10",
        })
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    assert resp.json()["task_id"]
