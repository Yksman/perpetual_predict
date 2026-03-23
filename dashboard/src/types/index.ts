export type Direction = 'UP' | 'DOWN' | 'NEUTRAL';

export interface Prediction {
  id: string;
  time: string;
  target_open: string;
  target_close: string;
  direction: Direction;
  confidence: number;
  key_factors: string[];
  reasoning: string;
  leverage: number;
  position_ratio: number;
  is_correct: boolean | null;
  actual_direction: Direction | null;
  actual_price_change: number | null;
  predicted_return: number | null;
  evaluated_at: string | null;
}

export interface PredictionsData {
  predictions: Prediction[];
}

export interface Trade {
  id: string;
  prediction_id: string;
  side: 'LONG' | 'SHORT';
  leverage: number;
  position_size: number;
  position_ratio: number;
  entry_price: number;
  entry_time: string;
  exit_price: number | null;
  exit_time: string | null;
  net_pnl: number | null;
  return_pct: number | null;
  balance_after: number | null;
  confidence: number;
}

export interface TradesData {
  trades: Trade[];
}

export interface DirectionAccuracy {
  total: number;
  correct: number;
}

export interface MetricsData {
  account: {
    initial_balance: number;
    current_balance: number;
  };
  performance: {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    profit_factor: number;
    cumulative_pnl: number;
    total_return_pct: number;
    avg_win: number;
    avg_loss: number;
    max_drawdown_pct: number;
    current_drawdown_pct: number;
    sharpe_ratio: number;
    max_consecutive_wins: number;
    max_consecutive_losses: number;
  };
  monthly_returns: Record<string, number>;
  prediction_accuracy: {
    total: number;
    correct: number;
    accuracy: number;
    avg_confidence: number;
    by_direction: Record<Direction, DirectionAccuracy>;
  };
  equity_curve: Array<{
    time: string;
    balance: number;
  }>;
}

export interface MetaData {
  exported_at: string;
  version: number;
  counts: {
    predictions: number;
    trades: number;
  };
}
