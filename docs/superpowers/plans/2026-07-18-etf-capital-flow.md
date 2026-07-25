# ETF 场内资金流分析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily ETF capital-flow intelligence pipeline (A 股场内 ETF) that produces three views (A 板块轮动 / B 宽基动向 / C 全市场总览), persists daily JSON snapshots, injects a structured block into the market-review report, and exposes a Web dashboard.

**Architecture:** Mirror the `intelligence` module pattern (service + endpoints + schemas + repository + ORM) and the `get_capital_flow_context` block pattern (`status / source_chain / warnings`, fail-open). All ETF data comes from a single akshare batch call (`fund_etf_spot_em`) with efinance as fallback; classification is keyword + manual override; aggregation follows "absolute-sum, ratio-weighted-average" rule.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy (SQLite) / akshare / pytest. React + TypeScript / Vite / recharts / vitest + @testing-library/react.

## Global Constraints

- **ETF detection**: `_is_etf_code` from `data_provider/base.py:200` (prefix tuple `("51","52","56","58","15","16","18")`). Reuse, do not redefine.
- **fail-open**: A data source failure must produce `status: "partial"` or `"failed"` with `warnings`, never raise through the market-review main flow (per AGENTS.md §7).
- **Aggregation rule** (from design §3): absolute-quantity metrics (净流入额, 份额变动额) use **SUM**; ratio/strength metrics (涨幅%, 净流入率%, 折溢价%, 份额变动率%) use **总市值-weighted average**. Never simple average.
- **Top-N selection**: per bucket, sort by `总市值` desc, apply liquidity floor (成交额 > 0), take top 10. No extra per-ETF requests.
- **No fabrication**: missing fields (折溢价, 份额变动 on first day) must be marked `null` with a `missing` flag in `warnings`, never zero-filled.
- **Persistence**: one SQLite row per (date) storing a JSON payload column. Auto-created via `Base.metadata.create_all` (existing pattern in `src/storage.py:1182`).
- **Field naming**: API responses use `snake_case`; frontend converts to `camelCase` via existing `toCamelCase` util.
- **Backwards compatibility**: existing `get_capital_flow_context` for individual stocks must remain unchanged. ETF batch path is a new method, not a modification of the existing one.
- **Commit messages**: English, no `Co-Authored-By`. PR title format `<类型>: <修改内容>` (per AGENTS.md §1.1).
- **Documentation**: update `docs/CHANGELOG.md` `[Unreleased]` with flat-format entries; create `docs/etf-capital-flow.md` for user-facing details.

---

## File Structure

### Backend (Python)

| File | Action | Responsibility |
|---|---|---|
| `src/data/etf_sector_mapping.py` | Create | Classify ETF code+name -> `{bucket_type, bucket_name}`. Keyword-based + manual override dict. |
| `src/data/__init__.py` | Create (if missing) | Package marker. |
| `data_provider/akshare_fetcher.py` | Modify | Add `get_etf_capital_flow_batch()` returning list of unified ETF snapshot dicts. |
| `data_provider/efinance_fetcher.py` | Modify | Add `get_etf_capital_flow_batch()` fallback (best-effort, may return empty). |
| `data_provider/base.py` | Modify | Add `DataFetcherManager.get_etf_capital_flow_context()` composing akshare+efinance with fail-open block. |
| `src/services/etf_capital_flow_service.py` | Create | Orchestrate: fetch -> classify -> top10 -> aggregate -> produce A/B/C views -> persist. |
| `src/repositories/etf_capital_flow_repo.py` | Create | `save_snapshot`, `get_snapshot`, `get_snapshots_range`. |
| `src/storage.py` | Modify | Add `EtfCapitalFlowSnapshot` ORM model. |
| `api/v1/schemas/etf_capital_flow.py` | Create | Pydantic models for API responses. |
| `api/v1/endpoints/etf_capital_flow.py` | Create | GET `/latest`, GET `/{date}`, GET `/range`. |
| `api/v1/router.py` | Modify | Register new router with prefix `/etf-capital-flow`. |
| `src/market_analyzer.py` | Modify | Inject ETF block into review prompt + structured table via `_inject_data_into_review`. |
| `src/core/market_review.py` | Modify | Compute ETF analysis before LLM call; pass to analyzer. |

### Frontend (TypeScript / React)

| File | Action | Responsibility |
|---|---|---|
| `apps/dsa-web/src/types/etfCapitalFlow.ts` | Create | TypeScript types mirroring backend schemas. |
| `apps/dsa-web/src/api/etfCapitalFlow.ts` | Create | `etfCapitalFlowApi` with `getLatest`, `getByDate`, `getRange`. |
| `apps/dsa-web/src/components/etf-flow/EtfKpiBar.tsx` | Create | Top KPI strip (net inflow total, sector counts, leader, source badge). |
| `apps/dsa-web/src/components/etf-flow/EtfTopFlowChart.tsx` | Create | Bidirectional bar chart (top 10 inflow vs outflow). |
| `apps/dsa-web/src/components/etf-flow/EtfSectorHeatmap.tsx` | Create | Sector × day heatmap (last 10 days). |
| `apps/dsa-web/src/components/etf-flow/EtfBroadIndexCard.tsx` | Create | Broad-based index cards (300/A500/500/1000/科创50/创业板). |
| `apps/dsa-web/src/components/etf-flow/EtfBucketDetail.tsx` | Create | Expandable bucket detail (top 10 members + mini trend). |
| `apps/dsa-web/src/pages/EtfCapitalFlowPage.tsx` | Create | Dashboard page composing the above. |
| `apps/dsa-web/src/pages/__tests__/EtfCapitalFlowPage.test.tsx` | Create | vitest + RTL tests. |
| `apps/dsa-web/src/App.tsx` | Modify | Add `/etf-flow` route. |
| `apps/dsa-web/src/components/layout/SidebarNav.tsx` | Modify | Add nav entry. |
| `apps/dsa-web/src/i18n/uiText.ts` | Modify | Add `etfFlow.*` keys (zh + en). |

### Tests

| File | Action |
|---|---|
| `tests/test_etf_sector_mapping.py` | Create |
| `tests/test_etf_capital_flow_service.py` | Create |
| `tests/test_etf_capital_flow_repo.py` | Create |
| `tests/test_etf_capital_flow_api.py` | Create |
| `tests/test_etf_capital_flow_injection.py` | Create |

### Docs

| File | Action |
|---|---|
| `docs/etf-capital-flow.md` | Create |
| `docs/CHANGELOG.md` | Modify |

---

## Task 1: ETF Sector/Index Classifier

**Files:**
- Create: `src/data/__init__.py` (empty file)
- Create: `src/data/etf_sector_mapping.py`
- Test: `tests/test_etf_sector_mapping.py`

**Interfaces:**
- Consumes: ETF `code: str` and `name: str`.
- Produces: `classify_etf(code: str, name: str) -> EtfBucketAssignment` where `EtfBucketAssignment` is a dataclass with `bucket_type: Literal["sector","index","other"]` and `bucket_name: str`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etf_sector_mapping.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.data.etf_sector_mapping'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etf_sector_mapping.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/data/__init__.py src/data/etf_sector_mapping.py tests/test_etf_sector_mapping.py
git commit -m "feat: add ETF sector/index classifier with keyword + manual override"
```

---

## Task 2: akshare ETF Batch Fetcher

**Files:**
- Modify: `data_provider/akshare_fetcher.py` (add method to `AkshareFetcher` class)
- Test: `tests/test_akshare_etf_batch.py`

**Interfaces:**
- Consumes: `ak.fund_etf_spot_em()` returning a pandas DataFrame with columns including `代码, 名称, 最新价, IOPV实时估值, 基金折价率, 涨跌幅, 成交量, 成交额, 主力净流入-净额, 主力净流入-净占比, 最新份额, 总市值, 流通市值, 数据日期`.
- Produces: `AkshareFetcher.get_etf_capital_flow_batch() -> Dict[str, Any]` with shape:
  ```python
  {
      "status": "ok" | "partial" | "failed",
      "data": List[EtfBatchItem],  # see below
      "source_chain": [{"provider": "akshare", "result": "ok"|"failed", "duration_ms": int}],
      "errors": List[str],
  }
  ```
  where `EtfBatchItem` is a TypedDict:
  ```python
  {
      "code": str, "name": str, "close": float, "iopv": Optional[float],
      "discount_pct": Optional[float], "change_pct": float, "volume": float,
      "turnover": float, "main_net_inflow": float, "main_net_inflow_pct": Optional[float],
      "latest_shares": Optional[float], "total_market_value": Optional[float],
      "circulating_market_value": Optional[float], "trade_date": str,  # YYYY-MM-DD
  }
  ```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_akshare_etf_batch.py
# -*- coding: utf-8 -*-
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
    monkeypatch.setattr("data_provider.akshare_fetcher.ak", fake_ak, raising=False)
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
    monkeypatch.setattr("data_provider.akshare_fetcher.ak", fake_ak, raising=False)
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
    monkeypatch.setattr("data_provider.akshare_fetcher.ak", fake_ak, raising=False)
    fetcher = AkshareFetcher()
    result = fetcher.get_etf_capital_flow_batch()
    assert result["status"] == "failed"
    assert result["data"] == []
    assert any("network down" in err for err in result["errors"])
    assert result["source_chain"][0]["result"] == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_akshare_etf_batch.py -v`
Expected: FAIL with `AttributeError: 'AkshareFetcher' object has no attribute 'get_etf_capital_flow_batch'`

- [ ] **Step 3: Write minimal implementation**

Add the following method to `AkshareFetcher` in `data_provider/akshare_fetcher.py`. Place it near `_get_etf_realtime_quote` (around line 1357) since they share the `fund_etf_spot_em` call but operate differently — the new method returns the full batch, not a single quote, and bypasses the realtime cache.

