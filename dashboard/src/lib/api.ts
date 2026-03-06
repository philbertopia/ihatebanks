import useSWR from "swr";

// Static mode: serve pre-computed JSON from /public/data/ (no backend needed).
// Set NEXT_PUBLIC_API_URL=http://localhost:8001/api for local dev with live backend.
const _apiUrl = process.env.NEXT_PUBLIC_API_URL;
const STATIC_MODE = !_apiUrl || _apiUrl === "static";
const BASE = STATIC_MODE ? "" : _apiUrl;

// Map API endpoint -> static file path (used when STATIC_MODE is true)
const STATIC_MAP: Record<string, string> = {
  "/stats/backtest": "/data/backtest_latest.json",
  "/stats/backtest/history": "/data/backtest_history.json",
  "/stats/backtest/strategies": "/data/strategies.json",
  "/stats/backtest/runs": "/data/runs.json",
  "/stats/backtest/catalog": "/data/catalog.json",
  "/stats/backtest/walkforward": "/data/walkforward.json",
  "/stats/backtest/walkforward/runs": "/data/walkforward_runs.json",
};

const fetcher = async (url: string) => {
  // In static mode, remap API paths to pre-computed JSON files
  let resolvedUrl = url;
  if (STATIC_MODE) {
    const suffix = url.replace(/^\/data/, ""); // already a static path
    const mapped = STATIC_MAP[suffix] ?? STATIC_MAP[url];
    if (mapped) resolvedUrl = mapped;
  }
  const res = await fetch(resolvedUrl);
  if (!res.ok) throw new Error(`API ${res.status}: ${resolvedUrl}`);
  return res.json();
};

// ── Types ──────────────────────────────────────────────────────

export interface Position {
  id: number;
  underlying: string;
  contract_symbol: string;
  option_type: string;
  strike: number;
  expiration_date: string;
  qty: number;
  entry_price: number;
  entry_date: string;
  entry_delta: number | null;
  entry_extrinsic_pct: number | null;
  current_delta: number | null;
  current_price: number | null;
  status: string;
  close_date: string | null;
  close_price: number | null;
  close_reason: string | null;
  realized_pnl: number | null;
  unrealized_pnl: number;
  notes: string | null;
}

export interface PortfolioStats {
  open_positions: number;
  portfolio_delta: number;
  total_unrealized_pnl: number;
  total_realized_pnl: number;
  total_closed: number;
  winners: number;
  losers: number;
  win_rate: number;
  profit_factor: number;
  gross_profit: number;
  gross_loss: number;
  avg_pnl: number | null;
}

export interface ScanResult {
  id: number;
  scan_date: string;
  underlying: string;
  contract_symbol: string;
  strike: number;
  expiration_date: string;
  dte: number;
  delta: number;
  ask: number;
  bid: number;
  spread_pct: number;
  open_interest: number | null;
  extrinsic_value: number;
  extrinsic_pct: number;
  implied_volatility: number | null;
  score: number | null;
  action_taken: string;
}

export interface DailyStats {
  stat_date: string;
  open_positions: number;
  positions_opened: number;
  positions_rolled: number;
  positions_closed: number;
  total_pnl_unrealized: number;
  total_pnl_realized: number;
  portfolio_delta: number;
}

export interface BacktestMetrics {
  total_trades: number;
  winners: number;
  losers: number;
  win_rate: number;
  total_realized_pnl: number;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number;
  avg_win: number;
  avg_loss: number;
  avg_hold_days: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  initial_equity: number;
  final_equity: number;
  total_return_pct: number;
  rolls_executed: number;
  trading_days: number;
  assumption_costs?: number;
}

export type AssumptionsMode = "legacy_replica" | "realistic_priced";

export interface AllocationState {
  regime_source?: string;
  enforced?: boolean;
  [k: string]: unknown;
}

export interface RiskControlEvents {
  allocator_block_days?: number | null;
  kill_switch_block_days?: number | null;
  macro_block_days?: number | null;
  kill_switch_active?: boolean | null;
  kill_switch_expectancy_r?: number | null;
  [k: string]: unknown;
}

export interface ExecutionRealism {
  avg_slippage_bps?: number | null;
  spread_cost_pct?: number | null;
  fill_rate?: number | null;
  partial_fill_rate?: number | null;
  slippage_cost_total?: number | null;
}

export interface OosSummary {
  windows?: number;
  avg_total_return_pct?: number;
  avg_sharpe_ratio?: number;
  avg_max_drawdown_pct?: number;
  pass_validation?: boolean;
  walkforward_id?: string;
  criteria?: {
    sharpe_threshold?: number;
    max_dd_threshold?: number;
    return_threshold?: number;
  };
}

export interface MonthlyReturnPoint {
  month: string;
  return_pct: number;
}

export interface BacktestSeries {
  equity_curve: number[];
  drawdown_curve?: number[];
  rolling_win_rate?: number[];
  monthly_returns?: MonthlyReturnPoint[];
}

