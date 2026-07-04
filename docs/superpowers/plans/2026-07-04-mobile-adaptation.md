# Mobile Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `apps/dsa-web/` 在手机（375–414px）和平板（768–1024px）viewport 下展示正常，6 个核心页面可用、4 个兜底页面不溢出。

**Architecture:** 渐进式响应式优化。在现有 Tailwind 断点基础上新增 `xs:375px`，为 5 处宽表格加移动端卡片变体（`<sm` 渲染卡片），补全多列 grid 中间断点，扫描 recharts 图表 `ResponsiveContainer`，扩展 Playwright 加 Pixel 5 + iPad Mini 两个项目跑 smoke。不引入新抽象、不改 API/数据结构。

**Tech Stack:** React 19、TypeScript 5.9、Vite 7、Tailwind CSS v4、recharts 3、Playwright 1.58、vitest 4。

## Global Constraints

- 所有改动仅在 `apps/dsa-web/` 内，不触碰后端、桌面端、工作流。
- 不引入 `useMediaQuery` / `ResponsiveSwitch` 等新抽象（YAGNI）。
- 不重写桌面端布局，桌面端 (`lg+`) 视觉与行为保持不变。
- 不加底部 tab bar / 触摸手势 / PWA。
- commit message 用英文，不加 `Co-Authored-By`。
- 每个 Task 结尾独立 commit，commit message 用 `feat`/`fix`/`chore`/`docs` 前缀。
- 验证矩阵：每个 Task 至少跑 `npm run lint && npm run build`；涉及 e2e 的 Task 跑 `npx playwright test mobile-smoke`。
- Spec 文件：`docs/superpowers/specs/2026-07-04-mobile-adaptation-design.md`（已 commit 为 dbcae4b，后续修正未 commit，作为 Task 7 的一部分提交）。

---

### Task 1: 基础设施 — xs 断点 + Playwright 移动项目 + mobile-smoke 骨架

**Files:**
- Modify: `apps/dsa-web/tailwind.config.js:16` (在 `extend` 内加 `screens`)
- Modify: `apps/dsa-web/playwright.config.ts:58-64` (扩展 `projects` 数组)
- Create: `apps/dsa-web/e2e/mobile-smoke.spec.ts`

**Interfaces:**
- Produces: `xs:` Tailwind 断点（375px+ 可用）；`mobile-chrome` 与 `tablet-chrome` Playwright 项目；`e2e/mobile-smoke.spec.ts` 测试文件（后续 Task 会扩展断言）。

- [ ] **Step 1: 修改 `tailwind.config.js` 加 `xs` 断点**

在 `extend` 对象内（第 16 行 `extend: {` 之后）第一个属性位置插入 `screens`：

```js
extend: {
  screens: {
    xs: '375px',
  },
  colors: {
    // ... 原有内容保持不变
```

- [ ] **Step 2: 修改 `playwright.config.ts` 扩展 `projects`**

将 `projects` 数组（第 58-64 行）替换为：

```ts
projects: [
  {
    name: 'chromium',
    use: { ...devices['Desktop Chrome'] },
  },
  {
    name: 'mobile-chrome',
    use: { ...devices['Pixel 5'] },
  },
  {
    name: 'tablet-chrome',
    use: { ...devices['iPad Mini'] },
  },
],
```

- [ ] **Step 3: 创建 `e2e/mobile-smoke.spec.ts` 骨架**

```ts
import { test, expect } from '@playwright/test';

const MOBILE_PAGES = [
  { name: 'home', path: '/' },
  { name: 'chat', path: '/chat' },
  { name: 'screening', path: '/screening' },
  { name: 'portfolio', path: '/portfolio' },
  { name: 'decision-signals', path: '/decision-signals' },
  { name: 'login', path: '/login' },
];

for (const page of MOBILE_PAGES) {
  test.describe(`${page.name} page mobile smoke`, () => {
    test('loads without console errors', async ({ page: browserPage }) => {
      const errors: string[] = [];
      browserPage.on('console', (msg) => {
        if (msg.type() === 'error') errors.push(msg.text());
      });
      await browserPage.goto(page.path);
      await browserPage.waitForLoadState('domcontentloaded');
      expect(errors).toEqual([]);
    });
  });
}
```

