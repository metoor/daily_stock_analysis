# 持仓明细追加股票中文名 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在持仓明细表格"代码"列中，代码下方追加显示股票中文名（`nameZh`），查不到名字时保持原样只显示代码。

**Architecture:** 前端方案，不动后端。新增一个对两边代码都归一化的查询函数 `findStockInIndexByCode`（解决 `SH603288` 与 `603288.SH` 格式不匹配问题），复用已有 `useStockIndex` hook 加载的 `/stocks.index.json` 索引；在 `PortfolioPage` 持仓行渲染时查询名字并以两行堆叠布局展示。

**Tech Stack:** React + TypeScript + Vitest + @testing-library/react，前端位于 `apps/dsa-web`。

## Global Constraints

- 不修改后端 `PortfolioPositionItem` 结构与快照 API
- 不新增 i18n key（名字是数据不是列）
- 名字查不到（索引未加载 / 索引未覆盖）时不渲染第二行，等价于改动前效果
- 复用已有 `normalizeStockCode`（`apps/dsa-web/src/utils/stockCode.ts`）做归一化，不引入新归一化逻辑
- 遵循现有代码风格：组件用函数式 hooks，测试用 vitest + `describe/test`

---

## File Structure

- **Modify** `apps/dsa-web/src/utils/stockIndexLoader.ts` — 新增 `findStockInIndexByCode` 导出函数，紧邻现有 `findStockInIndex` 之后
- **Modify** `apps/dsa-web/src/utils/__tests__/stockIndexLoader.test.ts` — 为新函数补充单测
- **Modify** `apps/dsa-web/src/pages/PortfolioPage.tsx` — 加载索引、查询名字、改造"代码"列单元格渲染

---

### Task 1: 新增 `findStockInIndexByCode` 查询函数（TDD）

**Files:**
- Modify: `apps/dsa-web/src/utils/stockIndexLoader.ts`（在现有 `findStockInIndex` 函数之后追加）
- Test: `apps/dsa-web/src/utils/__tests__/stockIndexLoader.test.ts`

**Interfaces:**
- Consumes: `normalizeStockCode(stockCode: string): string`（来自 `./stockCode`，已存在）
- Produces:
  ```ts
  export function findStockInIndexByCode(
    code: string,
    index: StockIndexItem[]
  ): StockIndexItem | null
  ```
  行为：对入参 `code` 与每个 `item.canonicalCode` 都调用 `normalizeStockCode(...).toUpperCase()` 后比较，返回首个匹配项；入参为空或无匹配返回 `null`。

**Why this comes first:** `PortfolioPage` 依赖此函数；先把它和单测做完，后面接线时可以直接调用。

- [ ] **Step 1: 写失败的单测**

在 `apps/dsa-web/src/utils/__tests__/stockIndexLoader.test.ts` 顶部的 `import { ... } from '../stockIndexLoader'` 块中加入 `findStockInIndexByCode`：

```ts
import {
  loadStockIndex,
  compressIndex,
  findStockInIndex,
  findStockInIndexByCode,
  getPopularStocks,
  groupStocksByMarket,
} from '../stockIndexLoader';
```

然后在文件末尾（最后一个 `describe` 块之后、最外层 `describe('stockIndexLoader', ...)` 闭合 `});` 之前）追加新 describe 块：

```ts
  describe('findStockInIndexByCode - Find stock by normalized code', () => {
    test('matches A-share code with SH prefix against canonical X.SH format', () => {
      const result = findStockInIndexByCode('SH600519', mockIndexData);
      expect(result).not.toBeNull();
      expect(result?.nameZh).toBe('贵州茅台');
    });

    test('matches SZ prefix against canonical X.SZ format', () => {
      const result = findStockInIndexByCode('SZ000001', mockIndexData);
      expect(result?.nameZh).toBe('平安银行');
    });

    test('matches bare canonical code directly', () => {
      const result = findStockInIndexByCode('600519.SH', mockIndexData);
      expect(result?.nameZh).toBe('贵州茅台');
    });

    test('matches HK code without canonical suffix form', () => {
      const result = findStockInIndexByCode('HK00700', mockIndexData);
      expect(result?.nameZh).toBe('腾讯控股');
    });

    test('matches US ticker case-insensitively', () => {
      const result = findStockInIndexByCode('aapl', mockIndexData);
      expect(result?.nameZh).toBe('苹果');
    });

    test('returns null when code not found', () => {
      const result = findStockInIndexByCode('NOTFOUND.US', mockIndexData);
      expect(result).toBeNull();
    });

    test('returns null for empty input', () => {
      expect(findStockInIndexByCode('', mockIndexData)).toBeNull();
      expect(findStockInIndexByCode('   ', mockIndexData)).toBeNull();
    });

    test('returns null for empty index', () => {
      const result = findStockInIndexByCode('600519.SH', []);
      expect(result).toBeNull();
    });
  });
```

