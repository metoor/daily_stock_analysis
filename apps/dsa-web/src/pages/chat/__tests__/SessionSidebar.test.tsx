import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SessionSidebar } from '../SessionSidebar';
import type { ChatSessionItem } from '../../../api/agent';

const mockSessions: ChatSessionItem[] = [
  {
    session_id: 's1',
    title: '会话1',
    message_count: 2,
    created_at: '',
    last_active: '',
  },
];

const mockStoreState = {
  sessions: mockSessions,
  sessionsLoading: false,
  sessionId: 's1',
};

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: (selector: (s: typeof mockStoreState) => unknown) =>
    selector(mockStoreState),
}));

describe('SessionSidebar', () => {
  it('renders session list from store', () => {
    render(
      <SessionSidebar
        isOpen={false}
        onClose={() => {}}
        isMobile={false}
        onSelectSession={() => {}}
        onNewChat={() => {}}
        onDeleteSession={() => {}}
      />,
    );
    expect(screen.getByText('会话1')).toBeInTheDocument();
    expect(screen.getByText('2 条对话')).toBeInTheDocument();
  });

  it('calls onNewChat when new chat button clicked', () => {
    const onNewChat = vi.fn();
    render(
      <SessionSidebar
        isOpen={false}
        onClose={() => {}}
        isMobile={false}
        onSelectSession={() => {}}
        onNewChat={onNewChat}
        onDeleteSession={() => {}}
      />,
    );
    fireEvent.click(screen.getByLabelText('开启新对话'));
    expect(onNewChat).toHaveBeenCalled();
  });

  it('calls onSelectSession and onClose when session clicked on mobile', () => {
    const onSelect = vi.fn();
    const onClose = vi.fn();
    render(
      <SessionSidebar
        isOpen={true}
        onClose={onClose}
        isMobile={true}
        onSelectSession={onSelect}
        onNewChat={() => {}}
        onDeleteSession={() => {}}
      />,
    );
    fireEvent.click(screen.getByLabelText('切换到对话 会话1'));
    expect(onSelect).toHaveBeenCalledWith('s1');
    expect(onClose).toHaveBeenCalled();
  });

  it('does not call onClose on desktop when session clicked', () => {
    const onClose = vi.fn();
    render(
      <SessionSidebar
        isOpen={false}
        onClose={onClose}
        isMobile={false}
        onSelectSession={() => {}}
        onNewChat={() => {}}
        onDeleteSession={() => {}}
      />,
    );
    fireEvent.click(screen.getByLabelText('切换到对话 会话1'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('opens delete confirm dialog and calls onDeleteSession on confirm', () => {
    const onDelete = vi.fn();
    render(
      <SessionSidebar
        isOpen={false}
        onClose={() => {}}
        isMobile={false}
        onSelectSession={() => {}}
        onNewChat={() => {}}
        onDeleteSession={onDelete}
      />,
    );
    fireEvent.click(screen.getByLabelText('删除对话 会话1'));
    expect(screen.getByText('删除对话')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '删除' }));
    expect(onDelete).toHaveBeenCalledWith('s1');
  });

  it('shows loading state when sessionsLoading is true', () => {
    mockStoreState.sessionsLoading = true;
    render(
      <SessionSidebar
        isOpen={false}
        onClose={() => {}}
        isMobile={false}
        onSelectSession={() => {}}
        onNewChat={() => {}}
        onDeleteSession={() => {}}
      />,
    );
    expect(screen.getByText('加载对话中...')).toBeInTheDocument();
    mockStoreState.sessionsLoading = false;
  });
});
