import { motion } from 'framer-motion';
import { EquityCurve } from '../components/charts/EquityCurve';
import { MonthlyReturns } from '../components/charts/MonthlyReturns';
import { TradeDistribution } from '../components/charts/TradeDistribution';
import { TradeTable } from '../components/tables/TradeTable';
import { useIsMobile } from '../hooks/useMediaQuery';
import type { Trade, MetricsData } from '../types';

interface TradingPageProps {
  trades: Trade[];
  metrics: MetricsData;
}

export function TradingPage({ trades, metrics }: TradingPageProps) {
  const isMobile = useIsMobile();

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      <EquityCurve
        equityCurve={metrics.equity_curve}
        currentBalance={metrics.account.current_balance}
      />
      <div style={{
        display: 'grid',
        gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1fr) minmax(0, 1fr)',
        gap: 'var(--gap)',
        marginTop: 'var(--gap)',
        background: 'var(--border)',
      }}>
        <MonthlyReturns monthlyReturns={metrics.monthly_returns} />
        <TradeDistribution trades={trades} />
      </div>
      <div style={{ marginTop: 'var(--gap)' }}>
        <TradeTable trades={trades} />
      </div>
    </motion.div>
  );
}
