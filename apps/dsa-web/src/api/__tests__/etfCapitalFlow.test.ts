import { describe, expect, it, vi, beforeEach } from 'vitest';
import { etfCapitalFlowApi } from '../etfCapitalFlow';

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }));
vi.mock('../index', () => ({
  default: { get: mockGet },
}));

beforeEach(() => {
  mockGet.mockReset();
});

describe('etfCapitalFlowApi', () => {
  it('getLatest calls /etf-capital-flow/latest', async () => {
    mockGet.mockResolvedValueOnce({
      data: {
        trade_date: '2026-07-17',
        status: 'ok',
        source_chain: [],
        warnings: [],
        market_overview: {
          total_net_inflow: 1000,
          inflow_count: 5,
          outflow_count: 3,
          top_inflow: [],
          top_outflow: [],
        },
        sector_buckets: [],
        index_buckets: [],
        details: [],
      },
    });
    const result = await etfCapitalFlowApi.getLatest();
    expect(mockGet).toHaveBeenCalledWith('/api/v1/etf-capital-flow/latest');
    expect(result.tradeDate).toBe('2026-07-17');
    expect(result.marketOverview.totalNetInflow).toBe(1000);
  });

  it('getByDate calls /etf-capital-flow/{date}', async () => {
    mockGet.mockResolvedValueOnce({ data: { trade_date: '2026-07-16', status: 'ok', market_overview: { total_net_inflow: 0, inflow_count: 0, outflow_count: 0, top_inflow: [], top_outflow: [] }, sector_buckets: [], index_buckets: [], details: [] } });
    await etfCapitalFlowApi.getByDate('2026-07-16');
    expect(mockGet).toHaveBeenCalledWith('/api/v1/etf-capital-flow/2026-07-16');
  });

  it('getRange calls /etf-capital-flow/range/list with params', async () => {
    mockGet.mockResolvedValueOnce({ data: { snapshots: [], total: 0 } });
    await etfCapitalFlowApi.getRange('2026-07-15', '2026-07-17');
    expect(mockGet).toHaveBeenCalledWith('/api/v1/etf-capital-flow/range/list', expect.objectContaining({
      params: { start_date: '2026-07-15', end_date: '2026-07-17' },
    }));
  });
});
