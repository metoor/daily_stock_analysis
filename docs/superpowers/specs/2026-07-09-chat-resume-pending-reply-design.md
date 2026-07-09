# 问股页面重开后续等 AI 回复设计

- 日期：2026-07-09
- 范围：`apps/dsa-web/src/stores/agentChatStore.ts`、`apps/dsa-web/src/pages/ChatPage.tsx`、`apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts`
- 关联：问股聊天流式回复后端（`api/v1/endpoints/agent.py`、`src/agent/executor.py`、`src/agent/conversation.py`）

## 1. 背景与问题

问股聊天（`/chat`）发出消息后 AI 回复较慢。若用户在 AI 生成期间关闭页面再重新打开，会出现：

- 重开后看不到"AI 正在生成"的任何指示；
- 必须手动刷新才能在 AI 生成完成后看到回复。

### 1.1 根因（代码现状）

**后端 `/api/v1/agent/chat/stream`（`api/v1/endpoints/agent.py:373`）**

- `executor.chat()` 在 `loop.run_in_executor` 的线程池里执行（`agent.py:441`）。线程**无法被取消**。
- **用户消息在分析开始时立即落库**：`src/agent/executor.py:655` `conversation_manager.add_message(session_id, "user", message)`。
- **AI 回复仅在全部生成完成后落库**：`src/agent/executor.py:667` `conversation_manager.add_message(session_id, "assistant", result.content)`。
- 客户端断开（关页面）→ SSE `event_generator` 被取消，`finally` 最多等线程 5s（`agent.py:454`）后返回，但**后台线程继续跑完并落库 assistant 消息**。这解释了"直到 AI 返回后才会展示返回的结果"。

**前端 `ChatPage` + `agentChatStore`**

- 发送时：用户消息先进内存 store，`loading=true`，发 SSE 请求（`agentChatStore.ts:256-273`）。
- 重开页面：`loadInitialSession` 从服务端拉已落库消息（`agentChatStore.ts:160-169`）。此时用户消息已在库，但 assistant 消息尚未生成完 → 不显示。
- 新页面 `loading=false`（`agentChatStore.ts:128`），**没有任何"正在生成"指示**。
- **没有轮询**，用户必须手动刷新。

### 1.2 体验差的两个直接原因

1. 重开页面后，看不出"这条用户消息的回复还在生成中"。
2. 生成完成后不会自动出现，要手动刷新。

## 2. 目标

- 重开页面后，若判定该 session 有"进行中"的回复，自动显示"AI 正在生成回复…"指示。
- 回复落库后自动展示，无需手动刷新。
- 轮询期间禁止再发新消息，避免同一 session 并发生成导致历史错乱。
- 移动端后台/弱网下行为合理（不误报超时、回前台即时补查）。

## 3. 非目标

- **不**做直播流续传（重连到进行中的 SSE、回放思考过程）。重开后只等最终回复，不补显实时思考步骤/工具调用——那些事件未持久化，纯前端拿不到。
- **不**改后端（不加"活跃生成"状态表/字段、不改并发保护）。
- **不**处理超过 5 分钟的无回复孤儿 user 消息（属于另一类"为什么没回复"问题）。
- **不**新增"取消等待"按钮（采用锁定 + 自动超时）。
- **不**做跨设备主动同步（但本方案的启发式对跨设备自然生效，见 5.4）。

## 4. 方案选择

| 维度 | 选项 | 选定 |
|---|---|---|
| 恢复体验 | A 轻量恢复（指示 + 轮询拿最终回复）／ B 完整续传（重连直播流）／ C 中间 | **A** |
| "生成中"判断 | 1 纯前端启发式／ 2 后端"活跃生成"状态 | **1** |
| 等待期间输入 | A 锁定 + 自动超时／ B 锁定 + 手动取消／ C 不锁定 | **A** |
| 实现位置 | store action／ 组件 hook／ 独立 util | **store action** |

选 A + 1 + A + store：后端"继续生成并落库"已在工作，前端只需"等得到、看得见"；纯前端启发式零后端改动且对崩溃/超时能兜底；锁定复用现有 `loading` 禁用机制天然堵住并发生成；store 已拥有 `loading`/`messages`/`sessionId`/abort 且 `loadInitialSession`/`switchSession` 都在此，resume 逻辑天然归属，并有 `agentChatStore.test.ts` 可测。

## 5. 架构说明

### 5.1 续等触发条件

在 `loadInitialSession` 和 `switchSession` 拉到消息后，检查 `shouldResume(messages)`：

