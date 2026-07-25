# tests/test_etf_capital_flow_context.py
# -*- coding: utf-8 -*-
from unittest.mock import MagicMock

from data_provider.base import DataFetcherManager


def _build_manager_with_fetchers(akshare_block, efinance_block):
    """Build a DataFetcherManager with mocked fetchers in _fetchers_by_name."""
    manager = DataFetcherManager.__new__(DataFetcherManager)
    manager._fetchers_by_name = {}
    manager._fetchers = []
    manager._fetchers_lock = MagicMock()

    mock_akshare = MagicMock()
    mock_akshare.get_etf_capital_flow_batch.return_value = akshare_block
    mock_efinance = MagicMock()
    mock_efinance.get_etf_capital_flow_batch.return_value = efinance_block

    manager._fetchers_by_name["AkshareFetcher"] = mock_akshare
    manager._fetchers_by_name["EfinanceFetcher"] = mock_efinance
    return manager


def test_get_etf_capital_flow_context_uses_akshare_first():
    manager = _build_manager_with_fetchers(
        akshare_block={
            "status": "ok", "data": [{"code": "510300"}],
            "source_chain": [{"provider": "akshare", "result": "ok", "duration_ms": 50}],
            "errors": [],
        },
        efinance_block={"status": "failed", "data": [], "source_chain": [], "errors": []},
    )
    result = manager.get_etf_capital_flow_context()
    assert result["status"] == "ok"
    assert len(result["data"]) == 1
    # Efinance should not be called when akshare succeeds
    manager._fetchers_by_name["EfinanceFetcher"].get_etf_capital_flow_batch.assert_not_called()


def test_get_etf_capital_flow_context_falls_back_to_efinance():
    manager = _build_manager_with_fetchers(
        akshare_block={
            "status": "failed", "data": [],
            "source_chain": [{"provider": "akshare", "result": "failed", "duration_ms": 0}],
            "errors": ["akshare down"],
        },
        efinance_block={
            "status": "ok", "data": [{"code": "510300"}],
            "source_chain": [{"provider": "efinance", "result": "ok", "duration_ms": 80}],
            "errors": [],
        },
    )
    result = manager.get_etf_capital_flow_context()
    assert result["status"] == "ok"
    assert len(result["data"]) == 1
    # source_chain should include both attempts
    providers = [s["provider"] for s in result["source_chain"]]
    assert "akshare" in providers
    assert "efinance" in providers


def test_get_etf_capital_flow_context_all_fail_returns_failed():
    manager = _build_manager_with_fetchers(
        akshare_block={"status": "failed", "data": [], "source_chain": [], "errors": ["akshare down"]},
        efinance_block={"status": "failed", "data": [], "source_chain": [], "errors": ["efinance down"]},
    )
    result = manager.get_etf_capital_flow_context()
    assert result["status"] == "failed"
    assert result["data"] == []
    assert any("akshare down" in e for e in result["errors"])
    assert any("efinance down" in e for e in result["errors"])
