import { Panel } from '../common/Panel';
import { Badge } from '../common/Badge';
import { DirectionIcon } from '../common/DirectionIcon';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { ExperimentPredictionComparison } from '../../types';
import { formatShortDate } from '../../utils/format';

interface ExperimentPredictionPairsProps {
  comparisons: ExperimentPredictionComparison[];
}

function formatArmLabel(key: string): string {
  if (key === 'control') return 'Control';
  return key.replace(/^variant_/, '').replace(/_/g, ' ');
}

export function ExperimentPredictionPairs({ comparisons }: ExperimentPredictionPairsProps) {
  const isMobile = useIsMobile();

  if (comparisons.length === 0) {
    return (
      <Panel title="Prediction Comparison">
        <div style={{
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          textAlign: 'center',
          padding: '40px 0',
        }}>
          No predictions yet
        </div>
      </Panel>
    );
  }

  // Get arm keys from the first comparison entry
  const armKeys = Object.keys(comparisons[0].arms);
  // Find a control arm to get actual_direction from
  const controlKey = armKeys.find(k => k === 'control') ?? armKeys[0];

  if (isMobile) {
    return (
      <Panel title="Prediction Comparison">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {comparisons.map(comp => {
            const controlArm = comp.arms[controlKey];
            return (
              <div
                key={comp.target_candle_open}
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
                  {formatShortDate(comp.target_candle_open)}
                  {controlArm?.actual_direction && (
                    <span style={{ marginLeft: '8px' }}>
                      Actual: <DirectionIcon direction={controlArm.actual_direction} size="sm" />
                    </span>
                  )}
                </div>
                {armKeys.map(key => {
                  const arm = comp.arms[key];
                  if (!arm) return null;
                  return (
                    <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <span style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.6rem',
                        color: key === 'control' ? 'var(--text-muted)' : 'var(--color-accent)',
                        width: '80px',
                        flexShrink: 0,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}>
                        {formatArmLabel(key)}
                      </span>
                      <DirectionIcon direction={arm.direction} size="sm" />
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-primary)' }}>
                        {(arm.confidence * 100).toFixed(0)}%
                      </span>
                      <Badge result={arm.is_correct} />
                    </div>
                  );
                })}
              </div>
            );
          })}
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
              {armKeys.map(key => (
                <th key={`${key}-dir`} style={{ ...headerStyle, textAlign: 'center' }}>
                  {formatArmLabel(key)} Dir
                </th>
              ))}
              {armKeys.map(key => (
                <th key={`${key}-conf`} style={{ ...headerStyle, textAlign: 'right' }}>
                  {formatArmLabel(key)} Conf
                </th>
              ))}
              <th style={{ ...headerStyle, textAlign: 'center' }}>Actual</th>
              {armKeys.map(key => (
                <th key={`${key}-result`} style={{ ...headerStyle, textAlign: 'center' }}>
                  {formatArmLabel(key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {comparisons.map(comp => {
              const controlArm = comp.arms[controlKey];
              return (
                <tr key={comp.target_candle_open}>
                  <td style={{ ...cellBase, color: 'var(--text-secondary)' }}>
                    {formatShortDate(comp.target_candle_open)}
                  </td>
                  {armKeys.map(key => (
                    <td key={`${key}-dir`} style={{ ...cellBase, textAlign: 'center' }}>
                      {comp.arms[key] ? <DirectionIcon direction={comp.arms[key].direction} size="sm" /> : '—'}
                    </td>
                  ))}
                  {armKeys.map(key => (
                    <td key={`${key}-conf`} style={{ ...cellBase, textAlign: 'right', color: 'var(--text-primary)' }}>
                      {comp.arms[key] ? `${(comp.arms[key].confidence * 100).toFixed(0)}%` : '—'}
                    </td>
                  ))}
                  <td style={{ ...cellBase, textAlign: 'center' }}>
                    {controlArm?.actual_direction
                      ? <DirectionIcon direction={controlArm.actual_direction} size="sm" />
                      : <span style={{ color: 'var(--text-muted)' }}>—</span>
                    }
                  </td>
                  {armKeys.map(key => (
                    <td key={`${key}-result`} style={{ ...cellBase, textAlign: 'center' }}>
                      {comp.arms[key] ? <Badge result={comp.arms[key].is_correct} /> : '—'}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
