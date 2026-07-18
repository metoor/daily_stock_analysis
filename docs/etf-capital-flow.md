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