```python
# In data_provider/akshare_fetcher.py, add to AkshareFetcher class:

def get_etf_capital_flow_batch(self) -> Dict[str, Any]:
    """Fetch the full A-share ETF spot batch with capital-flow fields.

    Single call to ak.fund_etf_spot_em() returns ~1500 ETFs with:
    主力净流入-净额, 基金折价率, 最新份额, 总市值, etc.

    Returns a fail-open block: never raises.
    """
    import time as _time
    import akshare as ak
    import math

    errors: List[str] = []
    source_chain: List[Dict[str, Any]] = []
    df: Optional[pd.DataFrame] = None
    api_start = _time.time()

    try:
        self._set_random_user_agent()
        self._enforce_rate_limit()
        df = ak.fund_etf_spot_em()
        elapsed_ms = int((_time.time() - api_start) * 1000)
        source_chain.append({"provider": "akshare", "result": "ok", "duration_ms": elapsed_ms})
    except Exception as exc:
        elapsed_ms = int((_time.time() - api_start) * 1000)
        source_chain.append({"provider": "akshare", "result": "failed", "duration_ms": elapsed_ms})
        errors.append(f"akshare fund_etf_spot_em failed: {exc}")
        return {"status": "failed", "data": [], "source_chain": source_chain, "errors": errors}

    if df is None or df.empty:
        errors.append("akshare fund_etf_spot_em returned empty frame")
        return {"status": "failed", "data": [], "source_chain": source_chain, "errors": errors}

    items: List[Dict[str, Any]] = []
    parse_errors: List[str] = []

    def _parse_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            f = float(value)
            if math.isnan(f) or math.isinf(f):
                return None
            return f
        except (TypeError, ValueError):
            return None

    for _, row in df.iterrows():
        try:
            code = str(row.get("代码", "")).strip()
            if not code:
                continue
            name = str(row.get("名称", "")).strip()
            trade_date_raw = str(row.get("数据日期", "")).strip()
            trade_date = trade_date_raw[:10] if trade_date_raw else ""

            item = {
                "code": code,
                "name": name,
                "close": _parse_float(row.get("最新价")) or 0.0,
                "iopv": _parse_float(row.get("IOPV实时估值")),
                "discount_pct": _parse_float(row.get("基金折价率")),
                "change_pct": _parse_float(row.get("涨跌幅")) or 0.0,
                "volume": _parse_float(row.get("成交量")) or 0.0,
                "turnover": _parse_float(row.get("成交额")) or 0.0,
                "main_net_inflow": _parse_float(row.get("主力净流入-净额")) or 0.0,
                "main_net_inflow_pct": _parse_float(row.get("主力净流入-净占比")),
                "latest_shares": _parse_float(row.get("最新份额")),
                "total_market_value": _parse_float(row.get("总市值")),
                "circulating_market_value": _parse_float(row.get("流通市值")),
                "trade_date": trade_date,
            }
            items.append(item)
        except Exception as exc:
            parse_errors.append(f"row parse failed for code={row.get('代码')}: {exc}")

    status = "ok" if items and not parse_errors else ("partial" if items else "failed")
    return {
        "status": status,
        "data": items,
        "source_chain": source_chain,
        "errors": errors + parse_errors,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_akshare_etf_batch.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add data_provider/akshare_fetcher.py tests/test_akshare_etf_batch.py
git commit -m "feat: add akshare ETF capital flow batch fetcher"
```

---

## Task 3: Aggregation Pure Functions

**Files:**
- Create: `src/services/etf_capital_flow_aggregator.py`
- Test: `tests/test_etf_capital_flow_aggregator.py`

**Interfaces:**
- Consumes: `List[EtfBatchItem]` (the unified dicts from Task 2), `EtfBucketAssignment` (from Task 1).
- Produces:
  - `select_top_n_by_scale(items: List[Dict], n: int = 10, liquidity_floor: float = 0.0) -> List[Dict]`
  - `aggregate_bucket(members: List[Dict]) -> Dict[str, Any]` returning `{bucket_name, member_count, total_scale, net_inflow_sum, weighted_change_pct, weighted_discount_pct, weighted_share_change_pct, share_change_sum}`
  - `compute_consecutive_inflow_days(daily_net_inflows: List[float]) -> int` (positive = inflow streak, negative = outflow streak)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_etf_capital_flow_aggregator.py
# -*- coding: utf-8 -*-
from src.services.etf_capital_flow_aggregator import (
    select_top_n_by_scale,
    aggregate_bucket,
    compute_consecutive_inflow_days,
)


def _item(code: str, scale: float, inflow: float, change_pct: float, discount: float, shares: float, turnover: float = 100.0):
    return {
        "code": code, "name": f"ETF{code}", "close": 1.0,
        "total_market_value": scale, "main_net_inflow": inflow,
        "change_pct": change_pct, "discount_pct": discount,
        "latest_shares": shares, "share_change": None,  # filled by service layer
        "turnover": turnover,
    }


def test_select_top_n_by_scale_picks_largest():
    items = [_item("a", 100), _item("b", 500), _item("c", 300)]
    result = select_top_n_by_scale(items, n=2)
    assert [r["code"] for r in result] == ["b", "c"]


def test_select_top_n_filters_low_liquidity():
    items = [_item("a", 100, turnover=0.0), _item("b", 50, turnover=10.0)]
    result = select_top_n_by_scale(items, n=10, liquidity_floor=1.0)
    assert [r["code"] for r in result] == ["b"]


def test_aggregate_bucket_sums_absolute_quantities():
    members = [
        _item("a", scale=100, inflow=10, change_pct=1.0, discount=0.5, shares=1000),
        _item("b", scale=300, inflow=20, change_pct=2.0, discount=-0.5, shares=2000),
    ]
    result = aggregate_bucket(members, bucket_name="券商", bucket_type="sector")
    assert result["bucket_name"] == "券商"
    assert result["bucket_type"] == "sector"
    assert result["member_count"] == 2
    assert result["total_scale"] == 400
    assert result["net_inflow_sum"] == 30
    assert result["share_change_sum"] is None  # no share_change data yet


def test_aggregate_bucket_weighted_average_by_scale():
    # 100@1.0% + 300@2.0% -> weighted avg = (100*1 + 300*2)/400 = 700/400 = 1.75
    members = [
        _item("a", scale=100, inflow=10, change_pct=1.0, discount=0.5, shares=1000),
        _item("b", scale=300, inflow=20, change_pct=2.0, discount=-0.5, shares=2000),
    ]
    result = aggregate_bucket(members, bucket_name="券商", bucket_type="sector")
    assert abs(result["weighted_change_pct"] - 1.75) < 1e-9
    # discount: (100*0.5 + 300*-0.5)/400 = (50 - 150)/400 = -0.25
    assert abs(result["weighted_discount_pct"] - (-0.25)) < 1e-9


def test_aggregate_bucket_skips_missing_optional_fields():
    members = [
        _item("a", scale=100, inflow=10, change_pct=1.0, discount=0.5, shares=1000),
        _item("b", scale=300, inflow=20, change_pct=2.0, discount=None, shares=2000),
    ]
    result = aggregate_bucket(members, bucket_name="半导体", bucket_type="sector")
    # Only member "a" has discount; weighted by its own scale
    assert result["weighted_discount_pct"] == 0.5


def test_aggregate_bucket_with_share_change():
    members = [
        {**_item("a", scale=100, inflow=10, change_pct=1.0, discount=0.5, shares=1000), "share_change": 100},
        {**_item("b", scale=300, inflow=20, change_pct=2.0, discount=-0.5, shares=2000), "share_change": 200},
    ]
    result = aggregate_bucket(members, bucket_name="沪深300", bucket_type="index")
    assert result["share_change_sum"] == 300
    # share_change_rate = share_change / latest_shares
    # a: 100/1000 = 0.1, b: 200/2000 = 0.1 -> weighted = 0.1
    assert abs(result["weighted_share_change_pct"] - 0.1) < 1e-9


def test_aggregate_bucket_empty_members_returns_zeros():
    result = aggregate_bucket([], bucket_name="空", bucket_type="sector")
    assert result["member_count"] == 0
    assert result["total_scale"] == 0
    assert result["net_inflow_sum"] == 0


def test_compute_consecutive_inflow_days_positive_streak_at_end():
    # last 3 days positive -> +3
    daily = [-1.0, 1.0, 2.0, 3.0]
    assert compute_consecutive_inflow_days(daily) == 3


def test_compute_consecutive_inflow_days_negative_streak_at_end():
    daily = [1.0, -1.0, -2.0]
    assert compute_consecutive_inflow_days(daily) == -2


def test_compute_consecutive_inflow_days_empty():
    assert compute_consecutive_inflow_days([]) == 0


def test_compute_consecutive_inflow_days_zero_treated_as_break():
    daily = [1.0, 0.0, 2.0]
    assert compute_consecutive_inflow_days(daily) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etf_capital_flow_aggregator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.etf_capital_flow_aggregator'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/services/etf_capital_flow_aggregator.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etf_capital_flow_aggregator.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/etf_capital_flow_aggregator.py tests/test_etf_capital_flow_aggregator.py
git commit -m "feat: add ETF capital flow aggregation pure functions"
```

---

## Task 4: ORM Model + Repository

**Files:**
- Modify: `src/storage.py` (add `EtfCapitalFlowSnapshot` class)
- Create: `src/repositories/etf_capital_flow_repo.py`
- Test: `tests/test_etf_capital_flow_repo.py`

**Interfaces:**
- Consumes: `DatabaseManager.get_instance()` (existing pattern in `src/storage.py`).
- Produces: `EtfCapitalFlowRepository` with:
  - `save_snapshot(trade_date: str, payload: Dict[str, Any]) -> None` (upsert by trade_date)
  - `get_snapshot(trade_date: str) -> Optional[Dict[str, Any]]`
  - `get_latest_snapshot() -> Optional[Dict[str, Any]]`
  - `get_snapshots_range(start_date: str, end_date: str) -> List[Dict[str, Any]]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_etf_capital_flow_repo.py
# -*- coding: utf-8 -*-
import os

import pytest

from src.config import Config
from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
from src.storage import DatabaseManager, EtfCapitalFlowSnapshot


@pytest.fixture()
def isolated_db(tmp_path):
    """Mirror tests/test_decision_signal_repo.py:isolate_db pattern."""
    old_database_path = os.environ.get("DATABASE_PATH")
    db_path = tmp_path / "etf_capital_flow_repo.db"
    os.environ["DATABASE_PATH"] = str(db_path)
    Config.reset_instance()
    DatabaseManager.reset_instance()
    db = DatabaseManager.get_instance()
    try:
        yield db
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        if old_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = old_database_path


@pytest.fixture
def repo(isolated_db):
    return EtfCapitalFlowRepository(db_manager=isolated_db)


def test_save_and_get_snapshot(repo):
    payload = {"trade_date": "2026-07-17", "buckets": [], "status": "ok"}
    repo.save_snapshot("2026-07-17", payload)
    result = repo.get_snapshot("2026-07-17")
    assert result is not None
    assert result["trade_date"] == "2026-07-17"
    assert result["status"] == "ok"


def test_save_snapshot_upserts_same_date(repo):
    repo.save_snapshot("2026-07-17", {"status": "ok", "v": 1})
    repo.save_snapshot("2026-07-17", {"status": "ok", "v": 2})
    result = repo.get_snapshot("2026-07-17")
    assert result["v"] == 2


def test_get_snapshot_missing_returns_none(repo):
    assert repo.get_snapshot("2026-01-01") is None


def test_get_latest_snapshot(repo):
    repo.save_snapshot("2026-07-16", {"status": "ok", "trade_date": "2026-07-16"})
    repo.save_snapshot("2026-07-17", {"status": "ok", "trade_date": "2026-07-17"})
    repo.save_snapshot("2026-07-15", {"status": "ok", "trade_date": "2026-07-15"})
    result = repo.get_latest_snapshot()
    assert result["trade_date"] == "2026-07-17"


