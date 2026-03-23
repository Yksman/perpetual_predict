export function Footer() {
  return (
    <footer style={{
      padding: '16px 24px',
      borderTop: '1px solid var(--border)',
      textAlign: 'center',
      fontFamily: 'var(--font-mono)',
      fontSize: '0.65rem',
      color: 'var(--text-muted)',
      display: 'flex',
      justifyContent: 'center',
      gap: '16px',
    }}>
      <span>Powered by Claude</span>
      <span>·</span>
      <a
        href="https://github.com/kevjbrave/perpetual_predict"
        target="_blank"
        rel="noopener noreferrer"
        style={{ color: 'var(--text-secondary)' }}
      >
        GitHub
      </a>
    </footer>
  );
}
