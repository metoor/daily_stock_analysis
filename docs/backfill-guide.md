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
- 该股 X 日已有**真实**记录 → 默认跳过；`force=true` 忽略查重并重新执行（可能与已有记录共存）。
- 回填记录可被回测消费；如需在回测中排除回填记录，按 `context_snapshot.enhanced_context.backfill` 标记过滤（本期不提供 UI 过滤）。

## 5. API

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analysis/backfill \
  -H "Content-Type: application/json" \
  -d '{"stock_codes":["600519"],"target_date":"2026-06-10"}'
```

返回 `202 {task_id, ...}`，轮询 `GET /api/v1/analysis/status/{task_id}` 查进度。

## 6. 已知限制

- **X 日 K 线缺失时 backfill 计 errors**：`get_analysis_context_as_of` 要求 `target_date` 当日 bar 与前一交易日 bar 均存在，任一缺失即返回 `None`，该股计入 `errors`。需先确保 X 日行情已入库（可先跑一次正常当日分析或手动补行情）。
- **回填记录的 `enhanced_context.date = X`**：回填记录的 `context_snapshot.enhanced_context.date` 严格等于用户选择的 `target_date`，回测据此归类。回填记录同时带 `backfill.target_date` 标记，与 `enhanced_context.date` 一致。
- **非忠实复现**：回填记录基于 X 日价格历史 + 今日模型生成，不含历史新闻/基本面，不等同于当天真实分析。