- [ ] **Step 4: 运行 lint 验证**

Run: `cd apps/dsa-web && npm run lint`
Expected: PASS（无新增错误）

- [ ] **Step 5: 运行 build 验证**

Run: `cd apps/dsa-web && npm run build`
Expected: PASS（Tailwind v4 识别 `xs` 断点，构建成功）

- [ ] **Step 6: 验证 Playwright 项目注册**

Run: `cd apps/dsa-web && npx playwright test --list 2>&1 | grep -E "mobile-chrome|tablet-chrome" | head -5`
Expected: 输出包含 `mobile-chrome` 与 `tablet-chrome` 项目名（即使测试因无 webServer 跳过，项目名也应出现）。

- [ ] **Step 7: Commit**

```bash
git add apps/dsa-web/tailwind.config.js apps/dsa-web/playwright.config.ts apps/dsa-web/e2e/mobile-smoke.spec.ts
git commit -m "feat(web): add xs breakpoint and mobile playwright projects"
```

---

### Task 2: 5 处宽表格移动端卡片变体

**Files:**
- Modify: `apps/dsa-web/src/components/alerts/AlertRuleList.tsx:172-230` (表格区域)
- Modify: `apps/dsa-web/src/components/alerts/AlertTriggerHistory.tsx:61-100` (表格区域)
- Modify: `apps/dsa-web/src/pages/AlertsPage.tsx:330-380` (表格区域)
- Modify: `apps/dsa-web/src/pages/PortfolioPage.tsx:1200-1260` (表格区域)
- Modify: `apps/dsa-web/src/pages/StockScreeningPage.tsx:1290-1360` (表格区域)
- Modify: `apps/dsa-web/e2e/mobile-smoke.spec.ts` (加表格断言)

**Interfaces:**
- Consumes: Task 1 的 `xs:` 断点、`mobile-chrome` 项目。
- Produces: 5 个表格在 `<sm` viewport 下渲染为卡片列表；`mobile-smoke.spec.ts` 新增表格页面 `<table>` 不存在断言。

**通用卡片变体模式（每个表格按此模式改造）：**

将原表格区域改为两份渲染分支：`<sm` 显示卡片列表，`sm+` 显示原表格。模板：

```tsx
{/* 移动端卡片列表 */}
<div className="sm:hidden space-y-3">
  {items.map((item) => (
    <Card key={item.id} variant="bordered" padding="sm" className="space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-foreground">{item.primaryField}</div>
          <div className="mt-0.5 text-xs text-muted-text">{item.secondaryField}</div>
        </div>
        <Badge variant={...}>{item.statusLabel}</Badge>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <dt className="text-muted-text">{label1}</dt>
        <dd className="text-secondary-text">{item.field1}</dd>
        <dt className="text-muted-text">{label2}</dt>
        <dd className="text-secondary-text">{item.field2}</dd>
      </dl>
      <div className="flex justify-end gap-2 border-t border-border/40 pt-2">
        {item.actions}
      </div>
    </Card>
  ))}
</div>

{/* 桌面端表格（原内容，外层加 hidden sm:block） */}
<div className="hidden sm:block min-h-0 flex-1 overflow-x-auto">
  <table className="w-full min-w-[XXXpx] text-left text-sm">
    {/* 原表格内容保持不变 */}
  </table>
</div>
```

- [ ] **Step 1: AlertRuleList 卡片变体**

文件：`src/components/alerts/AlertRuleList.tsx`

将第 172-230 行的 `<div className="min-h-0 flex-1 overflow-x-auto">...</div>` 包裹的 table 区域，拆为两份：

