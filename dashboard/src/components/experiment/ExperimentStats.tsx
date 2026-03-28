import { Panel } from '../common/Panel';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Experiment } from '../../types';

interface ExperimentStatsProps {
  experiment: Experiment;
}

function formatVariantLabel(name: string): string {
  return name.replace(/_/g, ' ');
}

export function ExperimentStats({ experiment }: ExperimentStatsProps) {
  const isMobile = useIsMobile();
  const r = experiment.result;
  const remaining = Math.max(0, experiment.min_samples - experiment.sample_size);
  const variants = r?.variant_results ?? [];

  return (
    <Panel title="Statistical Test">
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}>
        {/* Per-variant p-values */}
        <div style={{
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          gap: isMobile ? '12px' : '24px',
          flexWrap: 'wrap',
        }}>
          {variants.map(v => (
            <div key={v.variant_name} style={{
              textAlign: isMobile ? 'center' : 'left',
              minWidth: '120px',
            }}>
              <div style={{
                fontFamily: 'var(--font-display)',
                fontSize: '0.6rem',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                color: 'var(--text-secondary)',
                marginBottom: '2px',
              }}>
                {formatVariantLabel(v.variant_name)}
              </div>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: isMobile ? '1.2rem' : '1.5rem',
                fontWeight: 700,
                color: v.p_value != null
                  ? (v.is_significant ? 'var(--color-long)' : 'var(--text-primary)')
                  : 'var(--text-muted)',
              }}>
                {v.p_value != null ? v.p_value.toFixed(4) : '—'}
              </div>
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '1px 8px',
                borderRadius: '999px',
                fontSize: '0.6rem',
                fontFamily: 'var(--font-mono)',
                fontWeight: 500,
                marginTop: '4px',
                ...(v.is_significant ? {
                  color: 'var(--color-long)',
                  background: 'var(--color-long-dim)',
                } : {
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border)',
                }),
              }}>
                {v.is_significant ? 'Significant' : 'Not Significant'}
              </span>
            </div>
          ))}
        </div>

        {/* Alpha + winner/progress */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            color: 'var(--text-muted)',
          }}>
            alpha = {experiment.significance_level}
          </div>

          {/* Winner or progress */}
          {experiment.winner ? (
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.8rem',
              color: 'var(--color-accent)',
              fontWeight: 600,
            }}>
              Winner: {formatVariantLabel(experiment.winner)}
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
