# src/data/etf_sector_mapping.py
# -*- coding: utf-8 -*-
"""Classify A-share ETF codes into sector / index buckets for capital-flow aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class EtfBucketAssignment:
    bucket_type: Literal["sector", "index", "other"]
    bucket_name: str


# Broad-based index keywords -> canonical bucket name. Order matters: more specific first.
_INDEX_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("中证A500", "中证A500"),
    ("A500", "中证A500"),
    ("沪深300", "沪深300"),
    ("300ETF", "沪深300"),
    ("中证500", "中证500"),
    ("500ETF", "中证500"),
    ("中证1000", "中证1000"),
    ("1000ETF", "中证1000"),
    ("科创50", "科创50"),
    ("科创板50", "科创50"),
    ("创业板", "创业板指"),
    ("上证50", "上证50"),
    ("50ETF", "上证50"),
    ("红利", "红利指数"),
    ("上证指数", "上证指数"),
)

# Sector keywords -> canonical bucket name.
_SECTOR_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("券商", "券商"),
    ("证券", "券商"),
    ("银行", "银行"),
    ("保险", "保险"),
    ("房地产", "地产"),
    ("地产", "地产"),
    ("半导体", "半导体"),
    ("芯片", "半导体"),
    ("医药", "医药"),
    ("医疗", "医药"),
    ("生物", "医药"),
    ("食品饮料", "食品饮料"),
    ("白酒", "食品饮料"),
    ("消费", "消费"),
    ("新能源", "新能源"),
    ("光伏", "新能源"),
    ("有色", "有色"),
    ("煤炭", "煤炭"),
    ("钢铁", "钢铁"),
    ("军工", "军工"),
    ("国防", "军工"),
    ("电子", "电子"),
    ("计算机", "计算机"),
    ("信息", "信息技术"),
    ("通信", "通信"),
    ("传媒", "传媒"),
    ("电力", "电力"),
    ("汽车", "汽车"),
    ("机械", "机械"),
    ("农业", "农业"),
    ("化工", "化工"),
    ("建材", "建材"),
    ("建筑装饰", "建筑"),
    ("建筑", "建筑"),
    ("交通运输", "交通"),
    ("交通", "交通"),
    ("公用事业", "公用事业"),
    ("环保", "环保"),
    ("家电", "家电"),
    ("纺织服装", "纺织"),
    ("商贸", "商贸"),
    ("社会服务", "社服"),
    ("综合", "综合"),
    ("金融", "大金融"),
)

# Manual override: code -> (bucket_type, bucket_name). Wins over keyword match.
_MANUAL_OVERRIDE: dict[str, tuple[str, str]] = {
    "510300": ("index", "沪深300"),
    "510050": ("index", "上证50"),
    "510500": ("index", "中证500"),
    "512100": ("index", "中证1000"),
    "588000": ("index", "科创50"),
    "159915": ("index", "创业板指"),
    "563360": ("index", "中证A500"),
}


def classify_etf(code: str, name: str) -> EtfBucketAssignment:
    """Classify an ETF into a sector or broad-index bucket.

    Strategy: manual override (by code) -> index keyword (by name) -> sector keyword (by name) -> other.
    """
    normalized_code = (code or "").strip()
    normalized_name = (name or "").strip()

    if normalized_code in _MANUAL_OVERRIDE:
        bucket_type, bucket_name = _MANUAL_OVERRIDE[normalized_code]
        return EtfBucketAssignment(bucket_type=bucket_type, bucket_name=bucket_name)

    for keyword, bucket in _INDEX_KEYWORDS:
        if keyword in normalized_name:
            return EtfBucketAssignment(bucket_type="index", bucket_name=bucket)

    for keyword, bucket in _SECTOR_KEYWORDS:
        if keyword in normalized_name:
            return EtfBucketAssignment(bucket_type="sector", bucket_name=bucket)

    return EtfBucketAssignment(bucket_type="other", bucket_name="其他")