卡片字段映射（每条 `rule`）：
- `primaryField`: `rule.name`
- `secondaryField`: `formatUiText(text.source, { source: rule.source })`
- 状态 Badge: `rule.enabled ? 'success' : 'default'`，文案 `rule.enabled ? text.enabled : text.disabled`
- 类型 Badge: `ALERT_TYPE_LABELS[language][rule.alertType]`
- 目标: `formatTarget(rule, language)` + `ALERT_SCOPE_LABELS[language][rule.targetScope]`
- 参数: `formatParameters(rule, language)`
- 冷却: `isCoolingDown(rule) ? text.coolingDown : text.notCoolingDown` + `formatDateTime(rule.cooldownUntil)`
- 更新时间: `formatDateTime(rule.updatedAt ?? rule.createdAt)`
- 操作: 原 `<td>` 内的三个按钮（test/toggle/delete）

桌面端表格外层 `<div>` 改为 `<div className="hidden sm:block min-h-0 flex-1 overflow-x-auto">`。

- [ ] **Step 2: AlertTriggerHistory 卡片变体**

文件：`src/components/alerts/AlertTriggerHistory.tsx`

将第 61-100 行 `{!isLoading && triggers.length > 0 ? (<div className="overflow-x-auto">...</div>) : null}` 内层 div 拆为两份。

卡片字段映射（每条 `trigger`）：
- `primaryField`: `statusLabel[trigger.status] ?? trigger.status`（用 Badge 形式）
- `secondaryField`: `renderPhaseQuality(trigger)`
- 目标: `trigger.target` (font-mono)
- 观察值: `formatNullable(trigger.observedValue)`
- 阈值: `formatNullable(trigger.threshold)`
- 数据源: `formatNullable(trigger.dataSource)`
- 数据时间: `formatDateTime(trigger.dataTimestamp ?? trigger.triggeredAt)`
- 原因: `trigger.reason || trigger.diagnostics || '--'`

桌面端外层 div 改为 `className="hidden sm:block overflow-x-auto"`。

- [ ] **Step 3: AlertsPage 表格卡片变体**

文件：`src/pages/AlertsPage.tsx`

第 335 行 `<table className="w-full min-w-[680px] text-left text-sm">` 外层容器（找最近的 `<div className="overflow-x-auto">` 或类似包裹元素）拆为两份。

实现前先 Read `AlertsPage.tsx:320-380` 确认该表格的列定义与每行数据结构，按 Task 2 通用模式生成卡片变体。卡片字段映射根据该表格实际列填写。

桌面端外层 div 改为 `className="hidden sm:block ..."`。

- [ ] **Step 4: PortfolioPage 表格卡片变体**

文件：`src/pages/PortfolioPage.tsx`

第 1204 行 `<table className="min-w-[860px] w-full text-sm">` 外层容器拆为两份。

实现前先 Read `PortfolioPage.tsx:1190-1260` 确认列定义（grep 显示有 `decisionSignals.portfolioColumn`，说明有持仓相关列）。按通用模式生成卡片变体。

桌面端外层 div 改为 `className="hidden sm:block ..."`。

- [ ] **Step 5: StockScreeningPage 表格卡片变体**

文件：`src/pages/StockScreeningPage.tsx`

第 1297 行 `<table className="w-full min-w-[860px] border-collapse text-sm">` 外层容器拆为两份。

实现前先 Read `StockScreeningPage.tsx:1280-1360` 确认列定义。按通用模式生成卡片变体。

桌面端外层 div 改为 `className="hidden sm:block ..."`。

- [ ] **Step 6: 在 mobile-smoke.spec.ts 加表格页面断言**

在 `e2e/mobile-smoke.spec.ts` 末尾追加：

