import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi } from '../../../api/analysis';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../../utils/uiLanguage';
import { StockHistoryTrendDrawer } from '../StockHistoryTrendDrawer';
import type { AnalysisReport, HistoryItem } from '../../../types/analysis';

vi.mock('../../../api/analysis', () => ({
  analysisApi: {
    backfill: vi.fn(),
    getStatus: vi.fn(),
  },
}));

const report: AnalysisReport = {
  meta: {
    id: 1,
    queryId: 'q-1',
    stockCode: '600519',
    stockName: '贵州茅台',
    reportType: 'detailed',
    createdAt: '2026-03-20T08:00:00Z',
  },
  summary: {
    analysisSummary: '等待确认',
    operationAdvice: '买入',
    action: 'avoid',
    actionLabel: '回避',
    trendPrediction: '震荡',
    sentimentScore: 35,
  },
};

const items: HistoryItem[] = [
  {
    id: 1,
    queryId: 'q-1',
    stockCode: '600519',
    stockName: '贵州茅台',
    sentimentScore: 35,
    operationAdvice: '买入',
    action: 'avoid',
    actionLabel: '回避',
    trendPrediction: '震荡',
    createdAt: '2026-03-20T08:00:00Z',
  },
];

describe('StockHistoryTrendDrawer', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('uses structured action in summary and rows', () => {
    render(
      <StockHistoryTrendDrawer
        report={report}
        items={items}
        total={1}
        hasMore={false}
        isLoading={false}
        isLoadingMore={false}
        filters={{ range: 'all', model: 'all', sort: 'desc' }}
        onClose={vi.fn()}
        onRangeChange={vi.fn()}
        onLoadMore={vi.fn()}
        onSelectRecord={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getAllByText('回避').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('买入')).not.toBeInTheDocument();
  });

  it('keeps full legacy operation advice when structured action is absent', () => {
    render(
      <StockHistoryTrendDrawer
        report={{
          ...report,
          summary: {
            ...report.summary,
            operationAdvice: '继续持有，等待突破',
            action: null,
            actionLabel: null,
          },
        }}
        items={[
          {
            ...items[0],
            operationAdvice: '继续持有，等待突破',
            action: null,
            actionLabel: null,
          },
        ]}
        total={1}
        hasMore={false}
        isLoading={false}
        isLoadingMore={false}
        filters={{ range: 'all', model: 'all', sort: 'desc' }}
        onClose={vi.fn()}
        onRangeChange={vi.fn()}
        onLoadMore={vi.fn()}
        onSelectRecord={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getAllByText('继续持有，等待突破').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('持有')).not.toBeInTheDocument();
  });

  it('keeps multi-guard legacy advice as full text when structured action is absent', () => {
    render(
      <StockHistoryTrendDrawer
        report={{
          ...report,
          summary: {
            ...report.summary,
            operationAdvice: 'risk alert, avoid buying',
            action: null,
            actionLabel: null,
          },
        }}
        items={[
          {
            ...items[0],
            operationAdvice: 'risk alert, avoid buying',
            action: null,
            actionLabel: null,
          },
        ]}
        total={1}
        hasMore={false}
        isLoading={false}
        isLoadingMore={false}
        filters={{ range: 'all', model: 'all', sort: 'desc' }}
        onClose={vi.fn()}
        onRangeChange={vi.fn()}
        onLoadMore={vi.fn()}
        onSelectRecord={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getAllByText('risk alert, avoid buying').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('回避')).not.toBeInTheDocument();
    expect(screen.queryByText('预警')).not.toBeInTheDocument();
  });

  it('uses localized taxonomy labels before server labels in English UI mode', () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');

    render(
      <UiLanguageProvider>
        <StockHistoryTrendDrawer
          report={{
            ...report,
            summary: {
              ...report.summary,
              action: 'sell',
              actionLabel: '买入',
            },
          }}
          items={[
            {
              ...items[0],
              action: 'sell',
              actionLabel: '买入',
            },
          ]}
          total={1}
          hasMore={false}
          isLoading={false}
          isLoadingMore={false}
          filters={{ range: 'all', model: 'all', sort: 'desc' }}
          onClose={vi.fn()}
          onRangeChange={vi.fn()}
          onLoadMore={vi.fn()}
          onSelectRecord={vi.fn()}
          onRetry={vi.fn()}
        />
      </UiLanguageProvider>,
    );

    expect(screen.getAllByText('Sell').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('买入')).not.toBeInTheDocument();
  });

  it('renders backfill badge when item.backfilled is true', () => {
    render(
      <StockHistoryTrendDrawer
        report={report}
        items={[{ ...items[0], backfilled: true }]}
        total={1}
        hasMore={false}
        isLoading={false}
        isLoadingMore={false}
        filters={{ range: 'all', model: 'all', sort: 'desc' }}
        onClose={vi.fn()}
        onRangeChange={vi.fn()}
        onLoadMore={vi.fn()}
        onSelectRecord={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText('回填')).toBeInTheDocument();
  });

  it('renders backfill button and triggers API on click', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.mocked(analysisApi.backfill).mockResolvedValue({ status: 'accepted', taskId: 't1', message: '' });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({ status: 'completed', taskId: 't1' });

    render(
      <StockHistoryTrendDrawer
        report={report}
        items={[{ ...items[0], backfilled: false }]}
        total={1}
        hasMore={false}
        isLoading={false}
        isLoadingMore={false}
        filters={{ range: 'all', model: 'all', sort: 'desc' }}
        onClose={vi.fn()}
        onRangeChange={vi.fn()}
        onLoadMore={vi.fn()}
        onSelectRecord={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    const input = screen.getByLabelText(/Pick a date|选择日期/);
    fireEvent.change(input, { target: { value: '2026-06-10' } });
    const btn = screen.getByRole('button', { name: /Backfill date|补填指定日期/ });
    fireEvent.click(btn);
    await waitFor(() => {
      expect(analysisApi.backfill).toHaveBeenCalledWith({ stockCodes: ['600519'], targetDate: '2026-06-10' });
    });
  });
});
