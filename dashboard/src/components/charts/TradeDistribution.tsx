import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip, Cell, ReferenceLine } from 'recharts';
import { Panel } from '../common/Panel';
import type { Trade } from '../../types';

interface TradeDistributionProps {
  trades: Trade[];
}

export function TradeDistribution({ trades }: TradeDistributionProps) {
  const data = useMemo(() => {
    const closedTrades = trades.filter(t => t.return_pct !== null);
    if (closedTrades.length === 0) return [];

    // Create histogram buckets
    const bucketSize = 1; // 1% buckets
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

  return (
    <Panel title="Return Distribution (%)">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="range"
            tick={{ fill: 'var(--text-muted)', fontSize: 9, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
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
