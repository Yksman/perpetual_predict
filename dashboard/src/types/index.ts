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
  position_pct: number;
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
  position_pct: number;
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

// A/B Test Experiments

export type ExperimentStatus = 'active' | 'paused' | 'completed';

export interface ExperimentPredictionArm {
  direction: Direction;
  confidence: number;
  position_pct: number;
  is_correct: boolean | null;
  actual_direction: Direction | null;
  actual_price_change: number | null;
}

export interface ExperimentPredictionPair {
  target_candle_open: string;
  target_candle_close: string;
  control: ExperimentPredictionArm;
  variant: ExperimentPredictionArm;
}

export interface ExperimentResult {
  control_accuracy: number;
  variant_accuracy: number;
  control_return: number;
  variant_return: number;
  control_sharpe: number;
  variant_sharpe: number;
  p_value: number | null;
  is_significant: boolean;
  recommended_winner: 'control' | 'variant' | null;
}

export interface ExperimentAccount {
  initial_balance: number;
  current_balance: number;
}

export interface EquityPoint {
  time: string;
  balance: number;
}

export interface Experiment {
  experiment_id: string;
  name: string;
  description: string;
  status: ExperimentStatus;
  control_modules: string[];
  variant_modules: string[];
  module_diff: { added: string[]; removed: string[] };
  min_samples: number;
  significance_level: number;
  primary_metric: string;
  created_at: string;
  completed_at: string | null;
  winner: string | null;
  sample_size: number;
  progress_pct: number;
  result: ExperimentResult | null;
  accounts: {
    control: ExperimentAccount;
    variant: ExperimentAccount;
  };
  equity_curves: {
    control: EquityPoint[];
    variant: EquityPoint[];
  };
  prediction_pairs: ExperimentPredictionPair[];
}

export interface ExperimentsData {
  experiments: Experiment[];
}
