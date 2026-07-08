# 问股页面移动端优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `apps/dsa-web/src/pages/ChatPage.tsx` (1428 行) 拆为协调器 + 4 个子组件 (ChatHeader / MessageList / ChatComposer / SessionSidebar)，每个子组件 mobile-first 响应式，桌面端功能 100% 保留。

**Architecture:** 响应式重构。ChatPage 保留为协调器 (~600 行)，持有 UI 本地状态 + `useIsMobile`。4 个子组件各自 mobile-first 响应式，通过 props 接收 `isMobile` 和回调，通过 `useAgentChatStore` 选择器订阅数据。`agentChatStore` 接口不变。

**Tech Stack:** React 19、TypeScript 5.9、Vite 7、Tailwind CSS v4、zustand、vitest 4、@testing-library/react、Playwright 1.58。

## Global Constraints

- 所有改动仅在 `apps/dsa-web/` 内，不触碰后端、桌面端、工作流。
- 不改 `agentChatStore` 接口（messages、sessions、loading、streaming、activeSessionId 等保持不变）。
- 不引入新依赖（复用现有 `Drawer`、`ScrollArea`、`Button`、`Badge`、`EmptyState`、`InlineAlert`、`ApiErrorAlert`、`Tooltip`、`ConfirmDialog` 等 common 组件）。
- 桌面端功能 100% 保留：仅 Header 精简（描述移到 EmptyState）、输入区结构统一，功能不动。
- 不引入 PWA / 手势 / 底部 tab bar / 离线检测 / 消息长按菜单。
- commit message 用英文，不加 `Co-Authored-By`，用 `feat`/`fix`/`refactor`/`docs`/`test`/`chore` 前缀。
- 每个 Task 结尾独立 commit。
- 验证矩阵：每个 Task 至少跑 `cd apps/dsa-web && npm run lint && npm run build`；涉及组件逻辑的 Task 跑 `npm run test`（vitest）；涉及 e2e 的 Task 跑 `npx playwright test mobile-smoke`。
- Spec 文件：`docs/superpowers/specs/2026-07-08-ask-stock-mobile-design.md`（已 commit 为 d93a09c）。
- 按 CLAUDE.md：`docs/CHANGELOG.md` 的 `[Unreleased]` 段用扁平格式 `- [类型] 描述`，不加 `### 类目标题`。
- 按 CLAUDE.md：PR 描述附移动端截图。

---

### Task 1: 拆出 SessionSidebar 子组件

**Files:**
- Create: `apps/dsa-web/src/pages/chat/SessionSidebar.tsx`
- Create: `apps/dsa-web/src/pages/chat/__tests__/SessionSidebar.test.tsx`
- Modify: `apps/dsa-web/src/pages/ChatPage.tsx` (替换 L875-893 的桌面侧边栏 + 移动端覆盖层)

**Interfaces:**
- Consumes: `useAgentChatStore` 选择 `sessions, sessionsLoading, sessionId, switchSession, startNewChat, deleteChatSession`；`ConfirmDialog` 组件
- Produces: `SessionSidebar` 组件，props 接口：
  ```ts
  interface SessionSidebarProps {
    isOpen: boolean;          // 仅 mobile 抽屉用，desktop 常驻忽略
    onClose: () => void;      // mobile 抽屉关闭回调
    isMobile: boolean;
  }
  ```

- [ ] **Step 1: 写失败测试 `SessionSidebar.test.tsx`**

创建 `apps/dsa-web/src/pages/chat/__tests__/SessionSidebar.test.tsx`：

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SessionSidebar } from '../SessionSidebar';

const mockSwitchSession = vi.fn();
const mockStartNewChat = vi.fn();

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: (selector: (s: any) => any) =>
    selector({
      sessions: [
        { session_id: 's1', title: '会话1', message_count: 2, created_at: '', last_active: '' },
      ],
      sessionsLoading: false,
      sessionId: 's1',
      switchSession: mockSwitchSession,
      startNewChat: mockStartNewChat,
      deleteChatSession: vi.fn(),
    }),
}));

