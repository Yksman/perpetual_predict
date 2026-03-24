import { useState } from 'react';
import { Header } from './components/layout/Header';
import { Footer } from './components/layout/Footer';
import { TabNav } from './components/layout/TabNav';
import { KpiStrip } from './components/layout/KpiStrip';
import { PredictionPage } from './pages/PredictionPage';
import { TradingPage } from './pages/TradingPage';
import { ExperimentPage } from './pages/ExperimentPage';
import { usePredictions, useTrades, useMetrics, useMeta, useExperiments } from './hooks/useData';
import { useIsMobile } from './hooks/useMediaQuery';
import { Skeleton } from './components/common/Skeleton';

export default function App() {
  const [activeTab, setActiveTab] = useState('predictions');
  const isMobile = useIsMobile();

  const { data: predictionsData, loading: loadingPred } = usePredictions();
  const { data: tradesData, loading: loadingTrades } = useTrades();
  const { data: metricsData, loading: loadingMetrics } = useMetrics();
  const { data: metaData } = useMeta();
  const { data: experimentsData } = useExperiments();

  const loading = loadingPred || loadingTrades || loadingMetrics;

  const hasExperiments = (experimentsData?.experiments?.length ?? 0) > 0;
  const tabs = [
    { id: 'predictions', label: 'Predictions' },
    { id: 'trading', label: 'Trading' },
    ...(hasExperiments ? [{ id: 'experiments', label: 'Experiments' }] : []),
  ];

  return (
    <div style={{
      maxWidth: '1440px',
      margin: '0 auto',
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      border: isMobile ? 'none' : '1px solid var(--border)',
      borderTop: 'none',
      borderBottom: 'none',
    }}>
      <Header exportedAt={metaData?.exported_at ?? null} />

      {loading ? (
        <div style={{
          padding: isMobile ? '14px' : '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: isMobile ? '8px' : '16px',
        }}>
          <div style={{
            display: isMobile ? 'flex' : 'grid',
            gridTemplateColumns: isMobile ? undefined : 'repeat(5, 1fr)',
            gap: '8px',
            ...(isMobile ? { overflowX: 'hidden' } : {}),
          }}>
            {Array.from({ length: isMobile ? 3 : 5 }).map((_, i) => (
              <Skeleton key={i} height="80px" width={isMobile ? '140px' : '100%'} />
            ))}
          </div>
          <Skeleton height={isMobile ? '180px' : '300px'} />
          <Skeleton height={isMobile ? '150px' : '200px'} />
        </div>
      ) : metricsData && predictionsData && tradesData ? (
        <>
          <KpiStrip metrics={metricsData} />
          <TabNav activeTab={activeTab} onTabChange={setActiveTab} tabs={tabs} />
          <main style={{ flex: 1 }}>
            {activeTab === 'predictions' ? (
              <PredictionPage
                predictions={predictionsData.predictions}
                metrics={metricsData}
              />
            ) : activeTab === 'experiments' && hasExperiments ? (
              <ExperimentPage
                experiments={experimentsData!.experiments}
              />
            ) : (
              <TradingPage
                trades={tradesData.trades}
                metrics={metricsData}
              />
            )}
          </main>
        </>
      ) : (
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-muted)',
          fontSize: '0.85rem',
          padding: '0 14px',
          textAlign: 'center',
        }}>
          No data available. Run <code style={{ color: 'var(--color-accent)' }}>perpetual_predict export</code> first.
        </div>
      )}

      <Footer />
    </div>
  );
}
