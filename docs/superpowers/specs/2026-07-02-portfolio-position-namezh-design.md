# 持仓明细追加股票中文名 — 设计文档

## 背景

持仓管理页（`PortfolioPage`）的"持仓明细"表格中，"代码"列目前只展示 `row.symbol`（例如 `SH603288`）。用户希望在该列代码下方追加显示股票中文名（`nameZh`，例如 `海天味业`），与代码上下堆叠排列，提升可读性。

视觉参照：同表"现价"列已是 `div + div.text-[11px].text-secondary` 的两行堆叠布局。

## 目标

- 在"代码"列中，代码下方追加显示 `nameZh`
- 名字与代码上下对齐（同一 `<td>` 内的两个 `<div>`）
- 仅当前端索引能查到名字时才渲染第二行；查不到则保持现状（仅显示代码）

## 非目标

- 不改后端 `PortfolioPositionItem` 结构、不改快照 API
- 不新增表头列（名字是"代码"列内的附属信息）
- 不做名字缓存/预取等性能优化（持仓行数通常 <50，线性扫描可接受）
- 不处理索引未加载时的占位符

## 数据源

前端已有 `/stocks.index.json`（由 `static/stocks.index.json` 提供服务），包含 `canonicalCode`（如 `603288.SH`）与 `nameZh`（如 `海天味业`）。通过 [useStockIndex](../../../apps/dsa-web/src/hooks/useStockIndex.ts) hook 加载，已被 `StockAutocomplete` 组件使用。

## 代码格式不匹配问题

| 来源 | 格式 | 示例 |
|---|---|---|
| 索引 `canonicalCode` | 数字 + `.` + 后缀 | `603288.SH`、`000001.SZ` |
| 后端 `PortfolioPositionItem.symbol` | 前缀 + 数字 | `SH603288`（见 [portfolio_service.py:1242-1254](../../../src/services/portfolio_service.py#L1242-L1254)） |

现成的 [findStockInIndex](../../../apps/dsa-web/src/utils/stockIndexLoader.ts#L112) 是 `canonicalCode === canonicalCode` 的精确匹配，直接调用会全部查不到。因此新增一个对两边都归一化的查询函数。

## 设计

### 1. 新增查询函数（方案 A）

在 [stockIndexLoader.ts](../../../apps/dsa-web/src/utils/stockIndexLoader.ts) 中，紧邻现有 `findStockInIndex` 之后，新增：

```ts
import { normalizeStockCode } from './stockCode';

/**
 * Find stock in index by code, normalizing both sides to tolerate
 * different exchange-annotation formats (e.g. SH603288 vs 603288.SH).
 *
 * @param code - Stock code in any common format
 * @param index - Stock index
 * @returns Stock index item or null
 */
export function findStockInIndexByCode(
  code: string,
  index: StockIndexItem[]
): StockIndexItem | null {
  const target = normalizeStockCode(code).toUpperCase();
  if (!target) return null;
  return index.find(item => normalizeStockCode(item.canonicalCode).toUpperCase() === target) || null;
}
```

复用已有 `normalizeStockCode`（来自 `utils/stockCode`，会把 `SH603288` / `603288.SH` / `603288` 都归一化为 `603288`）。

### 2. 在 `PortfolioPage` 中加载索引并查询

在 [PortfolioPage.tsx](../../../apps/dsa-web/src/pages/PortfolioPage.tsx) 组件内：

1. 顶部 import：`useStockIndex`、`findStockInIndexByCode`
2. 组件体内调用 `const { index } = useStockIndex();`
3. 在持仓行渲染处（[第 1223 行附近](../../../apps/dsa-web/src/pages/PortfolioPage.tsx#L1223)）查询名字：

```tsx
const nameZh = findStockInIndexByCode(row.symbol, index)?.nameZh;
```

### 3. 渲染单元格

把当前：

```tsx
<td className="py-2 pr-2 font-mono text-foreground">{row.symbol}</td>
```

改为：

```tsx
<td className="py-2 pr-2">
  <div className="font-mono text-foreground">{row.symbol}</div>
  {nameZh && <div className="text-[11px] text-secondary">{nameZh}</div>}
</td>
```

- `font-mono` 仅作用于代码行，保持代码等宽视觉
- 名字行用 `text-[11px] text-secondary`，与"现价"列的次行样式一致
- `nameZh` 为空字符串/null 时不渲染第二行，等价于改动前效果

## 测试

- 不新增专门测试（最小改动原则）
- 跑现有 `apps/dsa-web` 的 `vitest`，确认 `PortfolioPage` 相关测试不回归
- 手动验证：打开持仓页，确认 A 股代码下方显示中文名；索引未覆盖的标的（如部分 ETF/港股/美股）下方无第二行

## 风险

- **索引覆盖率**：冷门股或新股可能不在 `stocks.index.json` 中 → 表现为不显示第二行，符合预期降级
- **多次挂载 `useStockIndex`**：hook 内部 `useEffect` 在每次挂载时都会 `fetch`。`PortfolioPage` 是单页内单实例，不会重复加载；不在此处优化
- **归一化覆盖度**：`normalizeStockCode` 已覆盖 A/HK/US/JP/KR/TW 主流格式（见 `stockCode.test.ts`），与索引 `canonicalCode` 的后缀格式（`.SZ`/`.HK`/`.T`/`.KS`/`.TW`）归一化后一致
