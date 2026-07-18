# 修复按日期补填分析实际按当前时间生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 `feat/backfill-historical-analysis` 分支上「按指定日期 X 补填分析」实际按当前时间生成的 bug，使回填记录的 `enhanced_context.date == X`、`backfill.target_date == X`、`realtime.price == X 日收盘`，回测能正确把它归到 X 日。

**Architecture:** 新增 `DatabaseManager.get_analysis_context_as_of(code, target_date)` 按 X 日精确取上下文（backfill 专用，不动公共 `get_analysis_context` 语义）；`pipeline.process_single_stock` 与 `analyze_stock` 增 `target_date` 参数，backfill 模式下直接 `set_frozen_target_date(X)`（绕过 `_resolve_resume_target_date` 的"未收盘退一日"逻辑）、调新方法取 context、`backfill.target_date` 直接写 X、`realtime` 用 X 日 bar；`analysis_service.backfill_as_of_date` 改传 `target_date` 替代 `current_time`。测试重写为真实内存 sqlite + 真实 db 取数路径。

**Tech Stack:** Python / SQLAlchemy / pytest（后端），内存 sqlite（`sqlite:///:memory:`）做隔离测试。

## Global Constraints

- commit message 使用英文、**不添加 `Co-Authored-By`**（AGENTS.md 硬规则）；未经确认不执行 `git commit`/`git push`/`git tag`。
- **仅修 backfill 路径**：`db.get_analysis_context` 公共方法语义不动（`storage.py:2536` 的 TODO 保留）；`backfill_mode=False` 时所有行为不变。
- `process_single_stock` / `analyze_stock` 新增的 `target_date` 参数默认 `None`，`backfill_mode=False` 或 `target_date=None` 时完全不影响原路径。
- 后端验证：`./scripts/ci_gate.sh` 与 `python -m py_compile <changed>`；测试：`python -m pytest tests/test_pipeline_backfill_mode.py tests/test_analysis_service_backfill.py -v`。
- 用户可见修复须同步 `docs/CHANGELOG.md`（`[Unreleased]` 扁平格式 `- [类型] 描述`）与 `docs/backfill-guide.md`。
- 不新增配置项、不改 `.env.example`、不改 API 契约（`POST /api/v1/analysis/backfill` 签名不变）、不改前端。

## File Structure

后端：
- `src/storage.py` - `DatabaseManager` 新增 `get_analysis_context_as_of(code, target_date)` 方法（与 `get_analysis_context` 同类，`pipeline.db` 可直接调）。
- `src/core/pipeline.py` - `process_single_stock` 增 `target_date` 参数 + backfill 模式直接冻结 X；`analyze_stock` 增 `target_date` 参数 + backfill 模式调新方法 + backfill 标记写 X + realtime 用 X bar；`process_single_stock` 透传 `target_date` 给 `analyze_stock`。
- `src/services/analysis_service.py` - `backfill_as_of_date` 改传 `target_date` 替代 `current_time`。

测试：
- `tests/test_pipeline_backfill_mode.py` - 重写为真实内存 sqlite + 真实 db 取数路径，断言 `enhanced_context.date == X` 等核心契约。
- `tests/test_analysis_service_backfill.py` - 补端到端测试，断言落库的 `context_snapshot.enhanced_context.date == X`。

文档：
- `docs/backfill-guide.md`（追加「已知限制」）、`docs/CHANGELOG.md`（追加 `[修复]` 条目）。

---

### Task 1: `DatabaseManager.get_analysis_context_as_of` 新方法

**Files:**
- Modify: `src/storage.py`（在 `get_analysis_context` 方法之后，约 2574 行附近，新增 `get_analysis_context_as_of`）
- Test: `tests/test_storage_backfill_context.py`（新建）