> 注：`HK00700` 经 `normalizeStockCode` 变为 `HK00700`，而索引 `canonicalCode` `00700.HK` 经同一函数也变为 `HK00700`（见 `stockCode.test.ts` 第 30-45 行），故能匹配。

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
cd apps/dsa-web && npx vitest run src/utils/__tests__/stockIndexLoader.test.ts
```
Expected: FAIL，报错包含 `findStockInIndexByCode is not a function` 或导入失败。

- [ ] **Step 3: 实现函数**

在 `apps/dsa-web/src/utils/stockIndexLoader.ts` 顶部的 import 区追加（紧接第 8 行 `import { INDEX_FIELD } from './stockIndexFields';` 之后）：

```ts
import { normalizeStockCode } from './stockCode';
```

然后在文件中现有的 `findStockInIndex` 函数（约第 112-117 行）之后追加：

```ts
/**
 * Find stock in index by code, normalizing both sides to tolerate
 * different exchange-annotation formats (e.g. SH600519 vs 603288.SH).
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

- [ ] **Step 4: 跑测试确认通过**

Run:
```bash
cd apps/dsa-web && npx vitest run src/utils/__tests__/stockIndexLoader.test.ts
```
Expected: PASS，全部用例（含新增 8 个）通过。

- [ ] **Step 5: 提交**

```bash
git add apps/dsa-web/src/utils/stockIndexLoader.ts apps/dsa-web/src/utils/__tests__/stockIndexLoader.test.ts
git commit -m "feat(stockIndex): add findStockInIndexByCode for normalized code lookup"
```

---

### Task 2: 在 `PortfolioPage` 接线并改造"代码"列渲染

**Files:**
- Modify: `apps/dsa-web/src/pages/PortfolioPage.tsx`
  - import 区（约第 53 行附近）追加两个 import
  - 组件体内加载索引
  - 持仓行渲染（约第 1223 行）改造单元格
- Test: 现有 `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx`（不新增用例，确保不回归）

**Interfaces:**
- Consumes:
  - `useStockIndex(): { index: StockIndexItem[]; ... }`（来自 `../hooks/useStockIndex`，已存在）
  - `findStockInIndexByCode(code: string, index: StockIndexItem[]): StockIndexItem | null`（Task 1 产出）
- Produces: 持仓明细"代码"列在能查到名字时多渲染一行 `nameZh`

**Note on test environment:** `useStockIndex` 内部 `loadStockIndex` 会 `fetch('/stocks.index.json')`。jsdom 下 `fetch` 未定义会抛错，但 hook 内 try/catch 会吞掉并进入 fallback（`index: []`），不影响组件渲染、不会让现有测试失败。无需为此 mock。

- [ ] **Step 1: 加 import**

在 `apps/dsa-web/src/pages/PortfolioPage.tsx` 顶部 import 区，找到第 53 行：

```ts
import { areStockCodesEquivalent, normalizeStockCode } from '../utils/stockCode';
```

在其**下方**追加两行：

```ts
import { useStockIndex } from '../hooks/useStockIndex';
import { findStockInIndexByCode } from '../utils/stockIndexLoader';
```

- [ ] **Step 2: 在组件体内调用 hook**

定位 `PortfolioPage` 主组件函数体（在已有的 hooks 调用附近，例如 `useState`/`useEffect` 集中区）。在组件函数顶部已有的 hook 调用之后，追加：

```ts
  const { index: stockIndex } = useStockIndex();
```

> 选位原则：紧跟其他顶层 hook，不要放进 `useEffect` 或条件块内。

- [ ] **Step 3: 改造"代码"列单元格**

定位第 1223 行：

```tsx
                      <td className="py-2 pr-2 font-mono text-foreground">{row.symbol}</td>
```

替换为：

```tsx
                      <td className="py-2 pr-2">
                        <div className="font-mono text-foreground">{row.symbol}</div>
                        {(() => {
                          const nameZh = findStockInIndexByCode(row.symbol, stockIndex)?.nameZh;
                          return nameZh ? (
                            <div className="text-[11px] text-secondary">{nameZh}</div>
                          ) : null;
                        })()}
                      </td>
```

> 说明：`font-mono` 从 `<td>` 移到代码所在的 `<div>`，确保只有代码等宽；名字行样式与同表"现价"列次行（`text-[11px] text-secondary`）一致；查不到名字时不渲染第二行。

- [ ] **Step 4: 跑 PortfolioPage 现有测试确认不回归**

Run:
```bash
cd apps/dsa-web && npx vitest run src/pages/__tests__/PortfolioPage.test.tsx
```
Expected: PASS（全部既有用例通过）。若出现 `fetch is not defined` 之类的 console.error 但用例仍 PASS，属预期（hook 内已捕获）；若用例 FAIL 需排查。

- [ ] **Step 5: 跑全量类型检查**

Run:
```bash
cd apps/dsa-web && npx tsc -p tsconfig.app.json --noEmit
```
Expected: 无新增类型错误。

- [ ] **Step 6: 提交**

```bash
git add apps/dsa-web/src/pages/PortfolioPage.tsx
git commit -m "feat(portfolio): show stock Chinese name under code in positions table"
```

- [ ] **Step 7: 手动验证（可选但推荐）**

启动前端 dev server，打开持仓管理页：
- A 股持仓（如 `SH603288`）代码下方应显示 `海天味业`
- 索引未覆盖的标的（部分 ETF / 冷门股）代码下方无第二行，与改动前一致
- 表格列宽与对齐无错乱

---

## Self-Review

**1. Spec coverage:**
- "在代码下方追加 nameZh，上下堆叠" → Task 2 Step 3 ✓
- "复用 useStockIndex + 新增查询函数（方案 A）" → Task 1 + Task 2 Step 2 ✓
- "查不到保持原样" → Task 2 Step 3 的 `nameZh ? ... : null` ✓
- "不动后端 / 不新增 i18n" → 全程无后端 / 无 featureText.ts 改动 ✓
- "格式不匹配问题（SH603288 vs 603288.SH）" → Task 1 用 `normalizeStockCode` 两边归一化 ✓

**2. Placeholder scan:** 无 TBD / TODO / "add appropriate..."。所有步骤含完整代码与命令。✓

**3. Type consistency:** `findStockInIndexByCode(code: string, index: StockIndexItem[]): StockIndexItem | null` 在 Task 1 定义、Task 2 调用一致；返回值通过可选链 `?.nameZh` 取字段，与 `StockIndexItem.nameZh: string` 类型一致。✓
