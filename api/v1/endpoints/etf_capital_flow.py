# -*- coding: utf-8 -*-
"""ETF capital flow API endpoints."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.etf_capital_flow import (
    EtfCapitalFlowListResponse,
    EtfCapitalFlowRefreshRequest,
    EtfCapitalFlowSnapshotResponse,
)
from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository

logger = logging.getLogger(__name__)
router = APIRouter()


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"error": "not_found", "message": message})


def _bad_request(message: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "bad_request", "message": message},
    )


def _internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error("%s: %s", message, str(exc))
    return HTTPException(
        status_code=500,
        detail={"error": "internal_error", "message": f"{message}: internal ETF capital flow error"},
    )


@router.get(
    "/latest",
    response_model=EtfCapitalFlowSnapshotResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get latest ETF capital flow snapshot",
)
def get_latest():
    try:
        result = EtfCapitalFlowRepository().get_latest_snapshot()
    except Exception as exc:
        raise _internal_error("Get latest ETF snapshot failed", exc)
    if result is None:
        raise _not_found("no ETF capital flow snapshot available")
    return EtfCapitalFlowSnapshotResponse(**result)


@router.get(
    "/range/list",
    response_model=EtfCapitalFlowListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="List ETF capital flow snapshots in a date range",
)
def get_range(
    start_date: str = Query(..., description="ISO date YYYY-MM-DD inclusive"),
    end_date: str = Query(..., description="ISO date YYYY-MM-DD inclusive"),
):
    try:
        snapshots = EtfCapitalFlowRepository().get_snapshots_range(start_date, end_date)
    except Exception as exc:
        raise _internal_error("List ETF snapshots by range failed", exc)
    items = [EtfCapitalFlowSnapshotResponse(**s) for s in snapshots]
    return EtfCapitalFlowListResponse(snapshots=items, total=len(items))


@router.get(
    "/{trade_date}",
    response_model=EtfCapitalFlowSnapshotResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get ETF capital flow snapshot for a specific trade date",
)
def get_by_date(trade_date: str):
    try:
        result = EtfCapitalFlowRepository().get_snapshot(trade_date)
    except Exception as exc:
        raise _internal_error("Get ETF snapshot by date failed", exc)
    if result is None:
        raise _not_found(f"no ETF capital flow snapshot for trade_date={trade_date}")
    return EtfCapitalFlowSnapshotResponse(**result)


@router.post(
    "/refresh",
    response_model=EtfCapitalFlowSnapshotResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Manually refresh an ETF capital flow snapshot (today or a past trade date)",
)
def refresh(body: Optional[EtfCapitalFlowRefreshRequest] = None):
    """Regenerate a snapshot on demand.

    - No body / empty ``trade_date`` / ``trade_date`` == today: full refresh
      via ``EtfCapitalFlowService.run_daily()`` (akshare ``fund_etf_spot_em``
      returns today's batch with all capital-flow fields).
    - ``trade_date`` is a past date (``YYYY-MM-DD``): partial backfill via
      ``EtfCapitalFlowService.backfill_for_date()`` using
      ``fund_etf_hist_em`` OHLCV. Capital-flow fields (``main_net_inflow``,
      ``discount_pct``, ``latest_shares``, ``iopv``) are unavailable for
      historical dates and will be null; ``status`` will be ``"partial"``.
    - ``trade_date`` is in the future: HTTP 400.
    - ``trade_date`` is not a valid ``YYYY-MM-DD`` date: HTTP 400.
    """
    # Lazy import to avoid circular dependencies with src.services / data_provider.
    from data_provider.base import DataFetcherManager
    from src.services.etf_capital_flow_service import EtfCapitalFlowService

    trade_date_raw = (body.trade_date or "").strip() if body else ""

    if trade_date_raw:
        try:
            trade_dt = datetime.strptime(trade_date_raw, "%Y-%m-%d").date()
        except ValueError:
            raise _bad_request(
                f"invalid trade_date={trade_date_raw!r}, expected YYYY-MM-DD"
            )
        today_dt = datetime.now().date()
        if trade_dt > today_dt:
            raise _bad_request(
                f"trade_date={trade_date_raw} is in the future; "
                "only today or past dates can be refreshed"
            )
        is_past = trade_dt < today_dt
    else:
        is_past = False

    try:
        manager = DataFetcherManager()
        service = EtfCapitalFlowService(
            fetcher=manager.get_etf_capital_flow_context
        )
        if is_past:
            payload = service.backfill_for_date(trade_date_raw)
        else:
            payload = service.run_daily()
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("Refresh ETF snapshot failed", exc)
    return EtfCapitalFlowSnapshotResponse(**payload)