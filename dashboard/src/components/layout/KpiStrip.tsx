import { KpiCard } from '../common/KpiCard';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { MetricsData } from '../../types';

interface KpiStripProps {
  metrics: MetricsData;
}

export function KpiStrip({ metrics }: KpiStripProps) {
  const { performance, prediction_accuracy } = metrics;
  const isMobile = useIsMobile();

  const containerStyle: React.CSSProperties = isMobile
    ? {
        display: 'flex',
        overflowX: 'auto',
        scrollSnapType: 'x mandatory',
        gap: 'var(--gap)',
        padding: 'var(--gap)',
        background: 'var(--border)',
      }
    : {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: 'var(--gap)',
        padding: 'var(--gap)',
        background: 'var(--border)',
      };

  return (
    <div className={isMobile ? 'hide-scrollbar' : ''} style={containerStyle}>
      <KpiCard label="Win Rate" value={performance.win_rate} suffix="%" />
      <KpiCard label="Total Return" value={performance.total_return_pct} suffix="%" colorize />
      <KpiCard label="Sharpe Ratio" value={performance.sharpe_ratio} decimals={2} />
      <KpiCard label="Max Drawdown" value={performance.max_drawdown_pct} suffix="%" colorize />
      <KpiCard label="Pred. Accuracy" value={prediction_accuracy.accuracy} suffix="%" />
    </div>
  );
}
