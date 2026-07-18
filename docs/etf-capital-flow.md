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
| `/api/v1/etf-capital-flow/refresh` | POST | 手动触发刷新指定日期快照 |

`POST /refresh` 支持两种刷新路径，由请求体 `{"trade_date": "YYYY-MM-DD"}`（可选字段）控制：

- **未传 `trade_date` / 空字符串 / 当天日期**：全量刷新。调用 `EtfCapitalFlowService.run_daily()`，重新拉取 akshare `fund_etf_spot_em()` 当日全市场快照（含主力净流入、折价率、最新份额等全部字段），upsert 当日 `trade_date` 行。适用于每日大盘复盘流程失败、当日数据缺失、ad-hoc 刷新当日数据。
- **历史日期**：降级回填。调用 `EtfCapitalFlowService.backfill_for_date(trade_date)`，按当日 `fund_etf_spot_em()` 总市值选 Top 100 ETF，逐只调用 `ak.fund_etf_hist_em(symbol=code, start_date=end_date=trade_date)` 拉取该日 OHLCV，构建降级快照。
- **未来日期**：HTTP 400。

响应均为 `EtfCapitalFlowSnapshotResponse`；服务异常返回 500；非法 `trade_date` 格式或未来日期返回 400。

### 历史日期回填的局限

`fund_etf_spot_em()` 仅返回当日全市场快照，akshare 没有历史资金流接口。历史日期回填只能基于 `fund_etf_hist_em()` 的 OHLCV 数据，存在以下字段缺口：

| 字段 | 当日全量刷新 | 历史日期回填 |
|---|---|---|
| `close` / `change_pct` / `turnover` / `volume` | ✅ | ✅（来自 OHLCV） |
| `total_market_value` | ✅ | ✅（来自当日 spot 排名，仅用于 Top-N 与加权） |
| `main_net_inflow` / `main_net_inflow_pct` | ✅ | `null` |
| `discount_pct` | ✅ | `null` |
| `latest_shares` / `share_change` | ✅ | `null` |
| `iopv` | ✅ | `null` |

历史回填快照 `status="partial"`，`warnings` 含 `"backfill: capital flow fields ... not available for historical dates"`。`market_overview.total_net_inflow` 为 `0.0`；`inflow_count` / `outflow_count` 改用 `change_pct` 符号统计（资金流数据不可用），并附 warning 说明。`market_overview.top_inflow` / `top_outflow` 为空（无法按 `main_net_inflow` 排序）。如果超过 50% 的 ETF 拉取失败，`status` 进一步降级为 `"failed"`。

Web 看板在 `status === "partial"` 时会在顶部展示"历史日期回填数据"黄色提示横幅，说明资金流字段缺失。

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
- 历史日期回填仅覆盖 Top 100 总市值 ETF 的价量数据（OHLCV）；`fund_etf_spot_em()` 仅返回当日全市场快照，akshare 没有历史资金流接口，因此历史日期的 `main_net_inflow` / `discount_pct` / `latest_shares` / `iopv` 等字段不可用，`status` 标为 `"partial"`。若当日定时任务失败，应在同一交易日内尽快调用 `POST /refresh` 全量刷新当日 `trade_date`；跨日只能通过历史回填路径补齐价量字段。