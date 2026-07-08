# 问股页面移动端优化设计

- 日期：2026-07-08
- 范围：`apps/dsa-web/src/pages/ChatPage.tsx` 及其拆分出的子组件
- 分支：`feat/mobile-adaptation`（在现有分支上继续）
- 关联设计：`docs/superpowers/specs/2026-07-04-mobile-adaptation-design.md`（整体移动端适配总设计，本文件是其对问股页面的深入细化）

## 1. 背景与目标

问股页面（`apps/dsa-web/src/pages/ChatPage.tsx`，1428 行）当前移动端适配处于早期阶段：侧边栏抽屉、技能折叠面板、移动端断点已就位，但 4 个核心能力区（SessionSidebar / ChatHeader / MessageList / ChatComposer）在移动端体验均未达到与桌面端功能对齐。

**目标**：

- 移动端问股页面与桌面端功能 100% 对齐（技能多选、股票代码、自选、追问、导出、历史会话等能力均不降级）
- 通过响应式重构（mobile-first）让桌面/移动共用一套组件结构，避免代码纠缠
- ChatPage.tsx 从 1428 行降至约 600 行（协调器），子组件各 200–400 行

**非目标**：

- 不重构 `agentChatStore`
- 不新增离线检测、消息长按菜单、重连机制
- 不优化其它页面（首页、报告页等）
- 不引入 PWA / 手势 / 底部 tab bar

## 2. 方案选择

采用**响应式重构**：把 ChatPage 拆为协调器 + 4 个子组件，每个子组件 mobile-first 响应式。桌面端布局可微调，但功能 100% 保留。

候选方案对比：

| 方案 | 改动面 | 风险 | 长期可维护性 |
|---|---|---|---|
| 渐进式适配（不拆分） | 小 | 小 | 差（1428 行继续膨胀） |
| **响应式重构（采用）** | 中 | 中（桌面回归） | 好 |
| 全面重设计（mobile 独立组件 + 新交互） | 大 | 大 | 中（两套代码） |

## 3. 子组件拆分边界

### 3.1 ChatPage.tsx（~600 行，协调器）

保留为协调器，负责：

- 路由级 UI 状态：`sidebarOpen`、`composerOpen`、`composerValue`
- 数据获取：`useAgentChatStore` 选择器、session 切换副作用
- 子组件编排：布局容器 + 4 个子组件位置
- 不再直接渲染消息/输入/Header 细节

### 3.2 4 个子组件职责

| 子组件 | 职责 | 关键 props |
|---|---|---|
| `ChatHeader` | 标题、描述、导出/发送按钮、toast 容器 | `onExport`, `onSend`, `isSending`, `onToggleSidebar` |
| `MessageList` | 消息渲染、空态快速提问、Markdown/思考过程/复制、滚动到底部按钮 | `messages`, `isStreaming`, `onFollowUp`, `onCopy`, `isMobile` |
| `ChatComposer` | 上下文压缩开关、技能多选、股票代码、自选按钮、textarea、发送 | `skills`, `onSend`, `isSending`, `composerValue`, `setComposerValue`, `isMobile` |
| `SessionSidebar` | 历史会话列表、新建会话、切换会话 | `sessions`, `activeSessionId`, `onSelect`, `onNew`, `isOpen`, `onClose`, `isMobile` |

### 3.3 状态归属

- `agentChatStore` 不变（messages、sessions、loading、streaming、activeSessionId 等）
- ChatPage 持有 UI 本地状态（`sidebarOpen`、`composerOpen`、`composerValue`）
- `useIsMobile` 在 ChatPage 顶层调用一次，结果作为 prop 传给子组件（避免重复 `matchMedia` 监听）

### 3.4 文件位置

- `apps/dsa-web/src/pages/chat/ChatHeader.tsx`
- `apps/dsa-web/src/pages/chat/MessageList.tsx`
- `apps/dsa-web/src/pages/chat/ChatComposer.tsx`
- `apps/dsa-web/src/pages/chat/SessionSidebar.tsx`
- `ChatPage.tsx` 保持在 `apps/dsa-web/src/pages/ChatPage.tsx`

## 4. 各能力区移动端具体形态

### 4.1 SessionSidebar（历史会话侧边栏）

- 形态：抽屉式（保留现状），宽度 `85vw / max 320px`
- 列表项 `min-h 44px`（触控友好），"新对话"按钮 sticky 顶部
- 关闭：点 overlay / 选会话自动关闭 / 顶部 X
- 入口：ChatHeader 左侧 hamburger（与 Shell 全局导航 hamburger 分离，两者内容不同，避免重叠）

### 4.2 ChatHeader

