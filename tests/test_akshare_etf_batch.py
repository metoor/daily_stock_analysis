# -*- coding: utf-8 -*-
import sys
import types
from unittest.mock import MagicMock

import pandas as pd

from data_provider.akshare_fetcher import AkshareFetcher


def _fake_spot_frame() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "代码": "510300", "名称": "沪深300ETF华泰", "最新价": 4.012,
            "IOPV实时估值": 4.015, "基金折价率": -0.07, "涨跌额": 0.02,
            "涨跌幅": 0.50, "成交量": 1000000.0, "成交额": 4012000.0,
            "开盘价": 4.0, "最高价": 4.02, "最低价": 3.99, "昨收": 3.99,
            "振幅": 0.75, "换手率": 0.5, "量比": 1.0, "委比": 0.0,
            "外盘": 500000.0, "内盘": 500000.0,
            "主力净流入-净额": 5000000.0, "主力净流入-净占比": 12.5,
            "超大单净流入-净额": 2000000.0, "超大单净流入-净占比": 5.0,
            "大单净流入-净额": 3000000.0, "大单净流入-净占比": 7.5,
            "中单净流入-净额": -1000000.0, "中单净流入-净占比": -2.5,
            "小单净流入-净额": -4000000.0, "小单净流入-净占比": -10.0,
            "现手": 100, "买一": 4.011, "卖一": 4.013,
            "最新份额": 1500000000.0, "流通市值": 6018000000.0,
            "总市值": 6018000000.0, "数据日期": "2026-07-17",
            "更新时间": "2026-07-17 16:11:40+08:00",
        },
    ])


def test_get_etf_capital_flow_batch_returns_unified_items(monkeypatch):
    fake_ak = types.SimpleNamespace(fund_etf_spot_em=MagicMock(return_value=_fake_spot_frame()))
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)
    fetcher = AkshareFetcher()
    result = fetcher.get_etf_capital_flow_batch()
    assert result["status"] == "ok"
    assert len(result["data"]) == 1
    item = result["data"][0]
    assert item["code"] == "510300"
    assert item["name"] == "沪深300ETF华泰"
    assert item["close"] == 4.012
    assert item["change_pct"] == 0.50
    assert item["main_net_inflow"] == 5000000.0
    assert item["discount_pct"] == -0.07
    assert item["latest_shares"] == 1500000000.0
    assert item["total_market_value"] == 6018000000.0
    assert item["trade_date"] == "2026-07-17"
    assert result["source_chain"][0]["provider"] == "akshare"
    assert result["source_chain"][0]["result"] == "ok"


def test_get_etf_capital_flow_batch_handles_missing_optional_fields(monkeypatch):
    frame = _fake_spot_frame()
    frame.loc[0, "基金折价率"] = float("nan")
    frame.loc[0, "最新份额"] = None
    fake_ak = types.SimpleNamespace(fund_etf_spot_em=MagicMock(return_value=frame))
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)
    fetcher = AkshareFetcher()
    result = fetcher.get_etf_capital_flow_batch()
    assert result["status"] == "ok"
    item = result["data"][0]
    assert item["discount_pct"] is None
    assert item["latest_shares"] is None


def test_get_etf_capital_flow_batch_returns_failed_on_exception(monkeypatch):
    fake_ak = types.SimpleNamespace(
        fund_etf_spot_em=MagicMock(side_effect=RuntimeError("network down"))
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)
    fetcher = AkshareFetcher()
    result = fetcher.get_etf_capital_flow_batch()
    assert result["status"] == "failed"
    assert result["data"] == []
    assert any("network down" in err for err in result["errors"])
    assert result["source_chain"][0]["result"] == "failed"