import type React from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import { EmptyState } from '../common/EmptyState';
import type { EtfRankingItem } from '../../types/etfCapitalFlow';

interface EtfTopFlowChartProps {
  topInflow: EtfRankingItem[];
  topOutflow: EtfRankingItem[];
}

function formatYi(value: number): string {
  const yi = value / 1e8;
  return `${yi.toFixed(2)}亿`;
}

function toChartData(items: EtfRankingItem[]) {
  return items.map((item) => ({
    name: item.name ?? item.code,
    code: item.code,
    value: item.mainNetInflow,
  }));
}

const TooltipContent: React.FC<{
  active?: boolean;
  payload?: Array<{ payload?: { code: string; name: string; value: number } }>;
}> = ({ active, payload }) => {
  if (!active || !payload?.[0]?.payload) return null;
  const datum = payload[0].payload;
  return (
    <div className="rounded-xl border border-border/70 bg-card/95 px-3 py-2 text-xs shadow-card">
      <div className="font-semibold text-foreground">{datum.name}</div>
      <div className="mt-1 text-secondary-text">{datum.code}</div>
      <div className="mt-1 text-foreground">{formatYi(datum.value)}</div>
    </div>
  );
};

export const EtfTopFlowChart: React.FC<EtfTopFlowChartProps> = ({ topInflow, topOutflow }) => {
  const { t } = useUiLanguage();
  const inflowData = toChartData(topInflow);
  const outflowData = toChartData(topOutflow);

  if (inflowData.length === 0 && outflowData.length === 0) {
    return <EmptyState title={t('common.noData')} />;
  }

  const renderChart = (data: ReturnType<typeof toChartData>, color: string) => (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid stroke="rgba(148, 163, 184, 0.18)" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11, fill: 'currentColor' }} stroke="rgba(148, 163, 184, 0.5)" />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 11, fill: 'currentColor' }}
            stroke="rgba(148, 163, 184, 0.5)"
            width={90}
          />
          <ChartTooltip cursor={{ fill: 'rgba(148, 163, 184, 0.12)' }} content={(props: unknown) => <TooltipContent {...(props as { active?: boolean; payload?: Array<{ payload?: { code: string; name: string; value: number } }> })} />} />
          <Bar dataKey="value" fill={color} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div>
        <div className="mb-2 text-sm font-medium text-foreground">{t('etfFlow.topFlow.inflowTitle')}</div>
        {renderChart(inflowData, '#dc2626')}
      </div>
      <div>
        <div className="mb-2 text-sm font-medium text-foreground">{t('etfFlow.topFlow.outflowTitle')}</div>
        {renderChart(outflowData, '#16a34a')}
      </div>
    </div>
  );
};
