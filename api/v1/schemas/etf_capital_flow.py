# -*- coding: utf-8 -*-
"""Pydantic schemas for ETF capital flow API responses."""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class EtfRankingItem(BaseModel):
    code: str
    name: Optional[str] = None
    main_net_inflow: float = 0.0
    change_pct: float = 0.0
    total_market_value: Optional[float] = None
    trade_date: Optional[str] = None


class EtfMarketOverview(BaseModel):
    total_net_inflow: float = 0.0
    inflow_count: int = 0
    outflow_count: int = 0
    top_inflow: List[EtfRankingItem] = Field(default_factory=list)
    top_outflow: List[EtfRankingItem] = Field(default_factory=list)


class EtfBucketSummary(BaseModel):
    bucket_name: str
    bucket_type: str
    member_count: int
    total_scale: float = 0.0
    net_inflow_sum: float = 0.0
    share_change_sum: Optional[float] = None
    weighted_change_pct: Optional[float] = None
    weighted_discount_pct: Optional[float] = None
    weighted_share_change_pct: Optional[float] = None


class EtfDetailItem(BaseModel):
    code: str
    name: Optional[str] = None
    bucket_type: str
    bucket_name: str
    close: Optional[float] = None
    change_pct: Optional[float] = None
    discount_pct: Optional[float] = None
    main_net_inflow: Optional[float] = None
    main_net_inflow_pct: Optional[float] = None
    latest_shares: Optional[float] = None
    share_change: Optional[float] = None
    total_market_value: Optional[float] = None
    turnover: Optional[float] = None
    trade_date: Optional[str] = None


class EtfCapitalFlowSnapshotResponse(BaseModel):
    trade_date: str
    status: str
    source_chain: List[Any] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    market_overview: EtfMarketOverview
    sector_buckets: List[EtfBucketSummary] = Field(default_factory=list)
    index_buckets: List[EtfBucketSummary] = Field(default_factory=list)
    details: List[EtfDetailItem] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EtfCapitalFlowListResponse(BaseModel):
    snapshots: List[EtfCapitalFlowSnapshotResponse]
    total: int