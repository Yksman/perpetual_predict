import { KpiCard } from '../common/KpiCard';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Experiment } from '../../types';

interface ExperimentSummaryProps {
  experiment: Experiment;
}

export function ExperimentSummary({ experiment }: ExperimentSummaryProps) {
  const isMobile = useIsMobile();

  return (
    <div style={{
      display: isMobile ? 'flex' : 'grid',
      gridTemplateColumns: isMobile ? undefined : 'repeat(auto-fit, minmax(160px, 1fr))',
      gap: 'var(--gap)',
      background: 'var(--border)',
      ...(isMobile ? {
        overflowX: 'auto',
        WebkitOverflowScrolling: 'touch',
        scrollSnapType: 'x mandatory',
        padding: '0',
      } : {}),
    }}
    className={isMobile ? 'hide-scrollbar' : ''}
    >
      <KpiCard label="Samples" value={experiment.sample_size} decimals={0} />
      <KpiCard label="Progress" value={experiment.progress_pct} decimals={1} suffix="%" />
      <KpiCard
        label="Control Balance"
        value={experiment.accounts.control.current_balance}
        decimals={2}
        prefix="$"
        colorize
      />
      <KpiCard
        label="Variant Balance"
        value={experiment.accounts.variant.current_balance}
        decimals={2}
        prefix="$"
        colorize
      />
    </div>
  );
}