1. 消息列表非空；
2. **最后一条 role === 'user'**，且其后无 assistant 回复；
3. 该 user 消息的 `created_at` 距当前在 `RESUME_WINDOW_MS`（5 分钟）内。

三者皆满足 → 调 `resumePendingReply(sessionId)`。

### 5.2 轮询循环 `resumePendingReply(sessionId)`

1. **入口守卫**：`if (get().loading) return;`（避免与直播流/已有轮询重复）。
2. **置态**：`set({ loading: true, resuming: true, chatError: null })`。
   - `loading: true` → 发送按钮禁用（`ChatPage.tsx:1457` `disabled={!input.trim() || loading}`），堵住并发生成。
   - 新增 `resuming: boolean`，供 UI 区分"续等"与"直播"。
3. **轮询**：每 `POLL_INTERVAL_MS`（3s）调 `agentApi.getChatSessionMessages(sessionId)`，重新拉取整条消息列表：
   - 若拉取到的列表最后一条变为 `role === 'assistant'`（即该 user 消息之后出现了 assistant 回复；含成功回复与 `[分析失败]` 错误备注两种情况，后者由 `executor.py:678` 落库）→ 将该 assistant 消息追加到 `messages`（保留现有 user 消息、仅追加新回复，行为对齐直播流 `agentChatStore.ts:347-361`），`set({ loading: false, resuming: false })`，刷新 `loadSessions()`，结束；若 `currentRoute !== '/chat'` 则 `set({ completionBadge: true })`（对齐 `agentChatStore.ts:364-366`）。
   - 否则（最后一条仍是该 user 消息）继续。
4. **超时**：累计等待超过 `MAX_WAIT_MS`（5 分钟）仍未等到 → 停止，`set({ loading: false, resuming: false, chatError: <回复可能已中断，请重试> })`，复用现有 `ApiErrorAlert` 展示，输入恢复可用。
5. **停止时机**：session 切换、`startStream` 被触发、完成、超时。新增 `resumeTimerRef`（store 持有时器 id），在 `startStream`/`switchSession`/`startNewChat` 里调 `clearResumeTimer()`。

### 5.3 移动端考量

- **后台 timer 节流**：移动端切后台时 `setTimeout`/`setInterval` 被系统节流/暂停，轮询与 `MAX_WAIT` 计时同步暂停，不会"没在看却超时"。
- **回前台即时补查**：监听 `visibilitychange`，页面从 hidden → visible 且当前 `resuming` 时，立即触发一次轮询（不等下一个 3s tick）。后端早已生成完时，用户回前台即见回复。
- **单次轮询失败不致命**：弱网导致某次 `getChatSessionMessages` 失败时，吞掉本次错误、等下个 tick 重试，不中止续等、不报错；仅 `MAX_WAIT` 整体超时才降级。
- **清理**：续等结束（完成/超时）时移除 `visibilitychange` 监听，随 action 生命周期管理，避免泄漏。

### 5.4 跨设备自然生效

启发式只依赖"该 session 最后一条是近 5 分钟内的 user 消息且无回复"。在设备 B 于 5 分钟内打开同一 session，同样触发续等并拿到设备 A 触发的后端生成结果，无需额外机制。

### 5.5 关键常量

| 常量 | 值 | 说明 |
|---|---|---|
| `RESUME_WINDOW_MS` | `5 * 60 * 1000` | 触发窗，对齐后端 SSE 300s 超时（`agent.py:445`） |
| `POLL_INTERVAL_MS` | `3000` | 轮询间隔 |
| `MAX_WAIT_MS` | `5 * 60 * 1000` | 单次续等最大等待 |

## 6. 改动清单

### 6.1 `apps/dsa-web/src/stores/agentChatStore.ts`

