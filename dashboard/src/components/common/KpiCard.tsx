import { CountUp } from './CountUp';

interface KpiCardProps {
  label: string;
  value: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
  colorize?: boolean;
}

export function KpiCard({ label, value, decimals = 1, suffix = '', prefix = '', colorize = false }: KpiCardProps) {
  let color = 'var(--text-primary)';
  if (colorize) {
    if (value > 0) color = 'var(--color-long)';
    else if (value < 0) color = 'var(--color-short)';
  }

  return (
    <div style={{
      background: 'var(--bg-tertiary)',
      border: '1px solid var(--border)',
      padding: '16px 20px',
      transition: 'border-color 0.15s, transform 0.15s',
      cursor: 'default',
    }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'var(--border-active)';
        e.currentTarget.style.transform = 'translateY(-1px)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'var(--border)';
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      <div style={{
        fontFamily: 'var(--font-display)',
        fontSize: '0.65rem',
        fontWeight: 500,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        color: 'var(--text-secondary)',
        marginBottom: '8px',
      }}>
        {label}
      </div>
      <CountUp
        end={value}
        decimals={decimals}
        prefix={colorize && value > 0 ? '+' : prefix}
        suffix={suffix}
        style={{
          fontSize: '1.75rem',
          fontWeight: 700,
          color,
          lineHeight: 1.1,
        }}
      />
    </div>
  );
}
