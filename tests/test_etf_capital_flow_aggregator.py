# -*- coding: utf-8 -*-
from src.services.etf_capital_flow_aggregator import (
    select_top_n_by_scale,
    aggregate_bucket,
    compute_consecutive_inflow_days,
)


def _item(code: str, scale: float, inflow: float = 0.0, change_pct: float = 0.0, discount: float = 0.0, shares: float = 0.0, turnover: float = 100.0):
    return {
        "code": code, "name": f"ETF{code}", "close": 1.0,
        "total_market_value": scale, "main_net_inflow": inflow,
        "change_pct": change_pct, "discount_pct": discount,
        "latest_shares": shares, "share_change": None,  # filled by service layer
        "turnover": turnover,
    }


def test_select_top_n_by_scale_picks_largest():
    items = [_item("a", 100), _item("b", 500), _item("c", 300)]
    result = select_top_n_by_scale(items, n=2)
    assert [r["code"] for r in result] == ["b", "c"]


def test_select_top_n_filters_low_liquidity():
    items = [_item("a", 100, turnover=0.0), _item("b", 50, turnover=10.0)]
    result = select_top_n_by_scale(items, n=10, liquidity_floor=1.0)
    assert [r["code"] for r in result] == ["b"]


def test_aggregate_bucket_sums_absolute_quantities():
    members = [
        _item("a", scale=100, inflow=10, change_pct=1.0, discount=0.5, shares=1000),
        _item("b", scale=300, inflow=20, change_pct=2.0, discount=-0.5, shares=2000),
    ]
    result = aggregate_bucket(members, bucket_name="券商", bucket_type="sector")
    assert result["bucket_name"] == "券商"
    assert result["bucket_type"] == "sector"
    assert result["member_count"] == 2
    assert result["total_scale"] == 400
    assert result["net_inflow_sum"] == 30
    assert result["share_change_sum"] is None  # no share_change data yet


def test_aggregate_bucket_weighted_average_by_scale():
    # 100@1.0% + 300@2.0% -> weighted avg = (100*1 + 300*2)/400 = 700/400 = 1.75
    members = [
        _item("a", scale=100, inflow=10, change_pct=1.0, discount=0.5, shares=1000),
        _item("b", scale=300, inflow=20, change_pct=2.0, discount=-0.5, shares=2000),
    ]
    result = aggregate_bucket(members, bucket_name="券商", bucket_type="sector")
    assert abs(result["weighted_change_pct"] - 1.75) < 1e-9
    # discount: (100*0.5 + 300*-0.5)/400 = (50 - 150)/400 = -0.25
    assert abs(result["weighted_discount_pct"] - (-0.25)) < 1e-9


def test_aggregate_bucket_skips_missing_optional_fields():
    members = [
        _item("a", scale=100, inflow=10, change_pct=1.0, discount=0.5, shares=1000),
        _item("b", scale=300, inflow=20, change_pct=2.0, discount=None, shares=2000),
    ]
    result = aggregate_bucket(members, bucket_name="半导体", bucket_type="sector")
    # Only member "a" has discount; weighted by its own scale
    assert result["weighted_discount_pct"] == 0.5


def test_aggregate_bucket_with_share_change():
    members = [
        {**_item("a", scale=100, inflow=10, change_pct=1.0, discount=0.5, shares=1000), "share_change": 100},
        {**_item("b", scale=300, inflow=20, change_pct=2.0, discount=-0.5, shares=2000), "share_change": 200},
    ]
    result = aggregate_bucket(members, bucket_name="沪深300", bucket_type="index")
    assert result["share_change_sum"] == 300
    # share_change_rate = share_change / latest_shares
    # a: 100/1000 = 0.1, b: 200/2000 = 0.1 -> weighted = 0.1
    assert abs(result["weighted_share_change_pct"] - 0.1) < 1e-9


def test_aggregate_bucket_empty_members_returns_zeros():
    result = aggregate_bucket([], bucket_name="空", bucket_type="sector")
    assert result["member_count"] == 0
    assert result["total_scale"] == 0
    assert result["net_inflow_sum"] == 0


def test_compute_consecutive_inflow_days_positive_streak_at_end():
    # last 3 days positive -> +3
    daily = [-1.0, 1.0, 2.0, 3.0]
    assert compute_consecutive_inflow_days(daily) == 3


def test_compute_consecutive_inflow_days_negative_streak_at_end():
    daily = [1.0, -1.0, -2.0]
    assert compute_consecutive_inflow_days(daily) == -2


def test_compute_consecutive_inflow_days_empty():
    assert compute_consecutive_inflow_days([]) == 0


def test_compute_consecutive_inflow_days_zero_treated_as_break():
    daily = [1.0, 0.0, 2.0]
    assert compute_consecutive_inflow_days(daily) == 1