import { Panel } from '../common/Panel';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Experiment } from '../../types';

interface ExperimentComparisonProps {
  experiment: Experiment;
}

export function ExperimentComparison({ experiment }: ExperimentComparisonProps) {
  const isMobile = useIsMobile();
  const r = experiment.result;

  if (!r) {
    return (
      <Panel title="Performance Comparison">
        <div style={{
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          textAlign: 'center',
          padding: '40px 0',
        }}>
          No results yet
        </div>
      </Panel>
    );
  }

  const rows: { label: string; control: string; variant: string; controlWins: boolean }[] = [
    {
      label: 'Accuracy',
      control: `${(r.control_accuracy * 100).toFixed(1)}%`,
      variant: `${(r.variant_accuracy * 100).toFixed(1)}%`,
      controlWins: r.control_accuracy > r.variant_accuracy,
    },
    {
      label: 'Net Return',
      control: `${r.control_return >= 0 ? '+' : ''}${r.control_return.toFixed(2)}%`,
      variant: `${r.variant_return >= 0 ? '+' : ''}${r.variant_return.toFixed(2)}%`,
      controlWins: r.control_return > r.variant_return,
    },
    {
      label: 'Sharpe Ratio',
      control: r.control_sharpe.toFixed(2),
      variant: r.variant_sharpe.toFixed(2),
      controlWins: r.control_sharpe > r.variant_sharpe,
    },
  ];

  const cellBase: React.CSSProperties = {
    padding: isMobile ? '10px 12px' : '10px 16px',
    fontFamily: 'var(--font-mono)',
    fontSize: isMobile ? '0.75rem' : '0.8rem',
    borderBottom: '1px solid var(--border)',
  };

  return (
    <Panel title="Performance Comparison">
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ ...cellBase, textAlign: 'left', color: 'var(--text-secondary)', fontFamily: 'var(--font-display)', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Metric
            </th>
            <th style={{ ...cellBase, textAlign: 'right', color: 'var(--text-secondary)', fontFamily: 'var(--font-display)', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Control
            </th>
            <th style={{ ...cellBase, textAlign: 'right', color: 'var(--text-secondary)', fontFamily: 'var(--font-display)', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Variant
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.label}>
              <td style={{ ...cellBase, color: 'var(--text-primary)', fontWeight: 500 }}>
                {row.label}
              </td>
              <td style={{
                ...cellBase,
                textAlign: 'right',
                color: row.controlWins ? 'var(--color-long)' : 'var(--color-short)',
                fontWeight: 600,
              }}>
                {row.control}
              </td>
              <td style={{
                ...cellBase,
                textAlign: 'right',
                color: row.controlWins ? 'var(--color-short)' : 'var(--color-long)',
                fontWeight: 600,
              }}>
                {row.variant}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
