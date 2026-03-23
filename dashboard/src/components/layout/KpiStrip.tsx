import { KpiCard } from '../common/KpiCard';
import type { MetricsData } from '../../types';

interface KpiStripProps {
  metrics: MetricsData;
}

export function KpiStrip({ metrics }: KpiStripProps) {
  const { performance, prediction_accuracy } = metrics;

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
      gap: 'var(--gap)',
      padding: 'var(--gap)',
      background: 'var(--border)',
    }}>
      <KpiCard
        label="Win Rate"
        value={performance.win_rate}
        suffix="%"
      />
      <KpiCard
        label="Total Return"
        value={performance.total_return_pct}
        suffix="%"
        colorize
      />
      <KpiCard
        label="Sharpe Ratio"
        value={performance.sharpe_ratio}
        decimals={2}
      />
      <KpiCard
        label="Max Drawdown"
        value={performance.max_drawdown_pct}
        suffix="%"
        colorize
      />
      <KpiCard
        label="Prediction Accuracy"
        value={prediction_accuracy.accuracy}
        suffix="%"
      />
    </div>
  );
}
