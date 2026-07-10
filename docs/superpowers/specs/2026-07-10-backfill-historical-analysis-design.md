# 按日期补填历史分析设计

- 日期：2026-07-10
- 范围：`src/core/pipeline.py`、`src/services/analysis_service.py`、`src/services/task_queue.py`（仅调用，不改签名）、`api/v1/endpoints/analysis.py`、`api/v1/schemas/analysis.py`、`apps/dsa-web/src/components/history/StockHistoryTrendDrawer.tsx`、`apps/dsa-web/src/types/analysis.ts`、`apps/dsa-web/src/i18n/uiText.ts`、历史摘要接口与类型
- 关联：回测模块（`src/services/backtest_service.py`、`src/core/backtest_engine.py`、`docs/backtest-guide.md`）、历史记录接口（`GET /api/v1/history`）、每日分析主流程（`src/core/pipeline.py`）

## 1. 背景与问题

回测模块对 `analysis_history` 做「后验评估」：取某条历史分析记录，以分析日收盘价为入场价，用其后 N 个交易日的行情判断 AI 建议准不准（见 `docs/backtest-guide.md`）。因此回测**强依赖**：① 该日存在 `analysis_history` 记录；② 该日前后存在日线行情。

实际使用中，常出现「**某整天没跑成每日分析**」（调度未触发、服务宕机、数据源当天异常等），导致 `analysis_history` 里**整批缺那一天**的记录，回测在对应时间段出现空洞、`processed=0`。

### 1.1 现状（代码事实）

- **历史趋势抽屉**（`StockHistoryTrendDrawer.tsx`）按股票列出 `analysis_history` 记录（来自 `GET /api/v1/history?stock_code=`），**只读**，且**只列已存在的记录**——缺失的日期不在列表里，无法在其上挂「补填」操作。
- **分析触发**（`POST /api/v1/analysis/analyze`、`AnalyzeRequest`）**没有「指定历史日期」参数**，分析始终以「今天」为基准。
- **已存在冻结日期机制**：`set_frozen_target_date(date)`（`src/services/history_loader.py`）在 `process_single_stock` 内按 `_resolve_resume_target_date(code, current_time)` 设置（`pipeline.py:2784-2846`）。它把 K 线历史截止日冻结到目标日（`load_history_df` 用 `end = frozen`）。**目前仅用于断点续传**，且**只冻结价格 K 线**，不冻结新闻/实时盘口/基本面。
- **回测如何认定「分析日期」**：`BacktestRepo.parse_analysis_date_from_snapshot`（`backtest_repo.py:430`）从 `context_snapshot.enhanced_context.date` 解析，回退到 `created_at.date()`。
- **管线容忍空新闻**：`search_service` 初始化失败时走「无搜索模式」（`pipeline.py:246`），`news_context` 为空也不阻断 LLM 分析（与 AGENTS.md「单一数据源失败不拖垮主流程」一致）。

### 1.2 关键可行性结论

将分析「冻结到 X 日」时，价格 K 线的截止日 = X，`context['date']`（即最新 bar 日期）= X，存入 `context_snapshot.enhanced_context.date` = X。因此**只要把 `current_time` 透传成目标日期，回测即可自动把补填记录认作 X 日**，无需为回测额外接线。新闻/基本面在补填模式下直接跳过（管线本就容忍缺失）。

## 2. 目标

- 提供「按指定历史日期补填分析」的后端能力：以 X 日价格为基准、跳过新闻/基本面、生成一条**明确标记为回填**的 `analysis_history` 记录，使回测能正确把它归到 X 日。
- 股票列表**可单可批**（后端能力），前端**先只做单股入口**（历史趋势抽屉）。
- 主分析热路径**零分支污染**：回填语义仅在回填调用链生效。
- 回填记录在历史趋势中**可见区分**（带「回填」标记），避免与真实当日分析混淆、误导回测结论与人工判断。

## 3. 非目标

- **不**追求忠实复现 X 日的全部输入（历史新闻、历史基本面、当日模型版本）。回填记录是「以 X 日价格历史为输入、用今天能拿到的情报（无）」生成的预测，**不等同于**当天真实分析。这是明确接受的降级。
- **不**做整日批量的前端入口（回测页「补填整天」等）。后端留口子，UI 后续迭代再加。
- **不**新增配置项 / `.env` 变更。复用现有配置，满足「不配置也可运行」。
- **不**改回测引擎、不改报告结构（回填记录就是普通 `analysis_history` + 一个标记字段，向后兼容）。
- **不**改 `task_queue` 的逐股提交路径签名。

## 4. 方案选择

| 维度 | 选项 | 选定 |
|---|---|---|
| 实现路径 | A 独立补填服务 + 独立端点 ／ B 扩展 `/analyze` 加 `target_date`+`backfill_mode` ／ C 纯 CLI | **A** |
| 新闻/基本面 | ① 跳过、允许缺失 ／ ② 尽量回溯历史新闻 | **①** |
| 触发范围 | A 单股 ／ B 整日批量 ／ 两者 | **后端两者，前端仅 A** |
| 异步模型 | 1 `submit_background_task` 单任务+轮询 ／ 2 逐股 `task_queue`+SSE | **1** |