**Interfaces:**
- Consumes: `DatabaseManager.get_data_range(code, start_date, end_date) -> List[StockDaily]`（已有，`storage.py:2333`）、`DatabaseManager._analyze_ma_status(StockDaily) -> str`（已有，`storage.py:2576`）。
- Produces: `DatabaseManager.get_analysis_context_as_of(code: str, target_date: date) -> Optional[Dict[str, Any]]`，返回形状与 `get_analysis_context` 一致：`{code, date, today, yesterday, volume_change_ratio?, price_change_ratio?, ma_status}`；X 日 bar 缺失返回 `None`。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_storage_backfill_context.py`：

```python
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
            "close": 9.5 + i * 0.1,  # 2026-06-10 close = 10.4
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
    # 删掉 2026-06-10 的 bar
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_storage_backfill_context.py -v`
Expected: FAIL with `AttributeError: 'DatabaseManager' object has no attribute 'get_analysis_context_as_of'`

- [ ] **Step 3: 实现 `get_analysis_context_as_of`**

在 `src/storage.py` 的 `get_analysis_context` 方法之后（约 2574 行后）新增：

```python
def get_analysis_context_as_of(
    self,
    code: str,
    target_date: date,
) -> Optional[Dict[str, Any]]:
    """
    按 target_date 精确取当日 + 前一交易日 bar，构造分析上下文。
    供 backfill 模式专用，不替代 get_analysis_context。

    - today_bar: 精确取 target_date 当日 bar（无 fallback）。
    - yesterday_bar: target_date 之前最近一根 bar（< target_date）。
    - 两者任一缺失 -> 返回 None。
    """
    from datetime import timedelta

    bars = self.get_data_range(
        code, target_date - timedelta(days=4), target_date
    )
    if not bars:
        return None

    today_bar = next((b for b in bars if b.date == target_date), None)
    if today_bar is None:
        return None

    prior_bars = [b for b in bars if b.date < target_date]
    if not prior_bars:
        return None
    yesterday_bar = prior_bars[-1]

    context: Dict[str, Any] = {
        "code": code,
        "date": target_date.isoformat(),
        "today": today_bar.to_dict(),
        "yesterday": yesterday_bar.to_dict(),
    }

    if yesterday_bar.volume and yesterday_bar.volume > 0:
        context["volume_change_ratio"] = round(
            today_bar.volume / yesterday_bar.volume, 2
        )
    if yesterday_bar.close and yesterday_bar.close > 0:
        context["price_change_ratio"] = round(
            (today_bar.close - yesterday_bar.close) / yesterday_bar.close * 100, 2
        )
    context["ma_status"] = self._analyze_ma_status(today_bar)
    return context
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_storage_backfill_context.py -v`
Expected: 3 passed

- [ ] **Step 5: py_compile 校验**

Run: `python -m py_compile src/storage.py`
Expected: 无输出（成功）

- [ ] **Step 6: Commit**

```bash
git add src/storage.py tests/test_storage_backfill_context.py
git commit -m "feat(storage): add get_analysis_context_as_of for backfill"
```

---

### Task 2: `pipeline.process_single_stock` + `analyze_stock` 改动 + 端到端测试重写

**Files:**
- Modify: `src/core/pipeline.py:2768-2867`（`process_single_stock` 签名 + 冻结逻辑 + 透传 target_date）
- Modify: `src/core/pipeline.py:360-669`（`analyze_stock` 签名 + 调新方法 + backfill 标记 + realtime）
- Test: `tests/test_pipeline_backfill_mode.py`（重写）

**Interfaces:**
- Consumes: `DatabaseManager.get_analysis_context_as_of(code, target_date)`（Task 1 产出）、`set_frozen_target_date(date)`（已有）、`get_frozen_target_date()`（已有）。
- Produces: `process_single_stock(..., target_date: Optional[date] = None, backfill_mode: bool = False)`；`analyze_stock(..., target_date: Optional[date] = None, backfill_mode: bool = False)`。backfill 模式下 `enhanced_context["date"] == X.isoformat()`、`enhanced_context["backfill"]["target_date"] == X.isoformat()`、`enhanced_context["realtime"]["price"] == X 日 close`。

- [ ] **Step 1: 重写 `tests/test_pipeline_backfill_mode.py` 为失败测试**

完整替换 `tests/test_pipeline_backfill_mode.py` 内容：

```python
# -*- coding: utf-8 -*-
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest


