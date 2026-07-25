export interface EtfRankingItem {
  code: string;
  name?: string | null;
  mainNetInflow: number;
  changePct: number;
  totalMarketValue?: number | null;
  tradeDate?: string | null;
}

export interface EtfMarketOverview {
  totalNetInflow: number;
  inflowCount: number;
  outflowCount: number;
  topInflow: EtfRankingItem[];
  topOutflow: EtfRankingItem[];
}

export interface EtfBucketSummary {
  bucketName: string;
  bucketType: string;
  memberCount: number;
  totalScale: number;
  netInflowSum: number;
  shareChangeSum?: number | null;
  weightedChangePct?: number | null;
  weightedDiscountPct?: number | null;
  weightedShareChangePct?: number | null;
}

export interface EtfDetailItem {
  code: string;
  name?: string | null;
  bucketType: string;
  bucketName: string;
  close?: number | null;
  changePct?: number | null;
  discountPct?: number | null;
  mainNetInflow?: number | null;
  mainNetInflowPct?: number | null;
  latestShares?: number | null;
  shareChange?: number | null;
  totalMarketValue?: number | null;
  turnover?: number | null;
  tradeDate?: string | null;
}

export interface EtfCapitalFlowSnapshot {
  tradeDate: string;
  status: string;
  sourceChain: Array<{ provider: string; result: string; durationMs?: number }>;
  warnings: string[];
  marketOverview: EtfMarketOverview;
  sectorBuckets: EtfBucketSummary[];
  indexBuckets: EtfBucketSummary[];
  details: EtfDetailItem[];
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface EtfCapitalFlowListResponse {
  snapshots: EtfCapitalFlowSnapshot[];
  total: number;
}
