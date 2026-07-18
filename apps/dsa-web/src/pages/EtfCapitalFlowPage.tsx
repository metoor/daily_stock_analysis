import { useCallback, useEffect, useState } from 'react';
import { AppPage } from '../components/common/AppPage';
import { PageHeader } from '../components/common/PageHeader';
import { Card } from '../components/common/Card';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import { getParsedApiError, ParsedApiError } from '../api/error';
import { etfCapitalFlowApi } from '../api/etfCapitalFlow';
import type { EtfCapitalFlowSnapshot } from '../types/etfCapitalFlow';
import { EtfKpiBar } from '../components/etf-flow/EtfKpiBar';
import { EtfTopFlowChart } from '../components/etf-flow/EtfTopFlowChart';
import { EtfSectorHeatmap } from '../components/etf-flow/EtfSectorHeatmap';
import { EtfBroadIndexCard } from '../components/etf-flow/EtfBroadIndexCard';

export function EtfCapitalFlowPage() {
  const { t } = useUiLanguage();
  const [snapshot, setSnapshot] = useState<EtfCapitalFlowSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [notFound, setNotFound] = useState(false);

  const fetchLatest = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const data = await etfCapitalFlowApi.getLatest();
      setSnapshot(data);
    } catch (err) {
      const status = (err as { response?: { status?: number } } | null | undefined)?.response?.status;
      if (status === 404) {
        setNotFound(true);
      } else {
        setError(getParsedApiError(err));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLatest();
  }, [fetchLatest]);

  return (
    <AppPage>
      <PageHeader
        eyebrow={t('etfFlow.eyebrow')}
        title={t('etfFlow.title')}
        description={t('etfFlow.description')}
      />
      {loading && <p>{t('common.loading')}...</p>}
      {error && <ApiErrorAlert error={error} />}
      {notFound && (
        <EmptyState
          title={t('etfFlow.empty.title')}
          description={t('etfFlow.empty.description')}
        />
      )}
      {snapshot && (
        <div className="space-y-4">
          <EtfKpiBar snapshot={snapshot} />
          <Card title={t('etfFlow.sections.marketOverview')}>
            <EtfTopFlowChart
              topInflow={snapshot.marketOverview.topInflow}
              topOutflow={snapshot.marketOverview.topOutflow}
            />
          </Card>
          <Card title={t('etfFlow.sections.sectorRotation')}>
            <EtfSectorHeatmap snapshots={[snapshot]} />
          </Card>
          <Card title={t('etfFlow.sections.broadIndex')}>
            <EtfBroadIndexCard indexBuckets={snapshot.indexBuckets} />
          </Card>
        </div>
      )}
    </AppPage>
  );
}
