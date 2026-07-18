import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { EtfCapitalFlowPage } from '../EtfCapitalFlowPage';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../utils/uiLanguage';

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: () => <div data-testid="bar-chart" />,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
}));

const { mockGetLatest } = vi.hoisted(() => ({ mockGetLatest: vi.fn() }));
vi.mock('../../api/etfCapitalFlow', () => ({
  etfCapitalFlowApi: { getLatest: mockGetLatest },
}));

beforeEach(() => {
  mockGetLatest.mockReset();
  window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
});

const sampleSnapshot = {
  tradeDate: '2026-07-17',
  status: 'ok',
  sourceChain: [{ provider: 'akshare', result: 'ok', durationMs: 100 }],
  warnings: [],
  marketOverview: {
    totalNetInflow: 38e8,
    inflowCount: 18,
    outflowCount: 12,
    topInflow: [],
    topOutflow: [],
  },
  sectorBuckets: [],
  indexBuckets: [],
  details: [],
};

describe('EtfCapitalFlowPage', () => {
  it('renders loading then snapshot', async () => {
    mockGetLatest.mockResolvedValueOnce(sampleSnapshot);
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfCapitalFlowPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/38\.0亿/)).toBeInTheDocument());
  });

  it('renders error state on API failure', async () => {
    mockGetLatest.mockRejectedValueOnce(new Error('network down'));
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfCapitalFlowPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/network down|错误|error/i)).toBeInTheDocument());
  });

  it('renders empty state when 404', async () => {
    const error = Object.assign(new Error('not found'), { response: { status: 404 } });
    mockGetLatest.mockRejectedValueOnce(error);
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfCapitalFlowPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/暂无|no data|empty/i)).toBeInTheDocument());
  });
});
