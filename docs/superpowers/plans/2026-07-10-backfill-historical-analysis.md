# 按日期补填历史分析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提供「按指定历史日期补填分析」能力——以 X 日价格为基准、跳过新闻/基本面、生成一条标记为回填的 `analysis_history` 记录，使回测能把它正确归到 X 日；前端在历史趋势抽屉提供单股补填入口。

**Architecture:** 给分析管线加 `backfill_mode`（冻结日期复用既有 `current_time`→`set_frozen_target_date`；跳过实时/新闻/社交/基本面；在 `enhanced_context` 注入 `backfill` 标记；现价取自 X 日 bar）。新增 `AnalysisService.backfill_as_of_date` 做校验+查重+逐股编排，`POST /api/v1/analysis/backfill` 用 `submit_background_task` 异步执行。历史摘要透出 `backfilled` 标记，抽屉据此显示标签并提供补填入口。

**Tech Stack:** Python / FastAPI / SQLAlchemy（后端），React + TypeScript + Tailwind + zustand（前端 `apps/dsa-web`），pytest / vitest + React Testing Library（测试）。

## Global Constraints

- commit message 使用英文、**不添加 `Co-Authored-By`**（AGENTS.md 硬规则）；未经确认不执行 `git push`/`git tag`。
- 不新增配置项、不改 `.env.example`（复用现有配置，满足「不配置也可运行」）。
- 主分析热路径零行为变更：`backfill_mode` 默认 `False`，所有守卫以 `and not backfill_mode` / `if backfill_mode` 形式叠加，正常调用路径完全不变。
- 后端验证：`./scripts/ci_gate.sh` 与 `python -m py_compile <changed>`；前端：`cd apps/dsa-web && npm run lint && npm run build`。
- 用户可见能力变更须同步 `docs/CHANGELOG.md`（`[Unreleased]` 扁平格式 `- [类型] 描述`）与专题文档；Web UI 改动 PR 须附截图。
- 回填标记落在持久化的 `context_snapshot.enhanced_context.backfill`（经 `_build_context_snapshot` 自然持久化，与回测读取的 `enhanced_context.date` 同层）。

## File Structure

后端：
- `src/core/pipeline.py` — 加 `backfill_mode` 参数 + 守卫 + 标记注入（主流程最小侵入）。
- `src/repositories/analysis_repo.py` — 加 `find_real_analysis_for_date` 查重。
- `src/services/analysis_service.py` — 加 `backfill_as_of_date` 编排。
- `api/v1/schemas/analysis.py` — 加 `BackfillRequest` / `BackfillAccepted`。
- `api/v1/endpoints/analysis.py` — 加 `POST /api/v1/analysis/backfill`。
- `src/services/history_service.py` + `api/v1/endpoints/history.py` + `api/v1/schemas/history.py` — 历史摘要透出 `backfilled`。

前端：
- `apps/dsa-web/src/types/analysis.ts` — `HistoryItem` 加 `backfilled`；加 `BackfillRequest`/`BackfillAccepted` 类型。
- `apps/dsa-web/src/api/analysis.ts` — 加 `analysisApi.backfill`。
- `apps/dsa-web/src/components/history/StockHistoryTrendDrawer.tsx` — 补填按钮 + 日期选择 + 轮询 + 「回填」标签。
- `apps/dsa-web/src/i18n/uiText.ts` — 中英 i18n key。

文档：
- `docs/backfill-guide.md`（新建）、`docs/CHANGELOG.md`（追加）。

测试：
- `tests/test_pipeline_backfill_mode.py`（新建）
- `tests/test_analysis_repo_backfill.py`（新建）
- `tests/test_analysis_service_backfill.py`（新建）
- `tests/test_backfill_api.py`（新建）
- `tests/test_history_backfilled_flag.py`（新建）
- `apps/dsa-web/src/components/history/__tests__/StockHistoryTrendDrawer.test.tsx`（追加）

---

### Task 1: 管线 `backfill_mode` 钩子

**Files:**
- Modify: `src/core/pipeline.py`（`process_single_stock` 签名 ~2751、`analyze_kwargs` ~2815；`analyze_stock` 签名 ~360、实时行情 ~423、基本面 ~480、新闻 ~558、社交 ~597、标记注入 ~652）
- Test: `tests/test_pipeline_backfill_mode.py`

