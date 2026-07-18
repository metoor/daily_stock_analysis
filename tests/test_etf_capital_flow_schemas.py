# -*- coding: utf-8 -*-
from api.v1.schemas.etf_capital_flow import (
    EtfCapitalFlowSnapshotResponse,
    EtfBucketSummary,
    EtfRankingItem,
    EtfDetailItem,
)


def test_snapshot_response_round_trips():
    payload = {
        "trade_date": "2026-07-17",
        "status": "ok",
        "source_chain": [{"provider": "akshare", "result": "ok", "duration_ms": 100}],
        "warnings": [],
        "market_overview": {
            "total_net_inflow": 1000000.0,
            "inflow_count": 100,
            "outflow_count": 50,
            "top_inflow": [{"code": "510300", "name": "沪深300", "main_net_inflow": 50000.0,
                            "change_pct": 0.5, "total_market_value": 1e9, "trade_date": "2026-07-17"}],
            "top_outflow": [],
        },
        "sector_buckets": [{"bucket_name": "券商", "bucket_type": "sector", "member_count": 2,
                            "total_scale": 800.0, "net_inflow_sum": 15.0, "share_change_sum": None,
                            "weighted_change_pct": 0.75, "weighted_discount_pct": 0.4,
                            "weighted_share_change_pct": None}],
        "index_buckets": [],
        "details": [{"code": "512000", "name": "券商ETF", "bucket_type": "sector",
                     "bucket_name": "券商", "close": 1.0, "change_pct": 1.0,
                     "discount_pct": 0.5, "main_net_inflow": 10.0, "main_net_inflow_pct": 1.0,
                     "latest_shares": 1000.0, "share_change": None,
                     "total_market_value": 500.0, "turnover": 100.0, "trade_date": "2026-07-17"}],
    }
    response = EtfCapitalFlowSnapshotResponse(**payload)
    assert response.trade_date == "2026-07-17"
    assert response.status == "ok"
    assert response.market_overview.total_net_inflow == 1000000.0
    assert len(response.sector_buckets) == 1
    assert response.sector_buckets[0].bucket_name == "券商"
    assert response.details[0].share_change is None


def test_snapshot_response_accepts_partial_status():
    response = EtfCapitalFlowSnapshotResponse(
        trade_date="2026-07-17",
        status="partial",
        source_chain=[],
        warnings=["partial data"],
        market_overview={"total_net_inflow": 0.0, "inflow_count": 0, "outflow_count": 0,
                         "top_inflow": [], "top_outflow": []},
        sector_buckets=[],
        index_buckets=[],
        details=[],
    )
    assert response.status == "partial"