```ts
const TABLE_PAGES = [
  { name: 'alerts', path: '/alerts' },
  { name: 'portfolio', path: '/portfolio' },
  { name: 'screening', path: '/screening' },
];

for (const page of TABLE_PAGES) {
  test.describe(`${page.name} table-to-card on mobile`, () => {
    test('renders card list instead of table in mobile-chrome', async ({ page: browserPage }) => {
      await browserPage.goto(page.path);
      await browserPage.waitForLoadState('domcontentloaded');
      // 等待表格或卡片渲染
      await browserPage.waitForTimeout(500);
      const tableCount = await browserPage.locator('table').count();
      expect(tableCount).toBe(0);
    });

    test('renders table in tablet-chrome', async ({ page: browserPage }) => {
      // tablet 768px >= sm(640px) 应显示表格
      await browserPage.goto(page.path);
      await browserPage.waitForLoadState('domcontentloaded');
      await browserPage.waitForTimeout(500);
      const tableCount = await browserPage.locator('table').count();
      expect(tableCount).toBeGreaterThan(0);
    });
  });
}
```

注意：`mobile-chrome` 项目使用 Pixel 5 (393×851)，`<sm` (640px)，应渲染卡片。`tablet-chrome` 使用 iPad Mini (768×1024)，`>=sm`，应渲染表格。两个 test 都会在两个项目下跑，但断言在 `mobile-chrome` 下应通过、在 `tablet-chrome` 下应失败——所以需要把两个 test 分别限定项目。改用 `test.describe.configure` 或在 test 名加项目过滤。

更稳妥的写法：把两个 test 分别放到不同 describe 中，并用项目名过滤。简化为只验证 `<sm` 下不存在 table：

```ts
for (const page of TABLE_PAGES) {
  test(`${page.name} no <table> in mobile viewport`, async ({ page: browserPage }) => {
    await browserPage.goto(page.path);
    await browserPage.waitForLoadState('domcontentloaded');
    await browserPage.waitForTimeout(500);
    const tableCount = await browserPage.locator('table').count();
    expect(tableCount).toBe(0);
  });
}
```

此 test 只在 `mobile-chrome` 项目跑会通过；在 `chromium` 与 `tablet-chrome` 下会失败。因此需要标记 test 仅在 mobile-chrome 跑。Playwright 用 `test.slow()` 或项目过滤：在 `playwright.config.ts` 的 `mobile-chrome` 项目加 `grep: /mobile/`，并把 test 名改为 `... mobile no-table`。

**简化方案**：把 TABLE_PAGES 的 test 名加 `mobile` 前缀，并在 `mobile-chrome` 项目配置 `grep: 'mobile'`：

修改 `playwright.config.ts` 第 58-64 行 `projects`：

```ts
projects: [
  {
    name: 'chromium',
    use: { ...devices['Desktop Chrome'] },
  },
  {
    name: 'mobile-chrome',
    use: { ...devices['Pixel 5'] },
    grep: /mobile/,
  },
  {
    name: 'tablet-chrome',
    use: { ...devices['iPad Mini'] },
  },
],
```

并把 TABLE_PAGES 的 test 名改为 `${page.name} mobile no-table`。

MOBILE_PAGES 的 test（Step 3 创建的）名也需带 `mobile` 前缀才能在 mobile-chrome 跑：把 `${page.name} page mobile smoke` 改为 `${page.name} mobile page smoke`。同时 tablet-chrome 与 chromium 不会跑这些 test（因为 grep 过滤），但 MOBILE_PAGES 在 chromium 下也应跑——所以不能把所有 test 都 grep 限制。

**最终方案**：不使用 grep，改用条件断言。test 内根据 viewport 判断：

```ts
for (const page of TABLE_PAGES) {
  test(`${page.name} table visibility by viewport`, async ({ page: browserPage, browserName }) => {
    await browserPage.goto(page.path);
    await browserPage.waitForLoadState('domcontentloaded');
    await browserPage.waitForTimeout(500);
    const tableCount = await browserPage.locator('table').count();
    const viewportWidth = browserPage.viewportSize()?.width ?? 0;
    if (viewportWidth < 640) {
      expect(tableCount).toBe(0);
    } else {
      expect(tableCount).toBeGreaterThan(0);
    }
  });
}
```

这样 test 在所有项目下都能跑，断言根据 viewport 自适应。

