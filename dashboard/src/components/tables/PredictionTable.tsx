import { Panel } from '../common/Panel';
import { Badge } from '../common/Badge';
import { DirectionIcon } from '../common/DirectionIcon';
import { formatShortDate } from '../../utils/format';
import type { Prediction } from '../../types';
import { motion } from 'framer-motion';

interface PredictionTableProps {
  predictions: Prediction[];
  limit?: number;
}

export function PredictionTable({ predictions, limit = 20 }: PredictionTableProps) {
  const sorted = [...predictions]
    .sort((a, b) => b.time.localeCompare(a.time))
    .slice(0, limit);

  return (
    <Panel title="Recent Predictions">
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Time', 'Direction', 'Confidence', 'Leverage', 'Ratio', 'Result', 'Price Δ'].map(h => (
                <th key={h} style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: '0.65rem',
                  fontWeight: 500,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: 'var(--text-secondary)',
                  padding: '10px 12px',
                  textAlign: h === 'Time' || h === 'Direction' ? 'left' : 'right',
                  borderBottom: '1px solid var(--border)',
                  whiteSpace: 'nowrap',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((p, i) => (
              <motion.tr
                key={p.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.03 }}
                style={{ cursor: 'default' }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.background = 'var(--bg-tertiary)';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.background = 'transparent';
                }}
              >
                <td style={cellStyle()}>{formatShortDate(p.time)}</td>
                <td style={cellStyle()}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                    <DirectionIcon direction={p.direction} size="sm" />
                    <span className="mono" style={{ fontSize: '0.75rem' }}>{p.direction}</span>
                  </span>
                </td>
                <td style={cellStyle('right')}>
                  <span className="mono" style={{ fontSize: '0.75rem' }}>
                    {(p.confidence * 100).toFixed(0)}%
                  </span>
                  <div style={{
                    marginTop: '2px',
                    height: '2px',
                    background: 'var(--border)',
                    borderRadius: '1px',
                  }}>
                    <div style={{
                      height: '100%',
                      width: `${p.confidence * 100}%`,
                      background: 'var(--color-accent)',
                      borderRadius: '1px',
                    }} />
                  </div>
                </td>
                <td style={cellStyle('right')}>
                  <span className="mono" style={{ fontSize: '0.75rem' }}>{p.leverage}x</span>
                </td>
                <td style={cellStyle('right')}>
                  <span className="mono" style={{ fontSize: '0.75rem' }}>
                    {(p.position_ratio * 100).toFixed(0)}%
                  </span>
                </td>
                <td style={cellStyle('right')}>
                  <Badge result={p.is_correct} />
                </td>
                <td style={cellStyle('right')}>
                  {p.actual_price_change !== null ? (
                    <span className="mono" style={{
                      fontSize: '0.75rem',
                      color: p.actual_price_change >= 0 ? 'var(--color-long)' : 'var(--color-short)',
                    }}>
                      {p.actual_price_change >= 0 ? '+' : ''}{p.actual_price_change.toFixed(2)}%
                    </span>
                  ) : (
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>—</span>
                  )}
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function cellStyle(align: 'left' | 'right' = 'left'): React.CSSProperties {
  return {
    padding: '10px 12px',
    textAlign: align,
    borderBottom: '1px solid var(--border)',
    fontFamily: 'var(--font-mono)',
    fontSize: '0.75rem',
    whiteSpace: 'nowrap',
    transition: 'background 0.15s',
  };
}