export interface RejectionCounts {
  reject_modeled_only?: number;
  reject_regime?: number;
  reject_hist_winrate?: number;
  reject_liquidity?: number;
  reject_spread?: number;
  reject_unusual_flow?: number;
  reject_dte?: number;
  reject_not_itm?: number;
  reject_atr?: number;
}

export interface BacktestComponentMetrics {
  stock?: Record<string, unknown>;
  tqqq?: Record<string, unknown>;
}

export interface IntradayScoringComponents {
  vol_oi: number;
  itm_depth: number;
  atr_pct: number;
  historical_win_rate: number;
}

export interface IntradayExitPlan {
  target_pct: number;
  stop_pct: number;
  trailing_activation_pct: number;
  trailing_pct: number;
}

export interface IntradayCandidate {
  rank?: number;
  ticker: string;
  name?: string;
  contract_symbol: string;
  option_type: string;
  expiry: string;
  expiry_kind?: string;
  strike: number;
  dte?: number;
  buy_volume: number;
  open_interest: number;
  vol_oi_ratio: number;
  unusual_factor?: number;
  itm_depth_pct: number;
  atr14: number;
  atr_pct: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  implied_volatility: number;
  bid: number;
  ask: number;
  previous_close: number;
  entry_limit: number;
  exit_plan: IntradayExitPlan;
  rationale: string[];
  risk_flags: string[];
  data_quality?: string;
  scoring_components: IntradayScoringComponents;
  historical_win_rate?: number;
  composite_edge_score: number;
  execution_window?: { entry_time: string; exit_time: string };
  simulated_exit_reason?: string;
  simulated_return_pct?: number;
}

export interface BacktestResults {
  run_id?: string;
  strategy_id?: string;
  strategy_name?: string;
  variant?: string;
  engine_type?: string;
  assumptions_mode?: AssumptionsMode | string;
  strategy_parameters?: Record<string, unknown>;
  feature_time_mode?: string;
  data_quality_policy?: string;
  component_metrics?: BacktestComponentMetrics | null;
  data_range?: {
    start?: string;
    end?: string;
    trading_days?: number;
    rows?: number;
  };
  universe_profile?: string;
  universe_size?: number;
  universe?: string;
  intraday_report?: IntradayCandidate[];
  candidate_count_total?: number;
  candidate_count_qualified?: number;
  data_quality_breakdown?: Record<string, number>;
  rejection_counts?: RejectionCounts;
  execution_window?: { entry_time: string; exit_time: string };
  allocator_state?: AllocationState | null;
  risk_control_events?: RiskControlEvents | null;
  execution_realism?: ExecutionRealism | null;
  walkforward_id?: string;
  oos_summary?: OosSummary | null;
  notes?: string;
  period_key?: string;
  start_date: string;
  end_date: string;
  generated_at: string;
  equity_curve: number[];
  series?: BacktestSeries;
  metrics: BacktestMetrics;
}

export interface BacktestRun {
  run_id: string;
  strategy_id: string;
  strategy_name: string;
  variant: string;
  engine_type?: string;
  assumptions_mode?: AssumptionsMode | string;
  strategy_parameters?: Record<string, unknown>;
  feature_time_mode?: string;
  data_quality_policy?: string;
  component_metrics?: BacktestComponentMetrics | null;
  data_range?: {
    start?: string;
    end?: string;
    trading_days?: number;
    rows?: number;
  };
  universe_profile?: string;
  universe_size?: number;
  universe?: string;
  intraday_report?: IntradayCandidate[];
  candidate_count_total?: number;
  candidate_count_qualified?: number;
  data_quality_breakdown?: Record<string, number>;
  rejection_counts?: RejectionCounts;
  execution_window?: { entry_time: string; exit_time: string };
  allocator_state?: AllocationState | null;
  risk_control_events?: RiskControlEvents | null;
  execution_realism?: ExecutionRealism | null;
  walkforward_id?: string;
  oos_summary?: OosSummary | null;
  notes?: string;
  period_key: string;
  start_date: string;
  end_date: string;
  generated_at: string;
  metrics: BacktestMetrics;
  equity_curve?: number[];
  series?: BacktestSeries;
}

export interface BacktestStrategyComparison {
  strategy_id: string;
  strategy_name: string;
  variant: string;
  engine_type?: string;
  assumptions_mode?: AssumptionsMode | string;
  universe_profile?: string;
  universe_size?: number;
  universe?: string;
  runs: number;
  latest_run_id: string;
  latest_generated_at: string;
  latest_period_key: string;
  latest_start_date: string;
  latest_end_date: string;
  latest_total_return_pct: number;
  latest_win_rate?: number;
  latest_profit_factor?: number;
  latest_sharpe_ratio?: number;
  latest_max_drawdown_pct?: number;
  latest_oos_return_pct?: number;
  latest_oos_sharpe_ratio?: number;
  latest_oos_max_drawdown_pct?: number;
  oos_pass_validation?: boolean;
  oos_criteria?: { sharpe_threshold?: number; max_dd_threshold?: number; return_threshold?: number } | null;
  has_oos_summary?: boolean;
  feature_time_mode?: string;
  data_quality_policy?: string;
  rejection_counts?: RejectionCounts;
  best_total_return_pct: number;
  worst_total_return_pct: number;
  avg_total_return_pct: number;
  avg_win_rate: number;
  avg_profit_factor: number;
  avg_sharpe_ratio: number;
  avg_max_drawdown_pct?: number;
  avg_oos_return_pct?: number;
  avg_oos_sharpe_ratio?: number;
  avg_oos_max_drawdown_pct?: number;
  has_component_metrics?: boolean;
}

