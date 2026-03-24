import { Panel } from '../common/Panel';
import { Badge } from '../common/Badge';
import { DirectionIcon } from '../common/DirectionIcon';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { ExperimentPredictionPair } from '../../types';
import { formatShortDate } from '../../utils/format';

interface ExperimentPredictionPairsProps {
  pairs: ExperimentPredictionPair[];
}

export function ExperimentPredictionPairs({ pairs }: ExperimentPredictionPairsProps) {
  const isMobile = useIsMobile();

  if (pairs.length === 0) {
    return (
      <Panel title="Prediction Comparison">
        <div style={{
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          textAlign: 'center',
          padding: '40px 0',
        }}>
          No paired predictions yet
        </div>
      </Panel>
    );
  }

  if (isMobile) {
    return (
      <Panel title="Prediction Comparison">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {pairs.map(pair => (
            <div
              key={pair.target_candle_open}
              style={{
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border)',
                padding: '12px',
              }}
            >
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.7rem',
                color: 'var(--text-secondary)',
                marginBottom: '8px',
              }}>
                {formatShortDate(pair.target_candle_open)}
                {pair.control.actual_direction && (
                  <span style={{ marginLeft: '8px' }}>
                    Actual: <DirectionIcon direction={pair.control.actual_direction} size="sm" />
                  </span>
                )}
              </div>
              {/* Control row */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.65rem',
                  color: 'var(--text-muted)',
                  width: '50px',
                }}>
                  Control
                </span>
                <DirectionIcon direction={pair.control.direction} size="sm" />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-primary)' }}>
                  {(pair.control.confidence * 100).toFixed(0)}%
                </span>
                <Badge result={pair.control.is_correct} />
              </div>
              {/* Variant row */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.65rem',
                  color: 'var(--color-accent)',
                  width: '50px',
                }}>
                  Variant
                </span>
                <DirectionIcon direction={pair.variant.direction} size="sm" />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-primary)' }}>
                  {(pair.variant.confidence * 100).toFixed(0)}%
                </span>
                <Badge result={pair.variant.is_correct} />
              </div>
            </div>
          ))}
        </div>
      </Panel>
    );
  }

  // Desktop table
  const cellBase: React.CSSProperties = {
    padding: '8px 12px',
    fontFamily: 'var(--font-mono)',
    fontSize: '0.75rem',
    borderBottom: '1px solid var(--border)',
    whiteSpace: 'nowrap',
  };

  const headerStyle: React.CSSProperties = {
    ...cellBase,
    color: 'var(--text-secondary)',
    fontFamily: 'var(--font-display)',
    fontSize: '0.65rem',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  };

  return (
    <Panel title="Prediction Comparison">
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ ...headerStyle, textAlign: 'left' }}>Candle</th>
              <th style={{ ...headerStyle, textAlign: 'center' }}>Ctrl Dir</th>
              <th style={{ ...headerStyle, textAlign: 'right' }}>Ctrl Conf</th>
              <th style={{ ...headerStyle, textAlign: 'center' }}>Var Dir</th>
              <th style={{ ...headerStyle, textAlign: 'right' }}>Var Conf</th>
              <th style={{ ...headerStyle, textAlign: 'center' }}>Actual</th>
              <th style={{ ...headerStyle, textAlign: 'center' }}>Ctrl</th>
              <th style={{ ...headerStyle, textAlign: 'center' }}>Var</th>
            </tr>
          </thead>
          <tbody>
            {pairs.map(pair => (
              <tr key={pair.target_candle_open}>
                <td style={{ ...cellBase, color: 'var(--text-secondary)' }}>
                  {formatShortDate(pair.target_candle_open)}
                </td>
                <td style={{ ...cellBase, textAlign: 'center' }}>
                  <DirectionIcon direction={pair.control.direction} size="sm" />
                </td>
                <td style={{ ...cellBase, textAlign: 'right', color: 'var(--text-primary)' }}>
                  {(pair.control.confidence * 100).toFixed(0)}%
                </td>
                <td style={{ ...cellBase, textAlign: 'center' }}>
                  <DirectionIcon direction={pair.variant.direction} size="sm" />
                </td>
                <td style={{ ...cellBase, textAlign: 'right', color: 'var(--text-primary)' }}>
                  {(pair.variant.confidence * 100).toFixed(0)}%
                </td>
                <td style={{ ...cellBase, textAlign: 'center' }}>
                  {pair.control.actual_direction
                    ? <DirectionIcon direction={pair.control.actual_direction} size="sm" />
                    : <span style={{ color: 'var(--text-muted)' }}>—</span>
                  }
                </td>
                <td style={{ ...cellBase, textAlign: 'center' }}>
                  <Badge result={pair.control.is_correct} />
                </td>
                <td style={{ ...cellBase, textAlign: 'center' }}>
                  <Badge result={pair.variant.is_correct} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
