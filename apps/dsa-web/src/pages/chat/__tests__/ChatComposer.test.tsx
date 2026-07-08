import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChatComposer } from '../ChatComposer';

vi.mock('../../../api/agent', () => ({
  agentApi: { getSkills: vi.fn().mockResolvedValue([]) },
}));
vi.mock('../../../api/systemConfig', () => ({
  systemConfigApi: {
    getConfig: vi.fn().mockResolvedValue({ items: [], configVersion: '', maskToken: '******' }),
    update: vi.fn().mockResolvedValue(undefined),
  },
}));

const mockStoreState = {
  loading: false,
  chatError: null,
};

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: (selector: (s: typeof mockStoreState) => unknown) =>
    selector(mockStoreState),
}));

const defaultProps = {
  isMobile: false,
  composerValue: '',
  setComposerValue: () => {},
  onSend: () => {},
  onKeyDown: () => {},
  skills: [],
  selectedSkillIds: [] as string[],
  setSelectedSkillIds: () => {},
  toggleSkillSelection: () => {},
  selectedSkillSummary: '通用分析',
  activeStockCode: null as string | null,
  onToggleWatchlist: () => {},
  stockInWatchlist: () => false,
  isWatchlistActioning: false,
  watchlistMessage: null as string | null,
  isFollowUpContextLoading: false,
};

describe('ChatComposer', () => {
  it('renders textarea and send button', () => {
    render(<ChatComposer {...defaultProps} />);
    expect(screen.getByPlaceholderText(/分析 600519/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '发送' })).toBeInTheDocument();
  });

  it('calls onSend when send button clicked', () => {
    const onSend = vi.fn();
    render(<ChatComposer {...defaultProps} composerValue="分析 600519" onSend={onSend} />);
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    expect(onSend).toHaveBeenCalled();
  });

  it('disables send button when input empty', () => {
    render(<ChatComposer {...defaultProps} />);
    expect(screen.getByRole('button', { name: '发送' })).toBeDisabled();
  });

  it('shows + button on mobile that toggles expansion drawer', () => {
    render(<ChatComposer {...defaultProps} isMobile={true} />);
    const expandBtn = screen.getByLabelText('展开更多选项');
    expect(expandBtn).toBeInTheDocument();
    fireEvent.click(expandBtn);
    expect(screen.getByTestId('chat-composer-drawer')).toBeInTheDocument();
  });

  it('hides + button on desktop', () => {
    render(<ChatComposer {...defaultProps} isMobile={false} />);
    expect(screen.queryByLabelText('展开更多选项')).toBeNull();
  });

  it('disables textarea when loading', () => {
    mockStoreState.loading = true;
    render(<ChatComposer {...defaultProps} composerValue="hi" />);
    expect(screen.getByPlaceholderText(/分析 600519/)).toBeDisabled();
    mockStoreState.loading = false;
  });
});
