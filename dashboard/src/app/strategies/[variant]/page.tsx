"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  useBacktestRuns,
  useBacktestStrategyComparison,
  useStrategyCatalog,
  type BacktestRun,
  type MonthlyReturnPoint,
} from "@/lib/api";
import { getEducationSlugForStrategy } from "@/lib/education-strategy-map";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
} from "recharts";

// ── Helpers (mirrors backtest page) ─────────────────────────────────────────

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function asNumber(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function periodSpanDays(s?: string, e?: string) {
  if (!s || !e) return 0;
  return Math.max(0, Math.floor((Date.parse(e) - Date.parse(s)) / 86_400_000));
}

function pickRun(runs: BacktestRun[]) {
  if (!runs.length) return undefined;
  return runs.reduce((best, row) => {
    const bs = periodSpanDays(best.start_date, best.end_date);
    const rs = periodSpanDays(row.start_date, row.end_date);
    if (rs !== bs) return rs > bs ? row : best;
    const bt = asNumber(best.metrics?.total_trades) ?? 0;
    const rt = asNumber(row.metrics?.total_trades) ?? 0;
    if (rt !== bt) return rt > bt ? row : best;
    return (Date.parse(row.generated_at) > Date.parse(best.generated_at)) ? row : best;
  });
}

function computeDrawdown(equity: number[]) {
  let peak = equity[0] ?? 0;
  return equity.map((v) => {
    if (v > peak) peak = v;
    return peak > 0 ? ((v - peak) / peak) * 100 : 0;
  });
}

function buildHeatmap(monthly: MonthlyReturnPoint[]) {
  const rows: Record<string, Record<number, number>> = {};
  for (const pt of monthly) {
    const [yr, mo] = pt.month.split("-");
    const idx = Number(mo) - 1;
    if (!Number.isFinite(idx) || idx < 0 || idx > 11) continue;
    rows[yr] ??= {};
    rows[yr][idx] = pt.return_pct;
  }
  return { years: Object.keys(rows).sort(), rows };
}

function heatColor(v: number | undefined) {
  if (v == null) return "rgba(75,85,99,0.35)";
  const abs = Math.min(Math.abs(v), 20);
  const alpha = 0.2 + abs / 30;
  return v >= 0 ? `rgba(34,197,94,${alpha})` : `rgba(239,68,68,${alpha})`;
}

function fmt(n: unknown, decimals = 1, suffix = "") {
  const v = asNumber(n);
  return v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}${suffix}`;
}

function fmtPlain(n: unknown, decimals = 2) {
  const v = asNumber(n);
  return v == null ? "—" : v.toFixed(decimals);
}

function familyLabel(strategyId: string, variant: string) {
  if (strategyId.includes("call_credit_spread")) return "Call Credit Spread";
  if (strategyId.includes("put_credit_spread")) return "Put Credit Spread";
  if (strategyId.includes("intraday_open_close")) return "Intraday O/C";
  if (strategyId.includes("stock_replacement")) {
    if (variant.startsWith("wheel_")) return "Wheel";
    if (variant.startsWith("leaps_")) return "LEAPS";
    return "Stock Replacement";
  }
  return "Strategy";
}

function familyColor(strategyId: string, variant: string) {
  if (strategyId.includes("call_credit_spread")) return "bg-rose-900/50 text-rose-300 border-rose-700";
  if (strategyId.includes("put_credit_spread")) return "bg-purple-900/50 text-purple-300 border-purple-700";
  if (strategyId.includes("stock_replacement")) {
    if (variant.startsWith("wheel_")) return "bg-amber-900/50 text-amber-300 border-amber-700";
    if (variant.startsWith("leaps_")) return "bg-sky-900/50 text-sky-300 border-sky-700";
    return "bg-orange-900/50 text-orange-300 border-orange-700";
  }
  return "bg-gray-700 text-gray-300 border-gray-600";
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function StrategyDetailPage({
}: {
  params?: { variant?: string };
}) {
  const routeParams = useParams<{ variant?: string | string[] }>();
  const rawVariant = routeParams?.variant;
  const variant = Array.isArray(rawVariant) ? rawVariant[0] : rawVariant ?? "";

  const { data: runs } = useBacktestRuns();
  const { data: catalog } = useStrategyCatalog();
  const { data: comparisons } = useBacktestStrategyComparison();

  const meta = useMemo(
    () => catalog?.find((c) => c.variant === variant),
    [catalog, variant]
  );

  const variantRuns = useMemo(
    () => (runs ?? []).filter((r) => r.variant === variant),
    [runs, variant]
  );

  const run = useMemo(() => pickRun(variantRuns), [variantRuns]);

  const comparison = useMemo(
    () => comparisons?.find((c) => c.variant === variant),
    [comparisons, variant]
  );

  // Related variants (same strategy family)
  const siblings = useMemo(() => {
    if (!meta || !catalog) return [];
    return catalog.filter(
      (c) => c.strategy_id === meta.strategy_id && c.variant !== variant && c.status !== "archived"
    );
  }, [meta, catalog, variant]);

  const equity = run?.series?.equity_curve ?? run?.equity_curve ?? [];
  const drawdown = run?.series?.drawdown_curve ?? computeDrawdown(equity);
  const monthly = run?.series?.monthly_returns ?? [];
  const { years, rows: heatRows } = buildHeatmap(monthly);

  const equityData = equity.map((v, i) => ({ i, value: Math.round(v) }));
  const ddData = drawdown.map((v, i) => ({ i, value: Math.round(v * 100) / 100 }));

  const m = run?.metrics;
  const entryRules = meta?.entry_rules ?? [];
  const managementRules = meta?.management_rules ?? [];
  if (!meta && !run) {
    return (
      <div className="max-w-3xl mx-auto py-16 px-6 text-center text-gray-500">
        Strategy not found.{" "}
        <Link href="/strategies" className="text-pink-300 underline">Back to leaderboard</Link>
      </div>
    );
  }

  const strategyId = meta?.strategy_id ?? run?.strategy_id ?? "";
  const strategyName = meta?.strategy_name ?? run?.strategy_name ?? variant;
  const fam = familyLabel(strategyId, variant);
  const famColor = familyColor(strategyId, variant);
  const isChampion = meta?.champion ?? false;
  const isValidated = comparison?.oos_pass_validation ?? false;
  const explainerSlug = getEducationSlugForStrategy(strategyId, variant);

  return (
    <div className="max-w-4xl mx-auto py-8 sm:py-10 px-4 sm:px-6 space-y-8 sm:space-y-10">

      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link href="/strategies" className="hover:text-gray-300 transition-colors">Strategies</Link>
        <span>/</span>
        <span className="text-gray-300">{variant}</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${famColor}`}>
              {fam}
            </span>
            {isChampion && (
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-yellow-900/50 text-yellow-300 border border-yellow-700">
                Champion
              </span>
            )}
            {isValidated ? (
              <span className="text-xs font-semibold text-green-400">OOS Validated</span>
            ) : comparison?.has_oos_summary ? (
              <span className="text-xs font-semibold text-red-400">OOS Not Validated</span>
            ) : null}
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">{strategyName}</h1>
          <p className="text-sm text-gray-500 mt-1 font-mono">{variant}</p>
          {explainerSlug && (
            <div className="mt-3">
              <Link
                href={`/education/strategies/${explainerSlug}`}
                className="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-md border border-pink-700 bg-pink-900/30 text-pink-300 hover:bg-pink-900/50"
              >
                Learn this strategy
              </Link>
            </div>
          )}
          {meta?.universe_note && (
            <p className="text-xs text-gray-500 mt-2">{meta.universe_note}</p>
          )}
        </div>
        <div className="text-left sm:text-right shrink-0">
          {m?.total_return_pct != null && (
            <div className={`text-3xl font-bold ${(m.total_return_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
              {fmt(m.total_return_pct, 1, "%")}
            </div>
          )}
          <div className="text-xs text-gray-500 mt-0.5">5-year return</div>
          {m?.sharpe_ratio != null && (
            <div className="text-sm text-gray-400 mt-1">Sharpe {fmtPlain(m.sharpe_ratio)}</div>
          )}
        </div>
      </div>

      {/* Key Metrics Strip */}
      {m && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { label: "Win Rate", value: m.win_rate != null ? `${(m.win_rate * 100).toFixed(1)}%` : "—" },
            { label: "Sharpe", value: fmtPlain(m.sharpe_ratio) },
            { label: "Max DD", value: m.max_drawdown_pct != null ? `${m.max_drawdown_pct.toFixed(1)}%` : "—" },
            { label: "Profit Factor", value: fmtPlain(m.profit_factor) },
            { label: "Avg Hold", value: m.avg_hold_days != null ? `${m.avg_hold_days.toFixed(1)}d` : "—" },
            { label: "Total Trades", value: m.total_trades?.toString() ?? "—" },
          ].map(({ label, value }) => (
            <div key={label} className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
              <div className="text-sm font-semibold text-white">{value}</div>
              <div className="text-xs text-gray-500 mt-0.5">{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Description + Hypothesis */}
      {(meta?.description || meta?.hypothesis) && (
        <div className="space-y-4">
          {meta.description && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-3">Overview</h2>
              <p className="text-gray-300 text-sm leading-relaxed">{meta.description}</p>
            </div>
          )}
          {meta.hypothesis && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-3">Why It Works</h2>
              <p className="text-gray-300 text-sm leading-relaxed">{meta.hypothesis}</p>
            </div>
          )}
        </div>
      )}

      {/* Entry + Management Rules */}
      {(entryRules.length > 0 || managementRules.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {entryRules.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">Entry Rules</h2>
              <ul className="space-y-2">
                {entryRules.map((rule: string, i: number) => (
                  <li key={i} className="flex gap-2 text-sm text-gray-300">
                    <span className="text-green-500 mt-0.5 shrink-0">+</span>
                    {rule}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {managementRules.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">Exit Rules</h2>
              <ul className="space-y-2">
                {managementRules.map((rule: string, i: number) => (
                  <li key={i} className="flex gap-2 text-sm text-gray-300">
                    <span className="text-pink-300 mt-0.5 shrink-0">→</span>
                    {rule}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Equity Curve */}
      {equityData.length > 1 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">Equity Curve</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={equityData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="i" hide />
              <YAxis
                tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                tick={{ fill: "#9ca3af", fontSize: 11 }}
                width={52}
              />
              <Tooltip
                contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
                labelFormatter={() => ""}
              />
              <ReferenceLine y={100000} stroke="#4b5563" strokeDasharray="4 4" />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#ec4899"
                dot={false}
                strokeWidth={1.5}
              />
            </LineChart>
          </ResponsiveContainer>

          {/* Drawdown below */}
          {ddData.length > 1 && (
            <>
              <div className="mt-4 mb-2">
                <span className="text-xs text-gray-500 uppercase tracking-widest">Drawdown</span>
              </div>
              <ResponsiveContainer width="100%" height={80}>
                <LineChart data={ddData} margin={{ top: 0, right: 4, bottom: 0, left: 0 }}>
                  <XAxis dataKey="i" hide />
                  <YAxis
                    tickFormatter={(v) => `${v.toFixed(0)}%`}
                    tick={{ fill: "#9ca3af", fontSize: 10 }}
                    width={40}
                    domain={["auto", 0]}
                  />
                  <ReferenceLine y={0} stroke="#4b5563" />
                  <Tooltip
                    contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
                    labelFormatter={() => ""}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="#ef4444"
                    dot={false}
                    strokeWidth={1}
                  />
                </LineChart>
              </ResponsiveContainer>
            </>
          )}
        </div>
      )}

      {/* Monthly Returns Heatmap */}
      {years.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">Monthly Returns</h2>
          <div className="overflow-x-auto">
            <table className="text-xs w-full">
              <thead>
                <tr>
                  <th className="text-left text-gray-500 pr-3 font-normal pb-1">Year</th>
                  {MONTHS.map((m) => (
                    <th key={m} className="text-center text-gray-500 font-normal w-10 pb-1">{m}</th>
                  ))}
                  <th className="text-right text-gray-500 font-normal pl-2 pb-1">Total</th>
                </tr>
              </thead>
              <tbody>
                {years.map((yr) => {
                  const yearTotal = Object.values(heatRows[yr] ?? {}).reduce((a, b) => a + b, 0);
                  return (
                    <tr key={yr}>
                      <td className="text-gray-400 pr-3 py-0.5 font-mono">{yr}</td>
                      {Array.from({ length: 12 }, (_, i) => {
                        const v = heatRows[yr]?.[i];
                        return (
                          <td key={i} className="text-center py-0.5">
                            <span
                              className="inline-block w-9 rounded text-center py-0.5 text-xs font-mono"
                              style={{ background: heatColor(v), color: v == null ? "#6b7280" : v >= 0 ? "#86efac" : "#fca5a5" }}
                            >
                              {v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}`}
                            </span>
                          </td>
                        );
                      })}
                      <td className="text-right pl-2 py-0.5">
                        <span className={`font-mono font-semibold ${yearTotal >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {yearTotal >= 0 ? "+" : ""}{yearTotal.toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* OOS Validation */}
      {comparison?.has_oos_summary && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">Out-of-Sample Validation</h2>
          <p className="text-xs text-gray-500 mb-4">
            Walk-forward testing splits the historical period into 7 non-overlapping windows.
            The strategy is trained on each window and evaluated on data it has never seen.
            This detects overfitting and tells you whether the edge is real.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
            {[
              { label: "OOS Avg Return", value: comparison.latest_oos_return_pct != null ? `${comparison.latest_oos_return_pct >= 0 ? "+" : ""}${comparison.latest_oos_return_pct.toFixed(1)}%` : "—" },
              { label: "OOS Avg Sharpe", value: comparison.latest_oos_sharpe_ratio?.toFixed(2) ?? "—" },
              { label: "OOS Avg Max DD", value: comparison.latest_oos_max_drawdown_pct != null ? `${comparison.latest_oos_max_drawdown_pct.toFixed(1)}%` : "—" },
            ].map(({ label, value }) => (
              <div key={label} className="bg-gray-800 rounded-lg p-3 text-center">
                <div className="text-sm font-semibold text-white">{value}</div>
                <div className="text-xs text-gray-500 mt-0.5">{label}</div>
              </div>
            ))}
          </div>
          <div className={`flex items-center gap-2 text-sm font-semibold ${isValidated ? "text-green-400" : "text-red-400"}`}>
            <span>{isValidated ? "✓" : "✗"}</span>
            <span>{isValidated ? "Passes out-of-sample validation" : "Does not pass out-of-sample validation"}</span>
            {comparison.oos_criteria && (
              <span className="text-xs font-normal text-gray-500 ml-1">
                (Sharpe ≥ {comparison.oos_criteria.sharpe_threshold}, MaxDD ≤ {comparison.oos_criteria.max_dd_threshold}%)
              </span>
            )}
          </div>
        </div>
      )}

      {/* Related Variants */}
      {siblings.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-3">Other Variants in This Family</h2>
          <div className="flex flex-wrap gap-2">
            {siblings.map((s) => (
              <Link
                key={s.variant}
                href={`/strategies/${s.variant}`}
                className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-sm text-gray-300 transition-colors"
              >
                {s.variant}
                {s.champion && <span className="ml-1.5 text-yellow-400 text-xs">★</span>}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Back link */}
      <div className="pt-4 border-t border-gray-800">
        <Link href="/strategies" className="text-sm text-pink-300 hover:text-pink-200 transition-colors">
          ← Back to all strategies
        </Link>
      </div>

    </div>
  );
}
