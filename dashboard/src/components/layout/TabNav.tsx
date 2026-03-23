import { useIsMobile } from '../../hooks/useMediaQuery';

interface TabNavProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const tabs = [
  { id: 'predictions', label: 'Predictions' },
  { id: 'trading', label: 'Trading' },
];

export function TabNav({ activeTab, onTabChange }: TabNavProps) {
  const isMobile = useIsMobile();

  return (
    <nav style={{
      position: 'sticky',
      top: 0,
      zIndex: 100,
      display: 'flex',
      borderBottom: '1px solid var(--border)',
      background: isMobile ? 'rgba(12, 12, 20, 0.85)' : 'var(--bg-secondary)',
      backdropFilter: isMobile ? 'blur(12px)' : 'none',
      WebkitBackdropFilter: isMobile ? 'blur(12px)' : 'none',
    }}>
      {tabs.map(tab => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            style={{
              flex: isMobile ? 1 : 'none',
              fontFamily: 'var(--font-display)',
              fontSize: '0.8rem',
              fontWeight: isActive ? 600 : 400,
              letterSpacing: '0.03em',
              textTransform: 'uppercase',
              padding: isMobile ? '14px 0' : '12px 24px',
              border: 'none',
              borderBottom: isActive
                ? '2px solid var(--color-accent)'
                : '2px solid transparent',
              background: isActive && isMobile
                ? 'rgba(0, 180, 216, 0.06)'
                : 'none',
              color: isActive
                ? 'var(--text-primary)'
                : 'var(--text-secondary)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              minHeight: '44px',
            }}
          >
            {tab.label}
          </button>
        );
      })}
    </nav>
  );
}
