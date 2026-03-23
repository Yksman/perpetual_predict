import { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip, ReferenceLine } from 'recharts';
import { Panel } from '../common/Panel';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Prediction } from '../../types';

interface AccuracyTimelineProps {
  predictions: Prediction[];
}

export function AccuracyTimeline({ predictions }: AccuracyTimelineProps) {
  const isMobile = useIsMobile();

  const data = useMemo(() => {
    const evaluated = predictions
      .filter(p => p.is_correct !== null)
      .sort((a, b) => a.time.localeCompare(b.time));

    if (evaluated.length < 7) return [];

    const points: Array<{ date: string; accuracy: number }> = [];
    for (let i = 6; i < evaluated.length; i++) {
      const window = evaluated.slice(i - 6, i + 1);
      const correct = window.filter(p => p.is_correct).length;
      points.push({
        date: evaluated[i].time.slice(5, 10),
        accuracy: Math.round((correct / 7) * 100),
      });
    }
    return points;
  }, [predictions]);

  if (data.length === 0) {
    return (
      <Panel title="Accuracy Over Time">
        <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', textAlign: 'center', padding: '60px 0' }}>
          Not enough data (need 7+ evaluated predictions)
        </div>
      </Panel>
    );
  }

  const tickFontSize = isMobile ? 9 : 10;

  return (
    <Panel title={isMobile ? 'Accuracy (7-rolling)' : 'Accuracy Over Time (7-prediction rolling)'}>
      <ResponsiveContainer width="100%" height={isMobile ? 180 : 220}>
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
            domain={[0, 100]}
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
            formatter={(value: any) => [`${value}%`, 'Accuracy']}
          />
          <ReferenceLine y={50} stroke="var(--text-muted)" strokeDasharray="5 5" />
          <Line
            type="monotone"
            dataKey="accuracy"
            stroke="var(--color-accent)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: 'var(--color-accent)' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Panel>
  );
}