def _build_pipeline_with_real_db():
    """真实内存 db + 真实 pipeline.db 取数路径，仅 mock LLM/网络/趋势分析。"""
    from src.core.pipeline import StockAnalysisPipeline
    from src.config import Config
    from src.storage import DatabaseManager

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
            "close": 9.5 + i * 0.1,  # 2026-06-10 close = 10.4
            "volume": 1000.0 + i * 100,
            "pct_chg": 1.0 + i * 0.1,
            "ma5": 9.0,
            "ma10": 8.8,
            "ma20": 8.5,
        })
    df = pd.DataFrame(rows)
    df["code"] = "600519"
    db.save_daily_data(df, "600519", "test")

    pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
    pipeline.db = db
    pipeline.config = MagicMock(spec=Config)
    pipeline.config.enable_realtime_quote = True
    pipeline.config.report_language = "zh"
    pipeline.config.agent_mode = False
    pipeline.config.agent_skills = []
    pipeline.config.fundamental_stage_timeout_seconds = 1
    pipeline.config.daily_market_context_enabled = False
    pipeline.config.market_review_enabled = False
    pipeline.config.litellm_model = "test-model"
    pipeline.query_source = "backfill"
    pipeline.analysis_phase = "auto"
    pipeline.analysis_skills = None
    pipeline.save_context_snapshot = True
    pipeline.portfolio_context = None

    pipeline.fetcher_manager = MagicMock()
    pipeline.fetcher_manager.get_stock_name.return_value = "测试股"
    pipeline.fetcher_manager.get_realtime_quote.return_value = None
    pipeline.fetcher_manager.get_chip_distribution.return_value = None
    pipeline.fetcher_manager.get_fundamental_context.return_value = {}
    pipeline.fetcher_manager.build_failed_fundamental_context.return_value = {}

    pipeline.search_service = MagicMock()
    pipeline.search_service.is_available = True
    pipeline.search_service.search_comprehensive_intel = MagicMock(return_value={})
    pipeline.social_sentiment_service = None

    pipeline.trend_analyzer = MagicMock()
    pipeline.trend_analyzer.analyze.return_value = SimpleNamespace(
        trend_status=SimpleNamespace(value="up"),
        buy_signal=SimpleNamespace(value="none"),
        signal_score=50,
        ma_alignment="bull",
        trend_strength=0.5,
        bias_ma5=0.01,
        bias_ma10=0.02,
        volume_status=SimpleNamespace(value="normal"),
        volume_trend="up",
        signal_reasons=[],
        risk_factors=[],
        ma5=10.0,
        ma10=9.8,
        ma20=9.5,
    )

    captured = {}

    def _fake_analyze(enhanced_context, **kwargs):
        captured["enhanced_context"] = enhanced_context
        return SimpleNamespace(
            success=True, code="600519", name="测试股",
            current_price=None, change_pct=None, query_id="q",
            operation_advice="持有", sentiment_score=60,
            model_used="test-model", report_language="zh",
            analysis_summary="", news_summary="", technical_analysis="",
            fundamental_analysis="", risk_warning="", to_dict=lambda: {},
            error_message=None,
        )

    pipeline.analyzer = MagicMock()
    pipeline.analyzer.analyze = _fake_analyze
    pipeline._emit_progress = MagicMock()
    # 避免 save_analysis_history 写真实 db 触发关联表依赖
    db.save_analysis_history = MagicMock(return_value=1)
    db.save_fundamental_snapshot = MagicMock()

    return pipeline, captured, target


