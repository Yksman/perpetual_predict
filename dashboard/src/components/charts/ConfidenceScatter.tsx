import { useMemo } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip, ReferenceLine } from 'recharts';
import { Panel } from '../common/Panel';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Prediction } from '../../types';

interface ConfidenceScatterProps {
  predictions: Prediction[];
}

export function ConfidenceScatter({ predictions }: ConfidenceScatterProps) {
  const isMobile = useIsMobile();

  const data = useMemo(() => {
    const evaluated = predictions.filter(p => p.is_correct !== null);

    const buckets: Record<number, { total: number; correct: number }> = {};
    for (const p of evaluated) {
      const bucket = Math.floor(p.confidence * 10) / 10;
      if (!buckets[bucket]) buckets[bucket] = { total: 0, correct: 0 };
      buckets[bucket].total++;
      if (p.is_correct) buckets[bucket].correct++;
    }

    return Object.entries(buckets).map(([conf, { total, correct }]) => ({
      confidence: parseFloat(conf) * 100,
      accuracy: Math.round((correct / total) * 100),
      count: total,
    }));
  }, [predictions]);

  if (data.length < 3) {
    return (
      <Panel title="Confidence Calibration">
        <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', textAlign: 'center', padding: '60px 0' }}>
          Not enough data
        </div>
      </Panel>
    );
  }

  const tickFontSize = isMobile ? 9 : 10;

  return (
    <Panel title="Confidence Calibration">
      <ResponsiveContainer width="100%" height={isMobile ? 180 : 220}>
        <ScatterChart>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="confidence"
            name="Confidence"
            tick={{ fill: 'var(--text-muted)', fontSize: tickFontSize, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
            tickFormatter={v => `${v}%`}
            domain={[0, 100]}
          />
          <YAxis
            dataKey="accuracy"
            name="Accuracy"
            tick={{ fill: 'var(--text-muted)', fontSize: tickFontSize, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
            tickFormatter={v => `${v}%`}
            domain={[0, 100]}
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
            formatter={(value: any, name: any) => [`${value}%`, name]}
          />
          <ReferenceLine
            segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]}
            stroke="var(--text-muted)"
            strokeDasharray="5 5"
          />
          <Scatter
            data={data}
            fill="var(--color-accent)"
          />
        </ScatterChart>
      </ResponsiveContainer>
    </Panel>
  );
}
