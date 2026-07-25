# tests/test_etf_sector_mapping.py
# -*- coding: utf-8 -*-
from src.data.etf_sector_mapping import classify_etf, EtfBucketAssignment


def test_classify_sector_by_name_keyword():
    result = classify_etf("512000", "券商ETF华泰")
    assert result.bucket_type == "sector"
    assert result.bucket_name == "券商"


def test_classify_broad_index_by_name_keyword():
    result = classify_etf("510300", "沪深300ETF华泰")
    assert result.bucket_type == "index"
    assert result.bucket_name == "沪深300"


def test_classify_manual_override_takes_priority():
    # 510300 already maps to 沪深300 by name; override to "宽基-沪深300" for testing override path
    result = classify_etf("510300", "沪深300ETF华泰")
    assert result.bucket_type == "index"
    # Override example: code 159919 normally would be unknown, but is嘉实300
    result2 = classify_etf("159919", "300ETF嘉实")
    assert result2.bucket_type == "index"
    assert result2.bucket_name == "沪深300"


def test_classify_unknown_etf_falls_into_other():
    result = classify_etf("588888", "新发未知ETF")
    assert result.bucket_type == "other"
    assert result.bucket_name == "其他"


def test_classify_strip_whitespace_in_name():
    result = classify_etf("512000", "  券商ETF  ")
    assert result.bucket_type == "sector"
    assert result.bucket_name == "券商"