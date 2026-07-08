import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MessageList } from '../MessageList';
import type { Message, ProgressStep } from '../../../stores/agentChatStore';

const makeMessage = (overrides: Partial<Message> = {}): Message => ({
  id: 'm1',
  role: 'user',
  content: 'hello',
  ...overrides,
});

let mockMessages: Message[] = [];
let mockLoading = false;
let mockProgressSteps: ProgressStep[] = [];
const mockChatError: { message: string } | null = null;

const mockStoreState = {
  get messages() { return mockMessages; },
  get loading() { return mockLoading; },
  get progressSteps() { return mockProgressSteps; },
  get chatError() { return mockChatError; },
};

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: (selector: (s: typeof mockStoreState) => unknown) =>
    selector(mockStoreState),
}));

const noopRef = { current: null };
const quickQuestions = [
  { label: '用缠论分析茅台', skill: 'chan_theory' },
  { label: '波浪理论看宁德时代', skill: 'wave_theory' },
];

function renderMessageList(isMobile: boolean) {
  return render(
    <MessageList
      isMobile={isMobile}
      quickQuestions={quickQuestions}
      onQuickQuestion={() => {}}
      messagesViewportRef={noopRef as never}
      messagesEndRef={noopRef as never}
      onScroll={() => {}}
      showJumpToBottom={false}
      onJumpToBottom={() => {}}
    />,
  );
}

describe('MessageList', () => {
  it('shows empty state with quick questions when no messages', () => {
    mockMessages = [];
    mockLoading = false;
    renderMessageList(false);
    expect(screen.getByText('开始问股')).toBeInTheDocument();
    expect(screen.getByText('用缠论分析茅台')).toBeInTheDocument();
  });

  it('renders user message bubble', () => {
    mockMessages = [makeMessage({ role: 'user', content: '分析 600519' })];
    renderMessageList(false);
    expect(screen.getByText('分析 600519')).toBeInTheDocument();
  });

  it('renders assistant message with markdown', () => {
    mockMessages = [makeMessage({ role: 'assistant', content: '# 标题\n\n正文' })];
    renderMessageList(false);
    expect(screen.getByRole('heading', { level: 1, name: '标题' })).toBeInTheDocument();
  });

  it('shows copy and export buttons on assistant message', () => {
    mockMessages = [makeMessage({ role: 'assistant', content: '回答' })];
    renderMessageList(false);
    expect(screen.getByText('复制')).toBeInTheDocument();
    expect(screen.getByLabelText('导出此条消息为 Markdown')).toBeInTheDocument();
  });

  it('uses 2-column grid for quick questions on mobile', () => {
    mockMessages = [];
    const { container } = renderMessageList(true);
    const grid = container.querySelector('.grid-cols-2');
    expect(grid).toBeInTheDocument();
  });

  it('uses flex-wrap for quick questions on desktop', () => {
    mockMessages = [];
    const { container } = renderMessageList(false);
    const flexWrap = container.querySelector('.flex-wrap');
    expect(flexWrap).toBeInTheDocument();
  });

  it('shows loading indicator with current stage', () => {
    mockMessages = [];
    mockLoading = true;
    mockProgressSteps = [{ type: 'thinking', message: '正在思考...' }];
    renderMessageList(false);
    expect(screen.getByText('正在思考...')).toBeInTheDocument();
    mockLoading = false;
    mockProgressSteps = [];
  });
});