def test_get_snapshots_range(repo):
    for d in ["2026-07-15", "2026-07-16", "2026-07-17", "2026-07-18"]:
        repo.save_snapshot(d, {"trade_date": d, "status": "ok"})
    result = repo.get_snapshots_range("2026-07-16", "2026-07-17")
    assert len(result) == 2
    assert {r["trade_date"] for r in result} == {"2026-07-16", "2026-07-17"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etf_capital_flow_repo.py -v`
Expected: FAIL with `ImportError: cannot import name 'EtfCapitalFlowSnapshot'` or `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

First, add the ORM model to `src/storage.py`. Insert after the `IntelligenceItem` class (around line 273), before `FundamentalSnapshot`:

```python
# In src/storage.py, add new ORM class:

class EtfCapitalFlowSnapshot(Base):
    """每日 ETF 资金流分析快照（方案 A 轻量持久化）。"""

    __tablename__ = 'etf_capital_flow_snapshots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, unique=True, index=True)
    payload = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default='ok', index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)

    def __repr__(self) -> str:
        return f"<EtfCapitalFlowSnapshot(trade_date={self.trade_date}, status={self.status})>"
```

Then create the repository:

```python
# src/repositories/etf_capital_flow_repo.py
# -*- coding: utf-8 -*-
"""Repository for daily ETF capital-flow snapshots."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.storage import DatabaseManager, EtfCapitalFlowSnapshot

logger = logging.getLogger(__name__)


class EtfCapitalFlowRepository:
    """DB access layer for daily ETF capital-flow snapshots."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def save_snapshot(self, trade_date: str, payload: Dict[str, Any]) -> None:
        """Upsert a daily snapshot by trade_date."""
        status = str(payload.get("status") or "ok")
        payload_json = json.dumps(payload, ensure_ascii=False, default=str)
        with self.db.get_session() as session:
            stmt = sqlite_insert(EtfCapitalFlowSnapshot).values(
                trade_date=trade_date,
                payload=payload_json,
                status=status,
                updated_at=datetime.now(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["trade_date"],
                set_={
                    "payload": stmt.excluded.payload,
                    "status": stmt.excluded.status,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            session.execute(stmt)
            session.commit()

    def get_snapshot(self, trade_date: str) -> Optional[Dict[str, Any]]:
        with self.db.get_session() as session:
            row = session.execute(
                select(EtfCapitalFlowSnapshot)
                .where(EtfCapitalFlowSnapshot.trade_date == trade_date)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._row_to_dict(row)

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        with self.db.get_session() as session:
            row = session.execute(
                select(EtfCapitalFlowSnapshot)
                .order_by(desc(EtfCapitalFlowSnapshot.trade_date))
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._row_to_dict(row)

    def get_snapshots_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(EtfCapitalFlowSnapshot)
                .where(EtfCapitalFlowSnapshot.trade_date >= start_date)
                .where(EtfCapitalFlowSnapshot.trade_date <= end_date)
                .order_by(EtfCapitalFlowSnapshot.trade_date.asc())
            ).scalars().all()
            return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row: EtfCapitalFlowSnapshot) -> Dict[str, Any]:
        try:
            payload = json.loads(row.payload) if row.payload else {}
        except json.JSONDecodeError:
            logger.warning("invalid JSON payload for etf snapshot trade_date=%s", row.trade_date)
            payload = {}
        return {
            "trade_date": row.trade_date,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            **payload,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etf_capital_flow_repo.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/storage.py src/repositories/etf_capital_flow_repo.py tests/test_etf_capital_flow_repo.py
git commit -m "feat: add ETF capital flow snapshot ORM model and repository"
```

---

## Task 5: ETF Capital Flow Service

**Files:**
- Create: `src/services/etf_capital_flow_service.py`
- Test: `tests/test_etf_capital_flow_service.py`

**Interfaces:**
- Consumes:
  - `DataFetcherManager.get_etf_capital_flow_context()` (will be added in Task 6; for testing, inject a callable)
  - `classify_etf` from Task 1
  - `select_top_n_by_scale`, `aggregate_bucket`, `compute_consecutive_inflow_days` from Task 3
  - `EtfCapitalFlowRepository` from Task 4
- Produces: `EtfCapitalFlowService.run_daily() -> Dict[str, Any]` returning the daily result payload (and persists it).

The daily payload shape (stored in DB):
```python
{
    "trade_date": "2026-07-17",
    "status": "ok" | "partial" | "failed",
    "source_chain": [...],
    "warnings": [...],
    "market_overview": {  # C view
        "total_net_inflow": float,
        "inflow_count": int,
        "outflow_count": int,
        "top_inflow": [...],  # top 10 ETFs by net inflow
        "top_outflow": [...],
    },
    "sector_buckets": [...],  # A view - aggregated buckets
    "index_buckets": [...],   # B view
    "details": [...],  # top 10 members per bucket (for drill-down)
}
```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_etf_capital_flow_service.py
# -*- coding: utf-8 -*-
from unittest.mock import MagicMock

import pytest

from src.services.etf_capital_flow_service import EtfCapitalFlowService


def _batch_item(code, name, scale, inflow, change, discount, shares, turnover=100.0):
    return {
        "code": code, "name": name, "close": 1.0,
        "iopv": None, "discount_pct": discount, "change_pct": change,
        "volume": 1000.0, "turnover": turnover,
        "main_net_inflow": inflow, "main_net_inflow_pct": None,
        "latest_shares": shares, "share_change": None,
        "total_market_value": scale, "circulating_market_value": scale,
        "trade_date": "2026-07-17",
    }


@pytest.fixture
def fake_fetcher():
    fetcher = MagicMock()
    fetcher.return_value = {
        "status": "ok",
        "data": [
            # 券商 bucket
            _batch_item("512000", "券商ETF华泰", scale=500, inflow=10, change=1.0, discount=0.5, shares=1000),
            _batch_item("512880", "证券ETF指数", scale=300, inflow=5, change=0.5, discount=0.3, shares=800),
            # 沪深300 bucket
            _batch_item("510300", "沪深300ETF华泰", scale=2000, inflow=50, change=0.8, discount=-0.1, shares=5000),
            # 未分类
            _batch_item("588888", "新主题ETF", scale=10, inflow=1, change=2.0, discount=None, shares=100),
        ],
        "source_chain": [{"provider": "akshare", "result": "ok", "duration_ms": 100}],
        "errors": [],
    }
    return fetcher


def test_run_daily_persists_and_returns_payload(fake_fetcher, isolated_db):
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
    repo = EtfCapitalFlowRepository(db_manager=isolated_db)

    service = EtfCapitalFlowService(fetcher=fake_fetcher, repository=repo)
    result = service.run_daily()

    assert result["status"] == "ok"
    assert result["trade_date"] == "2026-07-17"
    # Sector bucket "券商" should have 2 members
    sector_names = [b["bucket_name"] for b in result["sector_buckets"]]
    assert "券商" in sector_names
    broker_bucket = next(b for b in result["sector_buckets"] if b["bucket_name"] == "券商")
    assert broker_bucket["member_count"] == 2
    assert broker_bucket["net_inflow_sum"] == 15
    # Index bucket "沪深300"
    index_names = [b["bucket_name"] for b in result["index_buckets"]]
    assert "沪深300" in index_names
    # C view: total net inflow = 10+5+50+1 = 66
    assert result["market_overview"]["total_net_inflow"] == 66
    assert result["market_overview"]["inflow_count"] == 4
    # Persisted
    persisted = repo.get_snapshot("2026-07-17")
    assert persisted is not None
    assert persisted["trade_date"] == "2026-07-17"


def test_run_daily_marks_share_change_missing_when_no_history(fake_fetcher, isolated_db):
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
    repo = EtfCapitalFlowRepository(db_manager=isolated_db)

    service = EtfCapitalFlowService(fetcher=fake_fetcher, repository=repo)
    result = service.run_daily()
    broker_bucket = next(b for b in result["sector_buckets"] if b["bucket_name"] == "券商")
    # No previous snapshot -> share_change_sum should be None
    assert broker_bucket["share_change_sum"] is None
    assert any("share_change" in w for w in result["warnings"])


def test_run_daily_computes_share_change_from_previous_snapshot(fake_fetcher, isolated_db):
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
    repo = EtfCapitalFlowRepository(db_manager=isolated_db)

    # Seed previous day snapshot with shares
    prev_payload = {
        "trade_date": "2026-07-16",
        "status": "ok",
        "warnings": [],
        "market_overview": {},
        "sector_buckets": [],
        "index_buckets": [],
        "details": [
            {"code": "512000", "latest_shares": 950},
            {"code": "510300", "latest_shares": 4900},
        ],
    }
    repo.save_snapshot("2026-07-16", prev_payload)

    service = EtfCapitalFlowService(fetcher=fake_fetcher, repository=repo)
    result = service.run_daily()
    # share_change for 512000 = 1000 - 950 = 50
    detail_512000 = next(d for d in result["details"] if d["code"] == "512000")
    assert detail_512000["share_change"] == 50


def test_run_daily_fail_open_when_fetcher_fails(isolated_db):
    from src.repositories.etf_capital_flow_repo import EtfCapitalFlowRepository
    repo = EtfCapitalFlowRepository(db_manager=isolated_db)

    failing_fetcher = MagicMock(return_value={
        "status": "failed",
        "data": [],
        "source_chain": [{"provider": "akshare", "result": "failed", "duration_ms": 0}],
        "errors": ["network down"],
    })
    service = EtfCapitalFlowService(fetcher=failing_fetcher, repository=repo)
    result = service.run_daily()
    assert result["status"] == "failed"
    assert "network down" in result["warnings"]
    assert result["sector_buckets"] == []
    assert result["index_buckets"] == []


# Add this fixture at the bottom of the test file (mirror tests/test_decision_signal_repo.py):
@pytest.fixture()
def isolated_db(tmp_path):
    import os
    from src.config import Config
    from src.storage import DatabaseManager
    old_database_path = os.environ.get("DATABASE_PATH")
    db_path = tmp_path / "etf_capital_flow_service.db"
    os.environ["DATABASE_PATH"] = str(db_path)
    Config.reset_instance()
    DatabaseManager.reset_instance()
    db = DatabaseManager.get_instance()
    try:
        yield db
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        if old_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = old_database_path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etf_capital_flow_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.etf_capital_flow_service'`

- [ ] **Step 3: Write minimal implementation**

```python
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
    compute_consecutive_inflow_days,
    select_top_n_by_scale,
)

logger = logging.getLogger(__name__)

TOP_N_PER_BUCKET = 10
LIQUIDITY_FLOOR = 1_000_000  # 1M 成交额 floor


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
        sorted_by_inflow = sorted(items, key=lambda x: x.get("main_net_inflow") or 0.0, reverse=True)
        top_inflow = [self._ranking_item(m) for m in sorted_by_inflow[:10]]
        top_outflow = [self._ranking_item(m) for m in sorted_by_inflow[-10:][::-1]]
        inflow_count = sum(1 for m in items if (m.get("main_net_inflow") or 0.0) > 0)
        outflow_count = sum(1 for m in items if (m.get("main_net_inflow") or 0.0) < 0)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etf_capital_flow_service.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/etf_capital_flow_service.py tests/test_etf_capital_flow_service.py
git commit -m "feat: add ETF capital flow orchestration service"
```

---

## Task 6: DataFetcherManager.get_etf_capital_flow_context()

**Files:**
- Modify: `data_provider/base.py` (add method to `DataFetcherManager`)
- Test: `tests/test_etf_capital_flow_context.py`

**Interfaces:**
- Consumes: `AkshareFetcher.get_etf_capital_flow_batch()` (from Task 2), `EfinanceFetcher.get_etf_capital_flow_batch()` (will add in this task as a stub fallback).
- Produces: `DataFetcherManager.get_etf_capital_flow_context() -> Dict[str, Any]` with same shape as `EtfCapitalFlowService` fetcher input:
  ```python
  {"status": "ok"|"partial"|"failed", "data": [...], "source_chain": [...], "errors": [...]}
  ```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_etf_capital_flow_context.py
# -*- coding: utf-8 -*-
from unittest.mock import MagicMock

from data_provider.base import DataFetcherManager


def _build_manager_with_fetchers(akshare_block, efinance_block):
    """Build a DataFetcherManager with mocked fetchers in _fetchers_by_name."""
    manager = DataFetcherManager.__new__(DataFetcherManager)
    manager._fetchers_by_name = {}
    manager._fetchers = []
    manager._fetchers_lock = MagicMock()

    mock_akshare = MagicMock()
    mock_akshare.get_etf_capital_flow_batch.return_value = akshare_block
    mock_efinance = MagicMock()
    mock_efinance.get_etf_capital_flow_batch.return_value = efinance_block

    manager._fetchers_by_name["AkshareFetcher"] = mock_akshare
    manager._fetchers_by_name["EfinanceFetcher"] = mock_efinance
    return manager


def test_get_etf_capital_flow_context_uses_akshare_first():
    manager = _build_manager_with_fetchers(
        akshare_block={
            "status": "ok", "data": [{"code": "510300"}],
            "source_chain": [{"provider": "akshare", "result": "ok", "duration_ms": 50}],
            "errors": [],
        },
        efinance_block={"status": "failed", "data": [], "source_chain": [], "errors": []},
    )
    result = manager.get_etf_capital_flow_context()
    assert result["status"] == "ok"
    assert len(result["data"]) == 1
    # Efinance should not be called when akshare succeeds
    manager._fetchers_by_name["EfinanceFetcher"].get_etf_capital_flow_batch.assert_not_called()


def test_get_etf_capital_flow_context_falls_back_to_efinance():
    manager = _build_manager_with_fetchers(
        akshare_block={
            "status": "failed", "data": [],
            "source_chain": [{"provider": "akshare", "result": "failed", "duration_ms": 0}],
            "errors": ["akshare down"],
        },
        efinance_block={
            "status": "ok", "data": [{"code": "510300"}],
            "source_chain": [{"provider": "efinance", "result": "ok", "duration_ms": 80}],
            "errors": [],
        },
    )
    result = manager.get_etf_capital_flow_context()
    assert result["status"] == "ok"
    assert len(result["data"]) == 1
    # source_chain should include both attempts
    providers = [s["provider"] for s in result["source_chain"]]
    assert "akshare" in providers
    assert "efinance" in providers


def test_get_etf_capital_flow_context_all_fail_returns_failed():
    manager = _build_manager_with_fetchers(
        akshare_block={"status": "failed", "data": [], "source_chain": [], "errors": ["akshare down"]},
        efinance_block={"status": "failed", "data": [], "source_chain": [], "errors": ["efinance down"]},
    )
    result = manager.get_etf_capital_flow_context()
    assert result["status"] == "failed"
    assert result["data"] == []
    assert any("akshare down" in e for e in result["errors"])
    assert any("efinance down" in e for e in result["errors"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etf_capital_flow_context.py -v`
Expected: FAIL with `AttributeError: 'DataFetcherManager' object has no attribute 'get_etf_capital_flow_context'`

- [ ] **Step 3: Write minimal implementation**

First, add a stub `get_etf_capital_flow_batch()` to `EfinanceFetcher` in `data_provider/efinance_fetcher.py` (returns failed - we don't implement the actual efinance ETF batch call in this iteration; the design says "efinance 兜底" but efinance lacks a direct equivalent; mark as `not_implemented`):

```python
# In data_provider/efinance_fetcher.py, add to EfinanceFetcher class:

def get_etf_capital_flow_batch(self) -> Dict[str, Any]:
    """Efinance does not expose an ETF spot batch with capital-flow fields.

    Returns a failed block so DataFetcherManager can compose source_chain
    consistently; the akshare primary path is the only viable source.
    """
    return {
        "status": "failed",
        "data": [],
        "source_chain": [{"provider": "efinance", "result": "not_implemented", "duration_ms": 0}],
        "errors": ["efinance does not expose ETF capital flow batch"],
    }
```

Then, add the method to `DataFetcherManager` in `data_provider/base.py`. Place it near `get_capital_flow_context` (around line 3415). Fetchers are stored in `self._fetchers_by_name: Dict[str, BaseFetcher]` keyed by class name (`"AkshareFetcher"`, `"EfinanceFetcher"`); see `_init_default_fetchers` at line 1139 and `_refresh_fetcher_indexes_locked` at line 683 for reference.

```python
# In data_provider/base.py, add to DataFetcherManager class:

def get_etf_capital_flow_context(self) -> Dict[str, Any]:
    """Fetch the full A-share ETF batch with capital-flow fields.

    Composition: akshare primary (AkshareFetcher), efinance fallback (EfinanceFetcher).
    Fail-open: never raises.
    """
    source_chain: List[Dict[str, Any]] = []
    errors: List[str] = []

    for provider_name, fetcher in (
        ("akshare", self._fetchers_by_name.get("AkshareFetcher")),
        ("efinance", self._fetchers_by_name.get("EfinanceFetcher")),
    ):
        if fetcher is None:
            continue
        try:
            block = fetcher.get_etf_capital_flow_batch()
        except Exception as exc:
            source_chain.append({"provider": provider_name, "result": "failed", "duration_ms": 0})
            errors.append(f"{provider_name} raised: {exc}")
            continue
        source_chain.extend(block.get("source_chain", []))
        errors.extend(block.get("errors", []))
        if block.get("status") == "ok" and block.get("data"):
            return {
                "status": "ok",
                "data": block["data"],
                "source_chain": source_chain,
                "errors": errors,
            }
        if block.get("status") == "partial" and block.get("data"):
            return {
                "status": "partial",
                "data": block["data"],
                "source_chain": source_chain,
                "errors": errors,
            }

    return {
        "status": "failed",
        "data": [],
        "source_chain": source_chain,
        "errors": errors,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etf_capital_flow_context.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add data_provider/base.py data_provider/efinance_fetcher.py tests/test_etf_capital_flow_context.py
git commit -m "feat: add DataFetcherManager.get_etf_capital_flow_context with fail-open composition"
```

---

## Task 7: API Schemas

**Files:**
- Create: `api/v1/schemas/etf_capital_flow.py`
- Test: `tests/test_etf_capital_flow_schemas.py`

**Interfaces:**
- Consumes: the payload shape from Task 5.
- Produces: Pydantic models `EtfCapitalFlowSnapshotResponse`, `EtfCapitalFlowListResponse`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_etf_capital_flow_schemas.py
# -*- coding: utf-8 -*-
from api.v1.schemas.etf_capital_flow import (
    EtfCapitalFlowSnapshotResponse,
    EtfBucketSummary,
    EtfRankingItem,
    EtfDetailItem,
)


def test_snapshot_response_round_trips():
    payload = {
        "trade_date": "2026-07-17",
        "status": "ok",
        "source_chain": [{"provider": "akshare", "result": "ok", "duration_ms": 100}],
        "warnings": [],
        "market_overview": {
            "total_net_inflow": 1000000.0,
            "inflow_count": 100,
            "outflow_count": 50,
            "top_inflow": [{"code": "510300", "name": "沪深300", "main_net_inflow": 50000.0,
                            "change_pct": 0.5, "total_market_value": 1e9, "trade_date": "2026-07-17"}],
            "top_outflow": [],
        },
        "sector_buckets": [{"bucket_name": "券商", "bucket_type": "sector", "member_count": 2,
                            "total_scale": 800.0, "net_inflow_sum": 15.0, "share_change_sum": None,
                            "weighted_change_pct": 0.75, "weighted_discount_pct": 0.4,
                            "weighted_share_change_pct": None}],
        "index_buckets": [],
        "details": [{"code": "512000", "name": "券商ETF", "bucket_type": "sector",
                     "bucket_name": "券商", "close": 1.0, "change_pct": 1.0,
                     "discount_pct": 0.5, "main_net_inflow": 10.0, "main_net_inflow_pct": 1.0,
                     "latest_shares": 1000.0, "share_change": None,
                     "total_market_value": 500.0, "turnover": 100.0, "trade_date": "2026-07-17"}],
    }
    response = EtfCapitalFlowSnapshotResponse(**payload)
    assert response.trade_date == "2026-07-17"
    assert response.status == "ok"
    assert response.market_overview.total_net_inflow == 1000000.0
    assert len(response.sector_buckets) == 1
    assert response.sector_buckets[0].bucket_name == "券商"
    assert response.details[0].share_change is None


def test_snapshot_response_accepts_partial_status():
    response = EtfCapitalFlowSnapshotResponse(
        trade_date="2026-07-17",
        status="partial",
        source_chain=[],
        warnings=["partial data"],
        market_overview={"total_net_inflow": 0.0, "inflow_count": 0, "outflow_count": 0,
                         "top_inflow": [], "top_outflow": []},
        sector_buckets=[],
        index_buckets=[],
        details=[],
    )
    assert response.status == "partial"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etf_capital_flow_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# api/v1/schemas/etf_capital_flow.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etf_capital_flow_schemas.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add api/v1/schemas/etf_capital_flow.py tests/test_etf_capital_flow_schemas.py
git commit -m "feat: add ETF capital flow API schemas"
```

---

## Task 8: API Endpoints + Router Registration

**Files:**
- Create: `api/v1/endpoints/etf_capital_flow.py`
- Modify: `api/v1/router.py`
- Test: `tests/test_etf_capital_flow_api.py`

**Interfaces:**
- Consumes: `EtfCapitalFlowRepository` from Task 4, schemas from Task 7.
- Produces:
  - `GET /api/v1/etf-capital-flow/latest` -> `EtfCapitalFlowSnapshotResponse` (404 if none)
  - `GET /api/v1/etf-capital-flow/{trade_date}` -> `EtfCapitalFlowSnapshotResponse` (404 if none)
  - `GET /api/v1/etf-capital-flow/range?start_date=&end_date=` -> `EtfCapitalFlowListResponse`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_etf_capital_flow_api.py
# -*- coding: utf-8 -*-
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app


def _sample_payload(trade_date="2026-07-17"):
    return {
        "trade_date": trade_date,
        "status": "ok",
        "source_chain": [{"provider": "akshare", "result": "ok", "duration_ms": 50}],
        "warnings": [],
        "market_overview": {
            "total_net_inflow": 1000.0,
            "inflow_count": 5,
            "outflow_count": 3,
            "top_inflow": [{"code": "510300", "name": "沪深300", "main_net_inflow": 500.0,
                            "change_pct": 0.5, "total_market_value": 1e9, "trade_date": trade_date}],
            "top_outflow": [],
        },
        "sector_buckets": [],
        "index_buckets": [],
        "details": [],
        "created_at": "2026-07-17T18:00:00",
        "updated_at": "2026-07-17T18:00:00",
    }


def test_get_latest_returns_snapshot():
    app = create_app()
    client = TestClient(app)
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_latest_snapshot",
               return_value=_sample_payload()):
        response = client.get("/api/v1/etf-capital-flow/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["trade_date"] == "2026-07-17"
    assert data["status"] == "ok"
    assert data["market_overview"]["total_net_inflow"] == 1000.0


def test_get_latest_returns_404_when_empty():
    app = create_app()
    client = TestClient(app)
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_latest_snapshot",
               return_value=None):
        response = client.get("/api/v1/etf-capital-flow/latest")
    assert response.status_code == 404


def test_get_by_date_returns_snapshot():
    app = create_app()
    client = TestClient(app)
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_snapshot",
               return_value=_sample_payload("2026-07-16")):
        response = client.get("/api/v1/etf-capital-flow/2026-07-16")
    assert response.status_code == 200
    assert response.json()["trade_date"] == "2026-07-16"


def test_get_by_date_returns_404_when_missing():
    app = create_app()
    client = TestClient(app)
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_snapshot",
               return_value=None):
        response = client.get("/api/v1/etf-capital-flow/2026-01-01")
    assert response.status_code == 404


def test_get_range_returns_list():
    app = create_app()
    client = TestClient(app)
    snapshots = [_sample_payload("2026-07-15"), _sample_payload("2026-07-16"), _sample_payload("2026-07-17")]
    with patch("src.repositories.etf_capital_flow_repo.EtfCapitalFlowRepository.get_snapshots_range",
               return_value=snapshots):
        response = client.get("/api/v1/etf-capital-flow/range?start_date=2026-07-15&end_date=2026-07-17")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["snapshots"]) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etf_capital_flow_api.py -v`
Expected: FAIL with 404 (route not registered).

- [ ] **Step 3: Write minimal implementation**

```python
# api/v1/endpoints/etf_capital_flow.py
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
```

Then register the router in `api/v1/router.py`:

```python
# Modify api/v1/router.py:

