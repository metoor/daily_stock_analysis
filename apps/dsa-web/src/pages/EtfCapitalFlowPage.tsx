import { useCallback, useEffect, useMemo, useState } from 'react';
import { AppPage } from '../components/common/AppPage';
import { PageHeader } from '../components/common/PageHeader';
import { Card } from '../components/common/Card';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { InlineAlert } from '../components/common/InlineAlert';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { etfCapitalFlowApi } from '../api/etfCapitalFlow';
import type { EtfCapitalFlowSnapshot } from '../types/etfCapitalFlow';
import { EtfKpiBar } from '../components/etf-flow/EtfKpiBar';
import { EtfTopFlowChart } from '../components/etf-flow/EtfTopFlowChart';
import { EtfSectorHeatmap } from '../components/etf-flow/EtfSectorHeatmap';
import { EtfBroadIndexCard } from '../components/etf-flow/EtfBroadIndexCard';
import { EtfBucketDetail } from '../components/etf-flow/EtfBucketDetail';

const HEATMAP_WINDOW_DAYS = 10;

function formatYmd(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function EtfCapitalFlowPage() {
  const { t } = useUiLanguage();
  const [snapshot, setSnapshot] = useState<EtfCapitalFlowSnapshot | null>(null);
  const [rangeSnapshots, setRangeSnapshots] = useState<EtfCapitalFlowSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string>('');

  const fetchSnapshot = useCallback(async (date: string) => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const data = date
        ? await etfCapitalFlowApi.getByDate(date)
        : await etfCapitalFlowApi.getLatest();
      setSnapshot(data);
    } catch (err) {
      const status = (err as { response?: { status?: number } } | null | undefined)?.response?.status;
      if (status === 404) {
        setNotFound(true);
        setSnapshot(null);
      } else {
        setError(getParsedApiError(err));
        setSnapshot(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchRange = useCallback(async () => {
    const today = new Date();
    const start = new Date(today);
    start.setDate(start.getDate() - (HEATMAP_WINDOW_DAYS - 1));
    try {
      const resp = await etfCapitalFlowApi.getRange(formatYmd(start), formatYmd(today));
      setRangeSnapshots(resp.snapshots ?? []);
    } catch {
      // Heatmap falls back to the latest snapshot; no need to surface an error.
      setRangeSnapshots([]);
    }
  }, []);

  useEffect(() => {
    fetchSnapshot(selectedDate);
  }, [fetchSnapshot, selectedDate]);

  useEffect(() => {
    // Fetch the 10-day range once on mount for the heatmap. Skip when the user
    // is looking at a specific historical date; the single snapshot still
    // renders so the heatmap degrades gracefully.
    if (selectedDate === '') {
      fetchRange();
    }
  }, [fetchRange, selectedDate]);

  const heatmapSnapshots = useMemo<EtfCapitalFlowSnapshot[]>(() => {
    if (rangeSnapshots.length > 0) return rangeSnapshots;
    return snapshot ? [snapshot] : [];
  }, [rangeSnapshots, snapshot]);

  const handleDateChange = useCallback((value: string) => {
    setSelectedDate(value);
  }, []);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    setNotFound(false);
    try {
      // Pass the currently selected date so refresh regenerates that date's
      // snapshot. Empty selectedDate = today (full refresh via run_daily);
      // a past date = partial backfill via fund_etf_hist_em OHLCV.
      const data = await etfCapitalFlowApi.refresh(selectedDate || undefined);
      setSnapshot(data);
      // Keep the date picker in sync with the returned snapshot's trade date
      // so subsequent navigations / refreshes target the same date.
      setSelectedDate(data.tradeDate ?? selectedDate);
    } catch (err) {
      const status = (err as { response?: { status?: number } } | null | undefined)?.response?.status;
      if (status === 404) {
        setNotFound(true);
      } else {
        setError(getParsedApiError(err));
      }
    } finally {
      setRefreshing(false);
    }
  }, [selectedDate]);

  return (
    <AppPage>
      <PageHeader
        eyebrow={t('etfFlow.eyebrow')}
        title={t('etfFlow.title')}
        description={t('etfFlow.description')}
        actions={
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-secondary-text">
              <span>{t('etfFlow.datePicker.label')}</span>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => handleDateChange(e.target.value)}
                className="rounded border border-subtle bg-card px-2 py-1 text-foreground"
                aria-label={t('etfFlow.datePicker.label')}
              />
              {selectedDate ? (
                <button
                  type="button"
                  onClick={() => handleDateChange('')}
                  className="text-xs text-secondary-text underline hover:text-foreground"
                >
                  {t('etfFlow.datePicker.latest')}
                </button>
              ) : null}
            </label>
            <button
              type="button"
              onClick={handleRefresh}
              disabled={refreshing}
              className="rounded border border-subtle bg-card px-3 py-1 text-sm text-foreground hover:bg-subtle disabled:cursor-not-allowed disabled:opacity-60"
            >
              {refreshing ? t('etfFlow.actions.refreshing') : t('etfFlow.actions.refresh')}
            </button>
          </div>
        }
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
          {snapshot.status === 'partial' ? (
            <InlineAlert
              variant="warning"
              title={t('etfFlow.partialWarning.title')}
              message={t('etfFlow.partialWarning.description')}
            />
          ) : null}
          <EtfKpiBar snapshot={snapshot} />
          <Card title={t('etfFlow.sections.marketOverview')}>
            <EtfTopFlowChart
              topInflow={snapshot.marketOverview.topInflow}
              topOutflow={snapshot.marketOverview.topOutflow}
            />
          </Card>
          <Card title={t('etfFlow.sections.sectorRotation')}>
            <EtfSectorHeatmap snapshots={heatmapSnapshots} />
          </Card>
          <Card title={t('etfFlow.sections.broadIndex')}>
            <EtfBroadIndexCard indexBuckets={snapshot.indexBuckets} />
          </Card>
          <Card title={t('etfFlow.sections.detail')}>
            {snapshot.sectorBuckets.length === 0 ? (
              <EmptyState title={t('common.noData')} />
            ) : (
              <div className="space-y-4">
                {snapshot.sectorBuckets.map((bucket) => (
                  <EtfBucketDetail
                    key={bucket.bucketName}
                    bucketName={bucket.bucketName}
                    details={snapshot.details.filter(
                      (d) => d.bucketName === bucket.bucketName,
                    )}
                  />
                ))}
              </div>
            )}
          </Card>
        </div>
      )}
    </AppPage>
  );
}

export default EtfCapitalFlowPage;
