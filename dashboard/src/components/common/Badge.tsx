interface BadgeProps {
  result: boolean | null;
}

export function Badge({ result }: BadgeProps) {
  if (result === null) {
    return (
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 10px',
        borderRadius: '999px',
        fontSize: '0.7rem',
        fontFamily: 'var(--font-mono)',
        fontWeight: 500,
        border: '1px solid var(--color-neutral)',
        color: 'var(--color-neutral)',
        background: 'var(--color-neutral-dim)',
      }}>
        ⏳ Pending
      </span>
    );
  }

  if (result) {
    return (
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 10px',
        borderRadius: '999px',
        fontSize: '0.7rem',
        fontFamily: 'var(--font-mono)',
        fontWeight: 500,
        color: 'var(--color-long)',
        background: 'var(--color-long-dim)',
      }}>
        ✓ Correct
      </span>
    );
  }

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
      padding: '2px 10px',
      borderRadius: '999px',
      fontSize: '0.7rem',
      fontFamily: 'var(--font-mono)',
      fontWeight: 500,
      color: 'var(--color-short)',
      background: 'var(--color-short-dim)',
    }}>
      ✗ Wrong
    </span>
  );
}