def test_backfill_uses_target_date_context():
    pipeline, captured, target = _build_pipeline_with_real_db()
    pipeline.analyze_stock(
        code="600519",
        report_type=SimpleNamespace(value="detailed"),
        query_id="q1",
        target_date=target,
        backfill_mode=True,
    )
    ec = captured["enhanced_context"]
    assert ec["date"] == "2026-06-10"
    assert ec["today"]["date"] == date(2026, 6, 10)
    assert ec["today"]["close"] == 10.4
    assert ec["backfill"]["target_date"] == "2026-06-10"
    assert ec["realtime"]["price"] == 10.4
    assert ec["realtime"]["change_pct"] == 1.9  # 2026-06-10 的 pct_chg
    pipeline.search_service.search_comprehensive_intel.assert_not_called()


def test_backfill_missing_target_bar_returns_none():
    pipeline, captured, target = _build_pipeline_with_real_db()
    from src.storage import StockDaily
    with pipeline.db.get_session() as session:
        session.query(StockDaily).filter(
            StockDaily.code == "600519",
            StockDaily.date == target,
        ).delete()
        session.commit()
    result = pipeline.analyze_stock(
        code="600519",
        report_type=SimpleNamespace(value="detailed"),
        query_id="q2",
        target_date=target,
        backfill_mode=True,
    )
    assert result is None


