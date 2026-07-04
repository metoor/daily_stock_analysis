# 移动端适配设计

- 日期：2026-07-04
- 范围：`apps/dsa-web/`
- 分支：在新建 feature 分支中开发（分支名在实现阶段确定，建议 `feat/mobile-adaptation`）

## 1. 背景与目标

当前 Web 前端 (`apps/dsa-web/`) 已有基础响应式：viewport meta 已设置、Shell 已有 `<lg` 汉堡菜单 + Drawer、50+ 处 Tailwind 响应式断点类在使用。但仍存在以下移动端短板：

- 5 处宽表格使用 `min-w-[680px]` 到 `min-w-[960px]`，在手机上需要横向滚动，体验差
- 3 处多列 grid 缺少中间断点，平板竖屏下可能拥挤
- BacktestPage 部分图表未用 `ResponsiveContainer`，可能溢出
- ChatPage 移动端会话列表切换交互不完整
- HomePage `<md` 时隐藏右侧任务面板，移动端无法查看任务进度
- Playwright 仅配置 Desktop Chrome，无移动端 viewport 回归保护

**目标**：确保移动手机端（375–414px）和平板端（768–1024px）下展示正常，核心高频页面可用。

**非目标**：不重写桌面端、不引入 PWA/手势/底部 tab bar、不改 API 与数据结构。

## 2. 范围

### 2.1 设备范围
- 手机：375–414px（Pixel 5 / iPhone 12+ 等）
- 平板：768–1024px（iPad Mini / iPad 等）

### 2.2 优先页面（6 个，深度适配）
| 路径 | 页面 |
|---|---|
| `/` | HomePage |
| `/chat` | ChatPage |
| `/screening` | StockScreeningPage |
| `/portfolio` | PortfolioPage |
| `/decision-signals` | DecisionSignalsPage |
| `/login` | LoginPage |

### 2.3 兜底页面（4 个，基础可用性）
BacktestPage、AlertsPage、TokenUsagePage、SettingsPage — 只保证不溢出、可滚动、可点击。

## 3. 策略

采用**渐进式响应式优化**：保留现有桌面布局，在窄屏用卡片/折叠/横向滚动替代宽表格，针对性修复溢出与拥挤。不引入 `useMediaQuery` / `ResponsiveSwitch` 等新抽象（YAGNI）。

## 4. 断点策略

在 `tailwind.config.js` 新增 `xs: '375px'` 断点（Tailwind v4 默认从 `sm:640` 起）。

最终断点语义：
- `xs` 375–639px：手机竖屏
- `sm` 640–767px：手机横屏 / 小平板竖屏
- `md` 768–1023px：平板竖屏
- `lg` 1024px+：平板横屏 / 桌面

## 5. 组件级适配清单

### 5.1 宽表格 → 卡片变体（5 处）

| 文件:行 | 现状 | 改造 |
|---|---|---|
| `pages/AlertsPage.tsx:335` | `min-w-[680px]` | `<sm` 渲染卡片列表 |
| `pages/PortfolioPage.tsx:1204` | `min-w-[860px]` | `<sm` 渲染卡片列表 |
| `pages/StockScreeningPage.tsx:1297` | `min-w-[860px]` | `<sm` 渲染卡片列表 |
| `components/alerts/AlertRuleList.tsx:173` | `min-w-[960px]` | `<sm` 渲染卡片列表 |
| `components/alerts/AlertTriggerHistory.tsx:63` | `min-w-[860px]` | `<sm` 渲染卡片列表 |

**策略**：使用 Tailwind 断点类切换显示（`<div className="sm:hidden">{卡片列表}</div>` + `<div className="hidden sm:block">{表格}</div>`）。每条记录渲染为一张 `Card`，关键字段纵向排列，操作按钮放卡片右下角。复用现有 `Card` 组件，不引入新抽象。

### 5.2 多列 grid 补中间断点（3 处）

- `SettingsPage.tsx:1398` `lg:grid-cols-[280px_1fr]` → 加 `md:grid-cols-[240px_1fr]`，`<md` 单列
- `AlertsPage.tsx:284` `xl:grid-cols-[380px_minmax(0,1fr)]` → 加 `lg:grid-cols-[320px_minmax(0,1fr)]`，`<lg` 单列
- `DecisionSignalsPage.tsx:559` `xl:grid-cols-7` → 改为 `xs:grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7`

### 5.3 图表 ResponsiveContainer 全项目扫描

排查 `apps/dsa-web/src/` 全部 recharts 用法，未包裹 `ResponsiveContainer` 的全部包裹，`width="100%"`、`height` 取固定值。已知 `DecisionSignalTimeline:229`、`PortfolioPage:1295` 已包裹，需确认其余位置（如有）。

