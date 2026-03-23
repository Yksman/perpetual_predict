import { AreaChart, Area, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip } from 'recharts';
import { Panel } from '../common/Panel';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { MetricsData } from '../../types';
import { formatPrice } from '../../utils/format';

interface EquityCurveProps {
  equityCurve: MetricsData['equity_curve'];
  currentBalance: number;
}

export function EquityCurve({ equityCurve, currentBalance }: EquityCurveProps) {
  const isMobile = useIsMobile();

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

  const balanceDisplay = (
    <div style={{
      textAlign: isMobile ? 'left' : 'right',
      minWidth: isMobile ? undefined : '120px',
      paddingTop: isMobile ? '0' : '20px',
      ...(isMobile ? { marginBottom: '8px' } : {}),
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
        fontSize: isMobile ? '1.25rem' : '1.5rem',
        fontWeight: 700,
        color: 'var(--color-long)',
        textShadow: '0 0 12px #00dc8240',
      }}>
        ${formatPrice(currentBalance)}
      </div>
    </div>
  );

  const tickFontSize = isMobile ? 9 : 10;

  return (
    <Panel title="Equity Curve">
      {isMobile && balanceDisplay}
      <div style={{
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        alignItems: isMobile ? 'stretch' : 'flex-start',
        gap: isMobile ? '0' : '24px',
      }}>
        <div style={{ flex: 1 }}>
          <ResponsiveContainer width="100%" height={isMobile ? 180 : 250}>
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
                tickFormatter={v => isMobile ? `$${(v / 1000).toFixed(0)}K` : `$${v.toFixed(0)}`}
                width={isMobile ? 40 : 60}
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
        {!isMobile && balanceDisplay}
      </div>
    </Panel>
  );
}
