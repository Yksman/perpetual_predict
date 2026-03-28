import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { Panel } from '../common/Panel';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Experiment } from '../../types';
import { formatPrice } from '../../utils/format';

interface ExperimentEquityCurveProps {
  experiment: Experiment;
}

const ARM_COLORS: string[] = [
  '#10b981', // green (control)
  '#3b82f6', // blue
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // purple
  '#ec4899', // pink
  '#14b8a6', // teal
  '#f97316', // orange
];

function getArmColor(index: number): string {
  return ARM_COLORS[index % ARM_COLORS.length];
}

function formatArmLabel(key: string): string {
  if (key === 'control') return 'Control';
  return key.replace(/^variant_/, '').replace(/_/g, ' ');
}

export function ExperimentEquityCurve({ experiment }: ExperimentEquityCurveProps) {
  const isMobile = useIsMobile();
  const curves = experiment.equity_curves;
  const armKeys = Object.keys(curves);

  // Build lookup maps per arm
  const armMaps = new Map<string, Map<string, number>>();
  for (const key of armKeys) {
    armMaps.set(key, new Map(curves[key].map(p => [p.time, p.balance])));
  }

  // Collect all unique timestamps and sort chronologically
  const allTimes = Array.from(
    new Set(armKeys.flatMap(key => curves[key].map(p => p.time))),
  ).sort();

  // Merge into unified timeline with forward-fill
  const lastValues: Record<string, number | undefined> = {};
  const data = allTimes.map(time => {
    const entry: Record<string, string | number | undefined> = {};

    // Format as UTC date label (MM-DD HH:mm)
    const m = time.match(/(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    entry.date = m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : time.slice(5, 16);

    for (const key of armKeys) {
      const map = armMaps.get(key)!;
      if (map.has(time)) lastValues[key] = map.get(time);
      entry[key] = lastValues[key];
    }

    return entry;
  });

  if (data.length < 2) {
    return (
      <Panel title="Equity Curve">
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

  const allValues = data.flatMap(d =>
    armKeys.map(key => d[key]).filter((v): v is number => typeof v === 'number'),
  );
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const padding = (max - min) * 0.1 || 10;
  const tickFontSize = isMobile ? 9 : 10;

  return (
    <Panel title="Equity Curve">
      <ResponsiveContainer width="100%" height={isMobile ? 200 : 280}>
        <LineChart data={data}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tick={{ fill: 'var(--text-muted)', fontSize: tickFontSize, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
            interval={isMobile ? Math.max(0, Math.floor(data.length / 4) - 1) : 'preserveStartEnd'}
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
            formatter={(value: any, name: any) => [`$${formatPrice(value)}`, formatArmLabel(name)]}
          />
          <Legend
            wrapperStyle={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
            }}
          />
          {armKeys.map((key, idx) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              name={formatArmLabel(key)}
              stroke={getArmColor(idx)}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 3 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Panel>
  );
}