### 5.4 Shell 抽屉验证

现状（`Shell.tsx:17,40,72-81`）已有 `<lg` 汉堡菜单 + Drawer。`Drawer.tsx:47-49` 已实现 body scroll lock。

验证项：
- 抽屉打开时 body 滚动锁定（已实现，验证）
- resize 到 lg+ 自动关闭（已实现，验证）
- 路由切换后自动关闭（待验证，必要时补强）

### 5.5 ChatPage 移动端切换验证

现状（`ChatPage.tsx:875,879-893,914`）：`<md` 隐藏会话列表，第914行有切换按钮，第879-893行已有移动端覆盖层实现。

验证项：点击切换按钮弹出移动端覆盖层、选中会话后自动关闭、覆盖层与 Drawer 行为一致。如有缺陷再补强。

### 5.6 HomePage 任务面板验证

现状（`HomePage.tsx:705-712,878-893`）：`<md` 时右侧 sidebar 隐藏，第705-712行有移动端切换按钮，第883-893行已有移动端覆盖层实现，包含 TaskPanel 与 StockBar。

验证项：移动端切换按钮可点击、覆盖层滑出、TaskPanel 内容可见可操作、选中后自动关闭。如有缺陷再补强。

### 5.7 LoginPage

验证 375px 下：
- 表单不溢出
- 按钮可点击，触摸目标 ≥ 44px
- 输入框聚焦时键盘弹起不遮挡（input 进入视口）

## 6. 数据流

无变化。所有适配在视图层，不改动 zustand store、API、数据结构、Schema。

## 7. 错误处理

- 卡片变体复用表格现有的字段 fallback（`-` / `N/A`），不新增 fallback 逻辑
- `ResponsiveContainer` 在父容器宽度为 0 时不渲染（避免 recharts 警告）
- Drawer 路由切换关闭由现有 resize 监听延伸到路由变化监听

## 8. 测试

### 8.1 Playwright 配置扩展

`playwright.config.ts` 新增两个项目：
- `mobile-chrome`：使用 `devices['Pixel 5']` (393×851)
- `tablet-chrome`：使用 `devices['iPad Mini']` (768×1024)

### 8.2 新增 e2e 用例

新增 `e2e/mobile-smoke.spec.ts`：在两个 viewport 下访问 6 个优先页面，断言：
- 页面 load 无 console error
- 关键元素可见（首屏标题 / 主要 CTA）
- 汉堡菜单可点击、Drawer 滑出
- 表格在 `<sm` viewport 下 DOM 中不存在 `<table>`（验证切换为卡片）
- 图表容器不溢出（`scrollWidth <= clientWidth`）

### 8.3 单元测试

不新增 vitest 单测。CSS 改动由 e2e 验证更有效。

## 9. 交付顺序（4 个 commit）

1. 断点扩展 + Playwright 移动项目骨架 + mobile-smoke 用例骨架
2. 5 处宽表格卡片变体
3. 多列 grid + 图表 ResponsiveContainer + Shell/Chat/Home 杂项
4. LoginPage + 4 个兜底页面验证 + `docs/CHANGELOG.md` + 文档

## 10. 不在范围内（YAGNI）

- 不引入 `useMediaQuery` / `ResponsiveSwitch` 抽象
- 不重写桌面端布局
- 不加底部 tab bar / 触摸手势 / PWA
- 不改 API / 数据结构 / Schema
- 不改 Electron 桌面端

## 11. 风险与回滚

### 11.1 风险点
- 卡片变体与表格的字段渲染可能不一致，需要对照测试
- Playwright 移动项目可能因本地无对应 browser binary 首次失败
- Tailwind v4 的 `xs` 断点扩展可能与 `@config` 桥接配置冲突，需验证

### 11.2 回滚方式
- 4 个 commit 独立可回滚
- 如整体回滚：`git revert` 4 个 commit 即可恢复原状
- 改动均在 `apps/dsa-web/` 内，不影响后端 / 桌面端 / 工作流

## 12. 验证矩阵（按 CLAUDE.md 第 6 节）

本任务属于 Web 前端改动，适用范围 `apps/dsa-web/`：

- 默认执行：`cd apps/dsa-web && npm ci && npm run lint && npm run build`
- 移动端 e2e：`npm run test:e2e`（含新增 mobile-chrome、tablet-chrome 项目）
- 联动面：不涉及 API / 路由 / 状态管理 / Markdown 渲染 / 认证状态
- 未覆盖风险：真机触摸手势、iOS Safari 浏览器兼容性（仅 CI 跑 chromium）
