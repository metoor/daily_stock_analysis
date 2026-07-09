# 问股页面重开后续等 AI 回复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 问股聊天页（`/chat`）重开后，若该会话最近一条是未收到回复的用户消息，前端自动显示"AI 正在生成回复…"并轮询，等后端落库后自动展示回复，无需手动刷新。

**Architecture:** 纯前端改动。后端在客户端断开后仍会继续生成并落库 assistant 消息（`executor.py:655` 立即落库 user、`executor.py:667` 完成后落库 assistant）。前端在 `agentChatStore` 新增 `resumePendingReply` action：用启发式 `shouldResume`（最后一条 user + 5 分钟内 + 无回复）判断是否续等，命中后置 `loading=true`（复用现有发送禁用链路堵住并发生成）、轮询 `getChatSessionMessages`，出现 assistant 即追加展示，5 分钟未等到则降级为可重试错误。移动端监听 `visibilitychange` 回前台即时补查。

**Tech Stack:** React 19 + TypeScript + Zustand 5 + vitest 4（jsdom）。测试在 `apps/dsa-web`。

## Global Constraints

- 改动范围仅 `apps/dsa-web/src/`：后端零改动。
- commit message 用英文，不加 `Co-Authored-By`（AGENTS.md §1）。
- Web 验证：`cd apps/dsa-web && npm run lint && npm run build`；测试 `npx vitest run <path>`（AGENTS.md §6）。
- 用户可见变更需更新 `docs/CHANGELOG.md` `[Unreleased]` 段，扁平格式 `- [类型] 描述`（AGENTS.md §1）。
- 不写死端口/路径/模型名；不破坏现有 API/Schema/认证契约（AGENTS.md §1、§7）。
- 常量：`RESUME_WINDOW_MS = 5*60*1000`、`POLL_INTERVAL_MS = 3000`、`MAX_WAIT_MS = 5*60*1000`（对齐后端 SSE 300s 超时 `agent.py:445`）。

## File Structure

- `apps/dsa-web/src/stores/agentChatStore.ts`（修改）：`Message` 加 `created_at`；新增 `resuming` 状态、续等常量、模块级 timer 变量、`shouldResume` 纯函数、`clearResumeTimer`/`resumePendingReply` action；在 `loadInitialSession`/`switchSession` 触发续等，在 `switchSession`/`startNewChat`/`startStream` 清理续等。
- `apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts`（修改）：更新既有 `switchSession` 断言含 `created_at`；`beforeEach` 重置 `resuming` 并清续等；新增 `shouldResume`、`resumePendingReply`、续等接线测试。
- `apps/dsa-web/src/pages/ChatPage.tsx`（修改）：解构 `resuming`；loading 气泡文字续等时显示 `'AI 正在生成回复…'`。
- `apps/dsa-web/src/pages/__tests__/ChatPage.test.tsx`（修改）：`mockStoreState` 加 `resuming`；新增续等提示 UI 测试。
- `docs/CHANGELOG.md`（修改）：`[Unreleased]` 加一条 `[改进]`。

---

### Task 1: 保留加载消息的 `created_at`

续等判断需要 `created_at` 做"最近 5 分钟"检查，但 `loadInitialSession`/`switchSession` 映射消息时丢弃了它（`agentChatStore.ts:162-168`、`205-211`）。本任务先把它保留下来。

**Files:**
- Modify: `apps/dsa-web/src/stores/agentChatStore.ts:34-43`（`Message` 接口）、`162-168`（`loadInitialSession` 映射）、`205-211`（`switchSession` 映射）
- Test: `apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts:251-253`、`280-282`（既有断言）

**Interfaces:**
- Produces: `Message.created_at?: string | null`（后端 `get_conversation_messages` 已返回 ISO `created_at`，`src/storage.py:3027`）

- [ ] **Step 1: 更新既有测试断言，要求带 `created_at`**

`apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts` 第 251-253 行：

```typescript
    expect(state.messages).toEqual([
      { id: 'msg-2', role: 'assistant', content: '历史回复', created_at: null },
    ]);
```

第 280-282 行：

```typescript
    expect(state.messages).toEqual([
      { id: 'msg-b', role: 'assistant', content: 'B 回复', created_at: null },
    ]);
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd apps/dsa-web && npx vitest run src/stores/__tests__/agentChatStore.test.ts`
Expected: FAIL — 两个 `switchSession` 用例因实际映射不含 `created_at`（`expected created_at: null, received undefined`）。

