# src/services/etf_capital_flow_service.py
# -*- coding: utf-8 -*-
"""Service orchestrating the daily ETF capital-flow analysis.

Pipeline:
1. Fetch batch ETF data via injected fetcher (DataFetcherManager.get_etf_capital_flow_context).
2. Classify each ETF into a sector or index bucket.
3. Per bucket: sort by 总市值, take top 10.
4. Compute share_change by comparing latest_shares to previous day's snapshot.
5. Aggregate (sum + weighted avg).
6. Build C view (all-market ranking) + A view (sector buckets) + B view (index buckets).
7. Persist snapshot to repository.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.data.etf_sector_mapping import classify_etf
from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
from src.services.etf_capital_flow_aggregator import (
    aggregate_bucket,
    select_top_n_by_scale,
)

logger = logging.getLogger(__name__)

TOP_N_PER_BUCKET = 10
# Plan §Global Constraints: "apply liquidity floor (成交额 > 0)" - filter only
# zero-turnover items so mini/illiquid ETFs are excluded but test fixtures with
# small turnover values still flow through. Callers may pass a higher floor.
LIQUIDITY_FLOOR = 0.0


class EtfCapitalFlowService:
    """Orchestrate daily ETF capital-flow analysis and persistence."""

    def __init__(
        self,
        *,
        fetcher: Callable[[], Dict[str, Any]],
        repository: Optional[EtfCapitalFlowRepository] = None,
        top_n: int = TOP_N_PER_BUCKET,
        liquidity_floor: float = LIQUIDITY_FLOOR,
    ):
        self._fetcher = fetcher
        self._repo = repository or EtfCapitalFlowRepository()
        self._top_n = top_n
        self._liquidity_floor = liquidity_floor

    def run_daily(self) -> Dict[str, Any]:
        """Run the full pipeline and persist. Fail-open: never raises."""
        warnings: List[str] = []
        today = datetime.now().strftime("%Y-%m-%d")

        # 1. Fetch
        try:
            batch = self._fetcher()
        except Exception as exc:
            logger.exception("ETF batch fetcher raised")
            batch = {
                "status": "failed",
                "data": [],
                "source_chain": [],
                "errors": [f"fetcher raised: {exc}"],
            }

        status = batch.get("status", "failed")
        items = batch.get("data", []) or []
        source_chain = batch.get("source_chain", [])
        warnings.extend(batch.get("errors", []))

        if not items:
            payload = self._empty_payload(today, status, source_chain, warnings)
            self._repo.save_snapshot(today, payload)
            return payload

        # Determine trade_date from items (prefer item-level, fallback to today)
        trade_date = items[0].get("trade_date") or today

        # 2. Classify
        bucket_to_items: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
        for item in items:
            assignment = classify_etf(item.get("code", ""), item.get("name", ""))
            bucket_to_items[(assignment.bucket_type, assignment.bucket_name)].append(item)

        # 3. Compute share_change from previous snapshot
        previous = self._repo.get_latest_snapshot()
        previous_shares: Dict[str, float] = {}
        if previous and previous.get("trade_date") != trade_date:
            for detail in previous.get("details", []) or []:
                code = detail.get("code")
                shares = detail.get("latest_shares")
                if code and shares is not None:
                    previous_shares[code] = float(shares)
        else:
            warnings.append("share_change missing: no previous snapshot available")

        for item in items:
            code = item.get("code")
            latest_shares = item.get("latest_shares")
            if code and latest_shares is not None and code in previous_shares:
                item["share_change"] = float(latest_shares) - previous_shares[code]
            else:
                item["share_change"] = None

        # 4. Top-N per bucket + aggregate
        sector_buckets: List[Dict[str, Any]] = []
        index_buckets: List[Dict[str, Any]] = []
        details: List[Dict[str, Any]] = []

        for (bucket_type, bucket_name), members in bucket_to_items.items():
            top_members = select_top_n_by_scale(
                members, n=self._top_n, liquidity_floor=self._liquidity_floor
            )
            if not top_members:
                continue
            bucket_summary = aggregate_bucket(
                top_members, bucket_name=bucket_name, bucket_type=bucket_type
            )
            if bucket_type == "sector":
                sector_buckets.append(bucket_summary)
            elif bucket_type == "index":
                index_buckets.append(bucket_summary)
            # else: "other" bucket - not surfaced in A/B views but kept in details
            for member in top_members:
                details.append(self._detail_item(member, bucket_type, bucket_name))

        # 5. C view: all-market ranking
        # Filter by sign before slicing so top_inflow (positive) and top_outflow
        # (negative) never overlap when the universe has fewer than 10 items.
        sorted_by_inflow = sorted(items, key=lambda x: x.get("main_net_inflow") or 0.0, reverse=True)
        inflow_items = [m for m in sorted_by_inflow if (m.get("main_net_inflow") or 0.0) > 0]
        outflow_items = [m for m in sorted_by_inflow if (m.get("main_net_inflow") or 0.0) < 0]
        top_inflow = [self._ranking_item(m) for m in inflow_items[:10]]
        top_outflow = [self._ranking_item(m) for m in outflow_items[-10:][::-1]]
        inflow_count = len(inflow_items)
        outflow_count = len(outflow_items)
        total_net_inflow = sum(m.get("main_net_inflow") or 0.0 for m in items)

        # Sort buckets by net_inflow_sum desc
        sector_buckets.sort(key=lambda b: b.get("net_inflow_sum") or 0.0, reverse=True)
        index_buckets.sort(key=lambda b: b.get("net_inflow_sum") or 0.0, reverse=True)

        payload = {
            "trade_date": trade_date,
            "status": status,
            "source_chain": source_chain,
            "warnings": warnings,
            "market_overview": {
                "total_net_inflow": total_net_inflow,
                "inflow_count": inflow_count,
                "outflow_count": outflow_count,
                "top_inflow": top_inflow,
                "top_outflow": top_outflow,
            },
            "sector_buckets": sector_buckets,
            "index_buckets": index_buckets,
            "details": details,
        }

        self._repo.save_snapshot(trade_date, payload)
        return payload

    def _empty_payload(
        self,
        trade_date: str,
        status: str,
        source_chain: List[Dict[str, Any]],
        warnings: List[str],
    ) -> Dict[str, Any]:
        return {
            "trade_date": trade_date,
            "status": status,
            "source_chain": source_chain,
            "warnings": warnings,
            "market_overview": {
                "total_net_inflow": 0.0,
                "inflow_count": 0,
                "outflow_count": 0,
                "top_inflow": [],
                "top_outflow": [],
            },
            "sector_buckets": [],
            "index_buckets": [],
            "details": [],
        }

    @staticmethod
    def _ranking_item(m: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "code": m.get("code"),
            "name": m.get("name"),
            "main_net_inflow": m.get("main_net_inflow") or 0.0,
            "change_pct": m.get("change_pct") or 0.0,
            "total_market_value": m.get("total_market_value"),
            "trade_date": m.get("trade_date"),
        }

    @staticmethod
    def _detail_item(
        m: Dict[str, Any], bucket_type: str, bucket_name: str
    ) -> Dict[str, Any]:
        return {
            "code": m.get("code"),
            "name": m.get("name"),
            "bucket_type": bucket_type,
            "bucket_name": bucket_name,
            "close": m.get("close"),
            "change_pct": m.get("change_pct"),
            "discount_pct": m.get("discount_pct"),
            "main_net_inflow": m.get("main_net_inflow"),
            "main_net_inflow_pct": m.get("main_net_inflow_pct"),
            "latest_shares": m.get("latest_shares"),
            "share_change": m.get("share_change"),
            "total_market_value": m.get("total_market_value"),
            "turnover": m.get("turnover"),
            "trade_date": m.get("trade_date"),
        }
