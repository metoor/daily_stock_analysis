import type React from 'react';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import { Card } from '../common/Card';
import { EmptyState } from '../common/EmptyState';
import type { EtfBucketSummary } from '../../types/etfCapitalFlow';

interface EtfBroadIndexCardProps {
  indexBuckets: EtfBucketSummary[];
}

function formatYi(value: number): string {
  const yi = value / 1e8;
  const sign = yi >= 0 ? '+' : '';
  return `${sign}${yi.toFixed(2)}亿`;
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function shareChangeStars(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) return '';
  return value > 0 ? '★'.repeat(Math.min(3, Math.ceil(value))) : '☆'.repeat(Math.min(3, Math.ceil(Math.abs(value))));
}

export const EtfBroadIndexCard: React.FC<EtfBroadIndexCardProps> = ({ indexBuckets }) => {
  const { t } = useUiLanguage();

  if (indexBuckets.length === 0) {
    return <EmptyState title={t('common.noData')} />;
  }

  return (
    <div>
      <div className="mb-3 text-sm font-medium text-foreground">{t('etfFlow.broadIndex.title')}</div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {indexBuckets.map((bucket) => {
          const discount = bucket.weightedDiscountPct ?? null;
          const shareChange = bucket.shareChangeSum ?? bucket.weightedShareChangePct ?? null;
          return (
            <Card key={bucket.bucketName} padding="sm">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-foreground">{bucket.bucketName}</span>
                <span className="text-xs text-secondary-text">{shareChangeStars(shareChange)}</span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                <div>
                  <div className="text-secondary-text">{t('etfFlow.broadIndex.netInflow')}</div>
                  <div className={`mt-0.5 font-medium ${bucket.netInflowSum >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {formatYi(bucket.netInflowSum)}
                  </div>
                </div>
                <div>
                  <div className="text-secondary-text">{t('etfFlow.broadIndex.discount')}</div>
                  <div className="mt-0.5 font-medium text-foreground">{formatPct(discount)}</div>
                </div>
                <div>
                  <div className="text-secondary-text">{t('etfFlow.broadIndex.shareChange')}</div>
                  <div className={`mt-0.5 font-medium ${shareChange === null ? 'text-foreground' : shareChange >= 0 ? 'text-red-600' : 'text-green-600'}`}>{shareChange === null ? '-' : `${shareChange >= 0 ? '+' : ''}${shareChange.toFixed(2)}`}</div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
};
