import type React from 'react';
import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import { EmptyState } from '../common/EmptyState';
import type { EtfDetailItem } from '../../types/etfCapitalFlow';

interface EtfBucketDetailProps {
  bucketName: string;
  details: EtfDetailItem[];
}

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const yi = value / 1e8;
  const sign = yi >= 0 ? '+' : '';
  return `${sign}${yi.toFixed(2)}亿`;
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function formatShares(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return value > 0 ? `+${value}` : String(value);
}

export const EtfBucketDetail: React.FC<EtfBucketDetailProps> = ({ bucketName, details }) => {
  const { t } = useUiLanguage();
  const [open, setOpen] = useState(false);

  const members = details.slice(0, 10);

  return (
    <div className="rounded-2xl border border-subtle bg-card/70">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-hover"
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown className="h-4 w-4 text-secondary-text" /> : <ChevronRight className="h-4 w-4 text-secondary-text" />}
          <span className="font-medium text-foreground">{bucketName}</span>
          <span className="text-xs text-secondary-text">({members.length})</span>
        </div>
        <span className="text-xs text-secondary-text">{t('etfFlow.bucketDetail.title')}</span>
      </button>
      {open ? (
        <div className="border-t border-subtle px-4 pb-4 pt-2">
          {members.length === 0 ? (
            <EmptyState title={t('common.noData')} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-secondary-text">
                    <th className="px-2 py-1 text-left font-medium">{t('etfFlow.bucketDetail.col.code')}</th>
                    <th className="px-2 py-1 text-left font-medium">{t('etfFlow.bucketDetail.col.name')}</th>
                    <th className="px-2 py-1 text-right font-medium">{t('etfFlow.bucketDetail.col.changePct')}</th>
                    <th className="px-2 py-1 text-right font-medium">{t('etfFlow.bucketDetail.col.discountPct')}</th>
                    <th className="px-2 py-1 text-right font-medium">{t('etfFlow.bucketDetail.col.netInflow')}</th>
                    <th className="px-2 py-1 text-right font-medium">{t('etfFlow.bucketDetail.col.shareChange')}</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((item) => (
                    <tr key={item.code} className="border-t border-subtle">
                      <td className="px-2 py-1 text-foreground">{item.code}</td>
                      <td className="px-2 py-1 text-foreground">{item.name ?? '-'}</td>
                      <td className={`px-2 py-1 text-right ${(item.changePct ?? 0) >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {formatPct(item.changePct)}
                      </td>
                      <td className="px-2 py-1 text-right text-foreground">{formatPct(item.discountPct)}</td>
                      <td className={`px-2 py-1 text-right ${(item.mainNetInflow ?? 0) >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {formatYi(item.mainNetInflow)}
                      </td>
                      <td className={`px-2 py-1 text-right ${(item.shareChange ?? 0) >= 0 ? 'text-red-600' : 'text-green-600'}`}>{formatShares(item.shareChange)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
};