选 A + ① + (后端单/批，前端单) + 1：

- **A**：把回填语义（冻结日期、跳情报、打标记、查重）收拢在独立服务/端点，主分析热路径无 `backfill_mode` 条件分支，契约清晰，契合 AGENTS.md「稳定性优先 + 明确契约」。B 会给主流程加模式分支、有泄漏风险；C 满足不了前端诉求。
- **①**：新闻回溯在多数数据源上做不到，投入产出不划算；回测核心验「方向判断」，价格历史是最关键输入，新闻缺失让分析偏保守但不致回测失效。
- **后端单/批、前端仅单**：痛点是「天」级别（整天缺记录），后端按股票列表设计自然支持批量；但前端先只做单股入口（用户原始诉求是历史趋势内补填），避免提前做无用的批量 UI。
- **1**：`submit_background_task`（`task_queue.py:465`）是为「需任务可见性、但非标准逐股分析」的自定义任务设计的钩子（market-review 同款）。用它**不改逐股提交链路签名**，进度/SSE 自带；批量时仍是单任务、不灌爆队列、不误拦同股票正在跑的正常当日分析。Option 2 要给共享逐股路径穿三层签名、收益不抵风险。

## 5. 架构说明

### 5.1 数据流

```
[历史趋势抽屉] 点「补填指定日期」→ 选日期 X（须 < 今、且为该股交易日）
      │  POST /api/v1/analysis/backfill { stock_codes:[当前股], target_date:X }
      ▼
[analysis.py 端点] 校验 → submit_background_task → 202 {task_id}
      │
      ▼
[AnalysisService.backfill_as_of_date] 逐股：
   ① 查重：该股 X 日已有「真实」记录？→ skipped（force 可覆盖）
   ② process_single_stock(code, current_time=X, backfill_mode=True)
         ├─ set_frozen_target_date(X) → K 线截止 X → enhanced_context.date = X
         ├─ backfill_mode：跳过 实时盘口 / 新闻 / 社交 / 情报
         ├─ current_price/change_pct 取 X 日 bar 收盘/涨跌
         └─ context_snapshot 注入 backfill 标记 → 落库 analysis_history
   ③ 汇总 {processed, saved, skipped, errors, message, diagnostics}
      │
      ▼
[前端] 轮询任务状态 → 完成后刷新历史列表 → 新记录出现（带「回填」标签）
      │  （回测页正常触发回测 → 该记录因 enhanced_context.date=X 被正确归到 X 日）
```

### 5.2 管线钩子（`src/core/pipeline.py`）

- `process_single_stock` 增参 `backfill_mode: bool = False`，随现有 `current_time` 一并透传进 `analyze_stock`（`pipeline.py:2815-2818` 的 `analyze_kwargs`）。
- `pipeline.analyze_stock` 增参 `backfill_mode: bool = False`，为 `True` 时：
  - **跳过** 实时盘口获取（Step 1，`pipeline.py:421-429`）；`current_price`/`change_pct` 由 X 日那根日线 bar 的收盘价/涨跌填充（避免报告现价为空）。
  - **跳过** 新闻/社交/情报搜索（search_service / social_sentiment / intelligence），`news_context` 留空。
  - 在构建并持久化 `context_snapshot` 时注入标记：
    ```json
    "backfill": { "target_date": "YYYY-MM-DD", "data_scope": "price_only", "created_at": "<now iso>" }
    ```
- `current_time=target_date` 复用既有冻结逻辑，不改。**正常调用（`backfill_mode=False`）行为完全不变**。

### 5.3 服务层（`src/services/analysis_service.py`）

新增 `backfill_as_of_date(stock_codes, target_date, force=False, report_type="detailed", progress_callback=None)`：

- 逐股 `process_single_stock(..., current_time=datetime.combine(target_date, time()), backfill_mode=True)`。
- 单股失败不中断（沿用管线现有异常隔离）。
- 返回 `{processed, saved, skipped, errors, message, diagnostics}`，风格对齐回测 `run_backtest` 返回。

### 5.4 查重与校验

- **查重**：新增 repo 查询，判断 `(code, target_date)` 是否已存在**非回填**分析记录（按 `enhanced_context.date` 匹配，排除带 `backfill` 标记的记录）。存在 → `skipped`；`force=True` 才覆盖。已有**回填**记录 → 允许 `force` 重跑。
- **校验**：
  - `target_date >= today` → 拒绝（不能补未来/当日未收盘，避免「未来信息」污染回测）。
  - 该股市场下 `target_date` 非交易日 → 拒绝。判断用 `trading_calendar.is_market_open(market, target_date)`（`is_market_open` 为 fail-open：`exchange-calendars` 不可用时返回 `True`，即不拒绝——此时校验降级为「只挡未来日期」，可接受）。
  - 两条均返回明确错误信息。

### 5.5 异步模型（`submit_background_task`）