- [ ] **Step 3: 给 `Message` 接口加 `created_at`**

`apps/dsa-web/src/stores/agentChatStore.ts` 第 34-43 行，在 `content` 后加一行：

```typescript
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at?: string | null;
  skills?: string[];
  skill?: string;
  skillNames?: string[];
  skillName?: string;
  thinkingSteps?: ProgressStep[];
}
```

- [ ] **Step 4: `loadInitialSession` 映射保留 `created_at`**

`apps/dsa-web/src/stores/agentChatStore.ts` 第 160-169 行改为：

```typescript
          const msgs = await agentApi.getChatSessionMessages(savedId);
          if (msgs.length > 0) {
            set({
              messages: msgs.map((m) => ({
                id: m.id,
                role: m.role,
                content: m.content,
                created_at: m.created_at ?? null,
              })),
            });
          }
```

- [ ] **Step 5: `switchSession` 映射保留 `created_at`**

`apps/dsa-web/src/stores/agentChatStore.ts` 第 205-211 行改为：

```typescript
      set({
        messages: msgs.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          created_at: m.created_at ?? null,
        })),
      });
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `cd apps/dsa-web && npx vitest run src/stores/__tests__/agentChatStore.test.ts`
Expected: PASS（全部用例）。

- [ ] **Step 7: Commit**

```bash
git add apps/dsa-web/src/stores/agentChatStore.ts apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts
git commit -m "feat(chat): preserve created_at on loaded session messages"
```

---

### Task 2: 新增 `shouldResume` 纯函数与续等常量

把"是否需要续等"的判断抽成纯函数，独立单测。

**Files:**
- Modify: `apps/dsa-web/src/stores/agentChatStore.ts`（顶部加常量、加 `shouldResume` 并 export）
- Test: `apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts`（新增 `shouldResume` describe）

**Interfaces:**
- Produces: `export function shouldResume(messages: Message[]): boolean`；常量 `RESUME_WINDOW_MS`

- [ ] **Step 1: 写 `shouldResume` 失败测试**

在 `apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts` 顶部导入处（第 2 行）补充导入：

```typescript
import { shouldResume, useAgentChatStore } from '../agentChatStore';
```

在文件末尾追加：

```typescript
describe('shouldResume', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-09T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns true when the last message is a recent user message with no reply', () => {
    expect(
      shouldResume([{ id: 'u-1', role: 'user', content: 'q', created_at: '2026-07-09T11:58:00Z' }]),
    ).toBe(true);
  });

  it('returns false when the last message is an assistant reply', () => {
    expect(
      shouldResume([{ id: 'a-1', role: 'assistant', content: 'a', created_at: '2026-07-09T11:58:00Z' }]),
    ).toBe(false);
  });

  it('returns false when the dangling user message is older than the resume window', () => {
    expect(
      shouldResume([{ id: 'u-1', role: 'user', content: 'q', created_at: '2026-07-09T11:54:00Z' }]),
    ).toBe(false);
  });

  it('returns false for an empty message list', () => {
    expect(shouldResume([])).toBe(false);
  });

  it('returns false when the user message has no created_at', () => {
    expect(shouldResume([{ id: 'u-1', role: 'user', content: 'q' }])).toBe(false);
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd apps/dsa-web && npx vitest run src/stores/__tests__/agentChatStore.test.ts -t "shouldResume"`
Expected: FAIL — `shouldResume is not a function`。

- [ ] **Step 3: 实现常量与 `shouldResume`**

`apps/dsa-web/src/stores/agentChatStore.ts` 第 13 行 `const STORAGE_KEY_SESSION = ...;` 之后追加：

```typescript
const RESUME_WINDOW_MS = 5 * 60 * 1000;
const POLL_INTERVAL_MS = 3000;
const MAX_WAIT_MS = 5 * 60 * 1000;
const RESUME_TIMEOUT_MESSAGE = '回复可能已中断，请重试';

export function shouldResume(messages: Message[]): boolean {
  if (messages.length === 0) return false;
  const last = messages[messages.length - 1];
  if (last.role !== 'user' || !last.created_at) return false;
  const createdAt = new Date(last.created_at).getTime();
  if (Number.isNaN(createdAt)) return false;
  return Date.now() - createdAt <= RESUME_WINDOW_MS;
}
```

注意：`shouldResume` 引用 `Message` 类型，需在 `Message` 接口（第 34 行起）定义之后。把上面 `shouldResume` 函数放在 `getStreamFailureError` 函数（第 75-87 行）之后、`interface AgentChatState`（第 89 行）之前即可满足顺序。常量块放在第 13 行之后。

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd apps/dsa-web && npx vitest run src/stores/__tests__/agentChatStore.test.ts -t "shouldResume"`
Expected: PASS（5 个用例）。

- [ ] **Step 5: Commit**

```bash
git add apps/dsa-web/src/stores/agentChatStore.ts apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts
git commit -m "feat(chat): add shouldResume heuristic for pending reply"
```

---

### Task 3: 新增续等机制 `resumePendingReply` + `clearResumeTimer`

实现轮询机制本体，并通过直接调用验证。本任务不接线到 session 流（接线在 Task 4）。

**Files:**
- Modify: `apps/dsa-web/src/stores/agentChatStore.ts`（state/actions 接口、初始值、模块级 timer、`clearResumeTimer`、`resumePendingReply`、测试 `beforeEach`）
- Test: `apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts`（`beforeEach` 重置 `resuming`+清续等；新增 `resumePendingReply` describe）

**Interfaces:**
- Consumes: `agentApi.getChatSessionMessages`（`api/agent.ts:67`）、`createParsedApiError`（已导入，`agentChatStore.ts:5`）、`Message`、常量
- Produces: `AgentChatState.resuming: boolean`；`AgentChatActions.clearResumeTimer(): void`；`AgentChatActions.resumePendingReply(sessionId: string): Promise<void>`

- [ ] **Step 1: 加 `resuming` 状态字段**

`apps/dsa-web/src/stores/agentChatStore.ts` `interface AgentChatState`（第 89-101 行）在 `loading: boolean;` 下一行加：

```typescript
  resuming: boolean;
```

初始值（第 118-129 行 `create(...)` 内 `loading: false,` 下一行）加：

```typescript
  resuming: false,
```

- [ ] **Step 2: `beforeEach` 重置 `resuming`**

`apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts` 第 43-55 行 `setState` 内，在 `loading: false,` 下一行加 `resuming: false,`：

```typescript
  useAgentChatStore.setState({
    messages: [],
    loading: false,
    resuming: false,
    progressSteps: [],
    sessionId: 'session-test',
    sessions: [],
    sessionsLoading: false,
    chatError: null,
    currentRoute: '/chat',
    completionBadge: false,
    hasInitialLoad: true,
    abortController: null,
  });
```

- [ ] **Step 3: 写 `resumePendingReply` 失败测试**

`apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts` 顶部导入处补常量与类型（第 2 行附近）：

```typescript
import {
  MAX_WAIT_MS,
  POLL_INTERVAL_MS,
  RESUME_TIMEOUT_MESSAGE,
  shouldResume,
  useAgentChatStore,
} from '../agentChatStore';
```

在 `shouldResume` describe 之后追加：

```typescript
describe('agentChatStore.resumePendingReply', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    useAgentChatStore.getState().clearResumeTimer();
    vi.useRealTimers();
  });

  const setupDanglingUser = () => {
    useAgentChatStore.setState({
      sessionId: 'session-resume',
      messages: [
        { id: 'u-1', role: 'user', content: '分析茅台', created_at: '2026-07-09T11:58:00Z' },
      ],
      loading: false,
      resuming: false,
      hasInitialLoad: true,
      currentRoute: '/chat',
    });
  };

  it('sets loading and resuming while waiting for the reply', async () => {
    setupDanglingUser();
    vi.mocked(agentApi.getChatSessionMessages).mockResolvedValue([
      { id: 'u-1', role: 'user', content: '分析茅台', created_at: '2026-07-09T11:58:00Z' },
    ]);

    void useAgentChatStore.getState().resumePendingReply('session-resume');

    expect(useAgentChatStore.getState().loading).toBe(true);
    expect(useAgentChatStore.getState().resuming).toBe(true);
  });

  it('appends the assistant message and clears loading once the reply lands', async () => {
    setupDanglingUser();
    vi.mocked(agentApi.getChatSessionMessages).mockResolvedValue([
      { id: 'u-1', role: 'user', content: '分析茅台', created_at: '2026-07-09T11:58:00Z' },
      { id: 'a-1', role: 'assistant', content: '最终回复', created_at: '2026-07-09T11:58:30Z' },
    ]);

    void useAgentChatStore.getState().resumePendingReply('session-resume');
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.resuming).toBe(false);
    expect(state.messages).toHaveLength(2);
    expect(state.messages[1]).toMatchObject({ role: 'assistant', content: '最终回复' });
  });

  it('keeps waiting when the reply has not arrived yet', async () => {
    setupDanglingUser();
    vi.mocked(agentApi.getChatSessionMessages).mockResolvedValue([
      { id: 'u-1', role: 'user', content: '分析茅台', created_at: '2026-07-09T11:58:00Z' },
    ]);

    void useAgentChatStore.getState().resumePendingReply('session-resume');
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);

    const state = useAgentChatStore.getState();
    expect(state.resuming).toBe(true);
    expect(state.loading).toBe(true);
    expect(state.messages).toHaveLength(1);
  });

  it('tolerates a transient poll failure and keeps waiting', async () => {
    setupDanglingUser();
    vi.mocked(agentApi.getChatSessionMessages)
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce([
        { id: 'u-1', role: 'user', content: '分析茅台', created_at: '2026-07-09T11:58:00Z' },
        { id: 'a-1', role: 'assistant', content: '最终回复', created_at: '2026-07-09T11:58:30Z' },
      ]);

    void useAgentChatStore.getState().resumePendingReply('session-resume');
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS); // first poll rejects
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS); // second poll succeeds

    const state = useAgentChatStore.getState();
    expect(state.resuming).toBe(false);
    expect(state.messages[1]).toMatchObject({ role: 'assistant', content: '最终回复' });
  });

  it('times out with a chatError when no reply arrives within MAX_WAIT_MS', async () => {
    setupDanglingUser();
    vi.mocked(agentApi.getChatSessionMessages).mockResolvedValue([
      { id: 'u-1', role: 'user', content: '分析茅台', created_at: '2026-07-09T11:58:00Z' },
    ]);

    void useAgentChatStore.getState().resumePendingReply('session-resume');
    await vi.advanceTimersByTimeAsync(MAX_WAIT_MS + POLL_INTERVAL_MS);

    const state = useAgentChatStore.getState();
    expect(state.resuming).toBe(false);
    expect(state.loading).toBe(false);
    expect(state.chatError).toMatchObject({ message: RESUME_TIMEOUT_MESSAGE });
  });

  it('does not start when loading is already true', async () => {
    setupDanglingUser();
    useAgentChatStore.setState({ loading: true });

    await useAgentChatStore.getState().resumePendingReply('session-resume');

    expect(useAgentChatStore.getState().resuming).toBe(false);
  });
});
```

- [ ] **Step 4: 运行测试，确认失败**

Run: `cd apps/dsa-web && npx vitest run src/stores/__tests__/agentChatStore.test.ts -t "resumePendingReply"`
Expected: FAIL — `resumePendingReply is not a function` / `clearResumeTimer is not a function`。

- [ ] **Step 5: 导入 `ChatSessionMessage` 类型**

`apps/dsa-web/src/stores/agentChatStore.ts` 第 3 行改为：

```typescript
import type { ChatSessionItem, ChatSessionMessage, ChatStreamRequest } from '../api/agent';
```

- [ ] **Step 6: 加模块级 timer 变量**

`apps/dsa-web/src/stores/agentChatStore.ts` 在 Task 2 新增的常量块之后追加：

```typescript
let resumeTimerId: ReturnType<typeof setTimeout> | null = null;
let resumeVisibilityHandler: (() => void) | null = null;
```

- [ ] **Step 7: 扩展 actions 接口**

`apps/dsa-web/src/stores/agentChatStore.ts` `interface AgentChatActions`（第 103-111 行）在 `startStream` 之后追加：

```typescript
  clearResumeTimer: () => void;
  resumePendingReply: (sessionId: string) => Promise<void>;
```

- [ ] **Step 8: 实现 `clearResumeTimer` 与 `resumePendingReply`**

`apps/dsa-web/src/stores/agentChatStore.ts` 在 `startStream` action 之后（`startStream` 的结尾 `},` 之后、`}))` 之前）插入两个 action。先定位 `startStream` 的结尾：它是 `create(...)` 里最后一个 action，结尾是 `    } finally { ... await get().loadSessions(); } },` 然后跟 `}));`。在 `startStream` 整个函数结束的 `},` 之后插入：

```typescript

  clearResumeTimer: () => {
    if (resumeTimerId !== null) {
      clearTimeout(resumeTimerId);
      resumeTimerId = null;
    }
    if (resumeVisibilityHandler) {
      document.removeEventListener('visibilitychange', resumeVisibilityHandler);
      resumeVisibilityHandler = null;
    }
    if (get().resuming) {
      set({ loading: false, resuming: false });
    }
  },

  resumePendingReply: async (sessionId) => {
    if (get().loading) return;
    const targetSessionId = sessionId;
    const startedAt = Date.now();
    set({ loading: true, resuming: true, chatError: null });

    const pollOnce = async () => {
      if (!get().resuming) return;
      if (get().sessionId !== targetSessionId) {
        set({ loading: false, resuming: false });
        get().clearResumeTimer();
        return;
      }
      if (Date.now() - startedAt >= MAX_WAIT_MS) {
        set({
          loading: false,
          resuming: false,
          chatError: createParsedApiError({
            title: '请求失败',
            message: RESUME_TIMEOUT_MESSAGE,
            rawMessage: 'resume poll exceeded max wait',
            category: 'unknown',
          }),
        });
        get().clearResumeTimer();
        void get().loadSessions();
        return;
      }

      let msgs: ChatSessionMessage[];
      try {
        msgs = await agentApi.getChatSessionMessages(targetSessionId);
      } catch {
        if (!get().resuming) return;
        resumeTimerId = setTimeout(pollOnce, POLL_INTERVAL_MS);
        return;
      }
      if (!get().resuming || get().sessionId !== targetSessionId) return;

      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        set((s) => ({
          loading: false,
          resuming: false,
          messages: [
            ...s.messages,
            {
              id: String(last.id),
              role: 'assistant',
              content: last.content,
              created_at: last.created_at ?? null,
            },
          ],
        }));
        get().clearResumeTimer();
        if (get().currentRoute !== '/chat') {
          set({ completionBadge: true });
        }
        void get().loadSessions();
        return;
      }

      resumeTimerId = setTimeout(pollOnce, POLL_INTERVAL_MS);
    };

    resumeVisibilityHandler = () => {
      if (document.visibilityState === 'visible' && get().resuming) {
        void pollOnce();
      }
    };
    document.addEventListener('visibilitychange', resumeVisibilityHandler);

    resumeTimerId = setTimeout(pollOnce, POLL_INTERVAL_MS);
  },
```

- [ ] **Step 9: `beforeEach` 清续等**

`apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts` `beforeEach`（第 41 行起）在 `vi.clearAllMocks();` 之前加一行：

```typescript
  useAgentChatStore.getState().clearResumeTimer();
  vi.clearAllMocks();
```

- [ ] **Step 10: 运行测试，确认通过**

Run: `cd apps/dsa-web && npx vitest run src/stores/__tests__/agentChatStore.test.ts`
Expected: PASS（含 `resumePendingReply` 全部用例与既有用例）。

- [ ] **Step 11: Commit**

```bash
git add apps/dsa-web/src/stores/agentChatStore.ts apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts
git commit -m "feat(chat): add resumePendingReply polling machinery"
```

---

### Task 4: 接线到 session 加载/切换，并在发送/切会话时清理

让 `loadInitialSession`/`switchSession` 在拉到"最近无回复 user 消息"时触发续等；`switchSession`/`startNewChat`/`startStream` 开头清续等。

**Files:**
- Modify: `apps/dsa-web/src/stores/agentChatStore.ts`（`loadInitialSession`、`switchSession`、`startNewChat`、`startStream`）
- Test: `apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts`（新增续等接线 describe）

**Interfaces:**
- Consumes: `shouldResume`、`resumePendingReply`、`clearResumeTimer`（Task 2/3）

- [ ] **Step 1: 写接线失败测试**

`apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts` 在 `resumePendingReply` describe 之后追加：

```typescript
describe('agentChatStore resume wiring', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-09T12:00:00Z'));
  });

  afterEach(() => {
    useAgentChatStore.getState().clearResumeTimer();
    vi.useRealTimers();
  });

  it('starts resume polling after switching to a session with a recent dangling user message', async () => {
    vi.mocked(agentApi.getChatSessionMessages).mockResolvedValue([
      { id: 'u-1', role: 'user', content: '分析茅台', created_at: '2026-07-09T11:58:00Z' },
    ]);

    await useAgentChatStore.getState().switchSession('session-resume');

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(true);
    expect(state.resuming).toBe(true);
  });

  it('does not start resume polling when the last message is an assistant reply', async () => {
    vi.mocked(agentApi.getChatSessionMessages).mockResolvedValue([
      { id: 'a-1', role: 'assistant', content: '历史回复', created_at: '2026-07-09T11:58:00Z' },
    ]);

    await useAgentChatStore.getState().switchSession('session-resume');

    const state = useAgentChatStore.getState();
    expect(state.resuming).toBe(false);
    expect(state.loading).toBe(false);
  });

  it('stops resume polling when switching to another session', async () => {
    vi.mocked(agentApi.getChatSessionMessages).mockImplementation(async (id) => {
      if (id === 'session-a') {
        return [{ id: 'u-1', role: 'user', content: '分析茅台', created_at: '2026-07-09T11:58:00Z' }];
      }
      return [{ id: 'a-1', role: 'assistant', content: '历史回复', created_at: '2026-07-09T11:58:00Z' }];
    });

    await useAgentChatStore.getState().switchSession('session-a');
    expect(useAgentChatStore.getState().resuming).toBe(true);

    await useAgentChatStore.getState().switchSession('session-b');
    expect(useAgentChatStore.getState().resuming).toBe(false);
    expect(useAgentChatStore.getState().loading).toBe(false);
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd apps/dsa-web && npx vitest run src/stores/__tests__/agentChatStore.test.ts -t "resume wiring"`
Expected: FAIL — `switchSession` 未触发续等（`loading` 仍为 `false`）/ 未在切换时停止。

- [ ] **Step 3: `switchSession` 清续等 + 触发续等**

`apps/dsa-web/src/stores/agentChatStore.ts` `switchSession`（第 185-215 行）改为：

```typescript
  switchSession: async (targetSessionId) => {
    const { sessionId, messages, abortController } = get();
    if (targetSessionId === sessionId && messages.length > 0) return;
    get().clearResumeTimer();
    abortController?.abort();
    set({
      messages: [],
      sessionId: targetSessionId,
      loading: false,
      progressSteps: [],
      chatError: null,
      abortController: null,
    });
    localStorage.setItem(STORAGE_KEY_SESSION, targetSessionId);

    try {
      const msgs = await agentApi.getChatSessionMessages(targetSessionId);
      if (get().sessionId !== targetSessionId) {
        return;
      }
      const mapped = msgs.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        created_at: m.created_at ?? null,
      }));
      set({ messages: mapped });
      if (shouldResume(mapped)) {
        void get().resumePendingReply(targetSessionId);
      }
    } catch {
      // Ignore
    }
  },
```

- [ ] **Step 4: `loadInitialSession` 触发续等**

`apps/dsa-web/src/stores/agentChatStore.ts` `loadInitialSession` 中 Task 1 改过的消息映射块（`if (msgs.length > 0) { ... }`）改为：

```typescript
          const msgs = await agentApi.getChatSessionMessages(savedId);
          if (msgs.length > 0) {
            const mapped = msgs.map((m) => ({
              id: m.id,
              role: m.role,
              content: m.content,
              created_at: m.created_at ?? null,
            }));
            set({ messages: mapped });
            if (shouldResume(mapped)) {
              void get().resumePendingReply(savedId);
            }
          }
```

- [ ] **Step 5: `startNewChat` 清续等**

`apps/dsa-web/src/stores/agentChatStore.ts` `startNewChat`（第 217-230 行）在 `get().abortController?.abort();` 下一行加 `get().clearResumeTimer();`：

```typescript
  startNewChat: () => {
    // Abort any in-flight stream so the old request does not keep running
    get().abortController?.abort();
    get().clearResumeTimer();
    const newId = generateUUID();
    set({
      sessionId: newId,
      messages: [],
      loading: false,
      progressSteps: [],
      chatError: null,
      abortController: null,
    });
    localStorage.setItem(STORAGE_KEY_SESSION, newId);
  },
```

- [ ] **Step 6: `startStream` 清续等**

`apps/dsa-web/src/stores/agentChatStore.ts` `startStream`（第 232 行起）在 `if (get().loading) return;` 下一行加 `get().clearResumeTimer();`：

```typescript
  startStream: async (payload, meta) => {
    if (get().loading) return;
    get().clearResumeTimer();
    const { abortController: prevAc, sessionId: storeSessionId } = get();
    prevAc?.abort();
```

- [ ] **Step 7: 运行测试，确认通过**

Run: `cd apps/dsa-web && npx vitest run src/stores/__tests__/agentChatStore.test.ts`
Expected: PASS（含接线用例与全部既有用例）。

- [ ] **Step 8: Lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: 无错误。

- [ ] **Step 9: Commit**

```bash
git add apps/dsa-web/src/stores/agentChatStore.ts apps/dsa-web/src/stores/__tests__/agentChatStore.test.ts
git commit -m "feat(chat): resume pending reply on session load and switch"
```

---

### Task 5: ChatPage loading 气泡续等文案

续等时 `progressSteps` 为空，现有 `getCurrentStage([])` 返回 `'正在连接...'`（`ChatPage.tsx:695`）会误导。续等态改显 `'AI 正在生成回复…'`。

**Files:**
- Modify: `apps/dsa-web/src/pages/ChatPage.tsx:298-311`（解构）、`1247-1249`（气泡文案）
- Test: `apps/dsa-web/src/pages/__tests__/ChatPage.test.tsx`（`mockStoreState` + `beforeEach` 加 `resuming`；新增 UI 用例）

**Interfaces:**
- Consumes: store 的 `resuming` 状态（Task 3）

- [ ] **Step 1: `mockStoreState` 加 `resuming`**

`apps/dsa-web/src/pages/__tests__/ChatPage.test.tsx` `mockStoreState`（第 51-72 行）在 `loading: false,` 下一行加 `resuming: false,`：

```typescript
const mockStoreState = {
  messages: [] as Message[],
  loading: false,
  resuming: false,
  progressSteps: [] as ProgressStep[],
  sessionId: 'session-1',
  sessions: [
    {
      session_id: 'session-1',
      title: '请简要分析 600519',
      message_count: 2,
      created_at: '2026-03-15T09:00:00Z',
      last_active: '2026-03-15T09:05:00Z',
    },
  ],
  sessionsLoading: false,
  chatError: null,
  loadSessions: mockLoadSessions,
  loadInitialSession: mockLoadInitialSession,
  switchSession: mockSwitchSession,
  startStream: mockStartStream,
  clearCompletionBadge: mockClearCompletionBadge,
};
```

- [ ] **Step 2: `beforeEach` 重置 `resuming`**

`apps/dsa-web/src/pages/__tests__/ChatPage.test.tsx` `beforeEach`（第 146-162 行）在 `mockStoreState.loading = false;` 下一行加 `mockStoreState.resuming = false;`：

```typescript
  mockStoreState.messages = [];
  mockStoreState.loading = false;
  mockStoreState.resuming = false;
  mockStoreState.progressSteps = [];
  mockStoreState.chatError = null;
  mockStoreState.sessionsLoading = false;
  mockStoreState.sessionId = 'session-1';
```

- [ ] **Step 3: 写 UI 失败测试**

`apps/dsa-web/src/pages/__tests__/ChatPage.test.tsx` 在 `describe('ChatPage', () => {` 内任一用例之后追加：

```typescript
  it('shows a generating hint while resuming a pending reply', async () => {
    mockStoreState.loading = true;
    mockStoreState.resuming = true;
    mockStoreState.progressSteps = [];
    mockStoreState.messages = [
      { id: 'u-1', role: 'user', content: '分析茅台' },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByText('AI 正在生成回复…')).toBeInTheDocument();
  });
```

- [ ] **Step 4: 运行测试，确认失败**

Run: `cd apps/dsa-web && npx vitest run src/pages/__tests__/ChatPage.test.tsx -t "generating hint while resuming"`
Expected: FAIL — 找不到 `'AI 正在生成回复…'`（仍显示 `getCurrentStage([])` 的 `'正在连接...'`）。

- [ ] **Step 5: ChatPage 解构 `resuming`**

`apps/dsa-web/src/pages/ChatPage.tsx` 第 298-311 行解构处加 `resuming,`：

```typescript
  const {
    messages,
    loading,
    resuming,
    progressSteps,
    sessionId,
    sessions,
    sessionsLoading,
    chatError,
    loadSessions,
    loadInitialSession,
    switchSession,
    startStream,
    clearCompletionBadge,
  } = useAgentChatStore();
```

- [ ] **Step 6: loading 气泡文案续等分支**

`apps/dsa-web/src/pages/ChatPage.tsx` 第 1247-1249 行改为：

```tsx
                    <span className="text-secondary-text">
                      {resuming ? 'AI 正在生成回复…' : getCurrentStage(progressSteps)}
                    </span>
```

- [ ] **Step 7: 运行测试，确认通过**

Run: `cd apps/dsa-web && npx vitest run src/pages/__tests__/ChatPage.test.tsx`
Expected: PASS（含新用例与既有用例；既有 `loading:true + progressSteps` 用例因 `resuming` 默认 `false` 仍走 `getCurrentStage`，行为不变）。

- [ ] **Step 8: Lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: 无错误。

- [ ] **Step 9: Commit**

```bash
git add apps/dsa-web/src/pages/ChatPage.tsx apps/dsa-web/src/pages/__tests__/ChatPage.test.tsx
git commit -m "feat(chat): show generating hint while resuming pending reply"
```

---

### Task 6: 更新 CHANGELOG 与手动验证说明

**Files:**
- Modify: `docs/CHANGELOG.md`（`[Unreleased]` 段）

- [ ] **Step 1: 追加 CHANGELOG 条目**

`docs/CHANGELOG.md` 第 26 行（`[Unreleased]` 段最后一条 `[新功能] 飞书推送...` 之后）追加一行：

```markdown
- [改进] 问股聊天页重开后自动续等并展示未完成的 AI 回复，回复生成期间锁定输入避免并发，移动端回前台即时补查。
```

- [ ] **Step 2: 全量回归**

Run: `cd apps/dsa-web && npx vitest run && npm run lint && npm run build`
Expected: 全部通过。

- [ ] **Step 3: Commit**

```bash
git add docs/CHANGELOG.md
git commit -m "docs: changelog for chat resume pending reply"
```

- [ ] **Step 4: 手动验证（PR 描述附证据）**

按 spec §7.3 验证（无法在 CI 自动化，需人工）：

1. 桌面端：`/chat` 发送 → AI 生成中关闭页面 → 重开 → 见"AI 正在生成回复…"且发送禁用 → 回复落库后自动展示。
2. 移动端：发送 → 切后台 → 回前台 → 即时见到已完成的回复。
3. 超时：构造无回复场景（如停掉后端）→ 5 分钟后见"回复可能已中断，请重试"，输入恢复。

---

## Self-Review

**1. Spec coverage**
- §5.1 触发条件 → Task 2（`shouldResume`）+ Task 4（接线 `loadInitialSession`/`switchSession`）。✓
- §5.2 轮询循环（守卫、置态、轮询、超时、停止）→ Task 3（`resumePendingReply`）。✓
- §5.3 移动端（后台节流靠 timer 暂停、回前台 `visibilitychange` 即时补查、单次失败不致命、清理监听）→ Task 3（`resumeVisibilityHandler`、catch 分支、`clearResumeTimer` 移除监听）。✓
- §5.5 常量 → Task 2/3。✓
- §6.1 store 改动（`created_at`、`resuming`、`shouldResume`、`clearResumeTimer`、`resumePendingReply`、调用点）→ Task 1/2/3/4。✓
- §6.2 ChatPage 文案 → Task 5。✓
- §6.3 测试 → Task 2/3/4/5。✓
- §7 测试矩阵 → 各 Task TDD 步骤 + Task 6 手动验证。✓
- §8 风险（>5 分钟超时降级、启发式边界、多标签去重）→ 设计已说明；多标签"按消息 id 去重"由 `set((s) => ({ messages: [...s.messages, ...] }))` 追加实现，若重复触发需人工确认，属可接受边界（spec §8 已声明）。

**2. Placeholder scan**：无 TBD/TODO；每个代码步骤含完整代码与命令。

**3. Type consistency**：`Message.created_at?: string | null`（Task 1）在 Task 3 `resumePendingReply` 追加 assistant 消息时用 `created_at: last.created_at ?? null`（`ChatSessionMessage.created_at: string | null`，`api/agent.ts:49`），类型一致。`shouldResume(messages: Message[])`（Task 2）与 Task 4 调用 `shouldResume(mapped)`（`mapped` 为 `Message[]`）一致。`clearResumeTimer`/`resumePendingReply` 在 Task 3 接口声明与 Task 4 调用名一致。常量 `POLL_INTERVAL_MS`/`MAX_WAIT_MS`/`RESUME_TIMEOUT_MESSAGE` 在 Task 2/3 定义，Task 3 测试导入使用，名一致。
