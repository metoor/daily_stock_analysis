# -*- coding: utf-8 -*-
"""Pure aggregation functions for ETF capital-flow analysis.

Rules (from design spec §3):
- Absolute-quantity metrics (净流入额, 份额变动额) use SUM.
- Ratio/strength metrics (涨幅%, 折溢价%, 份额变动率%) use 总市值-weighted average.
- Never use simple average.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def select_top_n_by_scale(
    items: List[Dict[str, Any]],
    n: int = 10,
    liquidity_floor: float = 0.0,
) -> List[Dict[str, Any]]:
    """Sort by 总市值 descending, filter by liquidity floor, take top N."""
    eligible = [
        item for item in items
        if (item.get("turnover") or 0.0) > liquidity_floor
        and (item.get("total_market_value") or 0.0) > 0
    ]
    sorted_items = sorted(
        eligible,
        key=lambda x: x.get("total_market_value") or 0.0,
        reverse=True,
    )
    return sorted_items[:n]


def aggregate_bucket(
    members: List[Dict[str, Any]],
    *,
    bucket_name: str,
    bucket_type: str,
) -> Dict[str, Any]:
    """Aggregate a list of ETF items into a single bucket summary.

    Sums absolute quantities; weighted-averages ratios by 总市值.
    """
    if not members:
        return {
            "bucket_name": bucket_name,
            "bucket_type": bucket_type,
            "member_count": 0,
            "total_scale": 0.0,
            "net_inflow_sum": 0.0,
            "share_change_sum": None,
            "weighted_change_pct": None,
            "weighted_discount_pct": None,
            "weighted_share_change_pct": None,
        }

    total_scale = sum(m.get("total_market_value") or 0.0 for m in members)
    net_inflow_sum = sum(m.get("main_net_inflow") or 0.0 for m in members)

    # share_change_sum: only if at least one member has share_change data
    share_changes = [m.get("share_change") for m in members if m.get("share_change") is not None]
    share_change_sum = sum(share_changes) if share_changes else None

    def _weighted_avg(field: str) -> Optional[float]:
        numerator = 0.0
        denominator = 0.0
        for m in members:
            value = m.get(field)
            scale = m.get("total_market_value") or 0.0
            if value is None or scale <= 0:
                continue
            numerator += scale * value
            denominator += scale
        return (numerator / denominator) if denominator > 0 else None

    weighted_change_pct = _weighted_avg("change_pct")
    weighted_discount_pct = _weighted_avg("discount_pct")

    # share_change_rate = share_change / latest_shares (per member), then weighted avg
    weighted_share_change_pct: Optional[float] = None
    numerator = 0.0
    denominator = 0.0
    for m in members:
        share_change = m.get("share_change")
        latest_shares = m.get("latest_shares")
        scale = m.get("total_market_value") or 0.0
        if share_change is None or latest_shares is None or latest_shares <= 0 or scale <= 0:
            continue
        rate = share_change / latest_shares
        numerator += scale * rate
        denominator += scale
    if denominator > 0:
        weighted_share_change_pct = numerator / denominator

    return {
        "bucket_name": bucket_name,
        "bucket_type": bucket_type,
        "member_count": len(members),
        "total_scale": total_scale,
        "net_inflow_sum": net_inflow_sum,
        "share_change_sum": share_change_sum,
        "weighted_change_pct": weighted_change_pct,
        "weighted_discount_pct": weighted_discount_pct,
        "weighted_share_change_pct": weighted_share_change_pct,
    }


def compute_consecutive_inflow_days(daily_net_inflows: List[float]) -> int:
    """Return positive N for N-day net-inflow streak ending at last entry;
    negative N for net-outflow streak; 0 if empty or last day is zero.
    """
    if not daily_net_inflows:
        return 0
    last = daily_net_inflows[-1]
    if last == 0:
        return 0
    sign = 1 if last > 0 else -1
    count = 0
    for value in reversed(daily_net_inflows):
        if value == 0:
            break
        if (value > 0) == (last > 0):
            count += 1
        else:
            break
    return sign * count