# 1. Add etf_capital_flow to imports:
from api.v1.endpoints import (
    agent,
    alerts,
    alphasift,
    analysis,
    auth,
    backtest,
    decision_signals,
    etf_capital_flow,  # NEW
    health,
    history,
    intelligence,
    portfolio,
    stocks,
    system_config,
    usage,
)

# 2. Add include_router call after intelligence block (around line 111):
router.include_router(
    etf_capital_flow.router,
    prefix="/etf-capital-flow",
    tags=["EtfCapitalFlow"]
)
```

Note: the `/range/list` endpoint must be declared BEFORE `/{trade_date}` to avoid FastAPI matching "range" as a trade_date path parameter. The order shown above (latest, then by-date, then range/list) is wrong — put `range/list` before `{trade_date}`:

Revised endpoint order in `api/v1/endpoints/etf_capital_flow.py`:
1. `GET /latest`
2. `GET /range/list` (with query params)
3. `GET /{trade_date}`

Update the test path: `client.get("/api/v1/etf-capital-flow/range?start_date=...&end_date=...")` should become `client.get("/api/v1/etf-capital-flow/range/list?start_date=...&end_date=...")`. Fix the test to match.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etf_capital_flow_api.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add api/v1/endpoints/etf_capital_flow.py api/v1/router.py tests/test_etf_capital_flow_api.py
git commit -m "feat: add ETF capital flow API endpoints"
```

