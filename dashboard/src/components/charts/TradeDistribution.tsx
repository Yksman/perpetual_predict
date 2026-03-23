import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip, Cell, ReferenceLine } from 'recharts';
import { Panel } from '../common/Panel';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Trade } from '../../types';

interface TradeDistributionProps {
  trades: Trade[];
}

export function TradeDistribution({ trades }: TradeDistributionProps) {
  const isMobile = useIsMobile();

  const data = useMemo(() => {
    const closedTrades = trades.filter(t => t.return_pct !== null);
    if (closedTrades.length === 0) return [];

    const bucketSize = 1;
    const buckets: Record<number, number> = {};

    for (const t of closedTrades) {
      const bucket = Math.floor(t.return_pct! / bucketSize) * bucketSize;
      buckets[bucket] = (buckets[bucket] || 0) + 1;
    }

    return Object.entries(buckets)
      .map(([range, count]) => ({
        range: `${parseFloat(range)}%`,
        rangeNum: parseFloat(range),
        count,
      }))
      .sort((a, b) => a.rangeNum - b.rangeNum);
  }, [trades]);

  if (data.length === 0) {
    return (
      <Panel title="Return Distribution">
        <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', textAlign: 'center', padding: '60px 0' }}>
          No data yet
        </div>
      </Panel>
    );
  }

  const tickFontSize = isMobile ? 8 : 9;

  return (
    <Panel title="Return Distribution (%)">
      <ResponsiveContainer width="100%" height={isMobile ? 180 : 220}>
        <BarChart data={data}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="range"
            tick={{ fill: 'var(--text-muted)', fontSize: tickFontSize, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
            interval={isMobile ? 1 : 0}
          />
          <YAxis
            tick={{ fill: 'var(--text-muted)', fontSize: isMobile ? 9 : 10, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
            width={isMobile ? 25 : 35}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border)',
              borderRadius: '4px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.75rem',
            }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            formatter={(value: any) => [value, 'Trades']}
          />
          <ReferenceLine x="0%" stroke="var(--text-muted)" strokeDasharray="5 5" />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.rangeNum >= 0 ? 'var(--color-long)' : 'var(--color-short)'}
                fillOpacity={0.7}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Panel>
  );
}
