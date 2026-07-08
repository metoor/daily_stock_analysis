# 持仓卡片移动端「AI 建议」显示修复设计

- 日期：2026-07-08
- 范围：`apps/dsa-web/src/pages/PortfolioPage.tsx`、`apps/dsa-web/src/components/decision-signals/DecisionSignalDisplay.tsx`
- 关联：移动端适配（`docs/superpowers/specs/2026-07-04-mobile-adaptation-design.md`）的后续修复

## 1. 背景与问题

移动端持仓卡片（`<sm` 卡片列表变体）中「AI 建议」行（`PortfolioSignalSummary`）内容显示不全：

- **布局溢出**：`PortfolioSignalSummary` 根元素设了 `min-w-[11rem]`（176px），大于 2 列 `<dl>` 网格中单列宽度（约 165px @375px 屏），撑破网格导致信号区被卡片边界裁切。
- **文本截断**：`riskSummary` / `watchConditions` 用 `line-clamp-2` 限制为 2 行，完整内容不可见。

用户反馈两者都存在（c：布局溢出 + 文本截断）。

## 2. 目标

- 移动端卡片中信号区完整可见（无裁切、无横向溢出、全文显示）。
- 桌面端表格行为不变。
- 不引入新组件 / 新 prop / 新交互（YAGNI）。

## 3. 非目标

- 不改桌面端表格布局与单元格样式。
- 不改 `PortfolioSignalSummary` 的数据结构或 props。
- 不引入展开/折叠交互（选择方案 A：直接展示全文）。
- 不改其他卡片字段（金额、价格等）的渲染。

## 4. 方案选择

经可视化对比三个方案后选 **A · 信号通栏 + 完整文本**：

| 方案 | 说明 | 取舍 |
|---|---|---|
| **A（选定）** | 信号 dt/dd 整行通栏，移除移动端 min-w 与 line-clamp | 最简单，全文立即可见；文本长时卡片变高 |
| B | 信号移至卡片底部独立区 + 默认折叠 | 紧凑层次清晰；需多一次点击，加展开状态 |
| C | 信号通栏 + 默认折叠 | A/B 折中；仍需点击 |

选 A 理由：用户要全文可见，A 最直接；卡片变高的代价仅在信号文本较长时出现，可接受。

## 5. 架构说明

### 5.1 移动端 vs 桌面端渲染关系

`PortfolioPage` 用 `useIsMobile()`（`max-width:639px`）切换两套 JSX：

- `isMobile=true`（<640px）：渲染 `<Card>` 卡片列表，信号在 `<dd>` 中
- `isMobile=false`（≥640px）：渲染 `<table>`，信号在 `<td>` 中

`PortfolioSignalSummary` 是两端共用的同一组件。`useIsMobile` 断点（639px）与 Tailwind `sm:` 断点（640px）对齐，因此组件内用 `sm:` 前缀的响应式类即可自动适配两种上下文，无需 JS 分支或新 prop。

### 5.2 响应式类对齐表

| 类 | 移动端（<sm，卡片 `<dd>`） | 桌面端（≥sm，表格 `<td>`） |
|---|---|---|
| `sm:min-w-[11rem]` | 不生效（无 min-width，填满通栏 dd） | 生效（保持 176px 最小宽） |
| `sm:max-w-[18rem]` | 不生效 | 生效 |
| `sm:justify-end` | 不生效（badge 左对齐） | 生效（badge 右对齐） |
| `sm:line-clamp-2` | 不生效（全文显示） | 生效（2 行截断） |

## 6. 改动清单

### 6.1 `PortfolioPage.tsx`（移动卡片 dl 网格，约 L1250-1253）

信号行的 `dt` / `dd` 加 `col-span-2` 整行通栏：

```tsx
<dt className="text-secondary col-span-2">{t('decisionSignals.portfolioColumn')}</dt>
<dd className="text-secondary col-span-2">
  <PortfolioSignalSummary item={signal} loading={portfolioSignalsLoading} />
</dd>
```

其余字段（数量、均价、最新价、市值、浮盈）保持 2 列不变。

### 6.2 `DecisionSignalDisplay.tsx` `PortfolioSignalSummary`（L493-500）

根容器与子元素的宽度/对齐/截断类加 `sm:` 前缀：

- 根 `<div>`：`min-w-[11rem] max-w-[18rem] text-left` → `sm:min-w-[11rem] sm:max-w-[18rem] text-left`
- badge 行 `<div>`：`justify-end` → `sm:justify-end`
- `riskSummary` `<p>`：`line-clamp-2` → `sm:line-clamp-2`
- `watchConditions` `<p>`：`line-clamp-2` → `sm:line-clamp-2`

## 7. 测试

### 7.1 移动端 e2e（`apps/dsa-web/e2e/mobile-smoke.spec.ts`，390px）

- 扩展 `/portfolio` 用例：断言 `PortfolioSignalSummary` 的 riskSummary 文本在视口内可见（未被裁切）。
- 断言持仓卡片容器无横向溢出（`scrollWidth <= clientWidth`）。

### 7.2 单元测试（`DecisionSignalDisplay.test.tsx`）

- 现有用例测内容渲染，响应式类名改动不破坏断言。
- 补一条：传入较长 `riskSummary` 时，文本完整渲染于 DOM（断言文本节点存在，不依赖 `line-clamp`）。

## 8. 风险与回滚

- **风险低**：纯 className 改动，无逻辑/数据变更；桌面端 `sm:` 类生效，行为不变。
- **回滚**：还原两个文件即可。
