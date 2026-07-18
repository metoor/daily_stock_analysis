import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  EtfCapitalFlowListResponse,
  EtfCapitalFlowSnapshot,
} from '../types/etfCapitalFlow';

export const etfCapitalFlowApi = {
  async getLatest(): Promise<EtfCapitalFlowSnapshot> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/etf-capital-flow/latest');
    return toCamelCase<EtfCapitalFlowSnapshot>(response.data);
  },

  async getByDate(tradeDate: string): Promise<EtfCapitalFlowSnapshot> {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/etf-capital-flow/${tradeDate}`,
    );
    return toCamelCase<EtfCapitalFlowSnapshot>(response.data);
  },

  async getRange(startDate: string, endDate: string): Promise<EtfCapitalFlowListResponse> {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/etf-capital-flow/range/list',
      { params: { start_date: startDate, end_date: endDate } },
    );
    return toCamelCase<EtfCapitalFlowListResponse>(response.data);
  },

  async refresh(tradeDate?: string): Promise<EtfCapitalFlowSnapshot> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/etf-capital-flow/refresh',
      tradeDate ? { trade_date: tradeDate } : {},
    );
    return toCamelCase<EtfCapitalFlowSnapshot>(response.data);
  },
};
