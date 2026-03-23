import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { Panel } from '../common/Panel';
import type { MetricsData } from '../../types';

interface DirectionDonutProps {
  accuracy: MetricsData['prediction_accuracy'];
}

const COLORS: Record<string, string> = {
  UP: '#00dc82',
  DOWN: '#ff3b5c',
  NEUTRAL: '#ffb800',
};

export function DirectionDonut({ accuracy }: DirectionDonutProps) {
  const data = Object.entries(accuracy.by_direction).map(([dir, val]) => ({
    name: dir,
    value: val.total,
    correct: val.correct,
  }));

  return (
    <Panel title="Direction Distribution">
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={85}
            dataKey="value"
            stroke="var(--bg-secondary)"
            strokeWidth={2}
          >
            {data.map(entry => (
              <Cell key={entry.name} fill={COLORS[entry.name] || '#666'} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border)',
              borderRadius: '4px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.75rem',
              color: 'var(--text-primary)',
            }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            formatter={(value: any, _name: any, props: any) => {
              const { correct } = props.payload;
              return [`${value} total, ${correct} correct`, ''];
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        gap: '20px',
        marginTop: '8px',
      }}>
        {data.map(d => (
          <div key={d.name} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            color: 'var(--text-secondary)',
          }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '2px',
              background: COLORS[d.name],
            }} />
            {d.name}
          </div>
        ))}
      </div>
    </Panel>
  );
}
