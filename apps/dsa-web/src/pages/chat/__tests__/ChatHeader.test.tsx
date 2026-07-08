import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChatHeader } from '../ChatHeader';

vi.mock('../../../api/agent', () => ({
  agentApi: { sendChat: vi.fn().mockResolvedValue(undefined) },
}));
vi.mock('../../../api/error', () => ({
  getParsedApiError: vi.fn(() => ({ message: 'fail' })),
}));
vi.mock('../../../utils/chatExport', () => ({
  downloadSession: vi.fn(),
  formatSessionAsMarkdown: vi.fn(() => ''),
}));

let mockMessages: Array<{ id: string; role: 'user' | 'assistant'; content: string }> = [
  { id: 'm1', role: 'user', content: 'hi' },
];

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: (selector: (s: { messages: typeof mockMessages }) => unknown) =>
    selector({ messages: mockMessages }),
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
    mockMessages = [];
    rerender(<ChatHeader onToggleSidebar={() => {}} isMobile={false} />);
    expect(screen.queryByLabelText('导出会话为 Markdown 文件')).toBeNull();
    mockMessages = [{ id: 'm1', role: 'user', content: 'hi' }];
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
