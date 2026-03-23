import type { Direction } from '../../types';

interface DirectionIconProps {
  direction: Direction;
  size?: 'sm' | 'md' | 'lg';
}

const sizeMap = { sm: '0.75rem', md: '1rem', lg: '1.25rem' };

const config: Record<Direction, { symbol: string; color: string }> = {
  UP: { symbol: '▲', color: 'var(--color-long)' },
  DOWN: { symbol: '▼', color: 'var(--color-short)' },
  NEUTRAL: { symbol: '◆', color: 'var(--color-neutral)' },
};

export function DirectionIcon({ direction, size = 'md' }: DirectionIconProps) {
  const { symbol, color } = config[direction];
  return (
    <span style={{
      color,
      fontSize: sizeMap[size],
      fontWeight: 700,
      lineHeight: 1,
    }}>
      {symbol}
    </span>
  );
}
