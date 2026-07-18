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
import math
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
# How many top-by-总市值 ETFs to backfill per historical date. akshare
# fund_etf_hist_em is a per-symbol call, so we cap the universe to keep
# backfill latency reasonable.
BACKFILL_UNIVERSE_SIZE = 100


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

        # 2. Compute share_change from previous snapshot
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

        payload = self._assemble_payload(
            items=items,
            trade_date=trade_date,
            status=status,
            source_chain=source_chain,
            warnings=warnings,
        )

        self._repo.save_snapshot(trade_date, payload)
        return payload

    def backfill_for_date(self, target_date: str) -> Dict[str, Any]:
        """Backfill a past date's snapshot from historical OHLCV (partial).

        akshare ``fund_etf_spot_em`` only returns TODAY's batch, so a past
        trade date cannot be reproduced from the spot batch. Instead we:
        1. Call the spot batch once to get the ETF universe + 总市值 for ranking.
        2. Pick the top ``BACKFILL_UNIVERSE_SIZE`` ETFs by 总市值.
        3. For each, call ``ak.fund_etf_hist_em`` with start=end=target_date
           to fetch that date's OHLCV row.
        4. Build degraded items: close/change_pct/turnover/volume from hist;
           capital-flow fields (main_net_inflow, discount_pct, latest_shares,
           iopv) set to None; share_change set to None.
        5. Reuse the classify -> top-N -> aggregate -> persist pipeline with
           ``status="partial"`` and warnings explaining the missing fields.

        If ``target_date`` is today (or in the future), delegates to
        :meth:`run_daily` so callers can pass either an ad-hoc historical
        date or the latest trade date through the same entry point.

        Fail-open: never raises. If >50% of the per-ETF hist fetches fail,
        the snapshot is persisted with ``status="failed"`` instead of
        ``"partial"``.
        """
        # Lazy imports keep akshare / concurrent out of module-level side effects.
        import akshare as ak
        from concurrent.futures import (
            ThreadPoolExecutor,
            TimeoutError as FuturesTimeoutError,
            as_completed,
        )

        # 1. Validate target_date
        try:
            target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            logger.warning("backfill_for_date: invalid target_date=%r", target_date)
            payload = self._empty_payload(
                target_date or datetime.now().strftime("%Y-%m-%d"),
                "failed",
                [],
                [f"invalid target_date format: {target_date!r}, expected YYYY-MM-DD"],
            )
            return payload

        today = datetime.now().date()
        if target_dt >= today:
            # Today or future: today's data is available via the spot batch, so
            # delegate to run_daily() (which persists under today's trade_date).
            logger.info(
                "backfill_for_date: target_date=%s is today/future, delegating to run_daily()",
                target_date,
            )
            return self.run_daily()

        target_compact = target_dt.strftime("%Y%m%d")
        warnings: List[str] = [
            "backfill: capital flow fields (main_net_inflow, discount_pct, latest_shares) not available for historical dates",
            "backfill: inflow_count/outflow_count computed from change_pct sign (capital flow data unavailable)",
        ]

        # 2. Fetch today's spot batch for ETF universe + 总市值 ranking
        try:
            batch = self._fetcher()
        except Exception as exc:
            logger.exception("ETF batch fetcher raised during backfill")
            batch = {
                "status": "failed",
                "data": [],
                "source_chain": [],
                "errors": [f"fetcher raised: {exc}"],
            }

        source_chain = batch.get("source_chain", [])
        warnings.extend(batch.get("errors", []))

        today_items = batch.get("data", []) or []
        if not today_items:
            payload = self._empty_payload(target_date, "failed", source_chain, warnings)
            self._repo.save_snapshot(target_date, payload)
            return payload

        # 3. Select top-N by 总市值 (with liquidity floor). total_market_value
        # is preserved onto the backfilled items so the aggregator's
        # 总市值-weighted averages still work; only capital-flow / share
        # fields are nulled.
        eligible = [
            item for item in today_items
            if (item.get("turnover") or 0.0) > self._liquidity_floor
            and (item.get("total_market_value") or 0.0) > 0
        ]
        sorted_items = sorted(
            eligible,
            key=lambda x: x.get("total_market_value") or 0.0,
            reverse=True,
        )
        top_universe = sorted_items[:BACKFILL_UNIVERSE_SIZE]

        if not top_universe:
            payload = self._empty_payload(
                target_date,
                "failed",
                source_chain,
                warnings + ["no eligible ETFs after liquidity floor"],
            )
            self._repo.save_snapshot(target_date, payload)
            return payload

        # 4. Per-ETF historical OHLCV fetch (fail-open per ETF)
        def _fetch_one(item: Dict[str, Any]) -> Dict[str, Any]:
            code = item.get("code", "")
            try:
                df = ak.fund_etf_hist_em(
                    symbol=code,
                    period="daily",
                    start_date=target_compact,
                    end_date=target_compact,
                    adjust="",
                )
            except Exception as exc:  # noqa: BLE001 - fail-open per ETF
                return {"code": code, "error": f"hist_em raised: {exc}"}
            if df is None or df.empty:
                return {"code": code, "error": "empty frame"}
            # Defensive: hist_em may return rows around the target date; keep
            # only the exact match. The 日期 column is a string YYYY-MM-DD.
            try:
                df = df[df["日期"] == target_date]
            except Exception:  # noqa: BLE001 - column missing / dtype mismatch
                return {"code": code, "error": "日期 column missing"}
            if df.empty:
                return {"code": code, "error": f"no row for {target_date}"}
            row = df.iloc[0]
            return {
                "code": code,
                "name": item.get("name"),
                "close": _parse_float(row.get("收盘")),
                "change_pct": _parse_float(row.get("涨跌幅")) or 0.0,
                "turnover": _parse_float(row.get("成交额")) or 0.0,
                "volume": _parse_float(row.get("成交量")) or 0.0,
                "total_market_value": item.get("total_market_value"),
                "trade_date": target_date,
                # Capital flow / share fields: not available historically.
                "main_net_inflow": None,
                "main_net_inflow_pct": None,
                "discount_pct": None,
                "latest_shares": None,
                "share_change": None,
                "iopv": None,
            }

        items: List[Dict[str, Any]] = []
        fetch_errors: List[str] = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(_fetch_one, item) for item in top_universe]
            try:
                for future in as_completed(futures, timeout=60):
                    try:
                        result = future.result()
                    except Exception as exc:  # noqa: BLE001 - fail-open per ETF
                        fetch_errors.append(f"future raised: {exc}")
                        continue
                    if "error" in result:
                        fetch_errors.append(f"{result['code']}: {result['error']}")
                    else:
                        items.append(result)
            except FuturesTimeoutError:
                fetch_errors.append("ThreadPoolExecutor timed out after 60s")
                for fut in futures:
                    if not fut.done():
                        fut.cancel()

        warnings.extend(fetch_errors)

        # 5. Status: failed if >50% of ETFs failed, otherwise partial
        total_attempts = len(top_universe)
        failure_count = total_attempts - len(items)
        if total_attempts > 0 and failure_count / total_attempts > 0.5:
            status = "failed"
        else:
            status = "partial"

        if not items:
            payload = self._empty_payload(target_date, status, source_chain, warnings)
            self._repo.save_snapshot(target_date, payload)
            return payload

        # 6. Reuse the shared pipeline (classify -> top-N -> aggregate -> C view)
        # with counts_from_change_pct=True so the KPI bar still surfaces
        # up/down breadth from the OHLCV change_pct sign.
        payload = self._assemble_payload(
            items=items,
            trade_date=target_date,
            status=status,
            source_chain=source_chain,
            warnings=warnings,
            counts_from_change_pct=True,
        )

        self._repo.save_snapshot(target_date, payload)
        return payload

    def _assemble_payload(
        self,
        items: List[Dict[str, Any]],
        trade_date: str,
        status: str,
        source_chain: List[Dict[str, Any]],
        warnings: List[str],
        *,
        counts_from_change_pct: bool = False,
    ) -> Dict[str, Any]:
        """Shared classify -> top-N -> aggregate -> C-view -> payload builder.

        Callers must pre-populate ``share_change`` on each item (run_daily
        derives it from the previous snapshot; backfill_for_date sets it to
        None). When ``counts_from_change_pct=True``, inflow/outflow counts
        are derived from ``change_pct`` sign instead of ``main_net_inflow``
        sign -- used by backfill where capital-flow data is unavailable.
        """
        # Classify
        bucket_to_items: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
        for item in items:
            assignment = classify_etf(item.get("code", ""), item.get("name", ""))
            bucket_to_items[(assignment.bucket_type, assignment.bucket_name)].append(item)

        # Top-N per bucket + aggregate
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

        # C view: all-market ranking. Filter by sign before slicing so
        # top_inflow (positive) and top_outflow (negative) never overlap when
        # the universe has fewer than 10 items.
        sorted_by_inflow = sorted(items, key=lambda x: x.get("main_net_inflow") or 0.0, reverse=True)
        inflow_items = [m for m in sorted_by_inflow if (m.get("main_net_inflow") or 0.0) > 0]
        outflow_items = [m for m in sorted_by_inflow if (m.get("main_net_inflow") or 0.0) < 0]
        top_inflow = [self._ranking_item(m) for m in inflow_items[:10]]
        top_outflow = [self._ranking_item(m) for m in outflow_items[-10:][::-1]]
        if counts_from_change_pct:
            inflow_count = sum(1 for m in items if (m.get("change_pct") or 0.0) > 0)
            outflow_count = sum(1 for m in items if (m.get("change_pct") or 0.0) < 0)
        else:
            inflow_count = len(inflow_items)
            outflow_count = len(outflow_items)
        total_net_inflow = sum(m.get("main_net_inflow") or 0.0 for m in items)

        # Sort buckets by net_inflow_sum desc
        sector_buckets.sort(key=lambda b: b.get("net_inflow_sum") or 0.0, reverse=True)
        index_buckets.sort(key=lambda b: b.get("net_inflow_sum") or 0.0, reverse=True)

        return {
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


def _parse_float(value: Any) -> Optional[float]:
    """Best-effort float parse that rejects NaN/Inf (akshare hist rows)."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f