- 端点用 `task_queue.submit_background_task(run_backfill, stock_code=<code or "backfill">, ...)` 提交，返回 `task_id`。
- `run_backfill` 闭包内调 `AnalysisService.backfill_as_of_date(...)`，并用 `update_task_progress` / `append_task_flow_event` 上报「补填 X 中…」进度与运行流事件（SSE 自带）。
- 任务结果存 `task.result = {processed, saved, skipped, errors, ...}` 供查询。
- **不改** `submit_tasks_batch` / `TaskInfo` / `_execute_task` 签名。
- **不**注册进 `_analyzing_stocks`（无逐股 in-flight 去重）：无害——服务层「X 日已有真实记录→跳过」兜住重复点击，且避免误拦同股票正在跑的正常当日分析。若后续要提交级防重，端点加轻量 in-flight 检查即可，本期不做。

### 5.6 前端（`StockHistoryTrendDrawer.tsx`）

- **入口**：记录卡片头部（`RangeControls` 旁）加「补填指定日期」按钮。
- **交互**：点击 → 弹日期选择 → 二次确认（文案：「将以 X 日价格为基准生成分析，不含新闻/基本面，标记为回填」）→ 调端点 → toast「已提交」→ 轮询任务状态 → 完成后刷新历史列表（复用现有 `onRetry`/加载逻辑）。
- **回填标记可见**：`GET /api/v1/history` 摘要新增 `backfilled: bool`（取自 `context_snapshot.backfill`）；`HistoryItem` 类型加该字段；列表内回填记录显示「回填」小标签。
- i18n：`uiText.ts` 新增按钮、确认文案、标签文案（中英）。

## 6. API 契约

```
POST /api/v1/analysis/backfill
Body: BackfillRequest {
  stock_codes: List[str]          // 必填，可单可批
  target_date: date (YYYY-MM-DD)  // 必填，须 < 今 且为交易日
  force?: bool = false
  report_type?: str = "detailed"
  notify?: bool = false           // 回填默认不发通知
}
→ 202 BackfillAccepted { task_id, trace_id, status:"accepted", message }
```

- `BackfillRequest` / `BackfillAccepted` 加在 `api/v1/schemas/analysis.py`。
- 校验失败（未来日期/非交易日/空 codes）→ 400；重复同类任务在途 → 409（如启用提交级防重）。
- 任务进度/结果复用 `GET /api/v1/analysis/status/{task_id}`（`task.status` + `task.result`）。

## 7. 错误处理

| 场景 | 行为 |
|---|---|
| `target_date` ≥ 今天 / 非交易日 | 400，明确提示 |
| `stock_codes` 空 | 400 |
| 该股 X 日已有真实记录 | `skipped`（`force` 可覆盖） |
| 某股数据获取失败 / 无 X 日行情 | 该股计 `errors`，继续其余股 |
| X 日无可用 K 线（数据源拿不到） | 该股 `errors`，提示后续补行情后重试 |

单股失败不拖垮整批，与项目「单一数据源失败不拖垮主流程」一致。

## 8. 测试范围

- **单测**（`AnalysisService.backfill_as_of_date`）：查重（跳过真实记录 / force 覆盖 / 回填记录可重跑）；`target_date` 校验（未来/今日/非交易日拒绝）。
- **单测**（管线 `backfill_mode`）：断言 search/social/intelligence 未被调用；`frozen_target_date == X`；`enhanced_context.date == X`；`context_snapshot.backfill` 标记存在且 `data_scope="price_only"`；正常模式（`backfill_mode=False`）行为不变（回归）。
- **集成（价值锚点）**：补填产生的记录被 `BacktestService` 正确归到 X 日（验证 `_resolve_analysis_date` 返回 X，且可进入回测候选）。
- **API**：`POST /backfill` 返回 202、拒绝未来/非交易日；`force` 覆盖路径。
- **前端**：抽屉渲染「补填指定日期」按钮；回填记录显示「回填」标签。
- 参考现有 fixture 风格：`tests/test_backtest_service.py` 中 `context_snapshot='{"enhanced_context":{"date":"..."}}'`。

## 9. 文档与变更记录

- 新建 `docs/backfill-guide.md`：用途、限制（非忠实复现、缺新闻/基本面）、与回测的衔接、查重/force 语义。
- `docs/CHANGELOG.md` `[Unreleased]` 新增一条扁平格式：`- [新功能] 历史趋势支持按指定日期补填分析记录（价格基准、标记为回填），补齐回测缺失日期`。
- 无新增配置项 / `.env` 改动；不涉及桌面端启动链路、通知模板、报告结构破坏性变更。

## 10. 风险与回滚

- **风险**：回填记录是降级分析（无新闻/基本面、用今日模型），混入回测会**稀释**整体胜率等指标。缓解：`context_snapshot.backfill` 标记 + 前端「回填」标签可见区分；必要时回测可按该标记过滤（本期不做，留口子）。
- **风险**：`backfill_mode` 分支误渗入正常分析。缓解：参数默认 `False`，仅在 `backfill_as_of_date` 调用链置 `True`；单测覆盖正常模式回归。
- **回滚**：回退本次提交即可——回填记录是普通 `analysis_history` + 标记字段，历史查询/抽屉/接口/回测兼容性保持不变；删除回填记录可按 `context_snapshot` 含 `backfill` 标记筛选清理。