**Interfaces:**
- Produces: `StockAnalysisPipeline.process_single_stock(..., backfill_mode: bool = False)` 与 `analyze_stock(..., backfill_mode: bool = False)`。`backfill_mode=True` 时：不调实时/新闻/社交/基本面；`enhanced_context["backfill"]` 存在；`enhanced_context["date"]` == 目标日；`enhanced_context["realtime"]["price"]` 来自 X 日 bar。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_pipeline_backfill_mode.py
# -*- coding: utf-8 -*-
from datetime import datetime, date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _build_pipeline_with_mocks():
    from src.core.pipeline import StockAnalysisPipeline
    from src.config import Config

    pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
    pipeline.config = MagicMock(spec=Config)
    pipeline.config.enable_realtime_quote = True
    pipeline.config.report_language = "zh"
    pipeline.config.agent_mode = False
    pipeline.config.agent_skills = []
    pipeline.config.fundamental_stage_timeout_seconds = 1
    pipeline.query_source = "api"
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

    pipeline.db = MagicMock()
    # 返回两根 bar，使 context['date'] 落到目标日
    bar = SimpleNamespace(
        to_dict=lambda: {
            "date": "2026-06-10", "close": 10.0, "open": 9.5,
            "high": 10.2, "low": 9.4, "volume": 1000, "pct_chg": 1.0,
        }
    )
    pipeline.db.get_data_range.return_value = [bar]
    pipeline.db.save_fundamental_snapshot = MagicMock()
    pipeline.db.save_analysis_history.return_value = 1

    pipeline.trend_analyzer = MagicMock()
    pipeline.trend_analyzer.analyze.return_value = SimpleNamespace(
        trend_status=SimpleNamespace(value="up"),
        buy_signal=SimpleNamespace(value="none"),
        signal_score=50,
    )

    captured = {}

    def _fake_analyze(enhanced_context, **kwargs):
        captured["enhanced_context"] = enhanced_context
        return SimpleNamespace(
            success=True, code="600519", name="测试股",
            current_price=None, change_pct=None, query_id="q",
            operation_advice="持有", sentiment_score=60,
            model_used="m", report_language="zh",
            analysis_summary="", news_summary="", technical_analysis="",
            fundamental_analysis="", risk_warning="", to_dict=lambda: {},
            error_message=None,
        )

    pipeline.analyzer = MagicMock()
    pipeline.analyzer.analyze = _fake_analyze
    pipeline._emit_progress = MagicMock()
    return pipeline, captured


def test_backfill_mode_skips_intelligence_and_stamps_marker():
    pipeline, captured = _build_pipeline_with_mocks()
    target = date(2026, 6, 10)

    pipeline.analyze_stock(
        code="600519",
        report_type=SimpleNamespace(value="detailed"),
        query_id="q1",
        current_time=datetime.combine(target, datetime.min.time()),
        backfill_mode=True,
    )

    pipeline.search_service.search_comprehensive_intel.assert_not_called()
    ec = captured["enhanced_context"]
    assert "backfill" in ec
    assert ec["backfill"]["data_scope"] == "price_only"
    assert ec["realtime"]["price"] == 10.0


