import { Panel } from '../common/Panel';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Experiment, VariantResult } from '../../types';

interface ExperimentComparisonProps {
  experiment: Experiment;
}

function formatArmLabel(name: string): string {
  return name.replace(/_/g, ' ');
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

  const variants = r.variant_results;

  interface MetricRow {
    label: string;
    controlValue: number;
    controlDisplay: string;
    getVariantValue: (v: VariantResult) => number;
    formatVariant: (v: VariantResult) => string;
  }

  const metrics: MetricRow[] = [
    {
      label: 'Accuracy',
      controlValue: r.control_accuracy,
      controlDisplay: `${(r.control_accuracy * 100).toFixed(1)}%`,
      getVariantValue: v => v.accuracy,
      formatVariant: v => `${(v.accuracy * 100).toFixed(1)}%`,
    },
    {
      label: 'Net Return',
      controlValue: r.control_return,
      controlDisplay: `${r.control_return >= 0 ? '+' : ''}${r.control_return.toFixed(2)}%`,
      getVariantValue: v => v.net_return,
      formatVariant: v => `${v.net_return >= 0 ? '+' : ''}${v.net_return.toFixed(2)}%`,
    },
    {
      label: 'Sharpe Ratio',
      controlValue: r.control_sharpe,
      controlDisplay: r.control_sharpe.toFixed(2),
      getVariantValue: v => v.sharpe,
      formatVariant: v => v.sharpe.toFixed(2),
    },
  ];

  const cellBase: React.CSSProperties = {
    padding: isMobile ? '10px 12px' : '10px 16px',
    fontFamily: 'var(--font-mono)',
    fontSize: isMobile ? '0.75rem' : '0.8rem',
    borderBottom: '1px solid var(--border)',
  };

  const headerStyle: React.CSSProperties = {
    ...cellBase,
    textAlign: 'right',
    color: 'var(--text-secondary)',
    fontFamily: 'var(--font-display)',
    fontSize: '0.7rem',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  };

  return (
    <Panel title="Performance Comparison">
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ ...headerStyle, textAlign: 'left' }}>Metric</th>
              <th style={headerStyle}>Control</th>
              {variants.map(v => (
                <th key={v.variant_name} style={headerStyle}>
                  {formatArmLabel(v.variant_name)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metrics.map(metric => {
              // Find best value among all arms
              const allValues = [metric.controlValue, ...variants.map(v => metric.getVariantValue(v))];
              const bestValue = Math.max(...allValues);

              return (
                <tr key={metric.label}>
                  <td style={{ ...cellBase, color: 'var(--text-primary)', fontWeight: 500 }}>
                    {metric.label}
                  </td>
                  <td style={{
                    ...cellBase,
                    textAlign: 'right',
                    color: metric.controlValue === bestValue ? 'var(--color-long)' : 'var(--text-primary)',
                    fontWeight: 600,
                  }}>
                    {metric.controlDisplay}
                  </td>
                  {variants.map(v => {
                    const val = metric.getVariantValue(v);
                    return (
                      <td key={v.variant_name} style={{
                        ...cellBase,
                        textAlign: 'right',
                        color: val === bestValue ? 'var(--color-long)' : 'var(--text-primary)',
                        fontWeight: 600,
                      }}>
                        {metric.formatVariant(v)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
            {/* P-value row */}
            <tr>
              <td style={{ ...cellBase, color: 'var(--text-primary)', fontWeight: 500 }}>
                p-value
              </td>
              <td style={{ ...cellBase, textAlign: 'right', color: 'var(--text-muted)' }}>
                —
              </td>
              {variants.map(v => (
                <td key={v.variant_name} style={{
                  ...cellBase,
                  textAlign: 'right',
                  color: v.is_significant ? 'var(--color-long)' : 'var(--text-muted)',
                  fontWeight: v.is_significant ? 600 : 400,
                }}>
                  {v.p_value != null ? v.p_value.toFixed(4) : '—'}
                  {v.is_significant && ' *'}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
