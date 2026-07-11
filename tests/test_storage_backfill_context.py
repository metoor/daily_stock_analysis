# -*- coding: utf-8 -*-
from datetime import date, timedelta

import pandas as pd
import pytest

from src.storage import DatabaseManager, StockDaily


@pytest.fixture
def db_with_bars():
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    target = date(2026, 6, 10)
    rows = []
    for i in range(10):
        d = date(2026, 6, 1) + timedelta(days=i)
        rows.append({
            "date": d,
            "open": 9.0 + i * 0.1,
            "high": 10.0 + i * 0.1,
            "low": 8.5 + i * 0.1,
            "close": 9.5 + i * 0.1,
            "volume": 1000.0 + i * 100,
            "pct_chg": 1.0 + i * 0.1,
            "ma5": 9.0,
            "ma10": 8.8,
            "ma20": 8.5,
        })
    df = pd.DataFrame(rows)
    df["code"] = "600519"
    db.save_daily_data(df, "600519", "test")
    yield db, target
    DatabaseManager.reset_instance()


def test_get_analysis_context_as_of_returns_target_date_bar(db_with_bars):
    db, target = db_with_bars
    ctx = db.get_analysis_context_as_of("600519", target)
    assert ctx is not None
    assert ctx["code"] == "600519"
    assert ctx["date"] == "2026-06-10"
    assert ctx["today"]["date"] == date(2026, 6, 10)
    assert ctx["today"]["close"] == 10.4
    assert ctx["yesterday"]["date"] == date(2026, 6, 9)
    assert ctx["yesterday"]["close"] == 10.3
    assert "ma_status" in ctx


def test_get_analysis_context_as_of_returns_none_when_target_bar_missing(db_with_bars):
    db, target = db_with_bars
    with db.get_session() as session:
        session.query(StockDaily).filter(
            StockDaily.code == "600519",
            StockDaily.date == target,
        ).delete()
        session.commit()
    ctx = db.get_analysis_context_as_of("600519", target)
    assert ctx is None


def test_get_analysis_context_as_of_returns_none_when_no_data(db_with_bars):
    db, target = db_with_bars
    ctx = db.get_analysis_context_as_of("999999", target)
    assert ctx is None
