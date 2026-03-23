interface TabNavProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const tabs = [
  { id: 'predictions', label: 'Predictions' },
  { id: 'trading', label: 'Trading' },
];

export function TabNav({ activeTab, onTabChange }: TabNavProps) {
  return (
    <nav style={{
      display: 'flex',
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg-secondary)',
    }}>
      {tabs.map(tab => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '0.8rem',
            fontWeight: activeTab === tab.id ? 600 : 400,
            letterSpacing: '0.03em',
            textTransform: 'uppercase',
            padding: '12px 24px',
            border: 'none',
            borderBottom: activeTab === tab.id
              ? '2px solid var(--color-accent)'
              : '2px solid transparent',
            background: 'none',
            color: activeTab === tab.id
              ? 'var(--text-primary)'
              : 'var(--text-secondary)',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