---

## Task 9: Market Review Injection

**Files:**
- Modify: `src/core/market_review.py` (call ETF service before analyzer)
- Modify: `src/market_analyzer.py` (inject ETF block into prompt + structured table)
- Test: `tests/test_etf_capital_flow_injection.py`

**Interfaces:**
- Consumes: `EtfCapitalFlowService.run_daily()` from Task 5 (called by market_review orchestration).
- Produces: an "ETF 资金方向" block appended to the market-review report after the LLM's "资金与情绪" section.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_etf_capital_flow_injection.py
# -*- coding: utf-8 -*-
from src.market_analyzer import MarketAnalyzer


def test_inject_etf_block_after_capital_section():
    analyzer = MarketAnalyzer.__new__(MarketAnalyzer)
    review = """### 一、市场综述
大盘小幅上涨。

### 四、资金与情绪
北向资金小幅净流入。

### 五、明日观察
注意外围市场。
"""
    etf_payload = {
        "trade_date": "2026-07-17",
        "status": "ok",
        "sector_buckets": [
            {"bucket_name": "券商", "net_inflow_sum": 12.3e8, "weighted_change_pct": 1.2,
             "weighted_share_change_pct": None, "weighted_discount_pct": 0.3,
             "share_change_sum": None, "member_count": 5, "total_scale": 1000, "bucket_type": "sector"},
            {"bucket_name": "医药", "net_inflow_sum": -5.2e8, "weighted_change_pct": -0.5,
             "weighted_share_change_pct": None, "weighted_discount_pct": None,
             "share_change_sum": None, "member_count": 4, "total_scale": 800, "bucket_type": "sector"},
        ],
        "index_buckets": [
            {"bucket_name": "沪深300", "net_inflow_sum": 5e8, "weighted_change_pct": 0.4,
             "weighted_share_change_pct": 0.012, "weighted_discount_pct": -0.1,
             "share_change_sum": 1.8e8, "member_count": 3, "total_scale": 5000, "bucket_type": "index"},
        ],
        "market_overview": {"total_net_inflow": 38e8},
    }
    result = analyzer._build_etf_capital_flow_block(etf_payload)
    assert "资金方向（ETF）" in result
    assert "券商" in result
    assert "医药" in result
    assert "沪深300" in result


def test_inject_etf_block_returns_empty_when_no_data():
    analyzer = MarketAnalyzer.__new__(MarketAnalyzer)
    result = analyzer._build_etf_capital_flow_block({"status": "failed", "sector_buckets": [], "index_buckets": []})
    assert result == ""


def test_inject_etf_block_handles_missing_share_change():
    analyzer = MarketAnalyzer.__new__(MarketAnalyzer)
    etf_payload = {
        "trade_date": "2026-07-17",
        "status": "ok",
        "sector_buckets": [],
        "index_buckets": [
            {"bucket_name": "沪深300", "net_inflow_sum": 5e8, "weighted_change_pct": 0.4,
             "weighted_share_change_pct": None, "weighted_discount_pct": -0.1,
             "share_change_sum": None, "member_count": 3, "total_scale": 5000, "bucket_type": "index"},
        ],
        "market_overview": {"total_net_inflow": 5e8},
    }
    result = analyzer._build_etf_capital_flow_block(etf_payload)
    # Should not crash; should mention 沪深300 without share_change detail
    assert "沪深300" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etf_capital_flow_injection.py -v`
Expected: FAIL with `AttributeError: 'MarketAnalyzer' object has no attribute '_build_etf_capital_flow_block'`

- [ ] **Step 3: Write minimal implementation**

Add the method to `MarketAnalyzer` in `src/market_analyzer.py`:

```python
# In src/market_analyzer.py, add to MarketAnalyzer class:

def _build_etf_capital_flow_block(self, etf_payload: dict) -> str:
    """Build a compact markdown block summarizing ETF capital flow.

    Returns empty string if no data available (fail-open: report proceeds without ETF section).
    """
    if not etf_payload or etf_payload.get("status") == "failed":
        return ""
    sector_buckets = etf_payload.get("sector_buckets") or []
    index_buckets = etf_payload.get("index_buckets") or []
    if not sector_buckets and not index_buckets:
        return ""

    lines = ["**资金方向（ETF）**", ""]

    # Sector top 3 inflow / outflow
    sorted_sectors = sorted(sector_buckets, key=lambda b: b.get("net_inflow_sum") or 0.0, reverse=True)
    top_inflow = [b for b in sorted_sectors if (b.get("net_inflow_sum") or 0.0) > 0][:3]
    top_outflow = [b for b in reversed(sorted_sectors) if (b.get("net_inflow_sum") or 0.0) < 0][:3]

    if top_inflow:
        parts = [f"{b['bucket_name']}(+{self._format_amount(b.get('net_inflow_sum') or 0.0)})" for b in top_inflow]
        lines.append(f"- 净流入板块 Top{len(top_inflow)}：{'、'.join(parts)}")
    if top_outflow:
        parts = [f"{b['bucket_name']}({self._format_amount(b.get('net_inflow_sum') or 0.0)})" for b in top_outflow]
        lines.append(f"- 净流出板块 Top{len(top_outflow)}：{'、'.join(parts)}")

    # Broad-based index activity
    if index_buckets:
        index_parts = []
        for b in index_buckets[:4]:
            name = b.get("bucket_name") or ""
            share_change = b.get("share_change_sum")
            discount = b.get("weighted_discount_pct")
            net_inflow = b.get("net_inflow_sum") or 0.0
            part = f"{name}"
            if share_change is not None:
                part += f" 份额{self._format_amount(share_change, sign=True)}"
            if discount is not None:
                part += f" 折溢价{discount:+.2f}%"
            part += f" 净流入{self._format_amount(net_inflow, sign=True)}"
            index_parts.append(part)
        if index_parts:
            lines.append(f"- 宽基动向：{'; '.join(index_parts)}")

    return "\n".join(lines)


@staticmethod
def _format_amount(value: float, *, sign: bool = False) -> str:
    """Format an amount in 亿 unit. E.g., 1.23e8 -> '1.23亿'."""
    amount_yi = value / 1e8
    if sign:
        return f"{amount_yi:+.1f}亿"
    return f"{amount_yi:.1f}亿"
```

Then wire it into `_inject_data_into_review`:

```python
# In src/market_analyzer.py, modify _inject_data_into_review:

def _inject_data_into_review(
    self,
    review: str,
    overview: MarketOverview,
    news: Optional[List] = None,
    etf_payload: Optional[dict] = None,  # NEW parameter
) -> str:
    """Inject structured data tables into the corresponding LLM prose sections."""
    stats_block = self._build_stats_block(overview)
    indices_block = self._build_indices_block(overview)
    sector_block = self._build_sector_block(overview)
    etf_block = self._build_etf_capital_flow_block(etf_payload) if etf_payload else ""  # NEW
    patterns = (
        _ENGLISH_SECTION_PATTERNS
        if self._get_review_language() == "en"
        else _CHINESE_SECTION_PATTERNS
    )

    if stats_block:
        review = self._insert_after_section(review, patterns["market_summary"], stats_block)
    if indices_block:
        review = self._insert_after_section(review, patterns["index_commentary"], indices_block)
    if sector_block:
        original_review = review
        review = self._insert_after_section(review, patterns["sector_highlights"], sector_block)
        if review == original_review and sector_block not in review:
            fallback_heading = (
                "### 4. Sector Highlights"
                if self._get_review_language() == "en"
                else "### 三、板块主线"
            )
            review = f"{review.rstrip()}\n\n{fallback_heading}\n{sector_block}\n"

    # NEW: inject ETF block after funds_sentiment section
    if etf_block:
        review = self._insert_after_section(review, patterns["funds_sentiment"], etf_block)

    return review
