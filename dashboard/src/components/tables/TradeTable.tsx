import { Panel } from '../common/Panel';
import { formatShortDate, formatPrice, formatPnl } from '../../utils/format';
import { useIsMobile } from '../../hooks/useMediaQuery';
import type { Trade } from '../../types';
import { motion } from 'framer-motion';

interface TradeTableProps {
  trades: Trade[];
  limit?: number;
}

export function TradeTable({ trades, limit = 20 }: TradeTableProps) {
  const isMobile = useIsMobile();
  const sorted = [...trades]
    .filter(t => t.exit_time)
    .sort((a, b) => (b.exit_time || '').localeCompare(a.exit_time || ''))
    .slice(0, limit);

  if (isMobile) {
    return (
      <Panel title="Recent Trades">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {sorted.map((t, i) => {
            const pnlColor = (t.net_pnl ?? 0) >= 0 ? 'var(--color-long)' : 'var(--color-short)';
            return (
              <motion.div
                key={t.id}
                className="touch-feedback"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.02 }}
                style={{
                  padding: '12px 0',
                  borderBottom: i < sorted.length - 1 ? '1px solid var(--border)' : 'none',
                }}
              >
                {/* Row 1: Time + PnL */}
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '4px',
                }}>
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.7rem',
                    color: 'var(--text-secondary)',
                  }}>
                    {t.exit_time ? formatShortDate(t.exit_time) : '—'}
                  </span>
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    color: pnlColor,
                    padding: '1px 6px',
                    background: (t.net_pnl ?? 0) >= 0 ? 'var(--color-long-dim)' : 'var(--color-short-dim)',
                    borderRadius: '3px',
                  }}>
                    {(t.net_pnl ?? 0) >= 0 ? '+' : ''}${formatPnl(t.net_pnl ?? 0)}
                  </span>
                </div>
                {/* Row 2: Side + Leverage */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  marginBottom: '6px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.72rem',
                }}>
                  <span style={{
                    color: t.side === 'LONG' ? 'var(--color-long)' : 'var(--color-short)',
                    fontWeight: 600,
                  }}>
                    {t.side === 'LONG' ? '▲' : '▼'} {t.side}
                  </span>
                  <span>
                    <span style={{ color: 'var(--text-muted)' }}>Pos </span>
                    <span style={{ color: 'var(--text-secondary)' }}>{t.position_pct.toFixed(2)}x</span>
                  </span>
                </div>
                {/* Row 3: Entry → Exit + Return */}
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.68rem',
                }}>
                  <span>
                    <span style={{ color: 'var(--text-muted)' }}>Entry </span>
                    <span style={{ color: 'var(--text-secondary)' }}>${formatPrice(t.entry_price)}</span>
                    <span style={{ color: 'var(--text-muted)' }}> → </span>
                    <span style={{ color: 'var(--text-secondary)' }}>{t.exit_price ? `$${formatPrice(t.exit_price)}` : '—'}</span>
                  </span>
                  <span>
                    <span style={{ color: 'var(--text-muted)' }}>Ret </span>
                    <span style={{ color: pnlColor, fontWeight: 600 }}>
                      {t.return_pct !== null
                        ? `${t.return_pct >= 0 ? '+' : ''}${t.return_pct.toFixed(2)}%`
                        : '—'}
                    </span>
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>
      </Panel>
    );
  }

  // Desktop table view
  return (
    <Panel title="Recent Trades">
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Exit Time', 'Side', 'Position', 'Entry', 'Exit', 'Net PnL', 'Return'].map(h => (
                <th key={h} style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: 'var(--text-secondary)',
                  padding: 'var(--cell-padding)',
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
                  <td style={cellStyle('right')}>{t.position_pct.toFixed(2)}x</td>
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
    padding: 'var(--cell-padding)',
    textAlign: align,
    borderBottom: '1px solid var(--border)',
    fontFamily: 'var(--font-mono)',
    fontSize: 'var(--table-font)',
    whiteSpace: 'nowrap',
    transition: 'background 0.15s',
  };
}
