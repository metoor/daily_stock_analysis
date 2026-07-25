import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
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

const { mockGetLatest, mockGetByDate, mockGetRange, mockRefresh } = vi.hoisted(() => ({
  mockGetLatest: vi.fn(),
  mockGetByDate: vi.fn(),
  mockGetRange: vi.fn(),
  mockRefresh: vi.fn(),
}));
vi.mock('../../api/etfCapitalFlow', () => ({
  etfCapitalFlowApi: {
    getLatest: mockGetLatest,
    getByDate: mockGetByDate,
    getRange: mockGetRange,
    refresh: mockRefresh,
  },
}));

beforeEach(() => {
  mockGetLatest.mockReset();
  mockGetByDate.mockReset();
  mockGetRange.mockReset();
  mockRefresh.mockReset();
  mockGetRange.mockResolvedValue({ snapshots: [], total: 0 });
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

  it('renders date picker and triggers getByDate on change', async () => {
    mockGetLatest.mockResolvedValueOnce(sampleSnapshot);
    mockGetByDate.mockResolvedValueOnce(sampleSnapshot);
    const { container } = render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfCapitalFlowPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/38\.0亿/)).toBeInTheDocument());
    const dateInput = container.querySelector('input[type="date"]') as HTMLInputElement;
    expect(dateInput).toBeTruthy();
    expect(mockGetByDate).not.toHaveBeenCalled();
    // Simulate user picking a historical date.
    fireEvent.change(dateInput, { target: { value: '2026-07-10' } });
    await waitFor(() => expect(mockGetByDate).toHaveBeenCalledWith('2026-07-10'));
  });

  it('fetches 10-day range for heatmap on mount', async () => {
    mockGetLatest.mockResolvedValueOnce(sampleSnapshot);
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfCapitalFlowPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    await waitFor(() => expect(mockGetRange).toHaveBeenCalled());
    const [startDate, endDate] = mockGetRange.mock.calls[0];
    // The range window is 10 calendar days: start = today - 9, end = today.
    const parsedStart = new Date(startDate);
    const parsedEnd = new Date(endDate);
    const diffDays = Math.round(
      (parsedEnd.getTime() - parsedStart.getTime()) / (1000 * 60 * 60 * 24),
    );
    expect(diffDays).toBe(9);
  });

  it('renders EtfBucketDetail section per sector bucket', async () => {
    const snapshotWithBuckets = {
      ...sampleSnapshot,
      sectorBuckets: [
        { bucketName: '券商', bucketType: 'sector', memberCount: 1, totalScale: 500, netInflowSum: 10 },
      ],
      details: [
        { code: '512000', name: '券商ETF华泰', bucketType: 'sector', bucketName: '券商' },
      ],
    };
    mockGetLatest.mockResolvedValueOnce(snapshotWithBuckets);
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfCapitalFlowPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    // EtfBucketDetail renders the bucketDetail title; the bucket name "券商"
    // also appears in the KpiBar leading-sector slot, so match the title.
    await waitFor(() => expect(screen.getAllByText('券商').length).toBeGreaterThanOrEqual(1));
    expect(screen.getByText('成分明细')).toBeInTheDocument();
  });

  it('refresh button calls refresh API and renders refreshed snapshot', async () => {
    mockGetLatest.mockResolvedValueOnce(sampleSnapshot);
    const refreshedSnapshot = {
      ...sampleSnapshot,
      marketOverview: {
        ...sampleSnapshot.marketOverview,
        totalNetInflow: 50e8,
      },
    };
    mockRefresh.mockResolvedValueOnce(refreshedSnapshot);
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfCapitalFlowPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    // Wait for the initial snapshot to render.
    await waitFor(() => expect(screen.getByText(/38\.0亿/)).toBeInTheDocument());
    const refreshButton = screen.getByRole('button', { name: '刷新' });
    fireEvent.click(refreshButton);
    await waitFor(() => expect(mockRefresh).toHaveBeenCalledTimes(1));
    // The refreshed total (50e8) should now appear instead of the original (38e8).
    await waitFor(() => expect(screen.getByText(/50\.0亿/)).toBeInTheDocument());
  });
});