```

Then update `generate_market_review` to fetch ETF payload and pass it through:

```python
# In src/market_analyzer.py, modify generate_market_review around line 688:

prompt = self._build_review_prompt(overview, news)

# ... LLM call ...

if review:
    # Inject structured data tables into LLM prose sections
    etf_payload = self._fetch_etf_capital_flow_payload()
    return self._inject_data_into_review(review, overview, news, etf_payload=etf_payload)
```

Add the helper:

```python
def _fetch_etf_capital_flow_payload(self) -> Optional[dict]:
    """Fetch ETF capital flow analysis. Fail-open: returns None on any error."""
    try:
        from src.services.etf_capital_flow_service import EtfCapitalFlowService
        from data_provider.base import DataFetcherManager
        service = EtfCapitalFlowService(fetcher=DataFetcherManager.get_instance().get_etf_capital_flow_context)
        return service.run_daily()
    except Exception as exc:
        logger.warning("ETF capital flow analysis failed; skipping injection: %s", exc)
        return None
```

Also wire the prompt to mention ETF data is available — add a line in `_build_review_prompt` near the funds_sentiment section template:

```python
# In _build_review_prompt, after the existing 资金与情绪 instruction:
# Add: "（ETF 资金方向数据已附在结构化 block 中，请结合 ETF 板块轮动与宽基份额变动解读资金面）"
```

This addition goes in the prompt template around line 1360 (CN) and 1750 (EN).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etf_capital_flow_injection.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/market_analyzer.py tests/test_etf_capital_flow_injection.py
git commit -m "feat: inject ETF capital flow block into market review report"
```

---

## Task 10: Frontend Types and API Client

**Files:**
- Create: `apps/dsa-web/src/types/etfCapitalFlow.ts`
- Create: `apps/dsa-web/src/api/etfCapitalFlow.ts`
- Test: `apps/dsa-web/src/api/__tests__/etfCapitalFlow.test.ts`

**Interfaces:**
- Consumes: backend API from Task 8.
- Produces: `etfCapitalFlowApi` with `getLatest()`, `getByDate(date)`, `getRange(start, end)`.

- [ ] **Step 1: Write the failing test**

```typescript
// apps/dsa-web/src/api/__tests__/etfCapitalFlow.test.ts
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { etfCapitalFlowApi } from '../etfCapitalFlow';

const mockGet = vi.fn();
vi.mock('../index', () => ({
  default: { get: mockGet },
}));

beforeEach(() => {
  mockGet.mockReset();
});

describe('etfCapitalFlowApi', () => {
  it('getLatest calls /etf-capital-flow/latest', async () => {
    mockGet.mockResolvedValueOnce({
      data: {
        trade_date: '2026-07-17',
        status: 'ok',
        source_chain: [],
        warnings: [],
        market_overview: {
          total_net_inflow: 1000,
          inflow_count: 5,
          outflow_count: 3,
          top_inflow: [],
          top_outflow: [],
        },
        sector_buckets: [],
        index_buckets: [],
        details: [],
      },
    });
    const result = await etfCapitalFlowApi.getLatest();
    expect(mockGet).toHaveBeenCalledWith('/api/v1/etf-capital-flow/latest', expect.anything());
    expect(result.tradeDate).toBe('2026-07-17');
    expect(result.marketOverview.totalNetInflow).toBe(1000);
  });

  it('getByDate calls /etf-capital-flow/{date}', async () => {
    mockGet.mockResolvedValueOnce({ data: { trade_date: '2026-07-16', status: 'ok', market_overview: { total_net_inflow: 0, inflow_count: 0, outflow_count: 0, top_inflow: [], top_outflow: [] }, sector_buckets: [], index_buckets: [], details: [] } });
    await etfCapitalFlowApi.getByDate('2026-07-16');
    expect(mockGet).toHaveBeenCalledWith('/api/v1/etf-capital-flow/2026-07-16', expect.anything());
  });

  it('getRange calls /etf-capital-flow/range/list with params', async () => {
    mockGet.mockResolvedValueOnce({ data: { snapshots: [], total: 0 } });
    await etfCapitalFlowApi.getRange('2026-07-15', '2026-07-17');
    expect(mockGet).toHaveBeenCalledWith('/api/v1/etf-capital-flow/range/list', expect.objectContaining({
      params: { start_date: '2026-07-15', end_date: '2026-07-17' },
    }));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dsa-web && npx vitest run src/api/__tests__/etfCapitalFlow.test.ts`
Expected: FAIL with module not found.

- [ ] **Step 3: Write minimal implementation**

```typescript
// apps/dsa-web/src/types/etfCapitalFlow.ts
export interface EtfRankingItem {
  code: string;
  name?: string | null;
  mainNetInflow: number;
  changePct: number;
  totalMarketValue?: number | null;
  tradeDate?: string | null;
}

export interface EtfMarketOverview {
  totalNetInflow: number;
  inflowCount: number;
  outflowCount: number;
  topInflow: EtfRankingItem[];
  topOutflow: EtfRankingItem[];
}

export interface EtfBucketSummary {
  bucketName: string;
  bucketType: string;
  memberCount: number;
  totalScale: number;
  netInflowSum: number;
  shareChangeSum?: number | null;
  weightedChangePct?: number | null;
  weightedDiscountPct?: number | null;
  weightedShareChangePct?: number | null;
}

export interface EtfDetailItem {
  code: string;
  name?: string | null;
  bucketType: string;
  bucketName: string;
  close?: number | null;
  changePct?: number | null;
  discountPct?: number | null;
  mainNetInflow?: number | null;
  mainNetInflowPct?: number | null;
  latestShares?: number | null;
  shareChange?: number | null;
  totalMarketValue?: number | null;
  turnover?: number | null;
  tradeDate?: string | null;
}

export interface EtfCapitalFlowSnapshot {
  tradeDate: string;
  status: string;
  sourceChain: Array<{ provider: string; result: string; durationMs?: number }>;
  warnings: string[];
  marketOverview: EtfMarketOverview;
  sectorBuckets: EtfBucketSummary[];
  indexBuckets: EtfBucketSummary[];
  details: EtfDetailItem[];
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface EtfCapitalFlowListResponse {
  snapshots: EtfCapitalFlowSnapshot[];
  total: number;
}
```

```typescript
// apps/dsa-web/src/api/etfCapitalFlow.ts
import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  EtfCapitalFlowListResponse,
  EtfCapitalFlowSnapshot,
} from '../types/etfCapitalFlow';

export const etfCapitalFlowApi = {
  async getLatest(): Promise<EtfCapitalFlowSnapshot> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/etf-capital-flow/latest');
    return toCamelCase<EtfCapitalFlowSnapshot>(response.data);
  },

  async getByDate(tradeDate: string): Promise<EtfCapitalFlowSnapshot> {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/etf-capital-flow/${tradeDate}`,
    );
    return toCamelCase<EtfCapitalFlowSnapshot>(response.data);
  },

  async getRange(startDate: string, endDate: string): Promise<EtfCapitalFlowListResponse> {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/etf-capital-flow/range/list',
      { params: { start_date: startDate, end_date: endDate } },
    );
    return toCamelCase<EtfCapitalFlowListResponse>(response.data);
  },
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dsa-web && npx vitest run src/api/__tests__/etfCapitalFlow.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/dsa-web/src/types/etfCapitalFlow.ts apps/dsa-web/src/api/etfCapitalFlow.ts apps/dsa-web/src/api/__tests__/etfCapitalFlow.test.ts
git commit -m "feat(web): add ETF capital flow API client and types"
```

---

## Task 11: Frontend Dashboard Components

**Files:**
- Create: `apps/dsa-web/src/components/etf-flow/EtfKpiBar.tsx`
- Create: `apps/dsa-web/src/components/etf-flow/EtfTopFlowChart.tsx`
- Create: `apps/dsa-web/src/components/etf-flow/EtfSectorHeatmap.tsx`
- Create: `apps/dsa-web/src/components/etf-flow/EtfBroadIndexCard.tsx`
- Create: `apps/dsa-web/src/components/etf-flow/EtfBucketDetail.tsx`
- Test: `apps/dsa-web/src/components/etf-flow/__tests__/EtfKpiBar.test.tsx`

**Interfaces:**
- Consumes: types from Task 10.
- Produces: React components for each dashboard region.

This task bundles 5 small components under one test cycle. Each is a pure presentational component. If the implementer prefers finer granularity, split into 5 tasks — but since they share no test infrastructure and each is small, one task with one representative test is acceptable.

- [ ] **Step 1: Write the failing test**

```typescript
// apps/dsa-web/src/components/etf-flow/__tests__/EtfKpiBar.test.tsx
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { EtfKpiBar } from '../EtfKpiBar';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import type { EtfCapitalFlowSnapshot } from '../../../types/etfCapitalFlow';

const snapshot: EtfCapitalFlowSnapshot = {
  tradeDate: '2026-07-17',
  status: 'ok',
  sourceChain: [{ provider: 'akshare', result: 'ok', durationMs: 100 }],
  warnings: [],
  marketOverview: {
    totalNetInflow: 38e8,
    inflowCount: 18,
    outflowCount: 12,
    topInflow: [],
    topOutflow: [],
  },
  sectorBuckets: [
    { bucketName: '券商', bucketType: 'sector', memberCount: 5, totalScale: 1000,
      netInflowSum: 12.3e8, weightedChangePct: 1.2 },
  ],
  indexBuckets: [],
  details: [],
};

