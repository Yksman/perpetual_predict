import { Panel } from '../common/Panel';
import { formatShortDate, formatPrice, formatPnl } from '../../utils/format';
import type { Trade } from '../../types';
import { motion } from 'framer-motion';

interface TradeTableProps {
  trades: Trade[];
  limit?: number;
}

export function TradeTable({ trades, limit = 20 }: TradeTableProps) {
  const sorted = [...trades]
    .filter(t => t.exit_time)
    .sort((a, b) => (b.exit_time || '').localeCompare(a.exit_time || ''))
    .slice(0, limit);

  return (
    <Panel title="Recent Trades">
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Exit Time', 'Side', 'Leverage', 'Entry', 'Exit', 'Net PnL', 'Return'].map(h => (
                <th key={h} style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: '0.65rem',
                  fontWeight: 500,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: 'var(--text-secondary)',
                  padding: '10px 12px',
                  textAlign: h === 'Exit Time' || h === 'Side' ? 'left' : 'right',
                  borderBottom: '1px solid var(--border)',
                  whiteSpace: 'nowrap',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((t, i) => {
              const pnlColor = (t.net_pnl ?? 0) >= 0 ? 'var(--color-long)' : 'var(--color-short)';
              return (
                <motion.tr
                  key={t.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.03 }}
                  style={{ cursor: 'default' }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLElement).style.background = 'var(--bg-tertiary)';
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLElement).style.background = 'transparent';
                  }}
                >
                  <td style={cellStyle()}>
                    {t.exit_time ? formatShortDate(t.exit_time) : '—'}
                  </td>
                  <td style={cellStyle()}>
                    <span style={{
                      color: t.side === 'LONG' ? 'var(--color-long)' : 'var(--color-short)',
                      fontWeight: 600,
                    }}>
                      {t.side}
                    </span>
                  </td>
                  <td style={cellStyle('right')}>{t.leverage}x</td>
                  <td style={cellStyle('right')}>${formatPrice(t.entry_price)}</td>
                  <td style={cellStyle('right')}>
                    {t.exit_price ? `$${formatPrice(t.exit_price)}` : '—'}
                  </td>
                  <td style={{
                    ...cellStyle('right'),
                    color: pnlColor,
                    background: (t.net_pnl ?? 0) >= 0 ? 'var(--color-long-dim)' : 'var(--color-short-dim)',
                  }}>
                    ${formatPnl(t.net_pnl ?? 0)}
                  </td>
                  <td style={{ ...cellStyle('right'), color: pnlColor }}>
                    {t.return_pct !== null
                      ? `${t.return_pct >= 0 ? '+' : ''}${t.return_pct.toFixed(2)}%`
                      : '—'}
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function cellStyle(align: 'left' | 'right' = 'left'): React.CSSProperties {
  return {
    padding: '10px 12px',
    textAlign: align,
    borderBottom: '1px solid var(--border)',
    fontFamily: 'var(--font-mono)',
    fontSize: '0.75rem',
    whiteSpace: 'nowrap',
    transition: 'background 0.15s',
  };
}