- [ ] **Step 7: 运行 lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 8: 运行 mobile-smoke（如本地有 webServer 环境）**

Run: `cd apps/dsa-web && DSA_WEB_SMOKE_PASSWORD=xxx npx playwright test mobile-smoke --project=mobile-chrome`
Expected: 6 个 MOBILE_PAGES test PASS，3 个 TABLE_PAGES test PASS。

如本地无 webServer 环境，跳过并在交付说明中注明"e2e 待 CI 验证"。

- [ ] **Step 9: Commit**

```bash
git add apps/dsa-web/src/components/alerts/AlertRuleList.tsx apps/dsa-web/src/components/alerts/AlertTriggerHistory.tsx apps/dsa-web/src/pages/AlertsPage.tsx apps/dsa-web/src/pages/PortfolioPage.tsx apps/dsa-web/src/pages/StockScreeningPage.tsx apps/dsa-web/e2e/mobile-smoke.spec.ts
git commit -m "feat(web): render wide tables as card list on mobile viewport"
```

---

### Task 3: 多列 grid 中间断点

**Files:**
- Modify: `apps/dsa-web/src/pages/SettingsPage.tsx:1398`
- Modify: `apps/dsa-web/src/pages/AlertsPage.tsx:284`
- Modify: `apps/dsa-web/src/pages/DecisionSignalsPage.tsx:559`

**Interfaces:**
- Produces: 3 处多列 grid 在平板与手机下不拥挤。

- [ ] **Step 1: SettingsPage grid 改造**

文件：`src/pages/SettingsPage.tsx`

第 1398 行 `lg:grid-cols-[280px_1fr]` 改为：

```tsx
className="grid gap-4 md:grid-cols-[240px_1fr] lg:grid-cols-[280px_1fr]"
```

（确保原有 `grid gap-4` 等基础类不变，只新增 `md:grid-cols-[240px_1fr]`。`<md` 时退化为单列。）

- [ ] **Step 2: AlertsPage grid 改造**

文件：`src/pages/AlertsPage.tsx`

第 284 行 `xl:grid-cols-[380px_minmax(0,1fr)]` 改为：

```tsx
className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)] xl:grid-cols-[380px_minmax(0,1fr)]"
```

（`<lg` 退化为单列。）

- [ ] **Step 3: DecisionSignalsPage grid 改造**

文件：`src/pages/DecisionSignalsPage.tsx`

第 559 行 `xl:grid-cols-7` 改为：

```tsx
className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7"
```

- [ ] **Step 4: 运行 lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dsa-web/src/pages/SettingsPage.tsx apps/dsa-web/src/pages/AlertsPage.tsx apps/dsa-web/src/pages/DecisionSignalsPage.tsx
git commit -m "feat(web): add intermediate breakpoints for multi-column grids"
```

---

### Task 4: recharts 图表 ResponsiveContainer 扫描

**Files:**
- Modify: 视扫描结果而定，所有未用 `ResponsiveContainer` 的 recharts 图表位置。

**Interfaces:**
- Produces: 所有 recharts 图表在窄屏下不溢出。

- [ ] **Step 1: 全项目搜索 recharts 用法**

Run:
```bash
cd apps/dsa-web && grep -rn "from 'recharts'\|ResponsiveContainer\|LineChart\|BarChart\|AreaChart\|PieChart\|ComposedChart" src/ --include="*.tsx" --include="*.ts"
```

记录每个文件:行号 与是否已包裹 `ResponsiveContainer`。

- [ ] **Step 2: 列出未包裹 ResponsiveContainer 的位置**

预期已知位置：
- `src/components/decision-signals/DecisionSignalTimeline.tsx:229` — 已包裹，确认 `width="100%"`
- `src/pages/PortfolioPage.tsx:1295` — 已包裹，确认 `width="100%"`

其余位置（如有）需补包裹。模式：

```tsx
<ResponsiveContainer width="100%" height={240}>
  <LineChart data={...}>
    {/* 原内容 */}
  </LineChart>
