import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { Panel } from '../common/Panel';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Experiment } from '../../types';
import { formatPrice } from '../../utils/format';

interface ExperimentEquityCurveProps {
  experiment: Experiment;
}

export function ExperimentEquityCurve({ experiment }: ExperimentEquityCurveProps) {
  const isMobile = useIsMobile();
  const { control, variant } = experiment.equity_curves;

  // Merge both curves by time
  const timeMap = new Map<string, { date: string; control?: number; variant?: number }>();

  for (const p of control) {
    const date = p.time.slice(5, 10);
    const existing = timeMap.get(p.time) ?? { date };
    existing.control = p.balance;
    timeMap.set(p.time, existing);
  }
  for (const p of variant) {
    const date = p.time.slice(5, 10);
    const existing = timeMap.get(p.time) ?? { date };
    existing.variant = p.balance;
    timeMap.set(p.time, existing);
  }

  const data = Array.from(timeMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([, v]) => v);

  if (data.length < 2) {
    return (
      <Panel title="Equity Curve: Control vs Variant">
        <div style={{
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          textAlign: 'center',
          padding: '60px 0',
        }}>
          Not enough data yet
        </div>
      </Panel>
    );
  }

  const allValues = data.flatMap(d => [d.control, d.variant].filter((v): v is number => v != null));
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const padding = (max - min) * 0.1 || 10;
  const tickFontSize = isMobile ? 9 : 10;

  return (
    <Panel title="Equity Curve: Control vs Variant">
      <ResponsiveContainer width="100%" height={isMobile ? 200 : 280}>
        <LineChart data={data}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tick={{ fill: 'var(--text-muted)', fontSize: tickFontSize, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
            interval={isMobile ? Math.max(0, Math.floor(data.length / 5) - 1) : 'preserveStartEnd'}
          />
          <YAxis
            domain={[min - padding, max + padding]}
            tick={{ fill: 'var(--text-muted)', fontSize: tickFontSize, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
            tickFormatter={v => `$${v.toFixed(0)}`}
            width={isMobile ? 45 : 60}
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
            formatter={(value: any, name: any) => [`$${formatPrice(value)}`, name === 'control' ? 'Control' : 'Variant']}
          />
          <Legend
            wrapperStyle={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
            }}
          />
          <Line
            type="monotone"
            dataKey="control"
            name="Control"
            stroke="#00dc82"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 3 }}
          />
          <Line
            type="monotone"
            dataKey="variant"
            name="Variant"
            stroke="#00b4d8"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Panel>
  );
}
