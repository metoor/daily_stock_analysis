import type React from 'react';
import { Fragment } from 'react';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import { EmptyState } from '../common/EmptyState';
import type { EtfCapitalFlowSnapshot } from '../../types/etfCapitalFlow';

interface EtfSectorHeatmapProps {
  snapshots: EtfCapitalFlowSnapshot[];
}

function cellBackground(value: number | undefined | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return 'bg-surface-2 text-secondary-text';
  }
  if (value === 0) {
    return 'bg-surface-2 text-secondary-text';
  }
  const yi = value / 1e8;
  const abs = Math.abs(yi);
  if (value > 0) {
    if (abs >= 10) return 'bg-[#dc2626] text-white';
    if (abs >= 3) return 'bg-[#ef4444]/80 text-white';
    return 'bg-[#fca5a5] text-foreground';
  }
  if (abs >= 10) return 'bg-[#16a34a] text-white';
  if (abs >= 3) return 'bg-[#22c55e]/80 text-white';
  return 'bg-[#86efac] text-foreground';
}

function formatYiShort(value: number | undefined | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '-';
  const yi = value / 1e8;
  return yi.toFixed(1);
}

function shortDate(dateStr: string): string {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return dateStr;
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

export const EtfSectorHeatmap: React.FC<EtfSectorHeatmapProps> = ({ snapshots }) => {
  const { t } = useUiLanguage();

  if (snapshots.length === 0) {
    return <EmptyState title={t('common.noData')} />;
  }

  const sorted = [...snapshots].sort((a, b) => a.tradeDate.localeCompare(b.tradeDate));
  const dates = sorted.map((s) => s.tradeDate);

  const sectorNames = Array.from(
    sorted.reduce<Set<string>>((set, snap) => {
      snap.sectorBuckets.forEach((b) => set.add(b.bucketName));
      return set;
    }, new Set()),
  );

  const cellMap = new Map<string, number>();
  for (const snap of sorted) {
    for (const bucket of snap.sectorBuckets) {
      cellMap.set(`${bucket.bucketName}|${snap.tradeDate}`, bucket.netInflowSum);
    }
  }

  const lookup = (name: string, date: string): number | undefined =>
    cellMap.get(`${name}|${date}`);

  return (
    <div>
      <div className="mb-3 text-sm font-medium text-foreground">{t('etfFlow.heatmap.title')}</div>
      <div className="overflow-x-auto">
        <div className="inline-grid gap-1 text-xs" style={{ gridTemplateColumns: `120px repeat(${dates.length}, 1fr)` }}>
          <div className="px-2 py-1 text-secondary-text" />
          {dates.map((date) => (
            <div key={date} className="px-2 py-1 text-center text-secondary-text">
              {shortDate(date)}
            </div>
          ))}
          {sectorNames.map((name) => (
            <Fragment key={name}>
              <div className="px-2 py-1 font-medium text-foreground">{name}</div>
              {dates.map((date) => {
                const value = lookup(name, date);
                return (
                  <div
                    key={`${name}|${date}`}
                    className={`px-2 py-1 text-center ${cellBackground(value)}`}
                  >
                    {formatYiShort(value)}
                  </div>
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  );
};
