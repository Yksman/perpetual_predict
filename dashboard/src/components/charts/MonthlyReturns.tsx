import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip, Cell, ReferenceLine } from 'recharts';
import { Panel } from '../common/Panel';
import { useIsMobile } from '../../hooks/useMediaQuery';

interface MonthlyReturnsProps {
  monthlyReturns: Record<string, number>;
}

export function MonthlyReturns({ monthlyReturns }: MonthlyReturnsProps) {
  const isMobile = useIsMobile();

  const data = Object.entries(monthlyReturns).map(([month, value]) => ({
    month: month.slice(2),
    value,
  }));

  if (data.length === 0) {
    return (
      <Panel title="Monthly Returns">
        <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', textAlign: 'center', padding: '60px 0' }}>
          No data yet
        </div>
      </Panel>
    );
  }

  const tickFontSize = isMobile ? 9 : 10;

  return (
    <Panel title="Monthly Returns (%)">
      <ResponsiveContainer width="100%" height={isMobile ? 180 : 220}>
        <BarChart data={data}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="month"
            tick={{ fill: 'var(--text-muted)', fontSize: tickFontSize, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: 'var(--text-muted)', fontSize: tickFontSize, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
            tickFormatter={v => `${v}%`}
            width={isMobile ? 35 : 45}
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
            formatter={(value: any) => [`${value > 0 ? '+' : ''}${Number(value).toFixed(2)}%`, 'Return']}
          />
          <ReferenceLine y={0} stroke="var(--text-muted)" />
          <Bar dataKey="value" radius={[2, 2, 0, 0]}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.value >= 0 ? 'var(--color-long)' : 'var(--color-short)'}
                fillOpacity={0.8}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Panel>
  );
}