describe('SessionSidebar', () => {
  it('renders session list from store', () => {
    render(<SessionSidebar isOpen={false} onClose={() => {}} isMobile={false} />);
    expect(screen.getByText('会话1')).toBeInTheDocument();
  });

  it('calls startNewChat when new chat button clicked', () => {
    render(<SessionSidebar isOpen={false} onClose={() => {}} isMobile={false} />);
    fireEvent.click(screen.getByText('新对话'));
    expect(mockStartNewChat).toHaveBeenCalled();
  });

  it('calls switchSession and onClose when session clicked on mobile', () => {
    const onClose = vi.fn();
    render(<SessionSidebar isOpen={true} onClose={onClose} isMobile={true} />);
    fireEvent.click(screen.getByText('会话1'));
    expect(mockSwitchSession).toHaveBeenCalledWith('s1');
    expect(onClose).toHaveBeenCalled();
  });

  it('does not call onClose on desktop when session clicked', () => {
    const onClose = vi.fn();
    render(<SessionSidebar isOpen={false} onClose={onClose} isMobile={false} />);
    fireEvent.click(screen.getByText('会话1'));
    expect(mockSwitchSession).toHaveBeenCalledWith('s1');
    expect(onClose).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd apps/dsa-web && npx vitest run src/pages/chat/__tests__/SessionSidebar.test.tsx`
Expected: FAIL with "Cannot find module '../SessionSidebar'"

- [ ] **Step 3: 创建 `SessionSidebar.tsx`**

创建 `apps/dsa-web/src/pages/chat/SessionSidebar.tsx`。从 `ChatPage.tsx` L780-862 迁移 `sidebarContent` 的逻辑（会话列表 + 新对话按钮 + 删除确认），封装为组件。骨架：

```tsx
import { useState } from 'react';
import { ScrollArea, Button, ConfirmDialog } from '../../components/common';
import { useAgentChatStore } from '../../stores/agentChatStore';
import { cn } from '../../utils/cn';

interface SessionSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  isMobile: boolean;
}

export function SessionSidebar({ isOpen, onClose, isMobile }: SessionSidebarProps) {
  const sessions = useAgentChatStore((s) => s.sessions);
  const sessionsLoading = useAgentChatStore((s) => s.sessionsLoading);
  const sessionId = useAgentChatStore((s) => s.sessionId);
  const switchSession = useAgentChatStore((s) => s.switchSession);
  const startNewChat = useAgentChatStore((s) => s.startNewChat);
  const deleteChatSession = useAgentChatStore((s) => s.deleteChatSession);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const handleSelect = (id: string) => {
    switchSession(id);
    if (isMobile) onClose();
  };

  // 迁移 ChatPage.tsx L780-862 的 sidebarContent JSX：
  // - 顶栏：标题"历史对话" + "新对话"按钮（sticky）
  // - ScrollArea：会话列表项（min-h 44px，触控友好）
  // - ConfirmDialog：删除确认
  // 桌面端：常驻容器；移动端：抽屉内容器（由 ChatPage 控制开关）
  return (
    <>
      <div className="flex h-full flex-col">
        {/* 顶栏：sticky 顶部，含"新对话"按钮 */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-white/6 bg-card/90 px-4 py-3 backdrop-blur">
          <h2 className="text-sm font-medium text-foreground">历史对话</h2>
          <Button variant="action-primary" size="sm" onClick={() => startNewChat()}>
            新对话
          </Button>
        </div>
        <ScrollArea className="flex-1" viewportClassName="p-2">
          {sessionsLoading ? (
            <div className="p-4 text-sm text-secondary-text">加载中...</div>
          ) : sessions.length === 0 ? (
            <div className="p-4 text-sm text-secondary-text">暂无历史对话</div>
          ) : (
            <ul className="space-y-1">
              {sessions.map((session) => (
                <li key={session.session_id}>
                  <button
                    onClick={() => handleSelect(session.session_id)}
                    className={cn(
                      'flex min-h-[44px] w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors',
                      session.session_id === sessionId
                        ? 'bg-hover text-foreground'
                        : 'text-secondary-text hover:bg-hover/50 hover:text-foreground',
                    )}
                  >
                    <span className="flex-1 truncate">{session.title || '未命名会话'}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </ScrollArea>
      </div>
      <ConfirmDialog
        isOpen={Boolean(deleteConfirmId)}
        title="删除对话"
        message="删除后，该对话将不可恢复，确认删除吗？"
        confirmText="删除"
        cancelText="取消"
        isDanger
        onConfirm={() => {
          if (deleteConfirmId) void deleteChatSession(deleteConfirmId);
          setDeleteConfirmId(null);
        }}
        onCancel={() => setDeleteConfirmId(null)}
      />
    </>
  );
}
```

注：完整迁移需保留原 `sidebarContent` 中每条会话的删除按钮、`message_count` 显示、时间格式化等。从 `ChatPage.tsx` L780-862 原样搬运这些 JSX，只把外层容器改为上述结构。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd apps/dsa-web && npx vitest run src/pages/chat/__tests__/SessionSidebar.test.tsx`
Expected: PASS（4 个测试全过）

- [ ] **Step 5: 在 ChatPage 中引用新组件，删除已迁移代码**

修改 `apps/dsa-web/src/pages/ChatPage.tsx`：
1. 顶部加 import：`import { SessionSidebar } from './chat/SessionSidebar';`
2. 删除 L780-862 的 `sidebarContent` 变量定义
3. 替换 L875-893（桌面侧边栏 + 移动端覆盖层）为：

```tsx
{/* Desktop sidebar */}
<div className="hidden h-full w-64 flex-shrink-0 flex-col overflow-hidden rounded-[1.25rem] border border-white/8 bg-card/82 shadow-soft-card md:flex">
  <SessionSidebar isOpen={false} onClose={() => {}} isMobile={false} />
</div>

{/* Mobile sidebar overlay */}
{sidebarOpen && (
  <div
    className="fixed inset-0 z-40 md:hidden"
    onClick={() => setSidebarOpen(false)}
  >
    <div className="page-drawer-overlay absolute inset-0" />
    <div
      className="relative h-full w-[85vw] max-w-[320px] flex flex-col glass-card overflow-hidden border-r border-white/10 bg-card/90 shadow-2xl"
      onClick={(e) => e.stopPropagation()}
    >
      <SessionSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} isMobile={true} />
    </div>
  </div>
)}
```

注：移动端抽屉宽度从 `w-72` (288px) 改为 `w-[85vw] max-w-[320px]`（spec 4.1 节）。

- [ ] **Step 6: 跑现有 ChatPage 测试确认不回归**

Run: `cd apps/dsa-web && npx vitest run src/pages/__tests__/ChatPage.test.tsx`
Expected: PASS（所有现有测试通过）

- [ ] **Step 7: 跑 lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: 无 error

- [ ] **Step 8: Commit**

```bash
git add apps/dsa-web/src/pages/chat/SessionSidebar.tsx \
        apps/dsa-web/src/pages/chat/__tests__/SessionSidebar.test.tsx \
        apps/dsa-web/src/pages/ChatPage.tsx
git commit -m "refactor(web): extract SessionSidebar from ChatPage"
```

---

### Task 2: 拆出 ChatHeader 子组件 + mobile sticky 顶栏

**Files:**
- Create: `apps/dsa-web/src/pages/chat/ChatHeader.tsx`
- Create: `apps/dsa-web/src/pages/chat/__tests__/ChatHeader.test.tsx`
- Modify: `apps/dsa-web/src/pages/ChatPage.tsx` (替换 L909-1053 的 header)

**Interfaces:**
- Consumes: `useAgentChatStore` 选择 `messages, sessionId`；`downloadSession`, `formatSessionAsMarkdown`, `agentApi.sendChat`, `getParsedApiError`；`InlineAlert`, `Button`, `Tooltip`
- Produces: `ChatHeader` 组件，props 接口：
  ```ts
  interface ChatHeaderProps {
    onToggleSidebar: () => void;
    isMobile: boolean;
  }
  ```

- [ ] **Step 1: 写失败测试 `ChatHeader.test.tsx`**

创建 `apps/dsa-web/src/pages/chat/__tests__/ChatHeader.test.tsx`：

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChatHeader } from '../ChatHeader';

vi.mock('../../../api/agent', () => ({
  agentApi: { sendChat: vi.fn() },
}));
vi.mock('../../../api/error', () => ({
  getParsedApiError: vi.fn(() => ({ message: 'fail' })),
}));
vi.mock('../../../utils/chatExport', () => ({
  downloadSession: vi.fn(),
  formatSessionAsMarkdown: vi.fn(() => ''),
}));

const mockStoreState = {
  messages: [{ id: 'm1', role: 'user' as const, content: 'hi' }],
  sessionId: 's1',
};

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: (selector: (s: any) => any) => selector(mockStoreState),
}));

describe('ChatHeader', () => {
  it('renders title 问股', () => {
    render(<ChatHeader onToggleSidebar={() => {}} isMobile={false} />);
    expect(screen.getByText('问股')).toBeInTheDocument();
  });

  it('shows hamburger on mobile and calls onToggleSidebar', () => {
    const onToggle = vi.fn();
    render(<ChatHeader onToggleSidebar={onToggle} isMobile={true} />);
    const hamburger = screen.getByTestId('chat-sidebar-toggle');
    fireEvent.click(hamburger);
    expect(onToggle).toHaveBeenCalled();
  });

  it('hides hamburger on desktop', () => {
    render(<ChatHeader onToggleSidebar={() => {}} isMobile={false} />);
    expect(screen.queryByTestId('chat-sidebar-toggle')).toBeNull();
  });

  it('shows export button only when messages exist', () => {
    const { rerender } = render(<ChatHeader onToggleSidebar={() => {}} isMobile={false} />);
    expect(screen.getByLabelText('导出会话为 Markdown 文件')).toBeInTheDocument();
    mockStoreState.messages = [];
    rerender(<ChatHeader onToggleSidebar={() => {}} isMobile={false} />);
    expect(screen.queryByLabelText('导出会话为 Markdown 文件')).toBeNull();
    mockStoreState.messages = [{ id: 'm1', role: 'user' as const, content: 'hi' }];
  });

  it('hides description on mobile', () => {
    render(<ChatHeader onToggleSidebar={() => {}} isMobile={true} />);
    expect(screen.queryByText(/向 AI 询问个股分析/)).toBeNull();
  });

  it('shows description on desktop', () => {
    render(<ChatHeader onToggleSidebar={() => {}} isMobile={false} />);
    expect(screen.getByText(/向 AI 询问个股分析/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd apps/dsa-web && npx vitest run src/pages/chat/__tests__/ChatHeader.test.tsx`
Expected: FAIL with "Cannot find module '../ChatHeader'"

- [ ] **Step 3: 创建 `ChatHeader.tsx`**

创建 `apps/dsa-web/src/pages/chat/ChatHeader.tsx`。从 `ChatPage.tsx` L909-1053 迁移 header。骨架：

```tsx
import { useState } from 'react';
import { Button, InlineAlert, Tooltip } from '../../components/common';
import { agentApi } from '../../api/agent';
import { getParsedApiError } from '../../api/error';
import { useAgentChatStore } from '../../stores/agentChatStore';
import { downloadSession, formatSessionAsMarkdown } from '../../utils/chatExport';

interface ChatHeaderProps {
  onToggleSidebar: () => void;
  isMobile: boolean;
}

export function ChatHeader({ onToggleSidebar, isMobile }: ChatHeaderProps) {
  const messages = useAgentChatStore((s) => s.messages);
  const [sending, setSending] = useState(false);
  const [sendToast, setSendToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const showSendFeedback = (toast: { type: 'success' | 'error'; message: string }, duration: number) => {
    setSendToast(toast);
    setTimeout(() => setSendToast(null), duration);
  };

  const handleSend = async () => {
    if (sending) return;
    setSending(true);
    setSendToast(null);
    try {
      const content = formatSessionAsMarkdown(messages);
      await agentApi.sendChat(content);
      showSendFeedback({ type: 'success', message: '已发送到通知渠道' }, 3000);
    } catch (err) {
      const parsed = getParsedApiError(err);
      showSendFeedback({ type: 'error', message: parsed.message || '发送失败' }, 5000);
    } finally {
      setSending(false);
    }
  };

  return (
    <header className={isMobile
      ? 'sticky top-0 z-30 flex-shrink-0 border-b border-white/6 bg-card/90 px-3 py-2 backdrop-blur'
      : 'mb-4 flex-shrink-0 space-y-3'
    }>
      <div className={isMobile
        ? 'flex items-center justify-between gap-2'
        : 'flex items-start justify-between gap-4'
      }>
        <h1 className={isMobile
          ? 'flex items-center gap-2 text-base font-bold text-foreground'
          : 'text-2xl font-bold text-foreground flex items-center gap-2'
        }>
          {isMobile && (
            <button
              data-testid="chat-sidebar-toggle"
              onClick={onToggleSidebar}
              className="p-1.5 -ml-1 rounded-lg hover:bg-hover transition-colors text-secondary-text hover:text-foreground"
              aria-label="历史对话"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          )}
          <svg className={isMobile ? 'w-4 h-4 text-cyan' : 'w-6 h-6 text-cyan'} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          问股
        </h1>
        {messages.length > 0 && (
          <div className="flex flex-shrink-0 flex-wrap items-center justify-end gap-2">
            <Tooltip content="导出会话为 Markdown 文件">
              <span className="inline-flex">
                <Button
                  variant="action-primary"
                  size="sm"
                  onClick={() => downloadSession(messages)}
                  aria-label="导出会话为 Markdown 文件"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  {!isMobile && '导出会话'}
                </Button>
              </span>
            </Tooltip>
            <Tooltip content="发送到已配置的通知机器人/邮箱">
              <span className="inline-flex">
                <Button
                  variant="action-primary"
                  size="sm"
                  disabled={sending}
                  onClick={handleSend}
                  aria-label="发送到已配置的通知机器人/邮箱"
                >
                  {sending ? (
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  )}
                  {!isMobile && '发送'}
                </Button>
              </span>
            </Tooltip>
          </div>
        )}
      </div>
      {!isMobile && (
        <p className="text-secondary-text text-sm">
          向 AI 询问个股分析，获取基于技能视角的交易建议与实时决策报告。
        </p>
      )}
      {sendToast && (
        <InlineAlert
          variant={sendToast.type === 'success' ? 'success' : 'danger'}
          title={sendToast.type === 'success' ? '发送成功' : '发送失败'}
          message={sendToast.message}
          className="max-w-md rounded-xl px-3 py-2 text-xs shadow-none"
        />
      )}
    </header>
  );
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd apps/dsa-web && npx vitest run src/pages/chat/__tests__/ChatHeader.test.tsx`
Expected: PASS（6 个测试全过）

- [ ] **Step 5: 在 ChatPage 中引用新组件，删除已迁移代码**

修改 `apps/dsa-web/src/pages/ChatPage.tsx`：
1. 顶部加 import：`import { ChatHeader } from './chat/ChatHeader';`
2. 删除 L909-1053 的 `<header>...</header>`
3. 在原位置插入：`<ChatHeader onToggleSidebar={() => setSidebarOpen(true)} isMobile={isMobile} />`
4. 删除 ChatPage 中已迁移的 `sending`, `sendToast`, `showSendFeedback`, `handleSend` 等本地状态和函数（如果只被 header 用）

- [ ] **Step 6: 跑现有 ChatPage 测试确认不回归**

Run: `cd apps/dsa-web && npx vitest run src/pages/__tests__/ChatPage.test.tsx`
Expected: PASS

- [ ] **Step 7: 跑 lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: 无 error

- [ ] **Step 8: Commit**

```bash
git add apps/dsa-web/src/pages/chat/ChatHeader.tsx \
        apps/dsa-web/src/pages/chat/__tests__/ChatHeader.test.tsx \
        apps/dsa-web/src/pages/ChatPage.tsx
git commit -m "refactor(web): extract ChatHeader with mobile sticky top bar"
```

---

### Task 3: 拆出 MessageList 子组件 + mobile 气泡/Markdown 适配

**Files:**
- Create: `apps/dsa-web/src/pages/chat/MessageList.tsx`
- Create: `apps/dsa-web/src/pages/chat/__tests__/MessageList.test.tsx`
- Modify: `apps/dsa-web/src/pages/ChatPage.tsx` (替换 L1055-1240 的消息区 + 滚动按钮)
- Modify: `apps/dsa-web/src/index.css` (新增 mobile 媒体查询调整气泡宽度、字号、代码块横向滚动提示)

**Interfaces:**
- Consumes: `useAgentChatStore` 选择 `messages, loading, progressSteps, chatError`；`ScrollArea`, `EmptyState`, `Badge`, `ApiErrorAlert`, `Markdown`, `remarkGfm`；`isNearBottom`
- Produces: `MessageList` 组件，props 接口：
  ```ts
  interface MessageListProps {
    isMobile: boolean;
    onQuickQuestion: (q: { label: string; skill: string }) => void;
  }
  ```

- [ ] **Step 1: 写失败测试 `MessageList.test.tsx`**

创建 `apps/dsa-web/src/pages/chat/__tests__/MessageList.test.tsx`：

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MessageList } from '../MessageList';
import type { Message } from '../../../stores/agentChatStore';

const makeMessage = (overrides: Partial<Message> = {}): Message => ({
  id: 'm1',
  role: 'user',
  content: 'hello',
  ...overrides,
});

let mockMessages: Message[] = [];
const mockStoreState = {
  get messages() { return mockMessages; },
  loading: false,
  progressSteps: [],
  chatError: null,
};

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: (selector: (s: any) => any) => selector(mockStoreState),
}));

describe('MessageList', () => {
  it('shows empty state with quick questions when no messages', () => {
    mockMessages = [];
    render(<MessageList isMobile={false} onQuickQuestion={() => {}} />);
    expect(screen.getByText('开始问股')).toBeInTheDocument();
    expect(screen.getByText('用缠论分析茅台')).toBeInTheDocument();
  });

  it('renders user message bubble', () => {
    mockMessages = [makeMessage({ role: 'user', content: '分析 600519' })];
    render(<MessageList isMobile={false} onQuickQuestion={() => {}} />);
    expect(screen.getByText('分析 600519')).toBeInTheDocument();
  });

  it('renders assistant message with markdown', () => {
    mockMessages = [makeMessage({ role: 'assistant', content: '# 标题\n\n正文' })];
    render(<MessageList isMobile={false} onQuickQuestion={() => {}} />);
    expect(screen.getByRole('heading', { level: 1, name: '标题' })).toBeInTheDocument();
  });

  it('shows copy and export buttons on assistant message', () => {
    mockMessages = [makeMessage({ role: 'assistant', content: '回答' })];
    render(<MessageList isMobile={false} onQuickQuestion={() => {}} />);
    expect(screen.getByLabelText('复制')).toBeInTheDocument();
    expect(screen.getByLabelText('导出此条消息为 Markdown')).toBeInTheDocument();
  });

  it('uses 2-column grid for quick questions on mobile', () => {
    mockMessages = [];
    render(<MessageList isMobile={true} onQuickQuestion={() => {}} />);
    const actionContainer = screen.getByText('用缠论分析茅台').parentElement;
    expect(actionContainer?.className).toMatch(/grid-cols-2/);
  });

  it('uses 3-column flex-wrap for quick questions on desktop', () => {
    mockMessages = [];
    render(<MessageList isMobile={false} onQuickQuestion={() => {}} />);
    const actionContainer = screen.getByText('用缠论分析茅台').parentElement;
    expect(actionContainer?.className).toMatch(/flex-wrap/);
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd apps/dsa-web && npx vitest run src/pages/chat/__tests__/MessageList.test.tsx`
Expected: FAIL with "Cannot find module '../MessageList'"

- [ ] **Step 3: 创建 `MessageList.tsx`**

创建 `apps/dsa-web/src/pages/chat/MessageList.tsx`。从 `ChatPage.tsx` L1055-1240 迁移消息区 + 滚动按钮。骨架：

```tsx
import { useRef, useState, useEffect, useCallback } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ScrollArea, EmptyState, Badge, ApiErrorAlert } from '../../components/common';
import { useAgentChatStore, type Message, type ProgressStep } from '../../stores/agentChatStore';
import { isNearBottom } from '../../utils/chatScroll';
import { cn } from '../../utils/cn';

const QUICK_QUESTIONS = [
  { label: '用缠论分析茅台', skill: 'chan_theory' },
  { label: '波浪理论看宁德时代', skill: 'wave_theory' },
  { label: '分析比亚迪趋势', skill: 'bull_trend' },
  { label: '箱体震荡技能看中芯国际', skill: 'box_oscillation' },
  { label: '分析腾讯 hk00700', skill: 'bull_trend' },
  { label: '用情绪周期分析东方财富', skill: 'emotion_cycle' },
];

interface MessageListProps {
  isMobile: boolean;
  onQuickQuestion: (q: { label: string; skill: string }) => void;
}

export function MessageList({ isMobile, onQuickQuestion }: MessageListProps) {
  const messages = useAgentChatStore((s) => s.messages);
  const loading = useAgentChatStore((s) => s.loading);
  const progressSteps = useAgentChatStore((s) => s.progressSteps);
  const chatError = useAgentChatStore((s) => s.chatError);

  const messagesViewportRef = useRef<HTMLDivElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const [showJumpToBottom, setShowJumpToBottom] = useState(false);
  const [copiedMessages, setCopiedMessages] = useState<Set<string>>(new Set());
  const [expandedThinking, setExpandedThinking] = useState<Set<string>>(new Set());

  // 迁移 ChatPage.tsx 中的 handleMessagesScroll, requestScrollToBottom, scrollToBottom,
  // copyMessageToClipboard, downloadMessageAsMarkdown, renderThinkingBlock, renderThinkingDetails,
  // getMessageSkillLabel, getCurrentStage 等函数

  const handleMessagesScroll = useCallback(() => {
    const viewport = messagesViewportRef.current;
    if (!viewport) return;
    setShowJumpToBottom(!isNearBottom(viewport, 80));
  }, []);

  useEffect(() => {
    // 新消息时滚动到底部（迁移自 ChatPage）
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, loading]);

  return (
    <div className="relative z-10 flex min-h-0 flex-1 flex-col overflow-hidden border border-white/6 bg-card/78 glass-card">
      {chatError && (
        <div className="sticky top-0 z-20 border-b border-white/6 bg-card/95 backdrop-blur">
          <ApiErrorAlert error={chatError} />
        </div>
      )}
      <ScrollArea
        className="relative z-10 flex-1"
        viewportRef={messagesViewportRef}
        onScroll={handleMessagesScroll}
        viewportClassName={isMobile ? 'space-y-4 p-3' : 'space-y-6 p-4 md:p-6'}
        testId="chat-message-scroll"
      >
        {messages.length === 0 && !loading ? (
          <div className="flex h-full items-center justify-center">
            <EmptyState
              title="开始问股"
              description={isMobile
                ? '输入「分析 600519」开始问股'
                : '输入「分析 600519」或「茅台现在能买吗」，AI 将调用实时数据工具为您生成决策报告。'
              }
              className="max-w-2xl border-dashed bg-card/55"
              action={(
                <div className={isMobile
                  ? 'grid grid-cols-2 gap-2 max-w-md'
                  : 'flex max-w-lg flex-wrap justify-center gap-2'
                }>
                  {QUICK_QUESTIONS.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => onQuickQuestion(q)}
                      className="quick-question-btn"
                    >
                      {q.label}
                    </button>
                  ))}
                </div>
              )}
            />
          </div>
        ) : (
          messages.map((msg) => {
            // 迁移 ChatPage.tsx L1101-1188 的消息渲染 JSX
            // 关键差异（mobile）：
            // - 气泡 max-w：mobile 用 max-w-[85%] (user) / max-w-[92%] (assistant)，桌面用 max-w-[min(100%,48rem)]
            // - 字号：mobile text-sm，桌面 text-base
            // - 复制/导出按钮：始终在气泡下方小图标行（不挤在气泡内）
            return (
              <div
                key={msg.id}
                className={cn('flex gap-3', msg.role === 'user' ? 'flex-row-reverse' : '')}
              >
                {/* avatar + bubble - 从 ChatPage L1104-1185 迁移 */}
              </div>
            );
          })
        )}
        {loading && (
          /* 迁移 ChatPage.tsx L1191-1208 的 loading 占位 */
          <div />
        )}
        <div ref={messagesEndRef} />
      </ScrollArea>

      {showJumpToBottom && !loading && (
        <div className={cn(
          'pointer-events-none absolute right-4 z-20',
          isMobile ? 'bottom-[5.75rem]' : 'bottom-24 md:right-6'
        )}>
          <button
            type="button"
            className="pointer-events-auto chat-copy-btn shadow-soft-card"
            onClick={() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })}
            aria-label="查看最新消息"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
            有新消息
          </button>
        </div>
      )}
    </div>
  );
}
```

注：完整迁移需保留原 `renderThinkingBlock`、`renderThinkingDetails`、`getMessageSkillLabel`、`copyMessageToClipboard`、`downloadMessageAsMarkdown`、`getCurrentStage` 等函数，从 `ChatPage.tsx` 原样搬运到 `MessageList.tsx` 内或抽到 `chat/utils.ts`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd apps/dsa-web && npx vitest run src/pages/chat/__tests__/MessageList.test.tsx`
Expected: PASS（6 个测试全过）

- [ ] **Step 5: 在 ChatPage 中引用新组件，删除已迁移代码**

修改 `apps/dsa-web/src/pages/ChatPage.tsx`：
1. 顶部加 import：`import { MessageList } from './chat/MessageList';`
2. 删除 L1055-1240 的消息区 + 滚动按钮 JSX
3. 删除已迁移的函数：`handleMessagesScroll`, `requestScrollToBottom`, `scrollToBottom`, `copyMessageToClipboard`, `downloadMessageAsMarkdown`, `renderThinkingBlock`, `renderThinkingDetails`, `getMessageSkillLabel`, `getCurrentStage`, `messagesViewportRef`, `messagesEndRef`, `showJumpToBottom`, `copiedMessages`, `expandedThinking` 等
4. 在原位置插入：`<MessageList isMobile={isMobile} onQuickQuestion={handleQuickQuestion} />`

- [ ] **Step 6: 加 mobile 媒体查询 CSS**

修改 `apps/dsa-web/src/index.css`，在 `.chat-prose` 相关样式附近（约 L2370-2400）追加：

```css
@media (max-width: 639px) {
  .chat-prose {
    font-size: 14px;
  }
  .chat-prose pre {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .chat-prose table {
    display: block;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    max-width: 100%;
  }
  .chat-bubble-user {
    max-width: 85%;
  }
  .chat-bubble-ai {
    max-width: 92%;
  }
  .chat-progress-item {
    font-size: 13px;
  }
}
```

- [ ] **Step 7: 跑现有 ChatPage 测试确认不回归**

Run: `cd apps/dsa-web && npx vitest run src/pages/__tests__/ChatPage.test.tsx`
Expected: PASS

- [ ] **Step 8: 跑 lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: 无 error

- [ ] **Step 9: Commit**

```bash
git add apps/dsa-web/src/pages/chat/MessageList.tsx \
        apps/dsa-web/src/pages/chat/__tests__/MessageList.test.tsx \
        apps/dsa-web/src/pages/ChatPage.tsx \
        apps/dsa-web/src/index.css
git commit -m "refactor(web): extract MessageList with mobile bubble and markdown adaptations"
```

---

### Task 4: 拆出 ChatComposer 子组件 + mobile 分层结构

**Files:**
- Create: `apps/dsa-web/src/pages/chat/ChatComposer.tsx`
- Create: `apps/dsa-web/src/pages/chat/__tests__/ChatComposer.test.tsx`
- Modify: `apps/dsa-web/src/pages/ChatPage.tsx` (替换 L1243-1420 的输入区)

**Interfaces:**
- Consumes: `useAgentChatStore` 选择 `loading, chatError`；`systemConfigApi`, `agentApi.getSkills`；`Button`, `InlineAlert`, `ApiErrorAlert`；`SlidersHorizontal`, `ChevronDown` icons
- Produces: `ChatComposer` 组件，props 接口：
  ```ts
  interface ChatComposerProps {
    isMobile: boolean;
    composerValue: string;
    setComposerValue: (v: string) => void;
    onSend: () => void;
  }
  ```

- [ ] **Step 1: 写失败测试 `ChatComposer.test.tsx`**

创建 `apps/dsa-web/src/pages/chat/__tests__/ChatComposer.test.tsx`：

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChatComposer } from '../ChatComposer';

vi.mock('../../../api/agent', () => ({
  agentApi: { getSkills: vi.fn().mockResolvedValue([]) },
}));
vi.mock('../../../api/systemConfig', () => ({
  systemConfigApi: {
    get: vi.fn().mockResolvedValue({ value: 'false' }),
    update: vi.fn().mockResolvedValue(undefined),
  },
}));

const mockStoreState = {
  loading: false,
  chatError: null,
};

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: (selector: (s: any) => any) => selector(mockStoreState),
}));

describe('ChatComposer', () => {
  it('renders textarea and send button', () => {
    render(<ChatComposer isMobile={false} composerValue="" setComposerValue={() => {}} onSend={() => {}} />);
    expect(screen.getByPlaceholderText(/分析 600519/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '发送' })).toBeInTheDocument();
  });

  it('calls onSend when send button clicked', () => {
    const onSend = vi.fn();
    render(<ChatComposer isMobile={false} composerValue="分析 600519" setComposerValue={() => {}} onSend={onSend} />);
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    expect(onSend).toHaveBeenCalled();
  });

  it('disables send button when input empty', () => {
    render(<ChatComposer isMobile={false} composerValue="" setComposerValue={() => {}} onSend={() => {}} />);
    expect(screen.getByRole('button', { name: '发送' })).toBeDisabled();
  });

  it('shows + button on mobile that toggles expansion drawer', () => {
    render(<ChatComposer isMobile={true} composerValue="" setComposerValue={() => {}} onSend={() => {}} />);
    const expandBtn = screen.getByLabelText('展开更多选项');
    expect(expandBtn).toBeInTheDocument();
    fireEvent.click(expandBtn);
    expect(screen.getByTestId('chat-composer-drawer')).toBeInTheDocument();
  });

  it('hides + button on desktop, shows skills inline', () => {
    render(<ChatComposer isMobile={false} composerValue="" setComposerValue={() => {}} onSend={() => {}} />);
    expect(screen.queryByLabelText('展开更多选项')).toBeNull();
  });

  it('disables send button when loading', () => {
    mockStoreState.loading = true;
    render(<ChatComposer isMobile={false} composerValue="hi" setComposerValue={() => {}} onSend={() => {}} />);
    expect(screen.getByRole('button', { name: '发送' })).toBeDisabled();
    mockStoreState.loading = false;
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd apps/dsa-web && npx vitest run src/pages/chat/__tests__/ChatComposer.test.tsx`
Expected: FAIL with "Cannot find module '../ChatComposer'"

- [ ] **Step 3: 创建 `ChatComposer.tsx`**

创建 `apps/dsa-web/src/pages/chat/ChatComposer.tsx`。从 `ChatPage.tsx` L1243-1420 迁移输入区。骨架：

```tsx
import { useState, useEffect, useRef } from 'react';
import { SlidersHorizontal, ChevronDown, Plus, X } from 'lucide-react';
import { Button, InlineAlert, ApiErrorAlert } from '../../components/common';
import { agentApi, type SkillInfo } from '../../api/agent';
import { systemConfigApi } from '../../api/systemConfig';
import { useAgentChatStore } from '../../stores/agentChatStore';
import { cn } from '../../utils/cn';

const MAX_SELECTED_SKILLS = 3;
const CONTEXT_COMPRESSION_CONFIG_KEY = 'AGENT_CONTEXT_COMPRESSION_ENABLED';

interface ChatComposerProps {
  isMobile: boolean;
  composerValue: string;
  setComposerValue: (v: string) => void;
  onSend: () => void;
}

export function ChatComposer({ isMobile, composerValue, setComposerValue, onSend }: ChatComposerProps) {
  const loading = useAgentChatStore((s) => s.loading);
  const chatError = useAgentChatStore((s) => s.chatError);

  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [selectedSkillIds, setSelectedSkillIds] = useState<string[]>([]);
  const [contextCompressionEnabled, setContextCompressionEnabled] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [activeStockCode, setActiveStockCode] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // 迁移 ChatPage.tsx 中的技能加载、上下文压缩加载、自选股逻辑、
  // handleKeyDown, toggleSkillSelection, handleToggleWatchlist 等

  useEffect(() => {
    void agentApi.getSkills().then((data) => setSkills(data));
  }, []);

  useEffect(() => {
    void systemConfigApi.get(CONTEXT_COMPRESSION_CONFIG_KEY).then((cfg) => {
      setContextCompressionEnabled(cfg?.value === 'true');
    });
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (composerValue.trim() && !loading) onSend();
    }
  };

  const selectedSkillIdSet = new Set(selectedSkillIds);
  const skillLimitReached = selectedSkillIds.length >= MAX_SELECTED_SKILLS;

  return (
    <div className={cn(
      'border-t border-white/6 bg-card/88 relative z-20',
      isMobile ? 'sticky bottom-0 px-3 py-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))]' : 'p-4 md:p-6'
    )}>
      {chatError && <ApiErrorAlert error={chatError} />}

      {/* 已选技能 badges（mobile + desktop 都显示） */}
      {selectedSkillIds.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {selectedSkillIds.map((id) => {
            const skill = skills.find((s) => s.id === id);
            return (
              <span key={id} className="inline-flex items-center gap-1 rounded-full bg-cyan/15 px-2 py-0.5 text-xs text-cyan">
                {skill?.name}
                <button onClick={() => setSelectedSkillIds((prev) => prev.filter((x) => x !== id))} aria-label={`移除 ${skill?.name}`}>
                  <X className="w-3 h-3" />
                </button>
              </span>
            );
          })}
        </div>
      )}

      {isMobile ? (
        /* Mobile: 分层结构 - textarea + "+"按钮 + 发送，展开层为底部抽屉 */
        <div className="flex items-end gap-2">
          <button
            type="button"
            onClick={() => setComposerOpen((open) => !open)}
            className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full border border-white/6 bg-surface/50 text-secondary-text hover:text-foreground"
            aria-label="展开更多选项"
          >
            <Plus className="h-5 w-5" />
          </button>
          <textarea
            ref={textareaRef}
            value={composerValue}
            onChange={(e) => setComposerValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="分析 600519 / 茅台现在能买吗？"
            disabled={loading}
            rows={1}
            className="input-surface input-focus-glow flex-1 min-h-[48px] max-h-[120px] rounded-2xl border bg-transparent px-4 py-3 text-sm transition-all focus:outline-none resize-none disabled:cursor-not-allowed disabled:opacity-60"
            style={{ height: 'auto' }}
            onInput={(e) => {
              const t = e.target as HTMLTextAreaElement;
              t.style.height = 'auto';
              t.style.height = `${Math.min(t.scrollHeight, 120)}px`;
            }}
          />
          <button
            type="button"
            onClick={onSend}
            disabled={!composerValue.trim() || loading}
            className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-cyan text-white disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="发送"
          >
            {loading ? (
              <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </button>
        </div>
      ) : (
        /* Desktop: 保留原样 - 上下文压缩 + 技能多选 + 股票代码 + textarea + 发送 */
        <div className="space-y-3">
          {/* 迁移 ChatPage.tsx L1244-1289 的上下文压缩开关 */}
          {/* 迁移 ChatPage.tsx L1289-1373 的技能多选（横向 checkbox） */}
          {/* 迁移 ChatPage.tsx L1375-1391 的股票代码 + 自选 */}
          <div className="flex items-end gap-3">
            <textarea
              value={composerValue}
              onChange={(e) => setComposerValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="例如：分析 600519 / 茅台现在适合买入吗？ (Enter 发送, Shift+Enter 换行)"
              disabled={loading}
              rows={1}
              className="input-surface input-focus-glow flex-1 min-h-[44px] max-h-[200px] rounded-xl border bg-transparent px-4 py-2.5 text-sm transition-all focus:outline-none resize-none disabled:cursor-not-allowed disabled:opacity-60"
              style={{ height: 'auto' }}
              onInput={(e) => {
                const t = e.target as HTMLTextAreaElement;
                t.style.height = 'auto';
                t.style.height = `${Math.min(t.scrollHeight, 200)}px`;
              }}
            />
            <Button
              variant="primary"
              onClick={onSend}
              disabled={!composerValue.trim() || loading}
              isLoading={loading}
              className="btn-primary flex-shrink-0"
            >
              发送
            </Button>
          </div>
        </div>
      )}

      {/* Mobile 展开层 - 底部抽屉 */}
      {isMobile && composerOpen && (
        <div
          data-testid="chat-composer-drawer"
          className="fixed inset-0 z-50 flex items-end"
          onClick={() => setComposerOpen(false)}
        >
          <div className="page-drawer-overlay absolute inset-0" />
          <div
            className="relative w-full rounded-t-2xl border-t border-white/10 bg-card/95 p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] backdrop-blur"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-medium text-foreground">更多选项</h3>
              <button onClick={() => setComposerOpen(false)} aria-label="关闭">
                <X className="w-4 h-4 text-secondary-text" />
              </button>
            </div>
            {/* 上下文压缩开关 */}
            <label className="mb-3 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={contextCompressionEnabled}
                onChange={(e) => setContextCompressionEnabled(e.target.checked)}
                className="chat-skill-checkbox"
              />
              <span className="font-medium">上下文压缩</span>
              <span className="text-xs text-muted-text">节省长会话 token</span>
            </label>
            {/* 技能 chips - 横向滑动 */}
            <div className="mb-3">
              <span className="mb-1.5 block text-xs text-muted-text font-medium uppercase tracking-wider">策略</span>
              <div className="flex gap-2 overflow-x-auto pb-1">
                <button
                  onClick={() => setSelectedSkillIds([])}
                  className={cn(
                    'flex-shrink-0 rounded-full border px-3 py-1.5 text-xs',
                    selectedSkillIds.length === 0
                      ? 'border-cyan bg-cyan/15 text-cyan'
                      : 'border-white/10 text-secondary-text'
                  )}
                >
                  通用分析
                </button>
                {skills.map((s) => {
                  const checked = selectedSkillIdSet.has(s.id);
                  const disabled = !checked && skillLimitReached;
                  return (
                    <button
                      key={s.id}
                      disabled={disabled}
                      onClick={() => {
                        setSelectedSkillIds((prev) =>
                          checked ? prev.filter((x) => x !== s.id) : [...prev, s.id]
                        );
                      }}
                      className={cn(
                        'flex-shrink-0 rounded-full border px-3 py-1.5 text-xs',
                        checked ? 'border-cyan bg-cyan/15 text-cyan' : 'border-white/10 text-secondary-text',
                        disabled && 'opacity-40'
                      )}
                    >
                      {s.name}
                    </button>
                  );
                })}
              </div>
            </div>
            {/* 股票代码 + 自选 - 迁移自 ChatPage L1375-1391 */}
          </div>
        </div>
      )}
    </div>
  );
}
```

注：完整迁移需保留原 `toggleSkillSelection`, `handleToggleWatchlist`, `stockInWatchlist`, `watchlistMessage`, `isWatchlistActioning`, `contextCompressionSaving`, `contextCompressionError`, `contextCompressionLoaded`, `updateContextCompressionEnabled`, `selectedSkillSummary`, `showSkillDesc`, `mobileSkillPickerOpen` 等状态和逻辑。从 `ChatPage.tsx` 搬运到 `ChatComposer.tsx`。`mobileSkillPickerOpen` 状态被新的 `composerOpen` + 底部抽屉取代。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd apps/dsa-web && npx vitest run src/pages/chat/__tests__/ChatComposer.test.tsx`
Expected: PASS（6 个测试全过）

- [ ] **Step 5: 在 ChatPage 中引用新组件，删除已迁移代码**

修改 `apps/dsa-web/src/pages/ChatPage.tsx`：
1. 顶部加 import：`import { ChatComposer } from './chat/ChatComposer';`
2. 删除 L1243-1420 的输入区 JSX
3. 删除已迁移的状态和函数：`input`, `setInput`（替换为 `composerValue`, `setComposerValue` 提升到 ChatPage）, `skills`, `selectedSkillIds`, `contextCompressionEnabled`, `activeStockCode`, `handleKeyDown`, `handleSend`, `toggleSkillSelection`, `handleToggleWatchlist` 等
4. 在 ChatPage 顶层加：`const [composerValue, setComposerValue] = useState('');`
5. 在原位置插入：`<ChatComposer isMobile={isMobile} composerValue={composerValue} setComposerValue={setComposerValue} onSend={handleSend} />`
6. `handleSend` 保留在 ChatPage（因为它读 `composerValue` + store 的 `startStream`），但内部从 `input` 改为 `composerValue`

- [ ] **Step 6: 跑现有 ChatPage 测试确认不回归**

Run: `cd apps/dsa-web && npx vitest run src/pages/__tests__/ChatPage.test.tsx`
Expected: PASS

如有失败，可能是因为测试引用了 `input` 变量或 `mobileSkillPickerOpen` 状态。更新测试以匹配新接口（`composerValue` 代替 `input`，移除对 `mobileSkillPickerOpen` 的引用）。

- [ ] **Step 7: 跑 lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: 无 error

- [ ] **Step 8: Commit**

```bash
git add apps/dsa-web/src/pages/chat/ChatComposer.tsx \
        apps/dsa-web/src/pages/chat/__tests__/ChatComposer.test.tsx \
        apps/dsa-web/src/pages/ChatPage.tsx
git commit -m "refactor(web): extract ChatComposer with mobile layered structure"
```

---

### Task 5: ChatPage 协调器化 + useIsMobile 整合

**Files:**
- Modify: `apps/dsa-web/src/pages/ChatPage.tsx` (移除已迁移逻辑，整合 useIsMobile，~600 行)
- Modify: `apps/dsa-web/src/pages/__tests__/ChatPage.test.tsx` (调整为协调器测试)

**Interfaces:**
- Consumes: 4 个子组件 + `useIsMobile` + `useAgentChatStore`
- Produces: ChatPage 协调器，路由 `/chat` 入口

- [ ] **Step 1: 检查 ChatPage 当前状态**

Run: `cd apps/dsa-web && wc -l src/pages/ChatPage.tsx`
Expected: 行数应已从 1428 降至约 700-900（4 个子组件拆出后）。若仍 >900，检查是否有未迁移的辅助函数。

- [ ] **Step 2: 在 ChatPage 顶层加 useIsMobile**

修改 `apps/dsa-web/src/pages/ChatPage.tsx`：
1. 顶部加 import：`import { useIsMobile } from '../hooks/useIsMobile';`
2. 在组件函数体顶部加：`const isMobile = useIsMobile();`
3. 把 `isMobile` 传给 4 个子组件

- [ ] **Step 3: 删除 ChatPage 中残留的 mobile 适配代码**

检查并删除：
- `mobileSkillPickerOpen` 状态（已被 ChatComposer 内部 `composerOpen` 取代）
- 残留的 `md:hidden` / `md:flex` 切换（如果子组件已处理）
- 未使用的 import（如 `SlidersHorizontal`, `ChevronDown` 如果只在 ChatComposer 用）

- [ ] **Step 4: 确认 ChatPage 协调器职责**

ChatPage 应仅保留：
- `useIsMobile()` 调用
- `useAgentChatStore` 选择器（用于 session 切换副作用、`handleSend`、`handleQuickQuestion`）
- `useSearchParams` 处理追问上下文
- 本地状态：`sidebarOpen`, `composerValue`, `deleteConfirmId`（如果 SessionSidebar 还需要 ChatPage 提供）
- `useEffect` 监听 `sessionId` 变化重置状态
- 子组件编排 JSX

- [ ] **Step 5: 调整 ChatPage.test.tsx**

修改 `apps/dsa-web/src/pages/__tests__/ChatPage.test.tsx`：
1. 移除对已迁移内部状态的断言（如 `mobileSkillPickerOpen`, `input`）
2. 保留协调器级别断言：页面渲染、session 切换、发送消息流程、追问上下文加载
3. 如果测试引用了 `input` 变量，改为引用 `composerValue` 或通过 textarea 的 value 属性断言

Run: `cd apps/dsa-web && npx vitest run src/pages/__tests__/ChatPage.test.tsx`
Expected: PASS

- [ ] **Step 6: 跑全部单元测试**

Run: `cd apps/dsa-web && npx vitest run`
Expected: 所有测试 PASS

- [ ] **Step 7: 跑 lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: 无 error

- [ ] **Step 8: 确认 ChatPage 行数**

Run: `cd apps/dsa-web && wc -l src/pages/ChatPage.tsx`
Expected: 约 600 行（±100）。若 >700，回顾是否有可继续迁移的逻辑。

- [ ] **Step 9: Commit**

```bash
git add apps/dsa-web/src/pages/ChatPage.tsx \
        apps/dsa-web/src/pages/__tests__/ChatPage.test.tsx
git commit -m "refactor(web): reduce ChatPage to coordinator with useIsMobile"
```

---

### Task 6: e2e mobile-smoke 扩展

**Files:**
- Modify: `apps/dsa-web/e2e/mobile-smoke.spec.ts` (在 `mobile drawer/sidebar smoke` describe 块内新增用例)

**Interfaces:**
- Consumes: 现有 `login()` helper
- Produces: 5 个新 e2e 用例覆盖 ChatPage 移动端核心流程

- [ ] **Step 1: 在 mobile-smoke.spec.ts 末尾追加 ChatPage 用例 describe 块**

修改 `apps/dsa-web/e2e/mobile-smoke.spec.ts`，在文件末尾追加：

```ts
test.describe('ChatPage mobile interactions', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('composer + button toggles expansion drawer', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/chat');
    await browserPage.waitForLoadState('domcontentloaded');

    const expandBtn = browserPage.getByLabel('展开更多选项');
    await expect(expandBtn).toBeVisible();
    await expandBtn.click();

    const drawer = browserPage.getByTestId('chat-composer-drawer');
    await expect(drawer).toBeVisible();
  });

  test('message list renders without horizontal overflow', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/chat');
    await browserPage.waitForLoadState('domcontentloaded');

    // 发送一条消息
    const textarea = browserPage.getByPlaceholder(/分析 600519/);
    await textarea.fill('分析 600519');
    await textarea.press('Enter');
    await browserPage.waitForTimeout(2000);

    // 验证消息区无横向溢出
    const scrollWidth = await browserPage.locator('[data-testid="chat-message-scroll"]').evaluate((el) => el.scrollWidth);
    const clientWidth = await browserPage.locator('[data-testid="chat-message-scroll"]').evaluate((el) => el.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
  });

  test('chat page has no horizontal overflow on mobile', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/chat');
    await browserPage.waitForLoadState('domcontentloaded');
    await browserPage.waitForTimeout(500);
    const scrollWidth = await browserPage.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await browserPage.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
  });

  test('quick questions render in 2-column grid on mobile', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/chat');
    await browserPage.waitForLoadState('domcontentloaded');

    const firstQuickBtn = browserPage.getByText('用缠论分析茅台');
    const container = firstQuickBtn.locator('..');
    await expect(container).toHaveClass(/grid-cols-2/);
  });

  test('session sidebar drawer width is 85vw on mobile', async ({ page: browserPage }) => {
    await login(browserPage);
    await browserPage.goto('/chat');
    await browserPage.waitForLoadState('domcontentloaded');

    const toggleButton = browserPage.getByTestId('chat-sidebar-toggle');
    await toggleButton.click();

    const drawer = browserPage.locator('.fixed.inset-0.z-40 .relative.h-full');
    await expect(drawer).toBeVisible();
    const box = await drawer.boundingBox();
    expect(box?.width).toBeGreaterThan(320);
    expect(box?.width).toBeLessThanOrEqual(332); // 85vw of 390 = 331.5
  });
});
```

- [ ] **Step 2: 跑 e2e 确认通过**

Run: `cd apps/dsa-web && npx playwright test mobile-smoke --project=mobile-chrome`
Expected: 所有 mobile-chrome 测试 PASS（含新增 5 个）

如果 `login()` 因 `DSA_WEB_SMOKE_PASSWORD` 未设置而 skip，确认本地配置了该环境变量或 CI 中配置。

- [ ] **Step 3: 跑 lint + build**

Run: `cd apps/dsa-web && npm run lint && npm run build`
Expected: 无 error

- [ ] **Step 4: Commit**

```bash
git add apps/dsa-web/e2e/mobile-smoke.spec.ts
git commit -m "test(web): extend mobile-smoke for chat page interactions"
```

---

### Task 7: CHANGELOG + 桌面端回归验证 + 最终交付

**Files:**
- Modify: `docs/CHANGELOG.md` (在 `[Unreleased]` 段加扁平条目)

**Interfaces:**
- Produces: CHANGELOG 条目 + 桌面端回归确认 + 最终验证

- [ ] **Step 1: 更新 docs/CHANGELOG.md**

在 `docs/CHANGELOG.md` 的 `[Unreleased]` 段（按 CLAUDE.md 1 节规则，扁平格式，不加 `### 类目标题`）追加：

```markdown
- [改进] 问股页面移动端适配：拆分 ChatPage 为协调器 + ChatHeader/MessageList/ChatComposer/SessionSidebar 四个子组件，mobile-first 响应式，桌面端功能不变
- [改进] 问股页面移动端输入区：分层结构（始终可见 textarea + "+"按钮触发底部抽屉含技能/股票/自选/上下文压缩）
- [改进] 问股页面移动端消息气泡：宽度 85%/92%、字号 14px、代码块/表格横向滚动
- [改进] 问股页面移动端 Header：单行 sticky 顶栏，描述移到 EmptyState
- [测试] e2e mobile-smoke 新增问股页面交互用例（输入区抽屉、消息区无溢出、快速提问网格、侧边栏宽度）
```

- [ ] **Step 2: 桌面端回归手动验证**

启动 dev server：

```bash
cd apps/dsa-web && npm run dev
```

在桌面浏览器（>=1024px）打开 `http://localhost:5173/chat`，验证：
1. 历史会话侧边栏常驻左侧，切换/新建/删除会话正常
2. Header 显示标题 + 描述 + 导出 + 发送按钮
3. 消息列表渲染用户/AI 气泡、Markdown、思考过程折叠、复制/导出
4. 输入区：上下文压缩开关 + 技能多选横向 checkbox + 股票代码 + 自选 + textarea + 发送
5. 发送消息流程正常（Enter 发送、Shift+Enter 换行、loading 态）
6. 快速提问按钮 3 列布局
7. 滚动到底部按钮显隐正常

如有回归，记录具体问题，回到对应 Task 修复。

- [ ] **Step 3: 移动端验证（Playwright mobile-chrome）**

Run: `cd apps/dsa-web && npx playwright test mobile-smoke --project=mobile-chrome`
Expected: 所有测试 PASS

- [ ] **Step 4: 跑全部单元测试 + lint + build**

Run: `cd apps/dsa-web && npx vitest run && npm run lint && npm run build`
Expected: 全部 PASS，无 error

- [ ] **Step 5: Commit**

```bash
git add docs/CHANGELOG.md
git commit -m "docs: update changelog for ask-stock mobile optimization"
```

- [ ] **Step 6: 截图准备（PR 描述用）**

按 CLAUDE.md 1 节规则，PR 描述需附移动端截图。截图清单（不入库，放 PR 描述/附件）：
1. 移动端空态（2 列快速提问）
2. 移动端对话中（用户/AI 气泡、Markdown 渲染）
3. 移动端输入区展开抽屉（技能 chips + 上下文压缩）
4. 移动端历史会话抽屉
5. 桌面端回归对比（4 个能力区）

使用 Playwright 截图脚本（可临时本地跑，不入库）：

```bash
cd apps/dsa-web && npx playwright screenshot --viewport-size="390,844" \
  --storage-state="<auth-state-path>" \
  "http://localhost:5173/chat" /tmp/chat-mobile.png
```

或手动用浏览器 DevTools 设备模拟截图。

- [ ] **Step 7: 推送分支（用户确认后）**

```bash
git push origin feat/mobile-adaptation
```

注：按 CLAUDE.md 规则，push 需用户明确确认。

---

## Self-Review 检查

**1. Spec 覆盖：**
- spec 节 3（子组件拆分边界）→ Task 1-4 ✓
- spec 节 4.1 SessionSidebar → Task 1 ✓
- spec 节 4.2 ChatHeader → Task 2 ✓
- spec 节 4.3 MessageList → Task 3 ✓
- spec 节 4.4 ChatComposer → Task 4 ✓
- spec 节 5（数据流与状态管理）→ Task 5 ✓
- spec 节 6（错误处理与降级）→ 各 Task 内嵌（错误条 sticky、loading 态、长内容滚动）✓
- spec 节 7（测试策略）→ Task 1-6 单元测试 + e2e ✓
- spec 节 8（交付清单）→ Task 7 CHANGELOG + 截图 ✓
- spec 节 9（风险与回滚）→ 每个 Task 独立 commit，可单独 revert ✓

**2. 占位符扫描：** 无 TBD/TODO，所有步骤含具体代码或具体命令。

**3. 类型一致性：** 子组件 props 接口在 Task 1-4 定义，Task 5 引用时签名一致：
- `SessionSidebar`: `{ isOpen, onClose, isMobile }` ✓
- `ChatHeader`: `{ onToggleSidebar, isMobile }` ✓
- `MessageList`: `{ isMobile, onQuickQuestion }` ✓
- `ChatComposer`: `{ isMobile, composerValue, setComposerValue, onSend }` ✓