- 桌面端：保留原样（标题 + 描述 + 导出 + 发送按钮一行）
- 移动端形态：单行 sticky 顶栏
  - 左：hamburger（会话历史） / 中：标题"问股" / 右：导出图标 + 发送状态图标（loading 转圈）
  - 描述文字隐藏（移到 EmptyState 首次提示）
  - toast：顶部下拉，不遮输入区

### 4.3 MessageList

- 用户气泡：右对齐 `max-w-85%`；AI 气泡：左对齐 `max-w-92%`
- Markdown：字号 14px（桌面 15px），代码块/表格横向滚动 + 右侧渐变阴影提示可滑
- 思考过程：默认折叠，展开 13px，左缩进 + 竖线
- 复制/导出：气泡下方小图标行（不再挤在气泡内）
- 滚动到底部按钮：右下角 48×48 圆形，距底 72px（避开输入区）
- 空态快速提问：2 列网格（桌面 3 列）

### 4.4 ChatComposer（最痛点，分层结构）

- 桌面端：保留原样（上下文压缩开关 + 技能多选横向 checkbox + 股票代码 + 自选 + textarea + 发送，一行或两行布局）
- 移动端：分层结构
  - **始终可见层**：textarea + 发送按钮，`sticky bottom-0` + `safe-area-inset-bottom`
  - **展开层**：textarea 左侧"+"按钮触发底部抽屉，含技能 chips / 股票代码输入 / 自选按钮 / 上下文压缩开关
  - textarea：`min-h 48px / max-h 120px`，自动撑高
  - 发送按钮：48×48 圆形，禁用态灰色
  - 技能 chips：横向滑动（不换行），选中态主题色描边
  - 已选技能在 textarea 上方以小 badge 显示，点 × 移除

## 5. 数据流与状态管理

### 5.1 agentChatStore 不变

- 现有 store 接口（messages、sessions、loading、streaming、activeSessionId 等）保持不变
- 子组件通过选择器直接订阅所需切片，ChatPage 不再做"中转"

### 5.2 ChatPage 协调器持有的本地 UI 状态

- `sidebarOpen`：SessionSidebar 抽屉开关
- `composerOpen`：ChatComposer 展开层开关（仅 mobile）
- `composerValue`：textarea 值
- `useIsMobile` 顶层调用一次，结果作为 prop 传给子组件

### 5.3 子组件数据来源

| 子组件 | 从 store 读 | 从 props 读 |
|---|---|---|
| ChatHeader | isSending, activeSession | onExport, onSend, onToggleSidebar |
| MessageList | messages, isStreaming | onFollowUp, onCopy, isMobile |
| ChatComposer | skills, isSending | onSend, composerValue, setComposerValue, isMobile |
| SessionSidebar | sessions, activeSessionId | onSelect, onNew, isOpen, onClose, isMobile |

### 5.4 副作用归属

- session 切换副作用：保留在 ChatPage（useEffect 监听 activeSessionId，重置滚动、清空 composer）
- 滚动到底部：MessageList 内部自管（useRef + useLayoutEffect）
- textarea 自动撑高：ChatComposer 内部自管
- 抽屉焦点陷阱：SessionSidebar / ChatComposer 抽屉内部自管

### 5.5 键盘与焦点

- 移动端 textarea focus 时浏览器自动弹键盘，sticky bottom 输入条跟随上移
- 抽屉打开 trap focus，关闭还原焦点到触发按钮
- 技能 chips 横向滑动用箭头键可达（无障碍）

## 6. 错误处理与降级

### 6.1 空态（无消息）

- 桌面：EmptyState + 6 个快速提问按钮 3 列
- 移动：EmptyState + 2 列网格，标题精简，描述占满宽度
- 首次进入：展示被 ChatHeader 隐藏的描述文字

### 6.2 加载态（AI 回复中）

- 思考过程默认折叠（避免占满屏幕），流式进度用顶部细线 + 文案
- ChatComposer 发送按钮变 loading 转圈并禁用
- 滚动到底部按钮在 streaming 时隐藏

### 6.3 错误态（API 失败）

- 复用现有 `ApiErrorAlert` 组件
- 移动端：错误条放在 MessageList 顶部 sticky（不是底部），避开输入区
- 重试按钮在错误条内

### 6.4 流式中断

- 现有 stop 按钮保留
- 移动端 stop 按钮替换发送按钮位置（同一槽位切换）

### 6.5 长内容渲染

- Markdown 超长消息：不截断，正常滚动
- 代码块超长：横向滚动 + 右侧渐变阴影提示可滑
- 表格超长：横向滚动 + 右侧渐变阴影提示可滑
- 思考过程超长：默认折叠，展开后内部滚动 `max-h-300px`

