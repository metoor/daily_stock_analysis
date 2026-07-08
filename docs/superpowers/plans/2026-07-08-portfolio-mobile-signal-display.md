# 持仓卡片移动端「AI 建议」显示修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复移动端持仓卡片中 `PortfolioSignalSummary` 因 `min-w-[11rem]` 撑破 2 列网格导致的溢出裁切，并让风险摘要/观察条件全文显示。

**Architecture:** 纯响应式 CSS 改动。`PortfolioSignalSummary` 的 `min-w`/`max-w`/`justify-end`/`line-clamp-2` 加 `sm:` 前缀（桌面生效、移动端不生效）；移动卡片 dl 网格中信号行 `dt`/`dd` 加 `col-span-2` 整行通栏。`useIsMobile`（`max-width:639px`）与 Tailwind `sm:`（640px）断点对齐，同一组件自动适配两种上下文。

**Tech Stack:** React + TypeScript + Tailwind v4 + Vitest（单元）+ Playwright（e2e）

## Global Constraints

- Tailwind v4，`sm:` 断点 = 640px；`useIsMobile` 用 `(max-width: 639px)`，二者对齐。
- 不新增组件、不新增 prop、不新增交互。
- 桌面端表格（`<table>` 分支）行为不变：`sm:` 类在 ≥640px 生效，保持原 `min-w-[11rem]` + `line-clamp-2` + 右对齐。
- 单元测试用 Vitest + `@testing-library/react`；e2e 用 Playwright，需 `DSA_WEB_SMOKE_PASSWORD` 环境变量。
- 提交信息前缀沿用 `fix(web):` / `test(web):`。

---

### Task 1: PortfolioSignalSummary 响应式改造 + 单元回归测试

**Files:**
- Modify: `apps/dsa-web/src/components/decision-signals/DecisionSignalDisplay.tsx:493-500`
- Test: `apps/dsa-web/src/components/decision-signals/__tests__/DecisionSignalDisplay.test.tsx`

**Interfaces:**
- Consumes: `DecisionSignalItem`（含可选 `riskSummary`/`watchConditions` 字符串）、`useUiLanguage` 的 `t`
- Produces: `PortfolioSignalSummary` 组件（props 不变：`{ item?, loading? }`），仅 className 变化

**背景：** `line-clamp-2` 是纯 CSS 视觉截断，不移除 DOM 文本节点，故单元测试为回归守护（characterization test），断言全文文本存在于 DOM，防止后续误改为条件渲染。

- [ ] **Step 1: 写单元回归测试**

在 `DecisionSignalDisplay.test.tsx` 末尾 ` portfolio signal horizon` 测试（约 L217）之后、`});` 之前追加：

```tsx
  it('renders full risk summary and watch conditions text in the DOM', () => {
    const longRisk = '短期均线多头排列，成交量放大，但 RSI 接近超买区域，注意回调风险。板块整体走强，资金流入明显。';
    const longWatch = '突破前高 10.80 后回踩不破 10.50；日线 MACD 金叉有效。';
    render(
      <UiLanguageProvider>
        <PortfolioSignalSummary item={{ ...signal, riskSummary: longRisk, watchConditions: longWatch }} />
      </UiLanguageProvider>,
    );
    expect(screen.getByText(longRisk)).toBeInTheDocument();
    expect(screen.getByText(longWatch)).toBeInTheDocument();
  });
```

- [ ] **Step 2: 运行测试，确认通过（改动前即应通过，回归守护）**

Run: `cd apps/dsa-web && npx vitest run src/components/decision-signals/__tests__/DecisionSignalDisplay.test.tsx`
Expected: PASS（若失败说明 `signal` fixture 或导入路径有误，先修正）

- [ ] **Step 3: 改造 PortfolioSignalSummary 为响应式类**

将 `DecisionSignalDisplay.tsx` 中 `PortfolioSignalSummary` 的 return（约 L492-501）：

```tsx
  return (
    <div className="min-w-[11rem] max-w-[18rem] text-left">
      <div className="flex flex-wrap items-center justify-end gap-1.5">
        <Badge variant={getActionVariant(item)}>{actionLabel}</Badge>
        {item.horizon ? <span className="text-[11px] text-secondary-text">{getDecisionSignalHorizonLabel(item.horizon, t)}</span> : null}
      </div>
      {item.riskSummary ? <p className="mt-1 line-clamp-2 text-[11px] text-warning">{item.riskSummary}</p> : null}
      {item.watchConditions ? <p className="mt-1 line-clamp-2 text-[11px] text-secondary-text">{item.watchConditions}</p> : null}
    </div>
  );
```

改为（`min-w`/`max-w`/`justify-end`/`line-clamp-2` 均加 `sm:` 前缀）：

```tsx
  return (
    <div className="sm:min-w-[11rem] sm:max-w-[18rem] text-left">
      <div className="flex flex-wrap items-center sm:justify-end gap-1.5">
        <Badge variant={getActionVariant(item)}>{actionLabel}</Badge>
        {item.horizon ? <span className="text-[11px] text-secondary-text">{getDecisionSignalHorizonLabel(item.horizon, t)}</span> : null}
      </div>
      {item.riskSummary ? <p className="mt-1 sm:line-clamp-2 text-[11px] text-warning">{item.riskSummary}</p> : null}
      {item.watchConditions ? <p className="mt-1 sm:line-clamp-2 text-[11px] text-secondary-text">{item.watchConditions}</p> : null}
    </div>
  );
```