</ResponsiveContainer>
```

注意：`ResponsiveContainer` 的父容器必须有明确高度或宽度，否则渲染为 0。如果父容器无固定高度，给 `ResponsiveContainer` 设 `height={240}` 或 `aspect={2}`。

- [ ] **Step 3: 逐个修复未包裹位置**

按 Step 2 列表逐个修复。每个修复后跑 `npm run build` 确认无类型错误。

- [ ] **Step 4: 运行 lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 5: Commit（如有修复）**

```bash
git add <修改的文件列表>
git commit -m "fix(web): wrap recharts with ResponsiveContainer to prevent overflow"
```

如扫描后发现所有图表已包裹，跳过 commit，在交付说明中注明"扫描完成，无需修改"。

---

### Task 5: Shell/Chat/Home 移动端验证与补强

**Files:**
- Modify (如有缺陷): `apps/dsa-web/src/components/layout/Shell.tsx`
- Modify (如有缺陷): `apps/dsa-web/src/pages/ChatPage.tsx`
- Modify (如有缺陷): `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/e2e/mobile-smoke.spec.ts` (加抽屉/覆盖层断言)

**Interfaces:**
- Consumes: Task 1 的 `mobile-chrome` 项目。
- Produces: 验证 Shell 汉堡菜单、ChatPage 移动端会话切换、HomePage 移动端 sidebar 切换在移动 viewport 下可用；如发现缺陷则补强。

- [ ] **Step 1: 在 mobile-smoke.spec.ts 加抽屉断言**

追加：

```ts
test('Shell drawer opens on mobile', async ({ page: browserPage }) => {
  await browserPage.goto('/');
  await browserPage.waitForLoadState('domcontentloaded');
  // 汉堡菜单按钮（lg:hidden 的 button）
  const menuButton = browserPage.locator('button[aria-label]').filter({ hasText: '' }).first();
  // 用更稳定的选择器：lg:hidden 容器内的 button
  const mobileMenuButton = browserPage.locator('button.lg\\:hidden, [class*="lg:hidden"] button').first();
  await mobileMenuButton.click();
  // Drawer 滑出：等待 SidebarNav 可见
  await expect(browserPage.locator('nav, [aria-label*="nav" i], [aria-label*="menu" i]').first()).toBeVisible();
});
```

注意：选择器可能不稳定，实现时根据实际 DOM 调整。可用 `data-testid` 替代——如果 Shell 没有现成 testid，可在 Shell.tsx 给汉堡按钮加 `data-testid="mobile-menu-button"`、给 Drawer 内 SidebarNav 容器加 `data-testid="mobile-drawer-nav"`。

- [ ] **Step 2: 加 ChatPage 移动端会话切换断言**

```ts
test('ChatPage mobile sidebar opens', async ({ page: browserPage }) => {
  await browserPage.goto('/chat');
  await browserPage.waitForLoadState('domcontentloaded');
  // 移动端切换按钮（md:hidden 的 button）
  const toggleButton = browserPage.locator('[class*="md:hidden"] button').first();
  await toggleButton.click();
  // 覆盖层出现
  await expect(browserPage.locator('.page-drawer-overlay, [class*="fixed inset-0"]').first()).toBeVisible();
});
```

- [ ] **Step 3: 加 HomePage 移动端 sidebar 断言**

```ts
test('HomePage mobile sidebar opens', async ({ page: browserPage }) => {
  await browserPage.goto('/');
  await browserPage.waitForLoadState('domcontentloaded');
  const toggleButton = browserPage.locator('[class*="md:hidden"] button').first();
  await toggleButton.click();
  await expect(browserPage.locator('.page-drawer-overlay, [class*="fixed inset-0"]').first()).toBeVisible();
});
```

- [ ] **Step 4: 运行 e2e 验证**

Run: `cd apps/dsa-web && DSA_WEB_SMOKE_PASSWORD=xxx npx playwright test mobile-smoke --project=mobile-chrome`
Expected: 3 个新断言 PASS。

如本地无 webServer 环境，跳过并注明"e2e 待 CI 验证"。

- [ ] **Step 5: 根据测试结果补强**

如发现缺陷（如路由切换后抽屉不关闭），按以下方式补强：

**Shell.tsx 路由切换关闭**：在 `Shell.tsx:21-36` 的 `useEffect` 后追加：

```tsx
import { useLocation } from 'react-router-dom';
// ...
const location = useLocation();
useEffect(() => {
  setMobileOpen(false);
}, [location.pathname]);
```

**ChatPage/HomePage 路由切换关闭**：类似处理，监听 `location.pathname` 变化时 `setSidebarOpen(false)`。但 ChatPage 内部 sidebar 是会话切换不是路由切换，可能不需要。

补强后重新跑 e2e 确认 PASS。

- [ ] **Step 6: 运行 lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/dsa-web/src/components/layout/Shell.tsx apps/dsa-web/src/pages/ChatPage.tsx apps/dsa-web/src/pages/HomePage.tsx apps/dsa-web/e2e/mobile-smoke.spec.ts
git commit -m "test(web): add mobile sidebar/drawer smoke and harden route-close"
```

