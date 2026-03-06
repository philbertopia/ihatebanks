"use client";

import { useMemo, useState } from "react";
import {
  type BacktestResults,
  type BacktestRun,
  type MonthlyReturnPoint,
  fmtUsd,
  useBacktestHistory,
  useBacktestResults,
  useBacktestRuns,
  useBacktestStrategyComparison,
  useStrategyCatalog,
  useWalkforwardSummary,
} from "@/lib/api";
import StatCard from "@/components/StatCard";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const DURATION_POINTS: Record<"1m" | "3m" | "6m" | "1y" | "full", number> = {
  "1m": 21,
  "3m": 63,
  "6m": 126,
  "1y": 252,
  full: 0,
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function strategyFamily(strategyId: string): string {
  if (strategyId.includes("openclaw_stock_options")) return "Stock Options";
  if (strategyId.includes("openclaw_put_credit_spread")) return "Put Credit Spread";
  if (strategyId.includes("openclaw_tqqq_swing")) return "TQQQ Swing";
  if (strategyId.includes("openclaw_hybrid")) return "Hybrid";
  if (strategyId.includes("intraday_open_close_options")) return "Intraday O/C";
  if (strategyId.includes("stock_replacement")) return "Stock Replacement";
  return "Custom";
}

function modeLabel(mode: string | undefined, variant: string): string {
  if (mode) return mode;
  return variant || "base";
}

function sliceValues(values: number[], duration: "1m" | "3m" | "6m" | "1y" | "full"): number[] {
  const n = DURATION_POINTS[duration];
  if (!n || values.length <= n) return values;
  return values.slice(-n);
}

function computeDrawdownFallback(equity: number[]): number[] {
  if (!equity.length) return [];
  let peak = Math.max(equity[0], 0);
  return equity.map((v) => {
    const safeV = Math.max(v, 0);
    if (safeV > peak) peak = safeV;
    const dd = peak > 0 ? ((safeV - peak) / peak) * 100 : 0;
    return Math.max(Math.min(dd, 0), -100);
  });
}

function toLineData(values: number[], key: string) {
  return values.map((v, i) => ({ i, [key]: Math.round(v * 1000) / 1000 }));
}

function heatColor(v: number | undefined): string {
  if (v == null) return "rgba(75, 85, 99, 0.35)";
  const abs = Math.min(Math.abs(v), 20);
  const alpha = 0.2 + abs / 30;
  return v >= 0 ? `rgba(34,197,94,${alpha})` : `rgba(239,68,68,${alpha})`;
}

function buildHeatmap(monthly: MonthlyReturnPoint[]) {
  const rows: Record<string, Record<number, number>> = {};
  for (const point of monthly) {
    const parts = point.month.split("-");
    if (parts.length < 2) continue;
    const [year, month] = parts;
    const idx = Number(month) - 1;
    if (!Number.isFinite(idx) || idx < 0 || idx > 11) continue;
    rows[year] ??= {};
    rows[year][idx] = point.return_pct;
  }
  const years = Object.keys(rows).sort();
  return { years, rows };
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function toTimeMs(value: string | undefined): number {
  if (!value) return 0;
  const ts = Date.parse(value);
  return Number.isFinite(ts) ? ts : 0;
}

function periodSpanDays(start: string | undefined, end: string | undefined): number {
  if (!start || !end) return 0;
  const s = Date.parse(start);
  const e = Date.parse(end);
  if (!Number.isFinite(s) || !Number.isFinite(e)) return 0;
  return Math.max(0, Math.floor((e - s) / 86_400_000));
}

function pickRepresentativeRun(runs: BacktestRun[]): BacktestRun | undefined {
  if (!runs.length) return undefined;
  return runs.reduce((best, row) => {
    const bestSpan = periodSpanDays(best.start_date, best.end_date);
    const rowSpan = periodSpanDays(row.start_date, row.end_date);
    if (rowSpan !== bestSpan) return rowSpan > bestSpan ? row : best;

    const bestTrades = asNumber(best.metrics?.total_trades) ?? 0;
    const rowTrades = asNumber(row.metrics?.total_trades) ?? 0;
    if (rowTrades !== bestTrades) return rowTrades > bestTrades ? row : best;

    return toTimeMs(row.generated_at) > toTimeMs(best.generated_at) ? row : best;
  });
}

function sanitizeDrawdown(value: unknown): number | null {
  const n = asNumber(value);
  if (n == null) return null;
  return Math.min(Math.max(n, 0), 100);
}

function formatProfitFactor(value: unknown): string {
  const n = asNumber(value);
  return n == null ? "—" : n.toFixed(2);
}

function getSeries(run: BacktestRun | BacktestResults | undefined) {
  const baseEquity = run?.series?.equity_curve ?? run?.equity_curve ?? [];
  return {
    equity: baseEquity,
    drawdown: run?.series?.drawdown_curve ?? computeDrawdownFallback(baseEquity),
    rolling: run?.series?.rolling_win_rate ?? [],
    monthly: run?.series?.monthly_returns ?? [],
  };
}

export default function BacktestPage() {
  const { data: latest } = useBacktestResults();
  const { data: history, error: historyError } = useBacktestHistory();
  const { data: runs, error: runsError } = useBacktestRuns();
  const { data: comparisons } = useBacktestStrategyComparison();
  const { data: catalog, error: catalogError } = useStrategyCatalog();
  const { data: walkforwardSummary } = useWalkforwardSummary();

  const [selectedTab, setSelectedTab] = useState("");
  const [duration, setDuration] = useState<"1m" | "3m" | "6m" | "1y" | "full">("full");

  const allRuns = runs ?? [];

  const tabs = useMemo(() => {
    const map = new Map<
      string,
      {
        key: string;
        strategy_id: string;
        strategy_name: string;
        variant: string;
        status?: string;
        champion?: boolean;
        universe_note?: string;
      }
    >();

    for (const item of catalog ?? []) {
      if (item.status === "archived") continue;
      const key = `${item.strategy_id}|${item.variant}`;
      map.set(key, {
        key,
        strategy_id: item.strategy_id,
        strategy_name: item.strategy_name,
        variant: item.variant,
        status: item.status,
        champion: item.champion,
        universe_note: item.universe_note,
      });
    }

    return Array.from(map.values()).sort((a, b) => a.key.localeCompare(b.key));
  }, [catalog]);

  const latestKey =
    latest?.strategy_id && latest?.variant ? `${latest.strategy_id}|${latest.variant}` : "";

  const defaultKey = useMemo(() => {
    if (selectedTab && tabs.some((t) => t.key === selectedTab)) return selectedTab;
    if (latestKey && tabs.some((t) => t.key === latestKey)) return latestKey;
    return tabs[0]?.key ?? latestKey;
  }, [selectedTab, latestKey, tabs]);

  const [strategyId, variant] = defaultKey ? defaultKey.split("|") : ["", ""];

  const selectedRuns = useMemo(
    () =>
      allRuns
        .filter((r) => r.strategy_id === strategyId && r.variant === variant)
        .sort((a, b) => (a.generated_at < b.generated_at ? 1 : -1)),
    [allRuns, strategyId, variant]
  );

  const representativeRun = useMemo(
    () => pickRepresentativeRun(selectedRuns),
    [selectedRuns]
  );
  const latestForTab = selectedRuns[0];
  // Use a representative run for the detail cards/charts so short smoke runs
  // do not replace full-period strategy summaries.
  const effectiveRun = representativeRun ?? latestForTab;
  const series = getSeries(effectiveRun);
  const equity = sliceValues(series.equity, duration);
  const drawdown = sliceValues(series.drawdown, duration);
  const rolling = sliceValues(series.rolling, duration);
  const monthly = series.monthly;

  const equityData = toLineData(equity, "equity");
  const drawdownData = toLineData(drawdown, "drawdown");
  const rollingData = toLineData(rolling, "rolling");
  const heatmap = buildHeatmap(monthly);

  const selectedComparison = (comparisons ?? []).find(
    (c) => c.strategy_id === strategyId && c.variant === variant
  );
  const wfKey = `${strategyId}|${variant}|${effectiveRun?.universe_profile ?? ""}`;
  const selectedWf = walkforwardSummary?.[wfKey];

  const historyRows = Object.values(history ?? {})
    .filter((row) => row.strategy_id === strategyId && row.variant === variant)
    .sort((a, b) => (a.start_date < b.start_date ? -1 : 1));

  const timeline = selectedRuns.slice(0, 30);
  const metrics = effectiveRun?.metrics;
  const component = effectiveRun?.component_metrics;
  const intradayRows = (effectiveRun?.intraday_report ?? []).slice(0, 15);
  const intradayTotal = effectiveRun?.candidate_count_total ?? intradayRows.length;
  const intradayQualified = effectiveRun?.candidate_count_qualified ?? intradayRows.length;
  const dq = effectiveRun?.data_quality_breakdown ?? {};
  const totalReturnPct = asNumber(metrics?.total_return_pct) ?? 0;
  const winRatePct = asNumber(metrics?.win_rate) ?? 0;
  const profitFactor = asNumber(metrics?.profit_factor);
  const sharpeRatio = asNumber(metrics?.sharpe_ratio) ?? 0;
  const maxDrawdownPct = sanitizeDrawdown(metrics?.max_drawdown_pct) ?? 0;
  const avgHoldDays = asNumber(metrics?.avg_hold_days) ?? 0;
  const allocatorState = effectiveRun?.allocator_state ?? null;
  const riskState = effectiveRun?.risk_control_events ?? null;
  const execState = effectiveRun?.execution_realism ?? null;
  const oos = effectiveRun?.oos_summary ?? selectedWf?.oos_summary ?? null;
  const featureTimeMode =
    (effectiveRun?.feature_time_mode as string | undefined) ??
    (effectiveRun?.strategy_parameters?.feature_time_mode as string | undefined) ??
    "—";
  const dataQualityPolicy =
    (effectiveRun?.data_quality_policy as string | undefined) ??
    (effectiveRun?.strategy_parameters?.data_quality_policy as string | undefined) ??
    "—";
  const rejections = effectiveRun?.rejection_counts ?? {};
  const oosReturn = asNumber(oos?.avg_total_return_pct);
  const oosSharpe = asNumber(oos?.avg_sharpe_ratio);
  const oosDrawdown = sanitizeDrawdown(oos?.avg_max_drawdown_pct);
  const oosWindows = asNumber(oos?.windows);
  const oosPass = Boolean(oos?.pass_validation);

  const stockLeg = component?.stock as Record<string, unknown> | undefined;
  const tqqqLeg = component?.tqqq as Record<string, unknown> | undefined;

  return (
    <div className="space-y-6 sm:space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-white mb-1">Strategy Backtests</h2>
        <p className="text-sm text-gray-500">
          Document strategy variants, compare them side-by-side, and track backtest performance over time.
        </p>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Strategy Tab Header</h3>
        {tabs.length === 0 ? (
          <p className="text-gray-500 text-sm">
            No strategy variants found yet. Run{" "}
            <code className="bg-gray-900 px-1 rounded text-xs">python main.py backtest-batch --start 2020-01-01 --end 2025-12-31</code>.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {tabs.map((tab) => {
              const active = tab.key === defaultKey;
              const family = strategyFamily(tab.strategy_id);
              const mode = modeLabel(undefined, tab.variant);
              const compData = (comparisons ?? []).find(
                (c) => c.strategy_id === tab.strategy_id && c.variant === tab.variant
              );
              const uLabel = compData?.universe_profile
                ? `${compData.universe_profile}${compData.universe_size ? ` (${compData.universe_size})` : ""}`
                : null;
              return (
                <button
                  key={tab.key}
                  onClick={() => setSelectedTab(tab.key)}
                  className={`px-3 py-2 rounded-lg border text-xs text-left ${
                    tab.champion
                      ? active
                        ? "bg-yellow-600 border-yellow-500 text-black"
                        : "bg-yellow-900/30 border-yellow-700/60 text-yellow-100 hover:bg-yellow-900/50"
                      : active
                        ? "bg-pink-600 border-pink-500 text-white"
                        : "bg-gray-900 border-gray-700 text-gray-200 hover:bg-gray-700"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    {tab.champion && <span className="text-xs">👑</span>}
                    <span className="font-semibold">{tab.strategy_name}</span>
                  </div>
                  <div className="text-[11px] font-mono opacity-90">{tab.strategy_id} | {tab.variant}</div>
                  <div className="mt-1 flex gap-1 flex-wrap">
                    {tab.champion && (
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${active ? "bg-yellow-500 text-black" : "bg-yellow-700/50 text-yellow-300"}`}>
                        CHAMPION
                      </span>
                    )}
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${active && !tab.champion ? "bg-pink-700" : "bg-gray-700"}`}>{mode}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${active && !tab.champion ? "bg-pink-700" : "bg-gray-700"}`}>{family}</span>
                    {uLabel && (
                      <span className={`px-1.5 py-0.5 rounded text-[10px] ${active && !tab.champion ? "bg-pink-700" : "bg-gray-700/70"}`}>
                        {uLabel}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Selected Strategy Metrics</h3>
        {!metrics ? (
          <p className="text-gray-500 text-sm">
            No run exists for this strategy tab. Run{" "}
            <code className="bg-gray-900 px-1 rounded text-xs">python main.py backtest-batch --start 2020-01-01 --end 2025-12-31</code>.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4 mb-4">
              <StatCard
                label="Total Return"
                value={`${totalReturnPct >= 0 ? "+" : ""}${totalReturnPct.toFixed(2)}%`}
                color={totalReturnPct >= 0 ? "green" : "red"}
              />
              <StatCard label="Win Rate" value={`${winRatePct.toFixed(2)}%`} color={winRatePct >= 50 ? "green" : "red"} />
              <StatCard
                label="Profit Factor"
                value={profitFactor == null ? "—" : profitFactor.toFixed(2)}
                color={profitFactor == null ? "default" : profitFactor >= 1 ? "green" : "red"}
              />
              <StatCard label="Sharpe" value={sharpeRatio.toFixed(2)} color={sharpeRatio >= 0 ? "green" : "red"} />
              <StatCard label="Max Drawdown" value={`${maxDrawdownPct.toFixed(2)}%`} color="red" />
              <StatCard label="Avg Hold Days" value={`${avgHoldDays.toFixed(1)}d`} />
            </div>

            {strategyId === "openclaw_hybrid" && (stockLeg || tqqqLeg) && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <StatCard
                  label="Stock-Leg Return"
                  value={`${(asNumber(stockLeg?.total_return_pct) ?? 0).toFixed(2)}%`}
                  color={(asNumber(stockLeg?.total_return_pct) ?? 0) >= 0 ? "green" : "red"}
                />
                <StatCard
                  label="TQQQ-Leg Return"
                  value={`${(asNumber(tqqqLeg?.total_return_pct) ?? 0).toFixed(2)}%`}
                  color={(asNumber(tqqqLeg?.total_return_pct) ?? 0) >= 0 ? "green" : "red"}
                />
                <StatCard
                  label="Leg Contribution"
                  value={`${(asNumber(stockLeg?.contribution_pct) ?? 0).toFixed(1)}% / ${(asNumber(tqqqLeg?.contribution_pct) ?? 0).toFixed(1)}%`}
                  sub="stock / tqqq"
                />
              </div>
            )}
          </>
        )}
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Validation & Risk Diagnostics</h3>
        {!effectiveRun ? (
          <p className="text-gray-500 text-sm">No run selected.</p>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4 mb-4">
              <StatCard
                label="OOS Return"
                value={oosReturn == null ? "—" : `${oosReturn >= 0 ? "+" : ""}${oosReturn.toFixed(2)}%`}
                color={oosReturn == null ? "default" : oosReturn >= 0 ? "green" : "red"}
              />
              <StatCard
                label="OOS Sharpe"
                value={oosSharpe == null ? "—" : oosSharpe.toFixed(2)}
                color={oosSharpe == null ? "default" : oosSharpe >= 0.7 ? "green" : "amber"}
              />
              <StatCard
                label="OOS Max DD"
                value={oosDrawdown == null ? "—" : `${oosDrawdown.toFixed(2)}%`}
                color={oosDrawdown == null ? "default" : oosDrawdown <= 30 ? "green" : "red"}
              />
              <StatCard
                label="OOS Windows"
                value={oosWindows == null ? "—" : `${Math.round(oosWindows)}`}
              />
              <StatCard
                label="Validation"
                value={oos ? (oosPass ? "PASS" : "FAIL") : "—"}
                color={!oos ? "default" : oosPass ? "green" : "red"}
              />
              <StatCard
                label="WF ID"
                value={effectiveRun.walkforward_id ?? selectedWf?.walkforward_id ?? "—"}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-8 gap-4">
              <StatCard
                label="Allocator Live"
                value={allocatorState?.enforced ? "Enforced" : "Shadow/Off"}
                color={allocatorState?.enforced ? "blue" : "default"}
              />
              <StatCard
                label="Allocator Blocks"
                value={`${riskState?.allocator_block_days ?? 0}`}
                color={(riskState?.allocator_block_days ?? 0) > 0 ? "amber" : "default"}
              />
              <StatCard
                label="Kill Blocks"
                value={`${riskState?.kill_switch_block_days ?? 0}`}
                color={(riskState?.kill_switch_block_days ?? 0) > 0 ? "amber" : "default"}
              />
              <StatCard
                label="Macro Blocks"
                value={`${riskState?.macro_block_days ?? 0}`}
                color={(riskState?.macro_block_days ?? 0) > 0 ? "amber" : "default"}
              />
              <StatCard
                label="Fill Rate"
                value={execState?.fill_rate == null ? "—" : `${(execState.fill_rate * 100).toFixed(1)}%`}
                color={execState?.fill_rate == null ? "default" : execState.fill_rate >= 0.8 ? "green" : "amber"}
              />
              <StatCard
                label="Avg Slippage"
                value={execState?.avg_slippage_bps == null ? "—" : `${execState.avg_slippage_bps.toFixed(1)} bps`}
              />
              <StatCard label="Feature Timing" value={featureTimeMode} />
              <StatCard label="Data Policy" value={dataQualityPolicy} />
            </div>
          </>
        )}
      </div>

      {(strategyId === "intraday_open_close_options" || intradayRows.length > 0) && (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Top Intraday Candidates</h3>
          <p className="text-xs text-gray-500 mb-3">
            Ranked contracts for the latest run: scanned {intradayTotal}, qualified {intradayQualified}. Data quality — observed: {dq.observed ?? 0}, mixed: {dq.mixed ?? 0}, modeled: {dq.modeled ?? 0}.
          </p>
          <p className="text-xs text-gray-500 mb-3">
            Rejections — modeled: {rejections.reject_modeled_only ?? 0}, regime: {rejections.reject_regime ?? 0}, hist: {rejections.reject_hist_winrate ?? 0}, liquidity: {rejections.reject_liquidity ?? 0}, spread: {rejections.reject_spread ?? 0}, flow: {rejections.reject_unusual_flow ?? 0}.
          </p>
          {intradayRows.length === 0 ? (
            <p className="text-gray-500 text-sm">No intraday candidate snapshot in this run payload.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="border-b border-gray-700 text-gray-400 text-xs uppercase tracking-wider">
                    <th className="pb-3 pr-3">Rank</th>
                    <th className="pb-3 pr-3">Ticker</th>
                    <th className="pb-3 pr-3">Option</th>
                    <th className="pb-3 pr-3">Edge</th>
                    <th className="pb-3 pr-3">June 4 Stats</th>
                    <th className="pb-3 pr-3">ATR</th>
                    <th className="pb-3 pr-3">Greeks</th>
                    <th className="pb-3 pr-3">Entry</th>
                    <th className="pb-3 pr-3">Exit Plan</th>
                    <th className="pb-3 pr-3">Rationale</th>
                    <th className="pb-3">Risk Flags</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {intradayRows.map((row, idx) => (
                    <tr key={`${row.contract_symbol}-${idx}`} className="hover:bg-gray-700/30 align-top">
                      <td className="py-3 pr-3 text-gray-200 font-mono">{row.rank ?? idx + 1}</td>
                      <td className="py-3 pr-3 text-white font-semibold">{row.ticker}</td>
                      <td className="py-3 pr-3 text-gray-300 text-xs font-mono">
                        {row.option_type?.toUpperCase()} {row.expiry} {row.strike?.toFixed(2)}
                      </td>
                      <td className="py-3 pr-3 text-pink-300 font-mono">{(row.composite_edge_score ?? 0).toFixed(2)}</td>
                      <td className="py-3 pr-3 text-gray-300 text-xs">
                        <div>buy={row.buy_volume} oi={row.open_interest}</div>
                        <div>Vol/OI={(row.vol_oi_ratio ?? 0).toFixed(2)}</div>
                        <div>ITM={(row.itm_depth_pct ?? 0).toFixed(2)}%</div>
                      </td>
                      <td className="py-3 pr-3 text-gray-300 text-xs">
                        <div>{(row.atr14 ?? 0).toFixed(2)}</div>
                        <div>{(row.atr_pct ?? 0).toFixed(2)}%</div>
                      </td>
                      <td className="py-3 pr-3 text-gray-300 text-xs">
                        <div>d={(row.delta ?? 0).toFixed(3)} g={(row.gamma ?? 0).toFixed(4)}</div>
                        <div>th={(row.theta ?? 0).toFixed(4)} v={(row.vega ?? 0).toFixed(4)}</div>
                        <div>iv={(row.implied_volatility ?? 0).toFixed(3)}</div>
                      </td>
                      <td className="py-3 pr-3 text-gray-300 text-xs">
                        <div>bid={(row.bid ?? 0).toFixed(2)} ask={(row.ask ?? 0).toFixed(2)}</div>
                        <div>prev={(row.previous_close ?? 0).toFixed(2)} d={(row.delta ?? 0).toFixed(3)}</div>
                        <div className="text-pink-300 font-semibold">limit {(row.entry_limit ?? 0).toFixed(2)}</div>
                      </td>
                      <td className="py-3 pr-3 text-gray-300 text-xs">
                        <div>target {(row.exit_plan?.target_pct ?? 0).toFixed(1)}%</div>
                        <div>stop {(row.exit_plan?.stop_pct ?? 0).toFixed(1)}%</div>
                        <div>trail {(row.exit_plan?.trailing_activation_pct ?? 0).toFixed(1)}%/{(row.exit_plan?.trailing_pct ?? 0).toFixed(1)}%</div>
                      </td>
                      <td className="py-3 pr-3 text-gray-300 text-xs">
                        {(row.rationale ?? []).length === 0 ? (
                          "—"
                        ) : (
                          <div className="space-y-1">
                            {(row.rationale ?? []).slice(0, 2).map((r, i) => (
                              <div key={i}>• {r}</div>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="py-3 text-gray-400 text-xs">
                        {(row.risk_flags ?? []).join(", ") || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Equity Analytics</h3>
          <select
            value={duration}
            onChange={(e) => setDuration(e.target.value as "1m" | "3m" | "6m" | "1y" | "full")}
            className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200"
          >
            <option value="1m">1M</option>
            <option value="3m">3M</option>
            <option value="6m">6M</option>
            <option value="1y">1Y</option>
            <option value="full">Full</option>
          </select>
        </div>

        <div>
          <p className="text-xs text-gray-500 mb-2">Equity Curve</p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={equityData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="i" tick={{ fill: "#9ca3af", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#9ca3af", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${Math.round(v / 1000)}k`} />
              <Tooltip formatter={(v: number | string | undefined) => [fmtUsd(Number(v ?? 0)), "Equity"]} />
              <ReferenceLine y={100000} stroke="#4b5563" strokeDasharray="4 2" />
              <Line type="monotone" dataKey="equity" stroke="#ec4899" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-gray-500 mb-2">Drawdown Curve</p>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={drawdownData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="i" tick={{ fill: "#9ca3af", fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#9ca3af", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${Number(v).toFixed(0)}%`} />
                <Tooltip formatter={(v: number | string | undefined) => [`${Number(v ?? 0).toFixed(2)}%`, "Drawdown"]} />
                <ReferenceLine y={0} stroke="#4b5563" />
                <Line type="monotone" dataKey="drawdown" stroke="#ef4444" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div>
            <p className="text-xs text-gray-500 mb-2">Rolling Win Rate</p>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={rollingData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="i" tick={{ fill: "#9ca3af", fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#9ca3af", fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip formatter={(v: number | string | undefined) => [`${Number(v ?? 0).toFixed(2)}%`, "Win Rate"]} />
                <ReferenceLine y={50} stroke="#4b5563" strokeDasharray="4 2" />
                <Line type="monotone" dataKey="rolling" stroke="#22c55e" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div>
          <p className="text-xs text-gray-500 mb-2">Monthly Returns Heatmap</p>
          {monthly.length === 0 ? (
            <p className="text-gray-500 text-sm">No monthly returns series available for this run.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-400">
                    <th className="text-left pb-2 pr-2">Year</th>
                    {MONTHS.map((m) => (
                      <th key={m} className="pb-2 px-1">{m}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {heatmap.years.map((year) => (
                    <tr key={year}>
                      <td className="py-1 pr-2 text-gray-300 font-mono">{year}</td>
                      {MONTHS.map((_, idx) => {
                        const value = heatmap.rows[year][idx];
                        return (
                          <td key={`${year}-${idx}`} className="px-1 py-1">
                            <div
                              className="rounded px-1 py-1 text-center text-[10px] text-white"
                              style={{ backgroundColor: heatColor(value) }}
                              title={value == null ? "No data" : `${value.toFixed(2)}%`}
                            >
                              {value == null ? "—" : `${value.toFixed(1)}%`}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Historical Period Results</h3>
        {historyError ? (
          <p className="text-amber-400 text-sm">
            History data unavailable. If this is the public static site, run{" "}
            <code className="bg-gray-900 px-1 rounded text-xs">python scripts/export_dashboard_data.py</code>{" "}
            and redeploy.
          </p>
        ) : historyRows.length === 0 ? (
          <p className="text-gray-500 text-sm">
            No period rows for this tab yet. Run{" "}
            <code className="bg-gray-900 px-1 rounded text-xs">python main.py backtest-batch --start 2020-01-01 --end 2025-12-31</code>.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-gray-700 text-gray-400 text-xs uppercase tracking-wider">
                  <th className="pb-3 pr-4">Strategy</th>
                  <th className="pb-3 pr-4">Variant</th>
                  <th className="pb-3 pr-4">Assumptions</th>
                  <th className="pb-3 pr-4">Profile</th>
                  <th className="pb-3 pr-4">Size</th>
                  <th className="pb-3 pr-4">Universe</th>
                  <th className="pb-3 pr-4">Period</th>
                  <th className="pb-3 pr-4">Return</th>
                  <th className="pb-3 pr-4">Win Rate</th>
                  <th className="pb-3 pr-4">PF</th>
                  <th className="pb-3 pr-4">Sharpe</th>
                  <th className="pb-3 pr-4">OOS Sharpe</th>
                  <th className="pb-3 pr-4">Validated</th>
                  <th className="pb-3">Trades</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {historyRows.map((row) => (
                  <tr key={`${row.run_id ?? row.start_date}-${row.variant}`} className="hover:bg-gray-700/30">
                    <td className="py-3 pr-4 text-white">{row.strategy_name ?? row.strategy_id}</td>
                    <td className="py-3 pr-4 font-mono text-xs text-pink-300">{row.variant}</td>
                    <td className="py-3 pr-4 text-gray-300 text-xs">{modeLabel(row.assumptions_mode, row.variant ?? "base")}</td>
                    <td className="py-3 pr-4 text-gray-300 text-xs">{row.universe_profile ?? "—"}</td>
                    <td className="py-3 pr-4 text-gray-300 text-xs">{row.universe_size ?? "—"}</td>
                    <td className="py-3 pr-4 text-gray-400 text-xs">{row.universe ?? "—"}</td>
                    <td className="py-3 pr-4 font-mono text-xs text-gray-300">{row.start_date} to {row.end_date}</td>
                    <td className={`py-3 pr-4 font-mono ${(row.metrics.total_return_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {(row.metrics.total_return_pct ?? 0) >= 0 ? "+" : ""}{(row.metrics.total_return_pct ?? 0).toFixed(2)}%
                    </td>
                    <td className="py-3 pr-4 font-mono text-gray-200">{(row.metrics.win_rate ?? 0).toFixed(2)}%</td>
                    <td className="py-3 pr-4 font-mono text-gray-200">{formatProfitFactor(row.metrics.profit_factor)}</td>
                    <td className="py-3 pr-4 font-mono text-gray-200">{(row.metrics.sharpe_ratio ?? 0).toFixed(2)}</td>
                    <td className="py-3 pr-4 font-mono text-gray-200">
                      {row.oos_summary?.avg_sharpe_ratio == null ? "—" : Number(row.oos_summary.avg_sharpe_ratio).toFixed(2)}
                    </td>
                    <td className={`py-3 pr-4 font-mono ${row.oos_summary?.pass_validation ? "text-green-400" : "text-red-400"}`}>
                      {row.oos_summary ? (row.oos_summary.pass_validation ? "PASS" : "FAIL") : "—"}
                    </td>
                    <td className="py-3 font-mono text-gray-200">{row.metrics.total_trades ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Recent Backtest Runs (Timeline)</h3>
        {runsError ? (
          <p className="text-amber-400 text-sm">
            Run log data unavailable. If this is the public static site, run{" "}
            <code className="bg-gray-900 px-1 rounded text-xs">python scripts/export_dashboard_data.py</code>{" "}
            and redeploy.
          </p>
        ) : timeline.length === 0 ? (
          <p className="text-gray-500 text-sm">No run log rows for this strategy tab yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-gray-700 text-gray-400 text-xs uppercase tracking-wider">
                  <th className="pb-3 pr-4">Generated</th>
                  <th className="pb-3 pr-4">Strategy</th>
                  <th className="pb-3 pr-4">Variant</th>
                  <th className="pb-3 pr-4">Assumptions</th>
                  <th className="pb-3 pr-4">Profile</th>
                  <th className="pb-3 pr-4">Size</th>
                  <th className="pb-3 pr-4">Universe</th>
                  <th className="pb-3 pr-4">Period</th>
                  <th className="pb-3 pr-4">Return</th>
                  <th className="pb-3 pr-4">Win Rate</th>
                  <th className="pb-3 pr-4">PF</th>
                  <th className="pb-3 pr-4">OOS Sharpe</th>
                  <th className="pb-3 pr-4">Validated</th>
                  <th className="pb-3">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {timeline.map((row) => (
                  <tr key={row.run_id} className="hover:bg-gray-700/30">
                    <td className="py-3 pr-4 text-gray-300 font-mono text-xs">{row.generated_at}</td>
                    <td className="py-3 pr-4 text-white">{row.strategy_name}</td>
                    <td className="py-3 pr-4 font-mono text-xs text-pink-300">{row.variant}</td>
                    <td className="py-3 pr-4 text-gray-300 text-xs">{modeLabel(row.assumptions_mode, row.variant)}</td>
                    <td className="py-3 pr-4 text-gray-300 text-xs">{row.universe_profile ?? "—"}</td>
                    <td className="py-3 pr-4 text-gray-300 text-xs">{row.universe_size ?? "—"}</td>
                    <td className="py-3 pr-4 text-gray-400 text-xs">{row.universe ?? "—"}</td>
                    <td className="py-3 pr-4 text-gray-300 font-mono text-xs">{row.start_date} to {row.end_date}</td>
                    <td className={`py-3 pr-4 font-mono ${(row.metrics.total_return_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {(row.metrics.total_return_pct ?? 0) >= 0 ? "+" : ""}{(row.metrics.total_return_pct ?? 0).toFixed(2)}%
                    </td>
                    <td className="py-3 pr-4 font-mono text-gray-200">{(row.metrics.win_rate ?? 0).toFixed(2)}%</td>
                    <td className="py-3 pr-4 font-mono text-gray-200">{formatProfitFactor(row.metrics.profit_factor)}</td>
                    <td className="py-3 pr-4 font-mono text-gray-200">
                      {row.oos_summary?.avg_sharpe_ratio == null ? "—" : Number(row.oos_summary.avg_sharpe_ratio).toFixed(2)}
                    </td>
                    <td className={`py-3 pr-4 font-mono ${row.oos_summary?.pass_validation ? "text-green-400" : "text-red-400"}`}>
                      {row.oos_summary ? (row.oos_summary.pass_validation ? "PASS" : "FAIL") : "—"}
                    </td>
                    <td className="py-3 text-gray-400 text-xs">{row.notes || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Representative Backtest Details</h3>
        {!effectiveRun ? (
          <p className="text-gray-500 text-sm">
            No backtest results found. Run{" "}
            <code className="bg-gray-900 px-1 rounded text-xs">python main.py backtest-batch --start 2020-01-01 --end 2025-12-31</code>.
          </p>
        ) : (
          <div className="space-y-2 text-sm">
            {(() => {
              const tabMeta = tabs.find((t) => t.strategy_id === strategyId && t.variant === variant);
              return tabMeta?.champion ? (
                <div className="flex items-center gap-2 mb-3 px-3 py-2 bg-yellow-900/30 border border-yellow-700/50 rounded-lg">
                  <span>👑</span>
                  <span className="text-yellow-300 font-semibold text-sm">Champion Strategy</span>
                  {tabMeta.universe_note && (
                    <span className="text-yellow-200/60 text-xs ml-2">{tabMeta.universe_note}</span>
                  )}
                </div>
              ) : tabMeta?.universe_note ? (
                <div className="flex items-center gap-2 mb-3 px-3 py-2 bg-gray-700/40 border border-gray-600/50 rounded-lg">
                  <span className="text-gray-300 text-xs">{tabMeta.universe_note}</span>
                </div>
              ) : null;
            })()}
            <p className="text-white font-semibold">
              {effectiveRun.strategy_name} / {effectiveRun.variant} / {effectiveRun.start_date} to {effectiveRun.end_date}
            </p>
            <p className="text-gray-400">Engine: {effectiveRun.engine_type || "—"}</p>
            <p className="text-gray-400">Assumptions: {modeLabel(effectiveRun.assumptions_mode, effectiveRun.variant ?? "base")}</p>
            <p className="text-gray-400">Universe Profile: {effectiveRun.universe_profile || "—"}</p>
            <p className="text-gray-400">Universe Size: {effectiveRun.universe_size ?? "—"}</p>
            <p className="text-gray-400">Universe: {effectiveRun.universe || "—"}</p>
            <p className="text-gray-400">Final Equity: {fmtUsd(effectiveRun.metrics.final_equity)}</p>
            <p className="text-gray-400">
              OOS Validation: {oos ? (oosPass ? "PASS" : "FAIL") : "—"}
              {oosSharpe != null ? ` | OOS Sharpe ${oosSharpe.toFixed(2)}` : ""}
              {oosDrawdown != null ? ` | OOS Max DD ${oosDrawdown.toFixed(2)}%` : ""}
            </p>
            {selectedComparison && (
              <p className="text-gray-400">
                Avg Return Across Runs: {(asNumber(selectedComparison.avg_total_return_pct) ?? 0) >= 0 ? "+" : ""}
                {(asNumber(selectedComparison.avg_total_return_pct) ?? 0).toFixed(2)}% ({selectedComparison.runs} runs)
              </p>
            )}
          </div>
        )}
      </div>

      {catalogError && (
        <p className="text-amber-400 text-sm">
          Strategy catalog unavailable. Regenerate static dashboard data and redeploy.
        </p>
      )}
    </div>
  );
}
