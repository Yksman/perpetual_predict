import { useState } from 'react';
import { Header } from './components/layout/Header';
import { Footer } from './components/layout/Footer';
import { TabNav } from './components/layout/TabNav';
import { KpiStrip } from './components/layout/KpiStrip';
import { PredictionPage } from './pages/PredictionPage';
import { TradingPage } from './pages/TradingPage';
import { usePredictions, useTrades, useMetrics, useMeta } from './hooks/useData';
import { Skeleton } from './components/common/Skeleton';

export default function App() {
  const [activeTab, setActiveTab] = useState('predictions');

  const { data: predictionsData, loading: loadingPred } = usePredictions();
  const { data: tradesData, loading: loadingTrades } = useTrades();
  const { data: metricsData, loading: loadingMetrics } = useMetrics();
  const { data: metaData } = useMeta();

  const loading = loadingPred || loadingTrades || loadingMetrics;

  return (
    <div style={{
      maxWidth: '1440px',
      margin: '0 auto',
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      border: '1px solid var(--border)',
      borderTop: 'none',
      borderBottom: 'none',
    }}>
      <Header exportedAt={metaData?.exported_at ?? null} />

      {loading ? (
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px' }}>
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} height="80px" />
            ))}
          </div>
          <Skeleton height="300px" />
          <Skeleton height="200px" />
        </div>
      ) : metricsData && predictionsData && tradesData ? (
        <>
          <KpiStrip metrics={metricsData} />
          <TabNav activeTab={activeTab} onTabChange={setActiveTab} />
          <main style={{ flex: 1 }}>
            {activeTab === 'predictions' ? (
              <PredictionPage
                predictions={predictionsData.predictions}
                metrics={metricsData}
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
        }}>
          No data available. Run <code style={{ color: 'var(--color-accent)' }}>perpetual_predict export</code> first.
        </div>
      )}

      <Footer />
    </div>
  );
}