如无源码补强，仅 commit 测试文件：

```bash
git add apps/dsa-web/e2e/mobile-smoke.spec.ts
git commit -m "test(web): add mobile sidebar/drawer smoke"
```

---

### Task 6: LoginPage + 4 个兜底页面验证

**Files:**
- Modify (如有缺陷): `apps/dsa-web/src/pages/LoginPage.tsx`
- Modify (如有缺陷): `apps/dsa-web/src/pages/BacktestPage.tsx`
- Modify (如有缺陷): `apps/dsa-web/src/pages/AlertsPage.tsx`
- Modify (如有缺陷): `apps/dsa-web/src/pages/TokenUsagePage.tsx`
- Modify (如有缺陷): `apps/dsa-web/src/pages/SettingsPage.tsx`
- Modify: `apps/dsa-web/e2e/mobile-smoke.spec.ts`

**Interfaces:**
- Produces: LoginPage 在 375px 下不溢出、4 个兜底页面在 mobile/tablet viewport 下不溢出可滚动。

- [ ] **Step 1: 在 mobile-smoke.spec.ts 加溢出断言**

追加：

```ts
const ALL_PAGES = [
  { name: 'login', path: '/login' },
  { name: 'backtest', path: '/backtest' },
  { name: 'alerts', path: '/alerts' },
  { name: 'usage', path: '/usage' },
  { name: 'settings', path: '/settings' },
];

for (const page of ALL_PAGES) {
  test(`${page.name} no horizontal overflow on mobile`, async ({ page: browserPage }) => {
    await browserPage.goto(page.path);
    await browserPage.waitForLoadState('domcontentloaded');
    await browserPage.waitForTimeout(500);
    const scrollWidth = await browserPage.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await browserPage.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
  });
}
```

- [ ] **Step 2: 运行 e2e 识别溢出页面**

Run: `cd apps/dsa-web && DSA_WEB_SMOKE_PASSWORD=xxx npx playwright test mobile-smoke --project=mobile-chrome`
Expected: 5 个新断言 PASS。如有 FAIL，记录哪个页面溢出。

- [ ] **Step 3: 修复 LoginPage 溢出（如失败）**

文件：`src/pages/LoginPage.tsx`

常见溢出原因：固定宽度 input、按钮、卡片 `max-w` 与 `px` 冲突。修复模式：

- 检查所有 `w-[XXXpx]` 改为 `w-full max-w-[XXXpx]`
- 检查 `min-w-[XXXpx]` 在 `<sm` 下移除或改为 `sm:min-w-[XXXpx]`
- 检查 input/button 是否有 `flex-shrink-0` 导致无法收缩

- [ ] **Step 4: 修复 4 个兜底页面溢出（如失败）**

