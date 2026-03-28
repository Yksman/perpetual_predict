import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Experiment } from '../../types';

interface ExperimentSelectorProps {
  experiments: Experiment[];
  selectedId: string;
  onSelect: (id: string) => void;
}

const statusColors: Record<string, string> = {
  active: 'var(--color-long)',
  paused: 'var(--color-neutral)',
  completed: 'var(--color-accent)',
};

export function ExperimentSelector({ experiments, selectedId, onSelect }: ExperimentSelectorProps) {
  const isMobile = useIsMobile();

  return (
    <div style={{
      display: 'flex',
      gap: '8px',
      padding: isMobile ? '12px 14px' : '16px 24px',
      overflowX: 'auto',
      WebkitOverflowScrolling: 'touch',
    }}
    className="hide-scrollbar"
    >
      {experiments.map(exp => {
        const isSelected = exp.experiment_id === selectedId;
        return (
          <button
            key={exp.experiment_id}
            onClick={() => onSelect(exp.experiment_id)}
            style={{
              flexShrink: 0,
              minWidth: isMobile ? '200px' : '240px',
              padding: '12px 16px',
              background: isSelected ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
              border: `1px solid ${isSelected ? 'var(--color-accent)' : 'var(--border)'}`,
              cursor: 'pointer',
              textAlign: 'left',
              transition: 'border-color 0.15s',
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '6px',
            }}>
              <span style={{
                fontFamily: 'var(--font-display)',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: 'var(--text-primary)',
              }}>
                {exp.name}
              </span>
              <span style={{
                padding: '1px 8px',
                borderRadius: '999px',
                fontSize: '0.6rem',
                fontFamily: 'var(--font-mono)',
                fontWeight: 500,
                textTransform: 'uppercase',
                color: statusColors[exp.status] ?? 'var(--text-secondary)',
                border: `1px solid ${statusColors[exp.status] ?? 'var(--border)'}`,
              }}>
                {exp.status}
              </span>
            </div>
            <div style={{
              display: 'flex',
              gap: '4px',
              flexWrap: 'wrap',
              marginBottom: '8px',
            }}>
              <span style={{
                padding: '1px 6px',
                fontSize: '0.6rem',
                fontFamily: 'var(--font-mono)',
                color: 'var(--color-accent)',
                border: '1px solid var(--border)',
                borderRadius: '3px',
              }}>
                {Object.keys(exp.variant_diffs).length} variant{Object.keys(exp.variant_diffs).length !== 1 ? 's' : ''}
              </span>
              {Object.entries(exp.variant_diffs).flatMap(([, diff]) => [
                ...diff.added.map(m => ({ mod: m, type: 'added' as const })),
                ...diff.removed.map(m => ({ mod: m, type: 'removed' as const })),
              ])
                .filter((item, idx, arr) => arr.findIndex(a => a.mod === item.mod && a.type === item.type) === idx)
                .map(item => (
                  <span key={`${item.type}-${item.mod}`} style={{
                    padding: '1px 6px',
                    fontSize: '0.6rem',
                    fontFamily: 'var(--font-mono)',
                    color: item.type === 'added' ? 'var(--color-long)' : 'var(--color-short)',
                    background: item.type === 'added' ? 'var(--color-long-dim)' : 'var(--color-short-dim)',
                    borderRadius: '3px',
                  }}>
                    {item.type === 'added' ? '+' : '-'}{item.mod}
                  </span>
                ))
              }
            </div>
            {/* Progress bar */}
            <div style={{
              height: '3px',
              background: 'var(--border)',
              borderRadius: '2px',
              overflow: 'hidden',
            }}>
              <div style={{
                height: '100%',
                width: `${exp.progress_pct}%`,
                background: 'var(--color-accent)',
                borderRadius: '2px',
                transition: 'width 0.3s ease',
              }} />
            </div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: 'var(--text-muted)',
              marginTop: '4px',
            }}>
              {exp.sample_size}/{exp.min_samples} samples
            </div>
          </button>
        );
      })}
    </div>
  );
}
