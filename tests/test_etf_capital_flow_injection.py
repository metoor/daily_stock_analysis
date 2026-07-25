# tests/test_etf_capital_flow_injection.py
# -*- coding: utf-8 -*-
from src.market_analyzer import MarketAnalyzer


def test_inject_etf_block_after_capital_section():
    analyzer = MarketAnalyzer.__new__(MarketAnalyzer)
    etf_payload = {
        "trade_date": "2026-07-17",
        "status": "ok",
        "sector_buckets": [
            {"bucket_name": "券商", "net_inflow_sum": 12.3e8, "weighted_change_pct": 1.2,
             "weighted_share_change_pct": None, "weighted_discount_pct": 0.3,
             "share_change_sum": None, "member_count": 5, "total_scale": 1000, "bucket_type": "sector"},
            {"bucket_name": "医药", "net_inflow_sum": -5.2e8, "weighted_change_pct": -0.5,
             "weighted_share_change_pct": None, "weighted_discount_pct": None,
             "share_change_sum": None, "member_count": 4, "total_scale": 800, "bucket_type": "sector"},
        ],
        "index_buckets": [
            {"bucket_name": "沪深300", "net_inflow_sum": 5e8, "weighted_change_pct": 0.4,
             "weighted_share_change_pct": 0.012, "weighted_discount_pct": -0.1,
             "share_change_sum": 1.8e8, "member_count": 3, "total_scale": 5000, "bucket_type": "index"},
        ],
        "market_overview": {"total_net_inflow": 38e8},
    }
    result = analyzer._build_etf_capital_flow_block(etf_payload)
    assert "资金方向（ETF）" in result
    assert "券商" in result
    assert "医药" in result
    assert "沪深300" in result


def test_inject_etf_block_returns_empty_when_no_data():
    analyzer = MarketAnalyzer.__new__(MarketAnalyzer)
    result = analyzer._build_etf_capital_flow_block({"status": "failed", "sector_buckets": [], "index_buckets": []})
    assert result == ""


def test_inject_etf_block_handles_missing_share_change():
    analyzer = MarketAnalyzer.__new__(MarketAnalyzer)
    etf_payload = {
        "trade_date": "2026-07-17",
        "status": "ok",
        "sector_buckets": [],
        "index_buckets": [
            {"bucket_name": "沪深300", "net_inflow_sum": 5e8, "weighted_change_pct": 0.4,
             "weighted_share_change_pct": None, "weighted_discount_pct": -0.1,
             "share_change_sum": None, "member_count": 3, "total_scale": 5000, "bucket_type": "index"},
        ],
        "market_overview": {"total_net_inflow": 5e8},
    }
    result = analyzer._build_etf_capital_flow_block(etf_payload)
    # Should not crash; should mention 沪深300 without share_change detail
    assert "沪深300" in result
