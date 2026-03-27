import { Panel } from '../common/Panel';
import { Badge } from '../common/Badge';
import { DirectionIcon } from '../common/DirectionIcon';
import { formatShortDate } from '../../utils/format';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Prediction } from '../../types';
import { motion } from 'framer-motion';

interface PredictionTableProps {
  predictions: Prediction[];
  limit?: number;
}

export function PredictionTable({ predictions, limit = 20 }: PredictionTableProps) {
  const isMobile = useIsMobile();
  const sorted = [...predictions]
    .sort((a, b) => b.time.localeCompare(a.time))
    .slice(0, limit);

  if (isMobile) {
    return (
      <Panel title="Recent Predictions">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {sorted.map((p, i) => (
            <motion.div
              key={p.id}
              className="touch-feedback"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: i * 0.02 }}
              style={{
                padding: '12px 0',
                borderBottom: i < sorted.length - 1 ? '1px solid var(--border)' : 'none',
              }}
            >
              {/* Row 1: Time + Result */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '6px',
              }}>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.7rem',
                  color: 'var(--text-secondary)',
                }}>
                  {formatShortDate(p.time)}
                </span>
                <Badge result={p.is_correct} />
              </div>
              {/* Row 2: Direction */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.72rem',
                marginBottom: '6px',
              }}>
                <DirectionIcon direction={p.direction} size="sm" />
                <span style={{ fontWeight: 600 }}>{p.direction}</span>
              </div>
              {/* Row 3: Labeled metrics */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.68rem',
              }}>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <span>
                    <span style={{ color: 'var(--text-muted)' }}>Conf </span>
                    <span style={{ color: 'var(--text-secondary)' }}>{(p.confidence * 100).toFixed(0)}%</span>
                  </span>
                  <span>
                    <span style={{ color: 'var(--text-muted)' }}>Pos </span>
                    <span style={{ color: 'var(--text-secondary)' }}>{p.position_pct.toFixed(2)}x</span>
                  </span>
                </div>
                {p.actual_price_change !== null ? (
                  <span style={{
                    fontWeight: 600,
                    color: p.actual_price_change >= 0 ? 'var(--color-long)' : 'var(--color-short)',
                  }}>
                    {p.actual_price_change >= 0 ? '+' : ''}{p.actual_price_change.toFixed(2)}%
                  </span>
                ) : (
                  <span style={{ color: 'var(--text-muted)' }}>—</span>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </Panel>
    );
  }

  // Desktop table view
  return (
    <Panel title="Recent Predictions">
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Time', 'Direction', 'Confidence', 'Position', 'Result', 'Price Δ'].map(h => (
                <th key={h} style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: 'var(--text-secondary)',
                  padding: 'var(--cell-padding)',
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
                    <span className="mono" style={{ fontSize: 'var(--table-font)' }}>{p.direction}</span>
                  </span>
                </td>
                <td style={cellStyle('right')}>
                  <span className="mono" style={{ fontSize: 'var(--table-font)' }}>
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
                  <span className="mono" style={{ fontSize: 'var(--table-font)' }}>
                    {p.position_pct.toFixed(2)}x
                  </span>
                </td>
                <td style={cellStyle('right')}>
                  <Badge result={p.is_correct} />
                </td>
                <td style={cellStyle('right')}>
                  {p.actual_price_change !== null ? (
                    <span className="mono" style={{
                      fontSize: 'var(--table-font)',
                      color: p.actual_price_change >= 0 ? 'var(--color-long)' : 'var(--color-short)',
                    }}>
                      {p.actual_price_change >= 0 ? '+' : ''}{p.actual_price_change.toFixed(2)}%
                    </span>
                  ) : (
                    <span style={{ color: 'var(--text-muted)', fontSize: 'var(--table-font)' }}>—</span>
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
    padding: 'var(--cell-padding)',
    textAlign: align,
    borderBottom: '1px solid var(--border)',
    fontFamily: 'var(--font-mono)',
    fontSize: 'var(--table-font)',
    whiteSpace: 'nowrap',
    transition: 'background 0.15s',
  };
}
