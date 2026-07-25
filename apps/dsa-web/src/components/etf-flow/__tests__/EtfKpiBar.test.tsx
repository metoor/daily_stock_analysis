// apps/dsa-web/src/components/etf-flow/__tests__/EtfKpiBar.test.tsx
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { EtfKpiBar } from '../EtfKpiBar';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import type { EtfCapitalFlowSnapshot } from '../../../types/etfCapitalFlow';

const snapshot: EtfCapitalFlowSnapshot = {
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
  sectorBuckets: [
    { bucketName: '券商', bucketType: 'sector', memberCount: 5, totalScale: 1000,
      netInflowSum: 12.3e8, weightedChangePct: 1.2 },
  ],
  indexBuckets: [],
  details: [],
};

describe('EtfKpiBar', () => {
  it('renders total net inflow in 亿', () => {
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfKpiBar snapshot={snapshot} />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/38\.0亿/)).toBeInTheDocument();
  });

  it('shows inflow / outflow sector counts', () => {
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfKpiBar snapshot={snapshot} />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/18.*12/)).toBeInTheDocument();
  });

  it('shows source badge from sourceChain', () => {
    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <EtfKpiBar snapshot={snapshot} />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/akshare/)).toBeInTheDocument();
  });
});