- **`Message` 接口**：新增可选 `created_at?: string | null`（后端 `get_conversation_messages` 已返回 ISO 字符串，`src/storage.py:3027`）。
- **保留 `created_at`**：`loadInitialSession`（`agentChatStore.ts:162-168`）与 `switchSession`（`agentChatStore.ts:205-211`）映射消息时带上 `created_at`，不再丢弃。
- **新增状态**：`resuming: boolean`（初值 `false`）。
- **新增常量**：`RESUME_WINDOW_MS`、`POLL_INTERVAL_MS`、`MAX_WAIT_MS`。
- **新增 `shouldResume(messages)` 纯函数**：实现 5.1 的三个条件；可独立单测。
- **新增 `resumePendingReply(sessionId)` action**：实现 5.2 + 5.3。内部用模块级 `resumeTimerId`（或 store 字段）持有时器，`visibilitychange` 监听随续等生命周期增删。
- **新增 `clearResumeTimer()` 内部方法**：清时器 + 移除 `visibilitychange` 监听（监听器引用需保存以便移除）+ 若处于 `resuming` 则 `set({ loading: false, resuming: false })`。
- **调用点**：
  - `loadInitialSession` 拉到消息后调 `shouldResume` → 命中则 `resumePendingReply`。
  - `switchSession` 拉到消息后同上。
  - `switchSession`（`agentChatStore.ts:185`）、`startNewChat`（`agentChatStore.ts:217`）开头调 `clearResumeTimer()`：续等期间用户可点别的会话/新对话，必须停掉当前轮询；`switchSession` 现有 `set({ loading: false })`（`agentChatStore.ts:190-197`）与 `clearResumeTimer` 一致。
  - `startStream`（`agentChatStore.ts:232`）开头也调 `clearResumeTimer()` 作安全网；其入口守卫 `if (get().loading) return;`（`agentChatStore.ts:233`）已天然阻止"续等期间发送"，三重一致：发送按钮 `disabled`（`ChatPage.tsx:1457`）→ `handleSend` 守卫（`ChatPage.tsx:588`）→ `startStream` 守卫。

### 6.2 `apps/dsa-web/src/pages/ChatPage.tsx`

- 从 store 取 `resuming`（`ChatPage.tsx:298-311` 解构处补一项）。
- **loading 气泡文字**（`ChatPage.tsx:1236-1253`）：当前为 `getCurrentStage(progressSteps)`，续等时 `progressSteps` 为空会返回 `'正在连接...'`（`ChatPage.tsx:695`），误导。改为：

  ```tsx
  <span className="text-secondary-text">
    {resuming ? 'AI 正在生成回复…' : getCurrentStage(progressSteps)}
  </span>
  ```

  spinner 与其余 loading UI 不变。

### 6.3 `apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts`

新增用例覆盖 5.1–5.3 关键路径（见 7）。

## 7. 测试

### 7.1 `shouldResume` 纯函数单测

- 最后一条 user、`created_at` 在 5 分钟内 → `true`。
- 最后一条 assistant → `false`。
- 最后一条 user 但 `created_at` 超 5 分钟 → `false`。
- 空消息列表 → `false`。

### 7.2 `resumePendingReply` 行为单测（mock `agentApi.getChatSessionMessages` 与定时器）

- 命中续等后置 `loading: true`、`resuming: true`；首次返回无 assistant → 继续轮询；后续返回出现 assistant → 追加到 `messages`、`loading: false`、`resuming: false`、调用 `loadSessions`。
- 单次 `getChatSessionMessages` reject → 不中止、不报错，下个 tick 重试。
- 超 `MAX_WAIT_MS` 仍未等到 → `chatError` 非空、`loading: false`、`resuming: false`。
- `loading` 已为 `true` 时调用 → 直接 return，不重复启动。
- 续等期间触发 `startStream` / `switchSession` → `clearResumeTimer` 被调用，`resuming` 复位。

### 7.3 手动验证（PR 描述附证据）

- 桌面端：发送 → AI 生成中关闭页面 → 重开 → 见"AI 正在生成回复…"指示且输入禁用 → 回复落库后自动展示。
- 移动端：发送 → 切后台 → 回前台 → 即时见到已完成的回复。
- 超时路径：构造无回复场景（如后端不可用）→ 5 分钟后见"回复可能已中断，请重试"，输入恢复。

## 8. 风险与回滚

- **风险**：
  - 极少数 >5 分钟的超慢生成会触发超时提示，用户手动重发会产生重复 user 消息（后端每次 `executor.chat` 都落库 user 消息，`executor.py:655`）。这是有意的上限代价，不做无限等待。
  - 启发式无法 100% 区分"真在生成"与"刚崩溃"——靠 5 分钟超时统一降级为"可重试"，可接受。
  - 多标签页同时打开同一 session：两侧都可能续等轮询，但均为幂等只读 GET，不破坏数据；最坏是重复展示同一 assistant 消息需去重（按消息 id 去重即可）。
- **兼容性**：纯前端改动，不改 API/Schema/认证；后端行为不变。
- **回滚**：还原 `agentChatStore.ts`、`ChatPage.tsx` 两个文件及对应测试即可。
