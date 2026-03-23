import { AreaChart, Area, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip } from 'recharts';
import { Panel } from '../common/Panel';
import type { MetricsData } from '../../types';
import { formatPrice } from '../../utils/format';

interface EquityCurveProps {
  equityCurve: MetricsData['equity_curve'];
  currentBalance: number;
}

export function EquityCurve({ equityCurve, currentBalance }: EquityCurveProps) {
  const data = equityCurve.map(p => ({
    date: p.time.slice(5, 10),
    balance: p.balance,
  }));

  if (data.length < 2) {
    return (
      <Panel title="Equity Curve">
        <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', textAlign: 'center', padding: '60px 0' }}>
          Not enough data
        </div>
      </Panel>
    );
  }

  const min = Math.min(...data.map(d => d.balance));
  const max = Math.max(...data.map(d => d.balance));
  const padding = (max - min) * 0.1 || 10;

  return (
    <Panel title="Equity Curve">
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '24px' }}>
        <div style={{ flex: 1 }}>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={data}>
              <defs>
                <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00dc82" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#00dc82" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
              <XAxis
                dataKey="date"
                tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                axisLine={{ stroke: 'var(--border)' }}
                tickLine={false}
              />
              <YAxis
                domain={[min - padding, max + padding]}
                tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                axisLine={{ stroke: 'var(--border)' }}
                tickLine={false}
                tickFormatter={v => `$${v.toFixed(0)}`}
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
                formatter={(value: any) => [`$${formatPrice(value)}`, 'Balance']}
              />
              <Area
                type="monotone"
                dataKey="balance"
                stroke="#00dc82"
                strokeWidth={2}
                fill="url(#equityGrad)"
                dot={false}
                activeDot={{ r: 4, fill: '#00dc82', stroke: 'var(--bg-primary)', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div style={{
          textAlign: 'right',
          minWidth: '120px',
          paddingTop: '20px',
        }}>
          <div style={{
            fontFamily: 'var(--font-display)',
            fontSize: '0.65rem',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: 'var(--text-secondary)',
            marginBottom: '4px',
          }}>
            Balance
          </div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '1.5rem',
            fontWeight: 700,
            color: 'var(--color-long)',
            textShadow: '0 0 12px #00dc8240',
          }}>
            ${formatPrice(currentBalance)}
          </div>
        </div>
      </div>
    </Panel>
  );
}
