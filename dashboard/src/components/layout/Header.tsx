import { formatTimeAgo } from '../../utils/format';
import { useIsMobile } from '../../hooks/useMediaQuery';

interface HeaderProps {
  exportedAt: string | null;
}

export function Header({ exportedAt }: HeaderProps) {
  const isMobile = useIsMobile();

  return (
    <header style={{
      display: 'flex',
      alignItems: isMobile ? 'flex-start' : 'center',
      flexDirection: isMobile ? 'column' : 'row',
      justifyContent: 'space-between',
      padding: 'var(--header-padding)',
      gap: isMobile ? '6px' : '12px',
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg-secondary)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? '8px' : '12px' }}>
        <div style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: 'var(--color-long)',
          boxShadow: 'var(--glow-long)',
          flexShrink: 0,
        }} />
        <h1 style={{
          fontFamily: 'var(--font-display)',
          fontSize: isMobile ? '0.95rem' : '1.1rem',
          fontWeight: 700,
          letterSpacing: '-0.01em',
        }}>
          {isMobile ? 'PP' : 'Perpetual Predict'}
        </h1>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.65rem',
          color: 'var(--text-muted)',
          padding: '2px 8px',
          border: '1px solid var(--border)',
          borderRadius: '4px',
          whiteSpace: 'nowrap',
        }}>
          BTCUSDT.P · 4H
        </span>
      </div>

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '0.7rem',
        color: 'var(--text-secondary)',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        ...(isMobile ? { paddingLeft: '16px' } : {}),
      }}>
        {exportedAt && (
          <>
            <span style={{ color: 'var(--text-muted)' }}>Updated</span>
            {formatTimeAgo(exportedAt)}
          </>
        )}
      </div>
    </header>
  );
}