def test_normal_mode_does_not_set_backfill_marker():
    pipeline, captured = _build_pipeline_with_mocks()
    pipeline.analyze_stock(
        code="600519",
        report_type=SimpleNamespace(value="detailed"),
        query_id="q2",
        current_time=None,
        backfill_mode=False,
    )
    assert "backfill" not in captured["enhanced_context"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_pipeline_backfill_mode.py -v`
Expected: FAIL（`analyze_stock() got an unexpected keyword argument 'backfill_mode'`）

- [ ] **Step 3: 给 `process_single_stock` 加参数并透传**

`src/core/pipeline.py` 的 `process_single_stock` 签名加 `backfill_mode`：

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
    ) -> Optional[AnalysisResult]:
```

在同方法的 `analyze_kwargs` 处追加透传（位于现有 `if current_time is not None:` 之后、`result = self.analyze_stock(...)` 之前）：

```python
            analyze_kwargs = {"query_id": effective_query_id}
            if current_time is not None:
                analyze_kwargs["current_time"] = current_time
            if backfill_mode:
                analyze_kwargs["backfill_mode"] = True
            result = self.analyze_stock(code, report_type, **analyze_kwargs)
```

- [ ] **Step 4: 给 `analyze_stock` 加参数与守卫**

签名加 `backfill_mode: bool = False`：

```python
    def analyze_stock(
        self,
        code: str,
        report_type: ReportType,
        query_id: str,
        current_time: Optional[datetime] = None,
        backfill_mode: bool = False,
    ) -> Optional[AnalysisResult]:
```

实时行情守卫（原 `if self.config.enable_realtime_quote:` 改为）：

```python
                if self.config.enable_realtime_quote and not backfill_mode:
```

基本面守卫（将 `try:` 体里首行替换为带分支）：

```python
            fundamental_context = None
            try:
                if backfill_mode:
                    fundamental_context = {}
                else:
                    fundamental_context = self.fetcher_manager.get_fundamental_context(
                        code,
                        budget_seconds=getattr(
                            self.config,
                            'fundamental_stage_timeout_seconds',
                            FUNDAMENTAL_STAGE_TIMEOUT_SECONDS_DEFAULT,
                        ),
                    )
            except Exception as e:
                logger.warning(f"{stock_name}({code}) 基本面聚合失败: {e}")
                fundamental_context = self.fetcher_manager.build_failed_fundamental_context(code, str(e))
```

新闻守卫（原 `if self.search_service is not None and self.search_service.is_available:` 改为）：

```python
            if self.search_service is not None and self.search_service.is_available and not backfill_mode:
```

社交情绪守卫（原 `if self.social_sentiment_service is not None and self.social_sentiment_service.is_available and is_us_stock_code(code):` 改为）：

```python
            if self.social_sentiment_service is not None and self.social_sentiment_service.is_available and is_us_stock_code(code) and not backfill_mode:
```

- [ ] **Step 5: 注入回填标记 + 用 bar 补现价**

在 `enhanced_context` 构建完成之后（紧跟现有 `if portfolio_context is not None: enhanced_context["portfolio_context"] = dict(portfolio_context)` 之后、`# Step 7: 调用 AI 分析` 之前）插入：

```python
            if backfill_mode:
                enhanced_context["backfill"] = {
                    "target_date": context.get("date"),
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

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_pipeline_backfill_mode.py -v`
Expected: PASS（3 个测试全过）

- [ ] **Step 7: 提交**

```bash
git add src/core/pipeline.py tests/test_pipeline_backfill_mode.py
git commit -m "feat(analysis): add backfill_mode to analysis pipeline"
```

---

### Task 2: 分析记录查重（按分析日期）

**Files:**
- Modify: `src/repositories/analysis_repo.py`（加 `find_real_analysis_for_date`；import 补 `date`）
- Test: `tests/test_analysis_repo_backfill.py`

**Interfaces:**
- Produces: `AnalysisRepository.find_real_analysis_for_date(code: str, target_date: date) -> bool`——存在该股 `enhanced_context.date == target_date` 且**无** `backfill` 标记的真实记录时返回 `True`。
- Consumes: `BacktestRepo.parse_analysis_date_from_snapshot`（复用回测的日期解析，保证语义一致）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_analysis_repo_backfill.py
# -*- coding: utf-8 -*-
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.repositories.analysis_repo import AnalysisRepository


def _record(ctx_dict):
    return SimpleNamespace(context_snapshot=json.dumps(ctx_dict))


def _make_repo(records):
    repo = AnalysisRepository.__new__(AnalysisRepository)
    repo.db = MagicMock()
    repo.db.get_analysis_history.return_value = records
    return repo


def test_returns_true_when_real_record_matches_date():
    repo = _make_repo([_record({"enhanced_context": {"date": "2026-06-10"}})])
    assert repo.find_real_analysis_for_date("600519", date(2026, 6, 10)) is True


def test_returns_false_when_only_backfill_record_matches_date():
    repo = _make_repo([
        _record({"enhanced_context": {"date": "2026-06-10", "backfill": {"data_scope": "price_only"}}})
    ])
    assert repo.find_real_analysis_for_date("600519", date(2026, 6, 10)) is False


def test_returns_false_when_no_matching_date():
    repo = _make_repo([_record({"enhanced_context": {"date": "2026-06-09"}})])
    assert repo.find_real_analysis_for_date("600519", date(2026, 6, 10)) is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_analysis_repo_backfill.py -v`
Expected: FAIL（`AttributeError: 'AnalysisRepository' object has no attribute 'find_real_analysis_for_date'`）

- [ ] **Step 3: 实现**

`src/repositories/analysis_repo.py` 顶部 import 改为：

```python
from datetime import datetime, timedelta, date
```

在类内（`count_by_code` 之后）追加：

```python
    def find_real_analysis_for_date(self, code: str, target_date: date) -> bool:
        """
        判断该股是否已存在「真实」（非回填）分析记录，其分析日期 == target_date。

        分析日期取自 context_snapshot.enhanced_context.date（与回测同源）；
        带 backfill 标记的记录视为回填记录，不计入。
        """
        from src.repositories.backtest_repo import BacktestRepo
        from src.utils.data_processing import parse_json_field

        days = max(1, (date.today() - target_date).days + 3)
        try:
            records = self.db.get_analysis_history(code=code, days=days, limit=500)
        except Exception as e:
            logger.warning("find_real_analysis_for_date 查询失败 code=%s: %s", code, e)
            return False

        for record in records:
            snapshot = parse_json_field(getattr(record, "context_snapshot", None))
            if not isinstance(snapshot, dict):
                continue
            enhanced = snapshot.get("enhanced_context")
            if not isinstance(enhanced, dict) or "backfill" in enhanced:
                continue
            record_date = BacktestRepo.parse_analysis_date_from_snapshot(
                getattr(record, "context_snapshot", None)
            )
            if record_date == target_date:
                return True
        return False
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_analysis_repo_backfill.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/repositories/analysis_repo.py tests/test_analysis_repo_backfill.py
git commit -m "feat(analysis): add real-record lookup by analysis date"
```

---

### Task 3: `AnalysisService.backfill_as_of_date`

**Files:**
- Modify: `src/services/analysis_service.py`（加 `backfill_as_of_date`）
- Test: `tests/test_analysis_service_backfill.py`

**Interfaces:**
- Consumes: Task 1 的 `process_single_stock(..., current_time=<X>, backfill_mode=True)`；Task 2 的 `find_real_analysis_for_date`；`trading_calendar.is_market_open`。
- Produces: `AnalysisService.backfill_as_of_date(stock_codes, target_date, force=False, report_type="detailed", progress_callback=None) -> dict`，返回 `{processed, saved, skipped, errors, message, diagnostics}`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_analysis_service_backfill.py
# -*- coding: utf-8 -*-
from datetime import date, datetime
from unittest.mock import patch

from src.services.analysis_service import AnalysisService


def _service():
    return AnalysisService()


def test_rejects_future_target_date():
    svc = _service()
    future = date.today().replace(year=date.today().year + 1)
    result = svc.backfill_as_of_date(["600519"], future)
    assert result["processed"] == 0
    assert result["errors"] >= 1
    assert "未来" in result["message"] or "未收盘" in result["message"]


def test_skips_when_real_record_exists_without_force():
    svc = _service()
    with patch.object(svc.repo, "find_real_analysis_for_date", return_value=True), \
         patch("src.services.analysis_service.is_market_open", return_value=True):
        result = svc.backfill_as_of_date(["600519"], date(2026, 6, 10))
    assert result["skipped"] == 1
    assert result["processed"] == 0


def test_force_overrides_existing_record():
    svc = _service()
    with patch.object(svc.repo, "find_real_analysis_for_date", return_value=True), \
         patch("src.services.analysis_service.is_market_open", return_value=True), \
         patch("src.core.pipeline.StockAnalysisPipeline") as Pipe:
        Pipe.return_value.process_single_stock.return_value = None
        result = svc.backfill_as_of_date(["600519"], date(2026, 6, 10), force=True)
    assert result["skipped"] == 0
    Pipe.return_value.process_single_stock.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_analysis_service_backfill.py -v`
Expected: FAIL（`AttributeError: 'AnalysisService' object has no attribute 'backfill_as_of_date'` 与导入错误）

- [ ] **Step 3: 实现**

在 `src/services/analysis_service.py` 顶部 import 区追加：

```python
from datetime import datetime
from src.core.trading_calendar import is_market_open, get_market_for_stock
from src.services.stock_code_utils import normalize_stock_code
```

在 `AnalysisService` 类内（`analyze_stock` 之后）追加：

```python
    def backfill_as_of_date(
        self,
        stock_codes: List[str],
        target_date: "date",
        force: bool = False,
        report_type: str = "detailed",
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        以 target_date 为基准补填分析（冻结价格、跳过新闻/基本面、标记为回填）。

        - target_date 必须 < 今天且为该股交易日。
        - 该股 target_date 已有真实记录则跳过（force 可覆盖）。
        - 单股失败不中断，计入 errors。
        """
        from src.config import get_config
        from src.core.pipeline import StockAnalysisPipeline
        from src.enums import ReportType

        today = datetime.now().date()
        processed = saved = skipped = errors = 0
        skip_reasons: list = []

        if not stock_codes:
            return {"processed": 0, "saved": 0, "skipped": 0, "errors": 0,
                    "message": "stock_codes 不能为空", "diagnostics": {}}

        for code in stock_codes:
            if target_date >= today:
                errors += 1
                skip_reasons.append(f"{code}: 目标日期须早于今天（未收盘/未来日期不接受）")
                continue
            market = get_market_for_stock(normalize_stock_code(code))
            if not is_market_open(market, target_date):
                errors += 1
                skip_reasons.append(f"{code}: {target_date} 非该市场交易日（或日历不可用）")
                continue
            if not force and self.repo.find_real_analysis_for_date(code, target_date):
                skipped += 1
                skip_reasons.append(f"{code}: {target_date} 已有真实分析记录，已跳过（force 可覆盖）")
                continue

            processed += 1
            try:
                if progress_callback:
                    progress_callback(20, f"{code}：正在以 {target_date} 为基准补填分析")
                config = get_config()
                pipeline = StockAnalysisPipeline(
                    config=config,
                    query_id=uuid.uuid4().hex,
                    trace_id=uuid.uuid4().hex,
                    query_source="backfill",
                    progress_callback=progress_callback,
                )
                result = pipeline.process_single_stock(
                    code=code,
                    skip_analysis=False,
                    single_stock_notify=False,
                    report_type=ReportType.from_str(report_type),
                    current_time=datetime.combine(target_date, datetime.min.time()),
                    backfill_mode=True,
                )
                if result is not None and getattr(result, "success", False):
                    saved += 1
                else:
                    errors += 1
                    skip_reasons.append(f"{code}: 分析未成功（可能无 {target_date} 行情）")
            except Exception as e:
                errors += 1
                logger.error(f"backfill {code}@{target_date} 失败: {e}", exc_info=True)
                skip_reasons.append(f"{code}: {e}")

        message = (
            f"补填完成：处理 {processed}，保存 {saved}，跳过 {skipped}，错误 {errors}"
            if processed else ("未处理任何记录；" + "；".join(skip_reasons[:3]))
        )
        return {
            "processed": processed,
            "saved": saved,
            "skipped": skipped,
            "errors": errors,
            "message": message,
            "diagnostics": {"reasons": skip_reasons},
        }
```

注：`logger`、`uuid`、`date` 已在文件作用域可用（`uuid` 已 import；补 `from datetime import date, datetime` 到顶部 import，若 `date` 未导入）。检查文件顶部 `from typing import ...` 已含 `List, Dict, Any, Optional, Callable`（已有）。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_analysis_service_backfill.py -v`
Expected: PASS

- [ ] **Step 5: 集成测试——回测能把回填记录认作 X 日（价值锚点）**

在 `tests/test_analysis_service_backfill.py` 追加：

```python
def test_backfilled_record_resolves_to_target_date_for_backtest():
    """回填记录的 enhanced_context.date == target_date，回测据此归类。"""
    from src.repositories.backtest_repo import BacktestRepo
    svc = _service()
    # 模拟回填后落库的 context_snapshot（由管线 backfill_mode 产生）
    snapshot = '{"enhanced_context": {"date": "2026-06-10", "backfill": {"data_scope": "price_only"}}}'
    parsed = BacktestRepo.parse_analysis_date_from_snapshot(snapshot)
    assert parsed == date(2026, 6, 10)
```

Run: `python -m pytest tests/test_analysis_service_backfill.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/services/analysis_service.py tests/test_analysis_service_backfill.py
git commit -m "feat(analysis): add backfill_as_of_date service method"
```

---

### Task 4: API 契约 `POST /api/v1/analysis/backfill`

**Files:**
- Modify: `api/v1/schemas/analysis.py`（加 `BackfillRequest` / `BackfillAccepted`）
- Modify: `api/v1/endpoints/analysis.py`（加端点；import 补 `date`）
- Test: `tests/test_backfill_api.py`

**Interfaces:**
- Produces: `POST /api/v1/analysis/backfill`，Body `BackfillRequest{stock_codes, target_date, force?, report_type?, notify?}` → 202 `BackfillAccepted{task_id, trace_id, status, message}`。`target_date >= today` 或空 codes → 400。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_backfill_api.py
# -*- coding: utf-8 -*-
from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from server import app


client = TestClient(app)


def test_backfill_rejects_future_date():
    future = (date.today() + timedelta(days=1)).isoformat()
    resp = client.post("/api/v1/analysis/backfill", json={
        "stock_codes": ["600519"], "target_date": future,
    })
    assert resp.status_code == 400


def test_backfill_rejects_empty_codes():
    resp = client.post("/api/v1/analysis/backfill", json={
        "stock_codes": [], "target_date": "2026-06-10",
    })
    assert resp.status_code == 400


def test_backfill_accepts_valid_request():
    with patch("src.services.analysis_service.AnalysisService.backfill_as_of_date") as m:
        m.return_value = {"processed": 1, "saved": 1, "skipped": 0, "errors": 0, "message": "ok", "diagnostics": {}}
        resp = client.post("/api/v1/analysis/backfill", json={
            "stock_codes": ["600519"], "target_date": "2026-06-10",
        })
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    assert resp.json()["task_id"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_backfill_api.py -v`
Expected: FAIL（404，端点不存在）

- [ ] **Step 3: 加 schema**

`api/v1/schemas/analysis.py` import 补 `from datetime import date`，并在 `MarketReviewAccepted` 之后追加：

```python
class BackfillRequest(BaseModel):
    """按指定历史日期补填分析请求。"""

    stock_codes: List[str] = Field(
        ..., description="股票代码列表（可单可批）", json_schema_extra={"example": ["600519"]}
    )
    target_date: date = Field(
        ..., description="目标历史日期 YYYY-MM-DD，须早于今天且为交易日",
        json_schema_extra={"example": "2026-06-10"},
    )
    force: bool = Field(False, description="强制覆盖该日已有真实记录")
    report_type: str = Field(
        "detailed", description="报告类型", pattern="^(simple|detailed|full|brief)$"
    )
    notify: bool = Field(False, description="是否发送推送通知（默认不发）")


class BackfillAccepted(BaseModel):
    """按日期补填任务已接受。"""

    status: str = Field("accepted", description="提交状态")
    message: str = Field(..., description="提示信息")
    task_id: Optional[str] = Field(None, description="后台任务 ID")
    trace_id: Optional[str] = Field(None, description="诊断 trace ID")
```

- [ ] **Step 4: 加端点**

`api/v1/endpoints/analysis.py` import 区补：

```python
from datetime import date as _date
```

并在 schema import 块把 `BackfillRequest, BackfillAccepted` 加入从 `api.v1.schemas.analysis` 的导入。

在 `trigger_market_review` 端点之后追加：

```python
@router.post(
    "/backfill",
    response_model=BackfillAccepted,
    status_code=202,
    responses={
        202: {"description": "补填任务已接受", "model": BackfillAccepted},
        400: {"description": "请求参数错误", "model": ErrorResponse},
    },
    summary="按指定历史日期补填分析",
    description=(
        "以 target_date 为基准生成一条「价格基准、无新闻/基本面、标记为回填」的分析记录，"
        "补齐回测缺失日期。异步执行，返回 task_id 供轮询。"
    ),
)
def trigger_backfill(request: BackfillRequest) -> BackfillAccepted:
    if not request.stock_codes:
        raise api_error(400, "validation_error", "stock_codes 不能为空")
    if request.target_date >= _date.today():
        raise api_error(400, "validation_error", "target_date 必须早于今天（未收盘/未来日期不接受）")

    stock_codes = request.stock_codes
    target_date = request.target_date
    force = request.force
    report_type = request.report_type

    def _run_backfill():
        from src.services.analysis_service import AnalysisService
        return AnalysisService().backfill_as_of_date(
            stock_codes, target_date, force=force, report_type=report_type
        )

    task_id = uuid.uuid4().hex
    task = get_task_queue().submit_background_task(
        _run_backfill,
        stock_code="backfill",
        stock_name=f"补填 {target_date} 分析",
        message=f"补填 {target_date} 分析任务已提交",
        task_id=task_id,
    )
    return BackfillAccepted(
        status="accepted",
        message=f"补填 {target_date} 分析任务已提交，完成后记录会出现在历史趋势中",
        task_id=task.task_id,
        trace_id=_get_task_trace_id(task),
    )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_backfill_api.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add api/v1/schemas/analysis.py api/v1/endpoints/analysis.py tests/test_backfill_api.py
git commit -m "feat(analysis): add POST /api/v1/analysis/backfill endpoint"
```

---

### Task 5: 历史摘要透出 `backfilled`

**Files:**
- Modify: `src/services/history_service.py`（item 构建处 ~295-320 加 `backfilled`）
- Modify: `api/v1/endpoints/history.py`（`HistoryItem(...)` 映射 ~189 加 `backfilled`）
- Modify: `api/v1/schemas/history.py`（`HistoryItem` 加字段）
- Test: `tests/test_history_backfilled_flag.py`

**Interfaces:**
- Produces: `GET /api/v1/history` 返回的每个 item 含 `backfilled: bool`（取自 `context_snapshot.enhanced_context.backfill` 是否存在）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_history_backfilled_flag.py
# -*- coding: utf-8 -*-
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.services.history_service import HistoryService


def _record(ctx):
    rec = MagicMock()
    rec.id = 1
    rec.query_id = "q"
    rec.code = "600519"
    rec.name = "测试"
    rec.report_type = "detailed"
    rec.operation_advice = "持有"
    rec.trend_prediction = "上行"
    rec.analysis_summary = ""
    rec.sentiment_score = 60
    rec.created_at = None
    rec.context_snapshot = json.dumps(ctx) if ctx is not None else None
    rec.raw_result = None
    return rec


def test_history_item_backfilled_true_when_marker_present():
    svc = HistoryService.__new__(HistoryService)
    svc.db = MagicMock()
    item = svc._history_list_item(_record({"enhanced_context": {"date": "2026-06-10", "backfill": {"data_scope": "price_only"}}}))
    assert item["backfilled"] is True


def test_history_item_backfilled_false_when_absent():
    svc = HistoryService.__new__(HistoryService)
    item = svc._history_list_item(_record({"enhanced_context": {"date": "2026-06-10"}}))
    assert item["backfilled"] is False
```

> 注：若 `_history_list_item` 的真实方法名不同，以 `grep -n "def _.*item\|model_used.*record" src/services/history_service.py` 找到构建 item dict 的私有方法（约 295 行，含 `"model_used": normalize_model_used(...)`），在其中追加 `backfilled`。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_history_backfilled_flag.py -v`
Expected: FAIL（`AttributeError` 或返回 dict 无 `backfilled` 键）

- [ ] **Step 3: 服务层加字段**

在 `src/services/history_service.py` 的 item 构建方法（含 `"model_used": normalize_model_used(...)`、`"created_at": ...`、`"market_phase_summary": ...` 的 return dict）中追加一行：

```python
            "backfilled": self._extract_backfilled(getattr(record, "context_snapshot", None)),
```

并在类内追加辅助方法（紧邻 `_extract_history_market_fields`）：

```python
    @staticmethod
    def _extract_backfilled(context_snapshot: Any) -> bool:
        snapshot = parse_json_field(context_snapshot)
        if not isinstance(snapshot, dict):
            return False
        enhanced = snapshot.get("enhanced_context")
        return isinstance(enhanced, dict) and "backfill" in enhanced
```

`parse_json_field` 已在该文件 import（见 `from src.utils.data_processing import ... parse_json_field`）。

- [ ] **Step 4: 端点映射 + schema 加字段**

`api/v1/endpoints/history.py` 的 `HistoryItem(...)` 构造追加：

```python
                backfilled=item.get("backfilled"),
```

`api/v1/schemas/history.py` 的 `HistoryItem` 模型加字段（紧邻 `market_phase_summary`）：

```python
    backfilled: bool = Field(False, description="是否为按日期补填的回填记录（价格基准、无新闻/基本面）")
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_history_backfilled_flag.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/services/history_service.py api/v1/endpoints/history.py api/v1/schemas/history.py tests/test_history_backfilled_flag.py
git commit -m "feat(history): surface backfilled flag in history summary"
```

---

### Task 6: 前端类型与 API client

**Files:**
- Modify: `apps/dsa-web/src/types/analysis.ts`（`HistoryItem` 加 `backfilled`；加 `BackfillRequest`/`BackfillAccepted`）
- Modify: `apps/dsa-web/src/api/analysis.ts`（加 `backfill`）
- 无新测试（类型 + 简单封装，由 Task 7 的组件测试覆盖）

**Interfaces:**
- Produces: `analysisApi.backfill(data: BackfillRequest): Promise<BackfillAccepted>`；`HistoryItem.backfilled?: boolean`。

- [ ] **Step 1: 类型定义**

`apps/dsa-web/src/types/analysis.ts` 的 `HistoryItem` 接口追加（紧邻 `marketPhaseSummary`）：

```typescript
  backfilled?: boolean;
```

并在文件合适位置（`MarketReviewAccepted` 附近）追加：

```typescript
export interface BackfillRequest {
  stockCodes: string[];
  targetDate: string;  // YYYY-MM-DD
  force?: boolean;
  reportType?: string;
  notify?: boolean;
}

export interface BackfillAccepted {
  status: string;
  message: string;
  taskId?: string;
  traceId?: string;
}
```

- [ ] **Step 2: API client**

`apps/dsa-web/src/api/analysis.ts`：在顶部 type import 加入 `BackfillRequest, BackfillAccepted`；在 `analysisApi` 对象内（`triggerMarketReview` 之后）追加：

```typescript
  /**
   * 按指定历史日期补填分析（单股或批量）。异步，返回 task_id。
   */
  backfill: async (data: BackfillRequest): Promise<BackfillAccepted> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/analysis/backfill',
      {
        stock_codes: data.stockCodes,
        target_date: data.targetDate,
        force: data.force ?? false,
        report_type: data.reportType ?? 'detailed',
        notify: data.notify ?? false,
      },
      { validateStatus: (status) => status === 202 || status === 400 }
    );

    if (response.status === 400) {
      const detail = response.data?.detail;
      const message = detail && typeof detail === 'object' && 'message' in detail
        ? String((detail as { message?: unknown }).message || '')
        : String(response.data?.message || '参数错误');
      throw new Error(message || '补填参数错误');
    }

    return toCamelCase<BackfillAccepted>(response.data);
  },
```

- [ ] **Step 3: 校验类型与构建**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: 通过（无类型错误）

- [ ] **Step 4: 提交**

```bash
git add apps/dsa-web/src/types/analysis.ts apps/dsa-web/src/api/analysis.ts
git commit -m "feat(web): add backfill types and API client"
```

---

### Task 7: 历史趋势抽屉——补填入口 + 回填标签

**Files:**
- Modify: `apps/dsa-web/src/components/history/StockHistoryTrendDrawer.tsx`
- Modify: `apps/dsa-web/src/i18n/uiText.ts`
- Test: `apps/dsa-web/src/components/history/__tests__/StockHistoryTrendDrawer.test.tsx`

**Interfaces:**
- Consumes: Task 6 的 `analysisApi.backfill`、`analysisApi.getStatus`；现有 `onRetry`（补填完成后复用其刷新历史）。

- [ ] **Step 1: i18n key**

`apps/dsa-web/src/i18n/uiText.ts` 中文段（`stockTrend.*` 区块）追加：

```typescript
  'stockTrend.backfillButton': '补填指定日期',
  'stockTrend.backfillConfirm': '将以 {date} 的价格为基准生成分析，不含新闻/基本面，标记为回填。是否继续？',
  'stockTrend.backfillSubmitting': '已提交，正在补填…',
  'stockTrend.backfillDone': '补填完成，已刷新历史',
  'stockTrend.backfillFailed': '补填失败：{reason}',
  'stockTrend.backfillBadge': '回填',
  'stockTrend.backfillDateLabel': '选择日期',
```

英文段（同 key 的英文 map）追加：

```typescript
  'stockTrend.backfillButton': 'Backfill date',
  'stockTrend.backfillConfirm': 'Generates a price-only analysis as of {date} (no news/fundamentals), marked as backfill. Continue?',
  'stockTrend.backfillSubmitting': 'Submitted, backfilling…',
  'stockTrend.backfillDone': 'Backfill done, history refreshed',
  'stockTrend.backfillFailed': 'Backfill failed: {reason}',
  'stockTrend.backfillBadge': 'Backfill',
  'stockTrend.backfillDateLabel': 'Pick a date',
```

- [ ] **Step 2: 抽屉加状态与处理函数**

`StockHistoryTrendDrawer.tsx` 顶部 import 追加：

```typescript
import { analysisApi } from '../../api/analysis';
```

组件内（`const actionLabels = useMemo(...)` 附近）追加状态与处理：

```typescript
  const [backfillDate, setBackfillDate] = useState('');
  const [backfillBusy, setBackfillBusy] = useState(false);
  const [backfillNotice, setBackfillNotice] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  const handleBackfill = async () => {
    if (!backfillDate || backfillBusy) return;
    const stockCode = report.meta.stockCode;
    if (!stockCode || !window.confirm(t('stockTrend.backfillConfirm', { date: backfillDate }))) return;
    setBackfillBusy(true);
    setBackfillNotice(null);
    try {
      const accepted = await analysisApi.backfill({ stockCodes: [stockCode], targetDate: backfillDate });
      const taskId = accepted.taskId;
      // 轮询任务状态，完成或失败后刷新历史
      await new Promise<void>((resolve, reject) => {
        const start = Date.now();
        const tick = async () => {
          try {
            const status = await analysisApi.getStatus(taskId);
            if (status.status === 'completed') return resolve();
            if (status.status === 'failed') return reject(new Error(status.error || 'failed'));
            if (Date.now() - start > 5 * 60 * 1000) return reject(new Error('timeout'));
          } catch (e) {
            return reject(e);
          }
          window.setTimeout(tick, 2000);
        };
        tick();
      });
      setBackfillNotice({ kind: 'ok', text: t('stockTrend.backfillDone') });
      onRetry();  // 复用现有历史刷新
    } catch (e) {
      setBackfillNotice({ kind: 'err', text: t('stockTrend.backfillFailed', { reason: String((e as Error).message || e) }) });
    } finally {
      setBackfillBusy(false);
    }
  };
```

- [ ] **Step 3: 抽屉加按钮 UI**

在记录卡片头部（`<RangeControls ... />` 旁，`hasMore ? <Button>...</Button> : null` 同一行容器内）追加日期输入与按钮：

```tsx
                <input
                  type="date"
                  aria-label={t('stockTrend.backfillDateLabel')}
                  value={backfillDate}
                  onChange={(e) => setBackfillDate(e.target.value)}
                  className="rounded-lg border border-border/70 bg-background/50 px-2 py-1 text-xs text-foreground"
                />
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleBackfill}
                  isLoading={backfillBusy}
                  loadingText={t('stockTrend.backfillSubmitting')}
                  disabled={!backfillDate}
                >
                  {t('stockTrend.backfillButton')}
                </Button>
```

在该 `<Card>` 内、表格之前追加提示条：

```tsx
                {backfillNotice ? (
                  <p className={`mt-3 text-xs ${backfillNotice.kind === 'ok' ? 'text-primary' : 'text-red-500'}`}>
                    {backfillNotice.text}
                  </p>
                ) : null}
```

- [ ] **Step 4: 表格行加「回填」标签**

在 `<tbody>` 的行内「时间」单元格之后追加（`item.backfilled` 为真时显示）：

```tsx
                        {item.backfilled ? (
                          <span className="ml-1 rounded bg-muted/40 px-1.5 py-0.5 text-[10px] text-secondary-text">
                            {t('stockTrend.backfillBadge')}
                          </span>
                        ) : null}
```

- [ ] **Step 5: 写组件测试**

`StockHistoryTrendDrawer.test.tsx` 追加（沿用该文件已有的 render/mock 风格）：

```typescript
  it('renders backfill button and triggers API on click', async () => {
    const backfillMock = vi.fn().mockResolvedValue({ status: 'accepted', taskId: 't1' });
    const getStatusMock = vi.fn().mockResolvedValue({ status: 'completed' });
    vi.mock('../../../api/analysis', () => ({
      analysisApi: { backfill: backfillMock, getStatus: getStatusMock },
    }));
    const { user } = renderDrawerWithItems([{ ...baseItem, backfilled: false }]);
    const input = screen.getByLabelText(/Pick a date|选择日期/);
    await user.type(input, '2026-06-10');
    const btn = screen.getByRole('button', { name: /Backfill date|补填指定日期/ });
    await user.click(btn);
    expect(backfillMock).toHaveBeenCalledWith({ stockCodes: [expect.any(String)], targetDate: '2026-06-10' });
  });
```

> `renderDrawerWithItems` / `baseItem` 沿用该测试文件已有的辅助；若命名不同，复用其现有渲染封装。

- [ ] **Step 6: 运行测试 + 构建**

Run: `cd apps/dsa-web && npm run test -- StockHistoryTrendDrawer && npm run lint && npm run build`
Expected: 测试通过、lint/build 无错

- [ ] **Step 7: 提交**

```bash
git add apps/dsa-web/src/components/history/StockHistoryTrendDrawer.tsx apps/dsa-web/src/components/history/__tests__/StockHistoryTrendDrawer.test.tsx apps/dsa-web/src/i18n/uiText.ts
git commit -m "feat(web): add backfill entry to stock history trend drawer"
```

---

### Task 8: 文档与变更记录

**Files:**
- Create: `docs/backfill-guide.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 写 `docs/backfill-guide.md`**

```markdown
# 按日期补填历史分析（Backfill）指南

> 入口：Web「历史趋势」抽屉 →「补填指定日期」。后端：`POST /api/v1/analysis/backfill`。
> 源码锚点：`src/services/analysis_service.py:backfill_as_of_date`、`src/core/pipeline.py`（`backfill_mode`）、`api/v1/endpoints/analysis.py`。

## 1. 解决什么问题

回测依赖 `analysis_history` 记录。某天若未跑成每日分析（调度未触发/服务异常），回测在该日出现空洞。本功能允许**以指定历史日期为基准补生成一条分析记录**，补齐回测缺口。

## 2. 它是什么 / 不是什么

- **是**：以 X 日**价格历史**为输入、跳过新闻/基本面、明确**标记为回填**的分析记录。回测会按 `enhanced_context.date = X` 把它正确归到 X 日。
- **不是**：对 X 日当天分析的忠实复现。新闻/基本面为空、LLM 与模型为今天版本。回填记录是降级预测，质量低于真实记录。

## 3. 用法

历史趋势抽屉选某只股票 → 点「补填指定日期」→ 选一个**早于今天且为交易日**的日期 → 确认。任务异步执行，完成后历史列表自动刷新，新记录带「回填」标签。

## 4. 约束

- `target_date` 须 `< 今天`；非交易日会被拒绝（日历不可用时降级为只挡未来日期）。
- 该股 X 日已有**真实**记录 → 默认跳过；`force=true` 可覆盖。
- 回填记录可被回测消费；如需在回测中排除回填记录，按 `context_snapshot.enhanced_context.backfill` 标记过滤（本期不提供 UI 过滤）。

## 5. API

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analysis/backfill \
  -H "Content-Type: application/json" \
  -d '{"stock_codes":["600519"],"target_date":"2026-06-10"}'
```

返回 `202 {task_id, ...}`，轮询 `GET /api/v1/analysis/status/{task_id}` 查进度。
```

- [ ] **Step 2: 追加 CHANGELOG**

`docs/CHANGELOG.md` 的 `[Unreleased]` 段追加一行（扁平格式）：

```markdown
- [新功能] 历史趋势支持按指定日期补填分析记录（价格基准、标记为回填），补齐回测缺失日期
```

- [ ] **Step 3: 核对命令与文件名一致**

确认 `docs/backfill-guide.md` 路径、`POST /api/v1/analysis/backfill` 端点名、`backfill_mode` 命名与代码一致。

- [ ] **Step 4: 提交**

```bash
git add docs/backfill-guide.md docs/CHANGELOG.md
git commit -m "docs: add backfill historical analysis guide and changelog"
```

---

## 全局收尾验证

- [ ] **后端全量门禁**：`./scripts/ci_gate.sh`
- [ ] **后端单测**：`python -m pytest tests/test_pipeline_backfill_mode.py tests/test_analysis_repo_backfill.py tests/test_analysis_service_backfill.py tests/test_backfill_api.py tests/test_history_backfilled_flag.py -v`
- [ ] **前端**：`cd apps/dsa-web && npm run lint && npm run build && npm run test`
- [ ] **手测路径**：历史趋势抽屉补填一个过去交易日 → 记录出现且带「回填」标签 → 回测页触发回测 → 该记录被归到 X 日（`enhanced_context.date`）。
