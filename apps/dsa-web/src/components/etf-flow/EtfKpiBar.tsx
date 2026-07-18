// apps/dsa-web/src/components/etf-flow/EtfKpiBar.tsx
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import { Badge } from '../common/Badge';
import type { EtfCapitalFlowSnapshot } from '../../types/etfCapitalFlow';

interface EtfKpiBarProps {
  snapshot: EtfCapitalFlowSnapshot;
}

function formatAmount(value: number): string {
  const yi = value / 1e8;
  return `${yi.toFixed(1)}亿`;
}

export function EtfKpiBar({ snapshot }: EtfKpiBarProps) {
  const { t } = useUiLanguage();
  const { marketOverview, sourceChain, status } = snapshot;
  const source = sourceChain.find((s) => s.result === 'ok')?.provider ?? 'unknown';
  const badgeVariant = status === 'ok' ? 'success' : status === 'partial' ? 'warning' : 'danger';

  const leader = snapshot.sectorBuckets[0];

  return (
    <div className="grid grid-cols-4 gap-4 p-4 border rounded-md">
      <div>
        <div className="text-sm text-gray-500">{t('etfFlow.kpi.totalNetInflow')}</div>
        <div className="text-xl font-semibold">
          {marketOverview.totalNetInflow >= 0 ? '+' : ''}
          {formatAmount(marketOverview.totalNetInflow)}
        </div>
      </div>
      <div>
        <div className="text-sm text-gray-500">{t('etfFlow.kpi.sectorCounts')}</div>
        <div className="text-xl font-semibold">
          {marketOverview.inflowCount} / {marketOverview.outflowCount}
        </div>
      </div>
      <div>
        <div className="text-sm text-gray-500">{t('etfFlow.kpi.leader')}</div>
        <div className="text-xl font-semibold">{leader?.bucketName ?? '-'}</div>
      </div>
      <div>
        <div className="text-sm text-gray-500">{t('etfFlow.kpi.source')}</div>
        <div className="flex items-center gap-2">
          <span>{source}</span>
          <Badge variant={badgeVariant}>{status}</Badge>
        </div>
      </div>
    </div>
  );
}