export interface WalkforwardWindowRow {
  window_index: number;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  metrics: BacktestMetrics;
}

export interface WalkforwardRun {
  walkforward_id: string;
  strategy_id: string;
  strategy_name: string;
  variant: string;
  universe_profile?: string;
  universe_size?: number;
  universe?: string;
  train_days: number;
  test_days: number;
  step_days: number;
  start_date: string;
  end_date: string;
  generated_at: string;
  oos_summary: OosSummary;
  windows: WalkforwardWindowRow[];
}

export interface BacktestLatestCandidates {
  run_id?: string;
  strategy_id?: string;
  variant?: string;
  generated_at?: string;
  strategy_parameters?: Record<string, unknown>;
  feature_time_mode?: string;
  data_quality_policy?: string;
  execution_window?: { entry_time: string; exit_time: string };
  candidate_count_total?: number;
  candidate_count_qualified?: number;
  data_quality_breakdown?: Record<string, number>;
  rejection_counts?: RejectionCounts;
  intraday_report?: IntradayCandidate[];
}

export interface StrategyCatalogEntry {
  strategy_id: string;
  strategy_name: string;
  variant: string;
  status: "active" | "planned" | "retired" | string;
  champion?: boolean;
  universe_note?: string;
  description: string;
  hypothesis: string;
  entry_rules?: string[];
  management_rules?: string[];
}

// ── SWR Hooks ─────────────────────────────────────────────────

export function usePositions() {
  return useSWR<Position[]>(`${BASE}/positions`, fetcher, {
    refreshInterval: 30_000,
    revalidateOnFocus: false,
  });
}

export function useHistory() {
  return useSWR<Position[]>(`${BASE}/positions/history`, fetcher);
}

export function usePortfolioStats() {
  return useSWR<PortfolioStats>(`${BASE}/stats/portfolio`, fetcher, {
    refreshInterval: 30_000,
    revalidateOnFocus: false,
  });
}

export function useDailyStats() {
  return useSWR<DailyStats[]>(`${BASE}/stats/daily`, fetcher);
}

export function useTodayScans() {
  return useSWR<ScanResult[]>(`${BASE}/scans/today`, fetcher, {
    refreshInterval: 60_000,
    revalidateOnFocus: false,
  });
}

export function useScansForDate(date: string | null) {
  return useSWR<ScanResult[]>(date ? `${BASE}/scans/${date}` : null, fetcher);
}

export function useBacktestResults() {
  return useSWR<BacktestResults>(`${BASE}/stats/backtest`, fetcher);
}

export function useBacktestHistory() {
  return useSWR<Record<string, BacktestResults>>(
    `${BASE}/stats/backtest/history`,
    fetcher
  );
}

export function useBacktestRuns() {
  return useSWR<BacktestRun[]>(`${BASE}/stats/backtest/runs`, fetcher);
}

export function useBacktestStrategyComparison() {
  return useSWR<BacktestStrategyComparison[]>(`${BASE}/stats/backtest/strategies`, fetcher);
}

export function useStrategyCatalog() {
  return useSWR<StrategyCatalogEntry[]>(`${BASE}/stats/backtest/catalog`, fetcher);
}

export function useLatestBacktestCandidates(strategyId?: string, variant?: string) {
  const q = new URLSearchParams();
  if (strategyId) q.set("strategy_id", strategyId);
  if (variant) q.set("variant", variant);
  const qs = q.toString();
  const url = qs ? `${BASE}/stats/backtest/latest-candidates?${qs}` : `${BASE}/stats/backtest/latest-candidates`;
  return useSWR<BacktestLatestCandidates>(url, fetcher);
}

export function useWalkforwardSummary() {
  return useSWR<Record<string, {
    walkforward_id: string;
    strategy_id: string;
    strategy_name: string;
    variant: string;
    universe_profile?: string;
    generated_at: string;
    oos_summary: OosSummary;
  }>>(`${BASE}/stats/backtest/walkforward`, fetcher);
}

export function useWalkforwardRuns() {
  return useSWR<WalkforwardRun[]>(`${BASE}/stats/backtest/walkforward/runs`, fetcher);
}

// ── Helpers ───────────────────────────────────────────────────

export function fmtUsd(v: number | null | undefined): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : v > 0 ? "+" : "";
  return `${sign}$${abs.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

export function fmtDelta(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toFixed(3);
}

export function daysToExpiry(expDate: string): number {
  const now = new Date();
  const todayUtc = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const [y, m, d] = expDate.split("-").map(Number);
  const expUtc = Date.UTC(y, m - 1, d);
  return Math.round((expUtc - todayUtc) / 86_400_000);
}
