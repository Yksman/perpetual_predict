import type { CSSProperties, ReactNode } from 'react';

interface PanelProps {
  title?: string;
  children: ReactNode;
  style?: CSSProperties;
  className?: string;
}

export function Panel({ title, children, style, className = '' }: PanelProps) {
  return (
    <div className={`panel ${className}`} style={style}>
      {title && (
        <h3 style={{
          fontFamily: 'var(--font-display)',
          fontSize: '0.8rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          color: 'var(--text-secondary)',
          marginBottom: '16px',
        }}>
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}