def test_normal_mode_does_not_set_backfill_marker():
    pipeline, captured, _ = _build_pipeline_with_real_db()
    pipeline.analyze_stock(
        code="600519",
        report_type=SimpleNamespace(value="detailed"),
        query_id="q3",
        current_time=None,
        backfill_mode=False,
    )
    assert "backfill" not in captured["enhanced_context"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_pipeline_backfill_mode.py -v`
Expected: `test_backfill_uses_target_date_context` FAIL（`analyze_stock` 不接受 `target_date` 参数，或 `enhanced_context["date"]` 是今天而非 X）；`test_backfill_missing_target_bar_returns_none` 可能 FAIL 或 ERROR；`test_normal_mode_does_not_set_backfill_marker` 可能 PASS（回归不变）。

- [ ] **Step 3: 修改 `process_single_stock` 签名与冻结逻辑**

`src/core/pipeline.py:2768-2804`，把方法签名和冻结逻辑改为：

```python
def process_single_stock(
    self,
    code: str,
    skip_analysis: bool = False,
    single_stock_notify: bool = False,
    report_type: ReportType = ReportType.SIMPLE,
    analysis_query_id: Optional[str] = None,
    current_time: Optional[datetime] = None,
    backfill_mode: bool = False,
    target_date: Optional[date] = None,
) -> Optional[AnalysisResult]:
    """
    处理单只股票的完整流程

    Args:
        analysis_query_id: 查询链路关联 id
        code: 股票代码
        skip_analysis: 是否跳过 AI 分析
        single_stock_notify: 是否启用单股推送模式（每分析完一只立即推送）
        report_type: 报告类型枚举（从配置读取，Issue #119）
        current_time: 本轮运行冻结的参考时间，用于统一断点续传目标交易日判断
        backfill_mode: 回填模式，冻结日期由 target_date 直接接管
        target_date: 回填目标日期（backfill_mode=True 时必填），直接冻结到该日
    """
    logger.info(f"========== 开始处理 {code} ==========")

    from src.services.history_loader import set_frozen_target_date, reset_frozen_target_date
    if backfill_mode and target_date is not None:
        frozen_td = target_date
    else:
        frozen_td = self._resolve_resume_target_date(code, current_time=current_time)
    token = set_frozen_target_date(frozen_td)
```

- [ ] **Step 4: 修改 `process_single_stock` 透传 `target_date` 给 `analyze_stock`**

`src/core/pipeline.py:2833-2838`，把 `analyze_kwargs` 构造改为：

```python
analyze_kwargs = {"query_id": effective_query_id}
if current_time is not None:
    analyze_kwargs["current_time"] = current_time
if backfill_mode:
    analyze_kwargs["backfill_mode"] = True
    if target_date is not None:
        analyze_kwargs["target_date"] = target_date
result = self.analyze_stock(code, report_type, **analyze_kwargs)
```

- [ ] **Step 5: 修改 `analyze_stock` 签名**

`src/core/pipeline.py:360-367`，把签名改为：

```python
def analyze_stock(
    self,
    code: str,
    report_type: ReportType,
    query_id: str,
    current_time: Optional[datetime] = None,
    backfill_mode: bool = False,
    target_date: Optional[date] = None,
) -> Optional[AnalysisResult]:
```

- [ ] **Step 6: 修改 `analyze_stock` Step 5 取 context 逻辑**

`src/core/pipeline.py:620-636`，把取 context 与降级逻辑改为：

```python
# Step 5: 获取分析上下文（技术面数据）
self._emit_progress(58, f"{stock_name}：正在整理分析上下文")
if backfill_mode and target_date is not None:
    context = self.db.get_analysis_context_as_of(code, target_date)
else:
    context = self._get_analysis_context_with_market_fallback(code)

if context is None:
    if backfill_mode and target_date is not None:
        logger.warning(f"[{code}] backfill: 无 {target_date} 行情数据，跳过")
        return None
    logger.warning(f"[{stock_name}({code}) 无法获取历史行情数据，将仅基于新闻和实时行情分析")
    _mkt_date = get_market_now(
        get_market_for_stock(normalize_stock_code(code))
    ).date()
    context = {
        'code': code,
        'stock_name': stock_name,
        'date': _mkt_date.isoformat(),
        'data_missing': True,
        'today': {},
        'yesterday': {}
    }
```

- [ ] **Step 7: 修改 `analyze_stock` backfill 标记与 realtime**

`src/core/pipeline.py:658-669`，把 backfill 标记注入改为：

```python
if backfill_mode and target_date is not None:
    enhanced_context["backfill"] = {
        "target_date": target_date.isoformat(),
        "data_scope": "price_only",
        "created_at": datetime.now().isoformat(),
    }
    if not enhanced_context.get("realtime"):
        today_bar = context.get("today") or {}
        enhanced_context["realtime"] = {
            "price": today_bar.get("close"),
            "change_pct": today_bar.get("pct_chg"),
        }
```

- [ ] **Step 8: 确认 `date` 类型已 import**

Run: `grep -n "^from datetime import\|^import datetime" src/core/pipeline.py | head -3`
Expected: 已有 `from datetime import ... date ...` 或 `import datetime`。若仅有 `import datetime`，需把 `target_date: Optional[date]` 改为 `target_date: Optional["datetime.date"]` 或补 `from datetime import date`。

若缺失，在 `src/core/pipeline.py` 顶部 import 区补：

```python
from datetime import date, datetime, timedelta, timezone
```

- [ ] **Step 9: 运行测试确认通过**

Run: `python -m pytest tests/test_pipeline_backfill_mode.py -v`
Expected: 3 passed

若 `test_backfill_uses_target_date_context` 报 `AttributeError` 或 `KeyError`（mock 不全），按报错补 mock：常见缺 `pipeline._attach_belong_boards_to_fundamental_context`、`pipeline._build_legacy_analysis_artifacts` 依赖的属性。补 mock 时优先用 `MagicMock(return_value={})`。

- [ ] **Step 10: py_compile 校验**

Run: `python -m py_compile src/core/pipeline.py`
Expected: 无输出

- [ ] **Step 11: 回归现有 backfill 测试**

Run: `python -m pytest tests/test_analysis_service_backfill.py tests/test_pipeline_backfill_mode.py tests/test_backfill_api.py tests/test_history_backfilled_flag.py tests/test_analysis_repo_backfill.py -v`
Expected: 全部 PASS（现有测试不受影响）

- [ ] **Step 12: Commit**

```bash
git add src/core/pipeline.py tests/test_pipeline_backfill_mode.py
git commit -m "fix(pipeline): backfill uses target_date for context and frozen date"
```

---

### Task 3: `analysis_service.backfill_as_of_date` 改传 `target_date` + 端到端测试

**Files:**
- Modify: `src/services/analysis_service.py:211-218`（`backfill_as_of_date` 调 `process_single_stock` 时改传 `target_date`）
- Test: `tests/test_analysis_service_backfill.py`（追加端到端测试）

**Interfaces:**
- Consumes: `process_single_stock(..., target_date=date, backfill_mode=True)`（Task 2 产出）。
- Produces: `backfill_as_of_date` 调 `process_single_stock` 时传 `target_date`、不传 `current_time`；落库的 `context_snapshot.enhanced_context.date == X`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_analysis_service_backfill.py` 末尾追加：

```python
def test_backfill_writes_target_date_to_snapshot_e2e(tmp_path):
    """端到端：真实 pipeline + 真实 db，落库 enhanced_context.date == X。"""
    import json
    import os
    from unittest.mock import patch, MagicMock

    from src.storage import DatabaseManager
    from src.services.analysis_service import AnalysisService

    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url=f"sqlite:///{tmp_path}/backfill_e2e.db")

    target = date(2026, 6, 10)
    from datetime import timedelta
    import pandas as pd
    rows = []
    for i in range(10):
        d = date(2026, 6, 1) + timedelta(days=i)
        rows.append({
            "date": d, "open": 9.0 + i * 0.1, "high": 10.0 + i * 0.1,
            "low": 8.5 + i * 0.1, "close": 9.5 + i * 0.1,
            "volume": 1000.0 + i * 100, "pct_chg": 1.0 + i * 0.1,
            "ma5": 9.0, "ma10": 8.8, "ma20": 8.5,
        })
    df = pd.DataFrame(rows)
    df["code"] = "600519"
    db.save_daily_data(df, "600519", "test")

    saved_snapshots = []
    original_save = db.save_analysis_history

    def _capture_save(result, query_id, report_type, news_content, context_snapshot, save_snapshot):
        saved_snapshots.append(context_snapshot)
        return original_save(
            result=result, query_id=query_id, report_type=report_type,
            news_content=news_content, context_snapshot=context_snapshot,
            save_snapshot=save_snapshot,
        )

    db.save_analysis_history = _capture_save

    with patch("src.services.analysis_service.is_market_open", return_value=True), \
         patch("src.services.analysis_service.StockAnalysisPipeline") as Pipe:
        # 用真实管线行为：实例化后调 process_single_stock 走真实路径
        from src.core.pipeline import StockAnalysisPipeline
        from src.config import Config
        real_pipe = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        real_pipe.db = db
        real_pipe.config = MagicMock(spec=Config)
        real_pipe.config.enable_realtime_quote = True
        real_pipe.config.report_language = "zh"
        real_pipe.config.agent_mode = False
        real_pipe.config.agent_skills = []
        real_pipe.config.fundamental_stage_timeout_seconds = 1
        real_pipe.config.daily_market_context_enabled = False
        real_pipe.config.market_review_enabled = False
        real_pipe.config.litellm_model = "test-model"
        real_pipe.query_source = "backfill"
        real_pipe.analysis_phase = "auto"
        real_pipe.analysis_skills = None
        real_pipe.save_context_snapshot = True
        real_pipe.portfolio_context = None
        real_pipe.fetcher_manager = MagicMock()
        real_pipe.fetcher_manager.get_stock_name.return_value = "测试股"
        real_pipe.fetcher_manager.get_realtime_quote.return_value = None
        real_pipe.fetcher_manager.get_chip_distribution.return_value = None
        real_pipe.fetcher_manager.get_fundamental_context.return_value = {}
        real_pipe.fetcher_manager.build_failed_fundamental_context.return_value = {}
        real_pipe.search_service = MagicMock()
        real_pipe.search_service.is_available = True
        real_pipe.search_service.search_comprehensive_intel = MagicMock(return_value={})
        real_pipe.social_sentiment_service = None
        real_pipe.trend_analyzer = MagicMock()
        real_pipe.trend_analyzer.analyze.return_value = MagicMock(
            trend_status=MagicMock(value="up"), buy_signal=MagicMock(value="none"),
            signal_score=50, ma_alignment="bull", trend_strength=0.5,
            bias_ma5=0.01, bias_ma10=0.02,
            volume_status=MagicMock(value="normal"), volume_trend="up",
            signal_reasons=[], risk_factors=[], ma5=10.0, ma10=9.8, ma20=9.5,
        )
        real_pipe.analyzer = MagicMock()
        real_pipe.analyzer.analyze = MagicMock(return_value=MagicMock(
            success=True, code="600519", name="测试股",
            current_price=None, change_pct=None, query_id="q",
            operation_advice="持有", sentiment_score=60,
            model_used="m", report_language="zh",
            analysis_summary="", news_summary="", technical_analysis="",
            fundamental_analysis="", risk_warning="", to_dict=lambda: {},
            error_message=None,
        ))
        real_pipe._emit_progress = MagicMock()

        Pipe.return_value = real_pipe

        svc = AnalysisService()
        with patch.object(svc.repo, "find_real_analysis_for_date", return_value=False):
            result = svc.backfill_as_of_date(["600519"], target, force=True)

    assert result["saved"] == 1
    assert len(saved_snapshots) == 1
    snapshot = saved_snapshots[0]
    enhanced = snapshot.get("enhanced_context", {})
    assert enhanced.get("date") == "2026-06-10"
    assert enhanced.get("backfill", {}).get("target_date") == "2026-06-10"

    DatabaseManager.reset_instance()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_analysis_service_backfill.py::test_backfill_writes_target_date_to_snapshot_e2e -v`
Expected: FAIL（`result["saved"] == 1` 断言失败，因为 `backfill_as_of_date` 还在传 `current_time` 而非 `target_date`，pipeline 走旧冻结逻辑导致 frozen=X-1、context 取今天）

- [ ] **Step 3: 修改 `backfill_as_of_date` 调用**

`src/services/analysis_service.py:211-218`，把 `process_single_stock` 调用改为：

```python
result = pipeline.process_single_stock(
    code=code,
    skip_analysis=False,
    single_stock_notify=False,
    report_type=ReportType.from_str(report_type),
    target_date=target_date,
    backfill_mode=True,
)
```

移除原 `current_time=datetime.combine(target_date, datetime.min.time())` 这一行。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_analysis_service_backfill.py -v`
Expected: 全部 PASS（含原有 4 个 + 新增端到端 1 个）

若端到端测试因 mock 不全报 `AttributeError`，按报错补 mock（参考 Task 2 Step 9 说明）。

- [ ] **Step 5: py_compile 校验**

Run: `python -m py_compile src/services/analysis_service.py`
Expected: 无输出

- [ ] **Step 6: Commit**

```bash
git add src/services/analysis_service.py tests/test_analysis_service_backfill.py
git commit -m "fix(analysis_service): backfill passes target_date to pipeline"
```

---

### Task 4: 文档更新

**Files:**
- Modify: `docs/backfill-guide.md`（追加「已知限制」段）
- Modify: `docs/CHANGELOG.md`（`[Unreleased]` 追加一条扁平格式条目）

**Interfaces:**
- Consumes: 无。
- Produces: 文档与实际行为一致。

- [ ] **Step 1: 更新 `docs/backfill-guide.md`**

在 `docs/backfill-guide.md` 末尾或合适位置追加「已知限制」段：

```markdown
## 已知限制

- **X 日 K 线缺失时 backfill 计 errors**：`get_analysis_context_as_of` 要求 `target_date` 当日 bar 与前一交易日 bar 均存在，任一缺失即返回 `None`，该股计入 `errors`。需先确保 X 日行情已入库（可先跑一次正常当日分析或手动补行情）。
- **回填记录的 `enhanced_context.date = X`**：回填记录的 `context_snapshot.enhanced_context.date` 严格等于用户选择的 `target_date`，回测据此归类。回填记录同时带 `backfill.target_date` 标记，与 `enhanced_context.date` 一致。
- **非忠实复现**：回填记录基于 X 日价格历史 + 今日模型生成，不含历史新闻/基本面，不等同于当天真实分析。
```

- [ ] **Step 2: 更新 `docs/CHANGELOG.md`**

在 `docs/CHANGELOG.md` 的 `[Unreleased]` 段下追加一条扁平格式条目（不新增 `###` 类目标题）：

```markdown
- [修复] 按指定日期补填分析实际按当前时间生成（db.get_analysis_context 忽略 target_date、冻结日错位、backfill 标记取错日期）
```

- [ ] **Step 3: 核对命令与字段名**

Run: `grep -n "get_analysis_context_as_of\|enhanced_context.date\|backfill.target_date" docs/backfill-guide.md`
Expected: 能匹配到对应字段名，与代码一致。

- [ ] **Step 4: Commit**

```bash
git add docs/backfill-guide.md docs/CHANGELOG.md
git commit -m "docs: note backfill target_date fix and limitations"
```

---

### Task 5: 全量回归与 CI 门禁

**Files:**
- 无文件改动，仅运行验证。

**Interfaces:**
- Consumes: Task 1-4 全部完成。
- Produces: 验证证据（CI 通过、测试通过）。

- [ ] **Step 1: 运行受影响测试全套**

Run: `python -m pytest tests/test_pipeline_backfill_mode.py tests/test_analysis_service_backfill.py tests/test_storage_backfill_context.py tests/test_backfill_api.py tests/test_history_backfilled_flag.py tests/test_analysis_repo_backfill.py -v`
Expected: 全部 PASS

- [ ] **Step 2: 运行 CI 门禁**

Run: `./scripts/ci_gate.sh`
Expected: 通过（无 lint 错误、无 import 错误、关键模块导入 smoke 通过）

- [ ] **Step 3: py_compile 全量校验改动文件**

Run: `python -m py_compile src/storage.py src/core/pipeline.py src/services/analysis_service.py`
Expected: 无输出

- [ ] **Step 4: 检查 AI 协作资产一致性（若改动涉及）**

Run: `python scripts/check_ai_assets.py`
Expected: 通过（本任务未改 AI 协作资产，预期无变化）

- [ ] **Step 5: 汇总交付说明**

按 AGENTS.md 第 5 节「默认工作流」第 8 步交付结构，准备 PR 描述：

- **改了什么**：`DatabaseManager.get_analysis_context_as_of` 新方法（按 X 日精确取上下文）；`pipeline.process_single_stock` / `analyze_stock` 增 `target_date` 参数，backfill 模式直接冻结 X、调新方法、backfill 标记写 X、realtime 用 X bar；`analysis_service.backfill_as_of_date` 传 `target_date`；测试重写为端到端；文档补充。
- **为什么这么改**：原实现 `db.get_analysis_context` 忽略 `target_date` 取最新两天数据，导致 backfill 实际按当前时间分析；`current_time=X 00:00` 触发 `get_effective_trading_date` "未收盘退一日"导致 frozen=X-1；`backfill.target_date` 从 `context["date"]` 取到今天。
- **验证情况**：CI 门禁通过；新增/重写测试通过；现有 backfill 测试回归通过。
- **未验证项**：真实 LLM 调用（测试 mock analyzer）；跨市场（港股/美股）时区（方案 A 不依赖时区，理论无差异，测试只覆盖 A 股）。
- **风险点**：`get_analysis_context_as_of` 与 `get_analysis_context` 返回形状必须一致（单测覆盖）；`process_single_stock` 新增参数默认 `None`，正常调用路径不变（回归测试覆盖）。
- **回滚方式**：回退本次提交即可；回填记录仍是普通 `analysis_history` + backfill 标记，兼容性不变。

- [ ] **Step 6: （可选）推送与 PR**

按 AGENTS.md 规则，未经确认不执行 `git push`。若用户确认推送：

```bash
git push -u origin feat/backfill-historical-analysis
gh pr create --title "fix: 按指定日期补填分析实际按当前时间生成" --body "<交付说明>"
```