- [ ] **Step 4: 运行单元测试确认仍通过**

Run: `cd apps/dsa-web && npx vitest run src/components/decision-signals/__tests__/DecisionSignalDisplay.test.tsx`
Expected: PASS（全部用例，含新增的全文渲染用例）

- [ ] **Step 5: 类型检查**

Run: `cd apps/dsa-web && npx tsc -b`
Expected: exit 0，无错误

- [ ] **Step 6: 提交**

```bash
git add apps/dsa-web/src/components/decision-signals/DecisionSignalDisplay.tsx apps/dsa-web/src/components/decision-signals/__tests__/DecisionSignalDisplay.test.tsx
git commit -m "fix(web): make PortfolioSignalSummary responsive to mobile width

Prefix min-w/max-w/justify-end/line-clamp-2 with sm: so mobile cards
get full-width unclamped signal text while desktop table keeps its
compact clamped layout."
```

---

### Task 2: 移动卡片信号行通栏 + e2e 溢出回归

**Files:**
- Modify: `apps/dsa-web/src/pages/PortfolioPage.tsx:1250-1253`（信号 dt/dd）
- Modify: `apps/dsa-web/e2e/mobile-smoke.spec.ts`（OVERFLOW_PAGES 列表，约 L130-136）

**Interfaces:**
- Consumes: Task 1 产出的响应式 `PortfolioSignalSummary`
- Produces: 移动端持仓卡片信号行通栏布局；portfolio 纳入 e2e 溢出回归

- [ ] **Step 1: 给 e2e 溢出回归添加 portfolio 页**

在 `mobile-smoke.spec.ts` 的 `OVERFLOW_PAGES` 数组（约 L130-136）中加入 portfolio：

```ts
const OVERFLOW_PAGES = [
  { name: 'login', path: '/login', requiresAuth: false },
  { name: 'backtest', path: '/backtest', requiresAuth: true },
  { name: 'alerts', path: '/alerts', requiresAuth: true },
  { name: 'portfolio', path: '/portfolio', requiresAuth: true },
  { name: 'usage', path: '/usage', requiresAuth: true },
  { name: 'settings', path: '/settings', requiresAuth: true },
];
```

- [ ] **Step 2: 移动卡片信号 dt/dd 加 col-span-2**

在 `PortfolioPage.tsx` 移动卡片分支的 `<dl className="grid grid-cols-2 ...">` 内，找到信号行（约 L1250-1253）：

```tsx
                        <dt className="text-secondary">{t('decisionSignals.portfolioColumn')}</dt>
                        <dd className="text-secondary">
                          <PortfolioSignalSummary item={signal} loading={portfolioSignalsLoading} />
                        </dd>
```

改为（dt/dd 均加 `col-span-2`）：

```tsx
                        <dt className="text-secondary col-span-2">{t('decisionSignals.portfolioColumn')}</dt>
                        <dd className="text-secondary col-span-2">
                          <PortfolioSignalSummary item={signal} loading={portfolioSignalsLoading} />
                        </dd>
```

注意：只改信号行这一对 dt/dd，其余字段（数量、均价、最新价、市值、浮盈）保持 2 列不变。

- [ ] **Step 3: 类型检查 + 构建**

Run: `cd apps/dsa-web && npx tsc -b && npm run build`
Expected: exit 0，构建成功

- [ ] **Step 4: 运行 e2e 溢出回归（若环境可用）**

若设置了 `DSA_WEB_SMOKE_PASSWORD`：

Run: `cd apps/dsa-web && DSA_WEB_SMOKE_PASSWORD=<密码> npx playwright test e2e/mobile-smoke.spec.ts -g "portfolio no horizontal overflow on mobile" --project=mobile-chrome`
Expected: PASS（`scrollWidth <= clientWidth`）

若未设置密码，跳过运行，在提交信息中注明 e2e 需在配密码环境中验证。

- [ ] **Step 5: 提交**

```bash
git add apps/dsa-web/src/pages/PortfolioPage.tsx apps/dsa-web/e2e/mobile-smoke.spec.ts
git commit -m "fix(web): span portfolio mobile signal row full width

Signal dt/dd get col-span-2 so PortfolioSignalSummary no longer blows
out the 2-col grid on mobile. Adds portfolio to e2e overflow regression."
```

---

## Self-Review

**1. Spec coverage:**
- §6.1 PortfolioPage dt/dd col-span-2 -> Task 2 Step 2 ✓
- §6.2 PortfolioSignalSummary sm: 前缀 -> Task 1 Step 3 ✓
- §7.1 e2e 溢出回归 -> Task 2 Step 1/4 ✓
- §7.2 单元全文渲染测试 -> Task 1 Step 1 ✓
- §3 非目标（不改桌面、不加 prop/交互）-> 全程遵守 ✓

**2. Placeholder scan:** 无 TBD/TODO；每步含完整代码与命令。

**3. Type consistency:** `PortfolioSignalSummary` props `{ item?, loading? }` 未变；`signal` fixture 字段（`riskSummary`/`watchConditions`）与 `DecisionSignalItem` 类型一致；`col-span-2` 是 Tailwind 类名无类型影响。
