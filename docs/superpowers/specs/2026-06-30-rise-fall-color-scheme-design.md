# 涨跌颜色统一适配 MARKET_REVIEW_COLOR_SCHEME

**日期**: 2026-06-30
**状态**: 设计完成

## 问题

设置页的「大盘复盘涨跌颜色」(`MARKET_REVIEW_COLOR_SCHEME`) 切换为「红涨绿跌」后，持仓股页面和回测页面仍显示绿涨红跌。根因是前端多处涨跌颜色硬编码，未读取该设置。

## 排查结果

### 需要修复（PRICE_DIRECTION）

| # | 文件 | 行 | 当前实现 | 问题 |
|---|---|---|---|---|
| 1 | `StockHistoryTrendDrawer.tsx` | 58-63, 356 | `getPriceChangeStyle()` → inline `var(--home-price-up/down)` | CSS 变量硬编码红涨绿跌 |
| 2 | `ReportOverview.tsx` | 180-194, 235, 260, 263 | `getPriceChangeStyle()` → inline `var(--home-price-up/down)` | 同上 |
| 3 | `ReportOverview.tsx` | 209-214, 226 | `getBoardStatusVariant()` → `'success'`/`'danger'` Badge | 领涨/领跌 Badge 不跟随设置 |
| 4 | `StockScreeningPage.tsx` | 392 | `text-red-500` 硬编码 | 「强势领先」标签硬编码红色 |

### 已修复（上一轮）

- `PortfolioPage.tsx` — unrealizedPnlBase / unrealizedPnlPct 列 ✅
- `BacktestPage.tsx` — actualReturnPct 列 ✅

### 不需要修改（STATUS_INDICATOR）

- `BacktestPage.tsx:209,211` — win/loss/neutral tally（分类计数）
- `DecisionSignalsPage.tsx:655,659,663` — hit/miss/unable（预测准确率）
- `DecisionSignalDisplay.tsx:156,158,179` — 通用 tone 色板
- `StockScreeningPage.tsx:1232` — 运行状态图标
- `StockScreeningPage.tsx:1332` — 风险等级 Badge
- `MarketReviewReportView.tsx:552,595` — changePct 当前无颜色
- `SuggestionsList.tsx:80,81` — 市场分类 Badge
- 所有 error/success 图标、表单校验、连接状态等

## 方案

统一使用 `useColorScheme` hook（已创建于 `hooks/useColorScheme.ts`）。

```ts
// hooks/useColorScheme.ts — 已有实现
export function useColorScheme() {
  // 从 systemConfigApi 读取 MARKET_REVIEW_COLOR_SCHEME
  // green_up: riseClass='text-success', fallClass='text-danger'
  // red_up:   riseClass='text-danger',  fallClass='text-success'
  return { scheme, riseClass, fallClass };
}
```

### 修复 #1: StockHistoryTrendDrawer.tsx

- 删除组件外的 `getPriceChangeStyle` 函数
- 在组件内调用 `useColorScheme()`
- 将 `style={getPriceChangeStyle(item.changePct)}` 改为 `className={item.changePct > 0 ? riseClass : item.changePct < 0 ? fallClass : ''}`

### 修复 #2: ReportOverview.tsx

- 删除组件内的 `getPriceChangeStyle` 局部函数
- 在组件内调用 `useColorScheme()`
- 将 `style={getPriceChangeStyle(...)}` 改为 className 方式使用 riseClass/fallClass

### 修复 #3: ReportOverview.tsx (领涨/领跌 Badge)

- 删除 `getBoardStatusVariant` 函数
- 在渲染处改为：`variant={board.signal.status === 'leading' ? riseVariant : fallVariant}`
- riseVariant/fallVariant 根据 scheme 返回 `'success'`/`'danger'`

### 修复 #4: StockScreeningPage.tsx (强势领先)

- `getHotspotStrength` 改为接受 riseClass/fallClass 参数
- 将 `'bg-red-500/10 text-red-500'` 替换为动态的 riseClass + 对应 bg 类
- 在组件内调用 `useColorScheme()`

## 验证

- TypeScript 编译通过
- `green_up` 模式：涨绿跌红（默认，行为不变）
- `red_up` 模式：涨红跌绿（所有 6 处位置一致）