### 6.6 抽屉内错误

- SessionSidebar 加载会话失败：抽屉内显示错误条 + 重试
- ChatComposer 抽屉内技能加载失败：抽屉内显示错误条

### 6.7 不新增的能力（YAGNI）

- 不主动新增离线检测（`navigator.onLine`），除非项目已有
- 不新增消息长按菜单（4.3 改为气泡下方小图标行，已覆盖复制/导出）
- 不新增重连机制（依赖现有 store 的 streaming 重试）

## 7. 测试策略

### 7.1 单元测试（vitest + @testing-library/react）

现有 `src/pages/__tests__/ChatPage.test.tsx` 调整为聚焦"协调器"行为（子组件编排、session 切换副作用、useIsMobile 传递）。

新增 4 个子组件测试文件：

- `src/pages/chat/__tests__/ChatHeader.test.tsx`
- `src/pages/chat/__tests__/MessageList.test.tsx`
- `src/pages/chat/__tests__/ChatComposer.test.tsx`
- `src/pages/chat/__tests__/SessionSidebar.test.tsx`

关键覆盖点：

- **ChatHeader**: hamburger 触发 onToggleSidebar、导出按钮、loading 态
- **MessageList**: 空态快速提问、用户/AI 气泡、Markdown 渲染、代码块横向滚动、滚动到底部按钮显隐、错误条顶部 sticky
- **ChatComposer**: textarea 输入、发送、"+"展开抽屉、技能 chips 选择/移除、股票代码、自选、上下文压缩、loading 禁用
- **SessionSidebar**: 会话列表、切换、新建、抽屉开关、overlay 关闭

### 7.2 E2E 测试（playwright）

现有 `e2e/mobile-smoke.spec.ts` 扩展，新增用例：

- 输入框输入 + 发送 + AI 回复渲染
- "+"展开抽屉 + 选技能 + 关闭
- 历史会话切换
- 滚动到底部按钮显隐
- 代码块横向滚动

视图：`mobile-chrome`（Pixel 5, 393×851）、`tablet-chrome`（iPad Mini）

### 7.3 桌面端回归

- 4 个能力区在桌面端功能 100% 不变（手动 + 现有桌面测试）

### 7.4 CI 验证

- `web-gate`: `npm run lint` + `npm run build` 必须通过
- `mobile-smoke`: playwright mobile-chrome / tablet-chrome 项目

### 7.5 不验证项

- 真机 iOS Safari / Android Chrome（无设备，用 Playwright 近似）

## 8. 交付清单

- ChatPage.tsx 重构为协调器（~600 行）
- 新增 4 个子组件文件（`src/pages/chat/`）
- 调整 ChatPage 单元测试
- 新增 4 个子组件单元测试
- 扩展 `e2e/mobile-smoke.spec.ts`
- 更新 `docs/CHANGELOG.md`（`[Unreleased]` 扁平格式，按 CLAUDE.md 1 节规则）
- PR 描述附移动端截图（按 CLAUDE.md 1 节规则）

## 9. 风险与回滚

### 9.1 风险

- ChatPage 拆分改动面大，可能引入回归
- 桌面端布局微调可能影响现有用户习惯
- sticky bottom 输入条在不同移动浏览器表现不一致（iOS Safari 历史问题）

### 9.2 缓解

- 拆分按子组件逐个进行，每个子组件独立测试后再合并
- 桌面端布局微调最小化（仅 Header 精简、输入区结构统一），功能不动
- sticky bottom 用 `safe-area-inset-bottom` + viewport 元数据兜底

### 9.3 回滚

- 单子组件回滚：`git revert` 对应子组件提交
- 整体回滚：回退到拆分前的 commit（ChatPage 仍是 1428 行单文件）

## 10. 验证矩阵（按 CLAUDE.md 第 6 节）

本任务属于 Web 前端改动，适用范围 `apps/dsa-web/`：

- 默认执行：`cd apps/dsa-web && npm ci && npm run lint && npm run build`
- 单元测试：`cd apps/dsa-web && npm run test`（vitest）
- 移动端 e2e：`npm run test:e2e`（含 mobile-chrome、tablet-chrome 项目）
- 联动面：涉及状态管理（agentChatStore 不变但订阅方式调整）、Markdown 渲染（媒体查询调整）、路由（ChatPage 路由不变）
- 桌面端回归：现有桌面测试 + 手动验证 4 个能力区功能不变
- 未覆盖风险：真机 iOS Safari 键盘弹起行为、Android Chrome sticky 兼容性