按 Step 2 失败的页面逐个修复。常见模式：
- 表格外层加 `overflow-x-auto`（如已有则确认外层容器宽度约束）
- 固定宽度图表改为 `ResponsiveContainer`
- 多列 flex/grid 加中间断点

- [ ] **Step 5: 重新运行 e2e 确认**

Run: `cd apps/dsa-web && DSA_WEB_SMOKE_PASSWORD=xxx npx playwright test mobile-smoke --project=mobile-chrome`
Expected: 全部 PASS。

- [ ] **Step 6: 运行 lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add <修改的文件列表> apps/dsa-web/e2e/mobile-smoke.spec.ts
git commit -m "fix(web): prevent horizontal overflow on login and fallback pages"
```

---

### Task 7: 文档更新与 spec 修正提交

**Files:**
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/specs/2026-07-04-mobile-adaptation-design.md` (已修正未 commit)

**Interfaces:**
- Produces: CHANGELOG 记录移动端适配；spec 文件与实际代码状态一致。

- [ ] **Step 1: 更新 `docs/CHANGELOG.md` `[Unreleased]` 段**

按 CLAUDE.md 第 1 节规则，使用扁平格式：

```markdown
## [Unreleased]

- [改进] Web 前端新增手机与平板 viewport 适配（xs 断点、表格卡片变体、grid 中间断点、移动端 smoke 用例）
- [测试] Playwright 新增 mobile-chrome (Pixel 5) 与 tablet-chrome (iPad Mini) 项目
```

- [ ] **Step 2: 确认 spec 修正已包含**

`docs/superpowers/specs/2026-07-04-mobile-adaptation-design.md` 中 Task 5.3/5.4/5.5/5.6 的修正（已在 brainstorming 阶段写入工作区但未 commit）应一并提交。

Run: `git status --short`
Expected: 显示 spec 文件 modified。

- [ ] **Step 3: Commit**

```bash
git add docs/CHANGELOG.md docs/superpowers/specs/2026-07-04-mobile-adaptation-design.md
git commit -m "docs: sync mobile adaptation spec and changelog"
```

---

## 自审记录

**Spec 覆盖检查**：
- spec 第 1 节背景与目标 → 全 plan 覆盖
- spec 第 2 节范围（6 优先 + 4 兜底） → Task 1-5 覆盖优先页面、Task 6 覆盖兜底
- spec 第 3 节策略（渐进式） → Global Constraints 体现
- spec 第 4 节断点 → Task 1 Step 1
- spec 第 5.1 节 5 处表格 → Task 2 Step 1-5
- spec 第 5.2 节 3 处 grid → Task 3 Step 1-3
- spec 第 5.3 节图表扫描 → Task 4
- spec 第 5.4 节 Shell 验证 → Task 5 Step 1, 5
- spec 第 5.5 节 ChatPage 验证 → Task 5 Step 2, 5
- spec 第 5.6 节 HomePage 验证 → Task 5 Step 3, 5
- spec 第 5.7 节 LoginPage → Task 6 Step 3
- spec 第 6 节数据流无变化 → Global Constraints
- spec 第 7 节错误处理 → Task 2/4 内含 fallback
- spec 第 8 节测试 → Task 1/2/5/6
- spec 第 9 节交付顺序 → Task 1-7 与原 4 commit 顺序对齐
- spec 第 10 节 YAGNI → Global Constraints
- spec 第 11 节风险与回滚 → 每个 Task 独立 commit
- spec 第 12 节验证矩阵 → 每个 Task 含 lint/build/e2e

**Placeholder 扫描**：无 TBD/TODO；Task 4 的"视扫描结果而定"是真实条件分支非 placeholder；Task 6 Step 4 的"按失败页面修复"是真实条件分支。

**类型一致性**：无跨 task 类型/函数名依赖，每个 Task 独立。

**已知风险**：
- Task 2 Step 6 的 e2e 断言选择器可能不稳定，实现时根据实际 DOM 调整
- Task 5 Step 1-3 的 e2e 选择器同理
- Task 4 的扫描结果可能为空（所有图表已包裹），则跳过 commit
