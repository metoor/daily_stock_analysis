# -*- coding: utf-8 -*-
"""ETF capital flow API endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.etf_capital_flow import (
    EtfCapitalFlowListResponse,
    EtfCapitalFlowSnapshotResponse,
)
from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository

logger = logging.getLogger(__name__)
router = APIRouter()


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"error": "not_found", "message": message})


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