describe('EtfKpiBar', () => {
  it('renders total net inflow in 亿', () => {
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfKpiBar snapshot={snapshot} />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/38\.0亿/)).toBeInTheDocument();
  });

  it('shows inflow / outflow sector counts', () => {
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfKpiBar snapshot={snapshot} />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/18.*12/)).toBeInTheDocument();
  });

  it('shows source badge from sourceChain', () => {
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfKpiBar snapshot={snapshot} />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/akshare/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dsa-web && npx vitest run src/components/etf-flow/__tests__/EtfKpiBar.test.tsx`
Expected: FAIL with module not found.

- [ ] **Step 3: Write minimal implementation**

```tsx
// apps/dsa-web/src/components/etf-flow/EtfKpiBar.tsx
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import { Badge } from '../common/Badge';
import type { EtfCapitalFlowSnapshot } from '../../types/etfCapitalFlow';

interface EtfKpiBarProps {
  snapshot: EtfCapitalFlowSnapshot;
}

function formatAmount(value: number): string {
  const yi = value / 1e8;
  return `${yi.toFixed(1)}亿`;
}

export function EtfKpiBar({ snapshot }: EtfKpiBarProps) {
  const { t } = useUiLanguage();
  const { marketOverview, sourceChain, status } = snapshot;
  const source = sourceChain.find((s) => s.result === 'ok')?.provider ?? 'unknown';
  const badgeVariant = status === 'ok' ? 'success' : status === 'partial' ? 'warning' : 'danger';

  const leader = snapshot.sectorBuckets[0];

  return (
    <div className="grid grid-cols-4 gap-4 p-4 border rounded-md">
      <div>
        <div className="text-sm text-gray-500">{t('etfFlow.kpi.totalNetInflow')}</div>
        <div className="text-xl font-semibold">
          {marketOverview.totalNetInflow >= 0 ? '+' : ''}
          {formatAmount(marketOverview.totalNetInflow)}
        </div>
      </div>
      <div>
        <div className="text-sm text-gray-500">{t('etfFlow.kpi.sectorCounts')}</div>
        <div className="text-xl font-semibold">
          {marketOverview.inflowCount} / {marketOverview.outflowCount}
        </div>
      </div>
      <div>
        <div className="text-sm text-gray-500">{t('etfFlow.kpi.leader')}</div>
        <div className="text-xl font-semibold">{leader?.bucketName ?? '-'}</div>
      </div>
      <div>
        <div className="text-sm text-gray-500">{t('etfFlow.kpi.source')}</div>
        <div className="flex items-center gap-2">
          <span>{source}</span>
          <Badge variant={badgeVariant}>{status}</Badge>
        </div>
      </div>
    </div>
  );
}
```

For the other four components, follow the same pattern (pure presentational, recharts for chart components). Brief skeletons:

```tsx
// apps/dsa-web/src/components/etf-flow/EtfTopFlowChart.tsx
// Uses recharts BarChart - horizontal bidirectional layout
// Props: { topInflow: EtfRankingItem[]; topOutflow: EtfRankingItem[] }
// Render two bar charts side by side, mock recharts in tests
```

```tsx
// apps/dsa-web/src/components/etf-flow/EtfSectorHeatmap.tsx
// Props: { snapshots: EtfCapitalFlowSnapshot[] } (last 10 days)
// For each sector bucket, render a row of colored cells (red=inflow, green=outflow, intensity by magnitude)
// Pure CSS grid - no recharts needed
```

```tsx
// apps/dsa-web/src/components/etf-flow/EtfBroadIndexCard.tsx
// Props: { indexBuckets: EtfBucketSummary[] }
// For each index bucket, render a card with: name, share change (★ for consecutive streak if available),
// discount %, net inflow amount
```

```tsx
// apps/dsa-web/src/components/etf-flow/EtfBucketDetail.tsx
// Props: { bucketName: string; details: EtfDetailItem[] }
// Expandable table of top 10 members with columns: code, name, change%, discount%, net inflow, share change
```

Each component should be ~50-80 lines. Full code for all five is intentionally not shown here to keep the plan readable — the implementer writes the minimal code that satisfies the test for EtfKpiBar and applies the same patterns (useUiLanguage, Badge/Card components, recharts for charts) to the other four.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dsa-web && npx vitest run src/components/etf-flow/__tests__/EtfKpiBar.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/dsa-web/src/components/etf-flow/
git commit -m "feat(web): add ETF capital flow dashboard components"
```

---

## Task 12: Frontend Dashboard Page + Routing + Nav + i18n

**Files:**
- Create: `apps/dsa-web/src/pages/EtfCapitalFlowPage.tsx`
- Create: `apps/dsa-web/src/pages/__tests__/EtfCapitalFlowPage.test.tsx`
- Modify: `apps/dsa-web/src/App.tsx` (add route)
- Modify: `apps/dsa-web/src/components/layout/SidebarNav.tsx` (add nav entry)
- Modify: `apps/dsa-web/src/i18n/uiText.ts` (add `etfFlow.*` keys)

**Interfaces:**
- Consumes: components from Task 11, API client from Task 10.
- Produces: a working `/etf-flow` page accessible from the sidebar.

- [ ] **Step 1: Write the failing test**

```typescript
// apps/dsa-web/src/pages/__tests__/EtfCapitalFlowPage.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { EtfCapitalFlowPage } from '../EtfCapitalFlowPage';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: () => <div data-testid="bar-chart" />,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
}));

const mockGetLatest = vi.fn();
vi.mock('../../api/etfCapitalFlow', () => ({
  etfCapitalFlowApi: { getLatest: mockGetLatest },
}));

beforeEach(() => {
  mockGetLatest.mockReset();
});

const sampleSnapshot = {
  tradeDate: '2026-07-17',
  status: 'ok',
  sourceChain: [{ provider: 'akshare', result: 'ok', durationMs: 100 }],
  warnings: [],
  marketOverview: {
    totalNetInflow: 38e8,
    inflowCount: 18,
    outflowCount: 12,
    topInflow: [],
    topOutflow: [],
  },
  sectorBuckets: [],
  indexBuckets: [],
  details: [],
};

describe('EtfCapitalFlowPage', () => {
  it('renders loading then snapshot', async () => {
    mockGetLatest.mockResolvedValueOnce(sampleSnapshot);
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfCapitalFlowPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/38\.0亿/)).toBeInTheDocument());
  });

  it('renders error state on API failure', async () => {
    mockGetLatest.mockRejectedValueOnce(new Error('network down'));
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfCapitalFlowPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/network down|错误|error/i)).toBeInTheDocument());
  });

  it('renders empty state when 404', async () => {
    const error: any = new Error('not found');
    error.response = { status: 404 };
    mockGetLatest.mockRejectedValueOnce(error);
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfCapitalFlowPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/暂无|no data|empty/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dsa-web && npx vitest run src/pages/__tests__/EtfCapitalFlowPage.test.tsx`
Expected: FAIL with module not found.

- [ ] **Step 3: Write minimal implementation**

```tsx
// apps/dsa-web/src/pages/EtfCapitalFlowPage.tsx
import { useCallback, useEffect, useState } from 'react';
import { AppPage } from '../components/common/AppPage';
import { PageHeader } from '../components/common/PageHeader';
import { Card } from '../components/common/Card';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import { getParsedApiError, ParsedApiError } from '../api/error';
import { etfCapitalFlowApi } from '../api/etfCapitalFlow';
import type { EtfCapitalFlowSnapshot } from '../types/etfCapitalFlow';
import { EtfKpiBar } from '../components/etf-flow/EtfKpiBar';
import { EtfTopFlowChart } from '../components/etf-flow/EtfTopFlowChart';
import { EtfSectorHeatmap } from '../components/etf-flow/EtfSectorHeatmap';
import { EtfBroadIndexCard } from '../components/etf-flow/EtfBroadIndexCard';

export function EtfCapitalFlowPage() {
  const { t } = useUiLanguage();
  const [snapshot, setSnapshot] = useState<EtfCapitalFlowSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [notFound, setNotFound] = useState(false);

  const fetchLatest = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const data = await etfCapitalFlowApi.getLatest();
      setSnapshot(data);
    } catch (err: any) {
      if (err?.response?.status === 404) {
        setNotFound(true);
      } else {
        setError(getParsedApiError(err));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLatest();
  }, [fetchLatest]);

  return (
    <AppPage>
      <PageHeader
        eyebrow={t('etfFlow.eyebrow')}
        title={t('etfFlow.title')}
        description={t('etfFlow.description')}
      />
      {loading && <p>{t('common.loading')}...</p>}
      {error && <ApiErrorAlert error={error} />}
      {notFound && (
        <EmptyState
          title={t('etfFlow.empty.title')}
          description={t('etfFlow.empty.description')}
        />
      )}
      {snapshot && (
        <div className="space-y-4">
          <EtfKpiBar snapshot={snapshot} />
          <Card title={t('etfFlow.sections.marketOverview')}>
            <EtfTopFlowChart
              topInflow={snapshot.marketOverview.topInflow}
              topOutflow={snapshot.marketOverview.topOutflow}
            />
          </Card>
          <Card title={t('etfFlow.sections.sectorRotation')}>
            <EtfSectorHeatmap snapshots={[snapshot]} />
          </Card>
          <Card title={t('etfFlow.sections.broadIndex')}>
            <EtfBroadIndexCard indexBuckets={snapshot.indexBuckets} />
          </Card>
        </div>
      )}
    </AppPage>
  );
}
```

Add the route in `apps/dsa-web/src/App.tsx`:

```tsx
// Add lazy import near other lazy imports:
const EtfCapitalFlowPage = lazy(() => import('./pages/EtfCapitalFlowPage'));

// Add route inside <Routes>:
<Route path="/etf-flow" element={<EtfCapitalFlowPage />} />
```

Add nav entry in `apps/dsa-web/src/components/layout/SidebarNav.tsx`:

```tsx
// Add to NAV_ITEMS array (place near decision-signals or backtest):
{
  key: 'etf-flow',
  labelKey: 'layout.nav.etfFlow',
  to: '/etf-flow',
  icon: <YourIcon />,  // pick an existing icon from the project's icon set
}
```

Add translations in `apps/dsa-web/src/i18n/uiText.ts`:

```typescript
// Add to zh object:
'etfFlow.eyebrow': '资金流向',
'etfFlow.title': 'ETF 场内资金流',
'etfFlow.description': 'A 股场内 ETF 每日资金流向：板块轮动、宽基动向、全市场总览',
'etfFlow.empty.title': '暂无 ETF 资金流数据',
'etfFlow.empty.description': '数据将在每日收盘后生成',
'etfFlow.kpi.totalNetInflow': '全市场净流入',
'etfFlow.kpi.sectorCounts': '流入 / 流出板块数',
'etfFlow.kpi.leader': '领涨板块',
'etfFlow.kpi.source': '数据源',
'etfFlow.sections.marketOverview': '全市场总览',
'etfFlow.sections.sectorRotation': '板块轮动 · 近 10 日热力图',
'etfFlow.sections.broadIndex': '宽基动向',
'layout.nav.etfFlow': 'ETF 资金流',

// Add matching en object:
'etfFlow.eyebrow': 'Capital Flow',
'etfFlow.title': 'ETF Capital Flow',
'etfFlow.description': 'Daily A-share ETF capital flow: sector rotation, broad index activity, market overview',
'etfFlow.empty.title': 'No ETF capital flow data yet',
'etfFlow.empty.description': 'Data will be generated after market close each day',
'etfFlow.kpi.totalNetInflow': 'Total Net Inflow',
'etfFlow.kpi.sectorCounts': 'Inflow / Outflow Sectors',
'etfFlow.kpi.leader': 'Leading Sector',
'etfFlow.kpi.source': 'Source',
'etfFlow.sections.marketOverview': 'Market Overview',
'etfFlow.sections.sectorRotation': 'Sector Rotation · 10-Day Heatmap',
'etfFlow.sections.broadIndex': 'Broad-Based Index',
'layout.nav.etfFlow': 'ETF Flow',
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dsa-web && npx vitest run src/pages/__tests__/EtfCapitalFlowPage.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/dsa-web/src/pages/EtfCapitalFlowPage.tsx apps/dsa-web/src/pages/__tests__/EtfCapitalFlowPage.test.tsx apps/dsa-web/src/App.tsx apps/dsa-web/src/components/layout/SidebarNav.tsx apps/dsa-web/src/i18n/uiText.ts
git commit -m "feat(web): add ETF capital flow dashboard page with routing and nav"
```

---

## Task 13: Frontend Lint + Build Verification

**Files:**
- No new files. Verifies the frontend changes from Tasks 10-12 don't break lint/build.

- [ ] **Step 1: Run lint**

Run: `cd apps/dsa-web && npm run lint`
Expected: PASS with no new warnings/errors in etf-flow files.

- [ ] **Step 2: Run build**

Run: `cd apps/dsa-web && npm run build`
Expected: PASS. Build output should include the new EtfCapitalFlowPage chunk.

- [ ] **Step 3: If lint or build fails, fix the issues**

Common issues:
- Unused imports in component files
- Missing TypeScript types
- i18n key missing in either `zh` or `en` (TypeScript will catch via `Record<UiTextKey, string>`)

- [ ] **Step 4: Commit fixes (if any)**

```bash
git add -A
git commit -m "fix(web): resolve lint/build issues in ETF capital flow feature"
```

If no fixes needed, skip this step.

---

## Task 14: Documentation

**Files:**
- Create: `docs/etf-capital-flow.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: Write the user-facing doc**

```markdown
# ETF 场内资金流分析

> 功能：每日收盘后产出 A 股场内 ETF 资金流情报，注入大盘复盘报告"资金方向"段，并提供 Web 看板。

## 数据来源

- 主源：akshare `fund_etf_spot_em()` 单次批量接口（约 1500 只 ETF）
- 备源：efinance（当前未实现批量 ETF 资金流接口，仅占位）
- 失败降级：主源失败标 `status: partial` / `failed`，不阻断大盘复盘主流程

## 三视角

### A 板块轮动

按板块（券商、半导体、医药等）分组，每板块按总规模取前 10 只 ETF，聚合：
- 净流入额（求和）
- 涨幅、折溢价（规模加权平均）

### B 宽基动向

按宽基指数（沪深300、中证A500、中证500、中证1000、科创50、创业板指等）分组，每指数取前 10 只 ETF，额外关注：
- 份额净变动（净申购 / 赎回）—— 机构加减仓信号
- 折溢价（IOPV 偏离）

### C 全市场总览

- 全市场净流入总额
- 流入 / 流出 ETF 数量
- 净流入 / 流出 Top10 ETF 排行

## 聚合规则（关键）

- **绝对量类**（净流入额、份额变动额）：求和
- **比率 / 强度类**（涨幅%、折溢价%、份额变动率%）：总市值加权平均
- **连续净流入天数**：看桶净流入（求和）的连续正负符号

不允许简单平均，避免迷你 ETF 极端值拉偏。

## 持久化

- SQLite 表 `etf_capital_flow_snapshots`
- 每日一行 JSON 快照（按 `trade_date` upsert）
- 字段：`trade_date`, `payload`, `status`, `created_at`, `updated_at`

## API

| 路径 | 方法 | 说明 |
|---|---|---|
| `/api/v1/etf-capital-flow/latest` | GET | 获取最新快照 |
| `/api/v1/etf-capital-flow/{trade_date}` | GET | 获取指定交易日 |
| `/api/v1/etf-capital-flow/range/list?start_date=&end_date=` | GET | 范围查询 |

## Web 看板

路径：`/etf-flow`（侧边栏"ETF 资金流"入口）

分区：
- 顶部 KPI 条：全市场净流入、流入 / 流出板块数、领涨板块、数据源 + 状态
- 全市场总览：净流入 / 流出 Top10 双向条形图
- 板块轮动：板块 × 交易日热力图（近 10 日）
- 宽基动向：每只宽基一行 / 卡，份额净申购用 ★ 醒目标记
- 明细区：点击下钻桶内前 10 成员

## 容错与降级

- 批量拉取 fail-open：akshare 挂了走 efinance，全挂标 `failed`，不拖垮主流程
- 分类缺口：未分类 ETF 进"其他"桶并 warning
- 字段缺失：缺折溢价 / 份额变动 -> 该指标标 `null`，warning 提示

## 运行时机

挂进现有 `--market-review` 流程，每日收盘后由 `.github/workflows/00-daily-analysis.yml` 触发。无需新建调度。

## 限制

- 仅 A 股场内 ETF（不含港股 / 美股 ETF）
- 日频，无 intraday 实时
- 国家队判定仅为"疑似"信号，不写死结论
- 首日运行无历史快照，份额变动标 `missing`
```

- [ ] **Step 2: Update CHANGELOG**

Append to `docs/CHANGELOG.md` `[Unreleased]` section (flat format, one line per entry):

```
- [新功能] ETF 场内资金流分析：每日产出板块轮动 / 宽基动向 / 全市场总览三视角
- [新功能] ETF 资金流 Web 看板：`/etf-flow` 页面，含热力图与下钻明细
- [新功能] 大盘复盘报告注入"资金方向（ETF）"段
- [改进] 复用 `fund_etf_spot_em` 批量接口，单次拉取全市场 ETF 资金流数据
- [改进] 持久化采用 SQLite JSON 快照，按交易日 upsert
- [文档] 新增 `docs/etf-capital-flow.md` 用户文档
```

- [ ] **Step 3: Verify docs render correctly**

Run: `ls -la docs/etf-capital-flow.md && head -5 docs/etf-capital-flow.md`
Expected: file exists, first line is `# ETF 场内资金流分析`.

- [ ] **Step 4: Commit**

```bash
git add docs/etf-capital-flow.md docs/CHANGELOG.md
git commit -m "docs: add ETF capital flow user guide and changelog entry"
```

---

## Task 15: Backend CI Gate Verification

**Files:**
- No new files. Verifies the backend changes pass CI gate.

- [ ] **Step 1: Run CI gate**

Run: `./scripts/ci_gate.sh`
Expected: PASS. All four phases (syntax_check, flake8_checks, deterministic_checks, offline_test_suite) succeed.

- [ ] **Step 2: Run new tests explicitly**

Run: `python -m pytest tests/test_etf_sector_mapping.py tests/test_akshare_etf_batch.py tests/test_etf_capital_flow_aggregator.py tests/test_etf_capital_flow_repo.py tests/test_etf_capital_flow_service.py tests/test_etf_capital_flow_context.py tests/test_etf_capital_flow_schemas.py tests/test_etf_capital_flow_api.py tests/test_etf_capital_flow_injection.py -v`
Expected: all PASS.

- [ ] **Step 3: If any test fails, fix the underlying issue**

Do not skip tests or mark them xfail without justification. Investigate root cause.

- [ ] **Step 4: Commit fixes (if any)**

```bash
git add -A
git commit -m "fix: resolve backend test failures for ETF capital flow feature"
```

If no fixes needed, skip this step.

---

## Task 16: Manual Smoke Test (End-to-End)

**Files:**
- No file changes. Verifies the feature works end-to-end in a real run.

This task is intentionally manual because it requires live akshare data and a visual check of the Web UI. Per AGENTS.md §6, network-dependent verification is observational, not blocking.

- [ ] **Step 1: Run market review locally**

Run: `python main.py --market-review`
Expected:
- Command completes without error
- New row in `etf_capital_flow_snapshots` table
- Market review report markdown contains "**资金方向（ETF）**" block

- [ ] **Step 2: Verify the DB snapshot**

Run:
```bash
sqlite3 data/stock_analysis.db "SELECT trade_date, status, length(payload) FROM etf_capital_flow_snapshots ORDER BY trade_date DESC LIMIT 5;"
```
Expected: one row with today's date, `status='ok'` or `'partial'`, payload length > 1000.

- [ ] **Step 3: Verify the API**

Run: `curl -s http://localhost:8000/api/v1/etf-capital-flow/latest | python -m json.tool | head -40`
Expected: JSON response with `trade_date`, `status`, `market_overview`, `sector_buckets`, `index_buckets`, `details`.

- [ ] **Step 4: Verify the Web UI**

Start the dev server: `cd apps/dsa-web && npm run dev`
Open: `http://localhost:5173/etf-flow`
Expected:
- Page renders without errors
- KPI bar shows total net inflow amount in 亿
- At least one sector bucket appears in the heatmap
- Source badge shows "akshare" with green "ok" status

- [ ] **Step 5: Take screenshots for PR**

Per AGENTS.md §1 hard rule: "修改报告格式、报告渲染效果或 Web UI 界面时，PR 描述必须附受影响报告 / 页面截图".

Capture:
- Screenshot of the Web dashboard
- Screenshot of the market review report showing the "资金方向（ETF）" block

Attach to the PR description (not as repo files).

- [ ] **Step 6: No commit needed for this task**

This is verification only. If issues are found, create a fix commit addressing the root cause.

---

## Self-Review Summary

After writing the plan, the following checks were performed:

1. **Spec coverage**:
   - Design §3 (聚合规则): Task 3 implements sum + weighted average; tests explicitly assert against simple-average regression.
   - Design §4 (架构与落点): every file listed in the table maps to a task.
   - Design §5 (数据模型): Task 5's payload shape matches; Task 7's schemas mirror it.
   - Design §6 (数据流): Task 5 implements the 6-step pipeline.
   - Design §7 (报告注入): Task 9 injects the block.
   - Design §8 (Web 看板): Tasks 10-12 build the page with all 5 regions (KPI / C / A / B / 明细).
   - Design §9 (容错与降级): Task 6 implements fail-open composition; Task 5 propagates `status / warnings`.
   - Design §10 (测试策略): each task has TDD tests covering aggregator, repo, API contract, fail-open, frontend.
   - Design §11 (待验证 / 风险): akshare field availability confirmed in plan preamble; first-day share_change handled with `missing` warning in Task 5.

2. **Placeholder scan**: no TBD/TODO/"implement later" found. Each step has concrete code or commands.

3. **Type consistency**:
   - `EtfBucketAssignment` (Task 1) used in Task 5.
   - `EtfBatchItem` shape (Task 2) consumed by Task 3 and Task 5.
   - `EtfCapitalFlowRepository` methods (Task 4) called consistently in Task 5 and Task 8.
   - `EtfCapitalFlowSnapshotResponse` schema (Task 7) matches API responses (Task 8) and frontend types (Task 10).
   - Frontend type names (`EtfCapitalFlowSnapshot`, `EtfBucketSummary`, etc.) match across Tasks 10, 11, 12.

4. **Risks flagged for implementer**:
   - Task 6: fetchers are accessed via `self._fetchers_by_name["AkshareFetcher"]` / `"EfinanceFetcher"` (verified in `data_provider/base.py:643,683,1139`). The implementation code uses this exact pattern.
   - Task 8: FastAPI route ordering — `/range/list` must be declared before `/{trade_date}` to avoid path parameter collision. The plan calls this out explicitly.
   - Task 11: the four non-KpiBar components have skeleton specs only. The implementer writes the minimal code following the EtfKpiBar pattern. If full code is preferred, split Task 11 into 5 sub-tasks.
   - Task 16: requires live akshare data and visual verification — explicitly observational per AGENTS.md.
