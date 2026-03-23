import { CountUp } from './CountUp';
import { useIsMobile } from '../../hooks/useMediaQuery';

interface KpiCardProps {
  label: string;
  value: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
  colorize?: boolean;
}

export function KpiCard({ label, value, decimals = 1, suffix = '', prefix = '', colorize = false }: KpiCardProps) {
  const isMobile = useIsMobile();

  let color = 'var(--text-primary)';
  if (colorize) {
    if (value > 0) color = 'var(--color-long)';
    else if (value < 0) color = 'var(--color-short)';
  }

  return (
    <div
      className="touch-feedback"
      style={{
        background: 'var(--bg-tertiary)',
        border: '1px solid var(--border)',
        padding: 'var(--kpi-padding)',
        transition: 'border-color 0.15s, transform 0.15s',
        cursor: 'default',
        ...(isMobile ? {
          minWidth: '140px',
          scrollSnapAlign: 'start',
          flexShrink: 0,
        } : {}),
      }}
      onMouseEnter={isMobile ? undefined : e => {
        e.currentTarget.style.borderColor = 'var(--border-active)';
        e.currentTarget.style.transform = 'translateY(-1px)';
      }}
      onMouseLeave={isMobile ? undefined : e => {
        e.currentTarget.style.borderColor = 'var(--border)';
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      <div style={{
        fontFamily: 'var(--font-display)',
        fontSize: '0.65rem',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        color: 'var(--text-secondary)',
        marginBottom: isMobile ? '6px' : '8px',
      }}>
        {label}
      </div>
      <CountUp
        end={value}
        decimals={decimals}
        prefix={colorize && value > 0 ? '+' : prefix}
        suffix={suffix}
        style={{
          fontSize: 'var(--kpi-value-size)',
          fontWeight: 700,
          color,
          lineHeight: 1.1,
        }}
      />
    </div>
  );
}
