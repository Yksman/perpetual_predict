import { Panel } from '../common/Panel';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Experiment } from '../../types';

interface ExperimentStatsProps {
  experiment: Experiment;
}

export function ExperimentStats({ experiment }: ExperimentStatsProps) {
  const isMobile = useIsMobile();
  const r = experiment.result;
  const remaining = Math.max(0, experiment.min_samples - experiment.sample_size);

  return (
    <Panel title="Statistical Test">
      <div style={{
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? '16px' : '32px',
        alignItems: isMobile ? 'stretch' : 'center',
      }}>
        {/* P-value display */}
        <div style={{ textAlign: isMobile ? 'center' : 'left' }}>
          <div style={{
            fontFamily: 'var(--font-display)',
            fontSize: '0.65rem',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: 'var(--text-secondary)',
            marginBottom: '4px',
          }}>
            p-value
          </div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: isMobile ? '1.5rem' : '2rem',
            fontWeight: 700,
            color: r?.p_value != null
              ? (r.is_significant ? 'var(--color-long)' : 'var(--text-primary)')
              : 'var(--text-muted)',
          }}>
            {r?.p_value != null ? r.p_value.toFixed(4) : '—'}
          </div>
        </div>

        {/* Significance + alpha */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          flex: 1,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '2px 10px',
              borderRadius: '999px',
              fontSize: '0.7rem',
              fontFamily: 'var(--font-mono)',
              fontWeight: 500,
              ...(r?.is_significant ? {
                color: 'var(--color-long)',
                background: 'var(--color-long-dim)',
              } : {
                color: 'var(--text-secondary)',
                border: '1px solid var(--border)',
              }),
            }}>
              {r?.is_significant ? 'Significant' : 'Not Significant'}
            </span>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              color: 'var(--text-muted)',
            }}>
              alpha = {experiment.significance_level}
            </span>
          </div>

          {/* Winner or progress */}
          {r?.recommended_winner ? (
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.8rem',
              color: 'var(--color-accent)',
              fontWeight: 600,
            }}>
              Winner: {r.recommended_winner}
            </div>
          ) : remaining > 0 ? (
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
            }}>
              {remaining} more sample{remaining !== 1 ? 's' : ''} needed
            </div>
          ) : null}

          {/* Progress bar */}
          <div>
            <div style={{
              height: '4px',
              background: 'var(--border)',
              borderRadius: '2px',
              overflow: 'hidden',
              maxWidth: isMobile ? '100%' : '300px',
            }}>
              <div style={{
                height: '100%',
                width: `${experiment.progress_pct}%`,
                background: experiment.progress_pct >= 100 ? 'var(--color-long)' : 'var(--color-accent)',
                borderRadius: '2px',
                transition: 'width 0.3s ease',
              }} />
            </div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: 'var(--text-muted)',
              marginTop: '2px',
            }}>
              {experiment.sample_size} / {experiment.min_samples} ({experiment.progress_pct.toFixed(0)}%)
            </div>
          </div>
        </div>
      </div>
    </Panel>
  );
}
