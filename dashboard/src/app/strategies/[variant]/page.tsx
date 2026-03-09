"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  useCreditSpread10YResearch,
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

function parseMonthKey(month: string) {
  const [year, mon] = month.split("-").map(Number);
  if (!Number.isFinite(year) || !Number.isFinite(mon) || mon < 1 || mon > 12) {
    return null;
  }
  return { year, month: mon };
}

function monthDiff(a: string, b: string) {
  const left = parseMonthKey(a);
  const right = parseMonthKey(b);
  if (!left || !right) return 0;
  return (right.year - left.year) * 12 + (right.month - left.month);
}

function addMonths(month: string, offset: number) {
  const parsed = parseMonthKey(month);
  if (!parsed) return month;
  const total = (parsed.year * 12) + (parsed.month - 1) + offset;
  const year = Math.floor(total / 12);
  const mon = (total % 12) + 1;
  return `${year}-${String(mon).padStart(2, "0")}`;
}

function analyzeMonthlyCoverage(monthly: MonthlyReturnPoint[]) {
  const months = monthly
    .map((pt) => pt.month)
    .filter((month, idx, arr) => Boolean(parseMonthKey(month)) && arr.indexOf(month) === idx)
    .sort();

  if (!months.length) {
    return {
      firstMonth: null,
      lastMonth: null,
      expectedMonths: 0,
      actualMonths: 0,
      gaps: [] as Array<{ start: string; end: string; missingMonths: number }>,
      hasGaps: false,
    };
  }

  const gaps: Array<{ start: string; end: string; missingMonths: number }> = [];
  for (let i = 1; i < months.length; i += 1) {
    const diff = monthDiff(months[i - 1], months[i]);
    if (diff > 1) {
      gaps.push({
        start: addMonths(months[i - 1], 1),
        end: addMonths(months[i], -1),
        missingMonths: diff - 1,
      });
    }
  }

  return {
    firstMonth: months[0],
    lastMonth: months[months.length - 1],
    expectedMonths: monthDiff(months[0], months[months.length - 1]) + 1,
    actualMonths: months.length,
    gaps,
    hasGaps: gaps.length > 0,
  };
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

function capitalLabel(value: number | null | undefined): string | null {
  const capital = value != null && Number.isFinite(value) ? value : 100000;
  if (Math.abs(capital - 100000) < 0.005) return null;
  return `Cap $${capital.toLocaleString("en-US", {
    minimumFractionDigits: Number.isInteger(capital) ? 0 : 2,
    maximumFractionDigits: 2,
  })}`;
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

function strategyHref(strategyId: string, variant: string) {
  return {
    pathname: `/strategies/${variant}`,
    query: { strategy_id: strategyId },
  };
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function StrategyDetailPage({
}: {
  params?: { variant?: string };
}) {
  const routeParams = useParams<{ variant?: string | string[] }>();
  const searchParams = useSearchParams();
  const rawVariant = routeParams?.variant;
  const variant = Array.isArray(rawVariant) ? rawVariant[0] : rawVariant ?? "";
  const requestedStrategyId = searchParams.get("strategy_id") ?? "";
  const requestedInitialCapital = (() => {
    const raw = searchParams.get("initial_capital");
    if (raw == null) return null;
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  })();

  const { data: runs } = useBacktestRuns();
  const { data: catalog } = useStrategyCatalog();
  const { data: comparisons } = useBacktestStrategyComparison();
  const { data: research10y } = useCreditSpread10YResearch();

  const matchingCatalogEntries = useMemo(
    () => (catalog ?? []).filter((c) => c.variant === variant && c.status !== "archived"),
    [catalog, variant]
  );

  const ambiguousVariant = !requestedStrategyId && matchingCatalogEntries.length > 1;

  const meta = useMemo(
    () =>
      matchingCatalogEntries.find((c) => !requestedStrategyId || c.strategy_id === requestedStrategyId) ??
      matchingCatalogEntries[0],
    [matchingCatalogEntries, requestedStrategyId]
  );

  const variantRuns = useMemo(
    () =>
      (runs ?? []).filter(
        (r) =>
          r.variant === variant &&
          (!requestedStrategyId || r.strategy_id === requestedStrategyId) &&
          (requestedInitialCapital == null ||
            Math.abs((r.initial_capital ?? 100000) - requestedInitialCapital) < 0.005)
      ),
    [runs, variant, requestedStrategyId, requestedInitialCapital]
  );

  const run = useMemo(() => pickRun(variantRuns), [variantRuns]);

  const comparison = useMemo(
    () =>
      comparisons?.find(
        (c) =>
          c.variant === variant &&
          (!requestedStrategyId || c.strategy_id === requestedStrategyId) &&
          (requestedInitialCapital == null ||
            Math.abs((c.initial_capital ?? 100000) - requestedInitialCapital) < 0.005)
      ),
    [comparisons, variant, requestedStrategyId, requestedInitialCapital]
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
  const coverage = analyzeMonthlyCoverage(monthly);
  const backtestRangeLabel =
    run?.start_date && run?.end_date ? `${run.start_date} to ${run.end_date}` : null;

  const equityData = equity.map((v, i) => ({ i, value: Math.round(v) }));
  const ddData = drawdown.map((v, i) => ({ i, value: Math.round(v * 100) / 100 }));

  const m = run?.metrics;
  const entryRules = meta?.entry_rules ?? [];
  const managementRules = meta?.management_rules ?? [];

  if (ambiguousVariant) {
    return (
      <div className="max-w-3xl mx-auto py-12 px-6 space-y-6">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link href="/strategies" className="hover:text-gray-300 transition-colors">Strategies</Link>
          <span>/</span>
          <span className="text-gray-300">{variant}</span>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
          <div>
            <h1 className="text-2xl font-bold text-white">Choose a strategy family</h1>
            <p className="text-sm text-gray-400 mt-2">
              The variant slug <span className="font-mono text-gray-200">{variant}</span> exists in more than one
              family. Pick the exact strategy you want to inspect.
            </p>
          </div>
          <div className="grid gap-3">
            {matchingCatalogEntries.map((entry) => (
              <Link
                key={`${entry.strategy_id}|${entry.variant}`}
                href={strategyHref(entry.strategy_id, entry.variant)}
                className="rounded-lg border border-gray-800 bg-gray-950 px-4 py-3 hover:bg-gray-800/70"
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-[11px] px-2 py-0.5 rounded border ${familyColor(entry.strategy_id, entry.variant)}`}>
                    {familyLabel(entry.strategy_id, entry.variant)}
                  </span>
                  <span className="text-sm font-semibold text-white">{entry.strategy_name}</span>
                </div>
                <p className="text-xs text-gray-500 font-mono mt-1">{entry.strategy_id}|{entry.variant}</p>
              </Link>
            ))}
          </div>
        </div>
      </div>
    );
  }

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
  const universeSweepHref =
    strategyId === "openclaw_regime_credit_spread" && variant === "regime_legacy_defensive"
      ? "/education/articles/regime-credit-spread-universe-sweep"
      : null;
  const researchKey = strategyId ? `${strategyId}|${variant}` : "";
  const researchVariant = researchKey ? research10y?.variants_by_key?.[researchKey] : undefined;
  const researchMonthly = researchVariant?.full_period.monthly_returns ?? [];
  const researchHeatmap = buildHeatmap(researchMonthly);
  const researchMetrics = researchVariant?.full_period.metrics;
  const researchOos = researchVariant?.walkforward_summary;

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
            {researchVariant && (
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-sky-900/40 text-sky-300 border border-sky-700">
                10Y Research
              </span>
            )}
            {capitalLabel(comparison?.initial_capital ?? run?.initial_capital) && (
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-gray-900 text-gray-300 border border-gray-700">
                {capitalLabel(comparison?.initial_capital ?? run?.initial_capital)}
              </span>
            )}
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">{strategyName}</h1>
          <p className="text-sm text-gray-500 mt-1 font-mono">{variant}</p>
          {explainerSlug && (
            <div className="mt-3 flex flex-wrap gap-2">
              <Link
                href={`/education/strategies/${explainerSlug}`}
                className="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-md border border-pink-700 bg-pink-900/30 text-pink-300 hover:bg-pink-900/50"
              >
                Learn this strategy
              </Link>
              {universeSweepHref && (
                <Link
                  href={universeSweepHref}
                  className="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-md border border-sky-700 bg-sky-900/30 text-sky-300 hover:bg-sky-900/50"
                >
                  Read pair research
                </Link>
              )}
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
          <div className="text-xs text-gray-500 mt-0.5">Full-period return</div>
          {m?.sharpe_ratio != null && (
            <div className="text-sm text-gray-400 mt-1">Sharpe {fmtPlain(m.sharpe_ratio)}</div>
          )}
        </div>
      </div>

      {(backtestRangeLabel || coverage.actualMonths > 0) && (
        <div className={`rounded-xl border p-4 ${coverage.hasGaps ? "bg-amber-950/30 border-amber-800/70" : "bg-gray-900 border-gray-800"}`}>
          <div className="flex flex-col gap-2 text-sm">
            {backtestRangeLabel && (
              <p className={coverage.hasGaps ? "text-amber-200" : "text-gray-300"}>
                Backtest range: <span className="font-mono">{backtestRangeLabel}</span>
              </p>
            )}
            {coverage.actualMonths > 0 && (
              <p className={coverage.hasGaps ? "text-amber-200/90" : "text-gray-400"}>
                Monthly coverage: <span className="font-mono">{coverage.actualMonths}</span> reported months
                {coverage.expectedMonths > 0 ? ` out of ${coverage.expectedMonths}` : ""}
                {coverage.firstMonth && coverage.lastMonth ? (
                  <>
                    {" "}from <span className="font-mono">{coverage.firstMonth}</span> to <span className="font-mono">{coverage.lastMonth}</span>
                  </>
                ) : null}
              </p>
            )}
            {coverage.hasGaps && coverage.gaps[0] && (
              <p className="text-amber-300 text-xs">
                Coverage gap detected: <span className="font-mono">{coverage.gaps[0].start}</span> to{" "}
                <span className="font-mono">{coverage.gaps[0].end}</span>
                {" "}({coverage.gaps[0].missingMonths} missing months).
              </p>
            )}
          </div>
        </div>
      )}

      {/* Key Metrics Strip */}
      {m && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { label: "Win Rate", value: m.win_rate != null ? `${m.win_rate.toFixed(1)}%` : "—" },
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

      {researchVariant && researchMetrics && researchOos && (
        <div className="bg-sky-950/20 border border-sky-900/60 rounded-xl p-6 space-y-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="flex items-center gap-2 flex-wrap mb-2">
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-sky-900/40 text-sky-300 border border-sky-700">
                  Research Only
                </span>
                <span className="text-xs text-sky-200/80">10-Year Research</span>
              </div>
              <h2 className="text-sm font-semibold text-sky-100 uppercase tracking-widest">2016-2025 Extension</h2>
              <p className="text-xs text-sky-200/70 mt-2 max-w-3xl">
                This panel is separate from the official persisted dashboard metrics. It uses the local SPY/QQQ cache plus
                a filled ETF price-history gap for longer-horizon research coverage.
              </p>
            </div>
            <Link
              href="/education/articles/credit-spread-10-year-research-coverage"
              className="text-xs px-3 py-1.5 rounded-md border border-sky-700 bg-sky-900/30 text-sky-300 hover:bg-sky-900/50"
            >
              Read 10-year research
            </Link>
          </div>

          {researchVariant.sample_warning && (
            <div className="rounded-lg border border-amber-800 bg-amber-950/40 px-4 py-3 text-sm text-amber-200">
              {researchVariant.sample_warning_reason}
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
            {[
              { label: "10Y Return", value: researchMetrics.total_return_pct != null ? `${researchMetrics.total_return_pct >= 0 ? "+" : ""}${researchMetrics.total_return_pct.toFixed(1)}%` : "—" },
              { label: "10Y Sharpe", value: researchMetrics.sharpe_ratio != null ? researchMetrics.sharpe_ratio.toFixed(2) : "—" },
              { label: "10Y Max DD", value: researchMetrics.max_drawdown_pct != null ? `${researchMetrics.max_drawdown_pct.toFixed(1)}%` : "—" },
              { label: "Trades", value: researchMetrics.total_trades?.toString() ?? "—" },
              { label: "OOS Return", value: researchOos.avg_total_return_pct != null ? `${researchOos.avg_total_return_pct >= 0 ? "+" : ""}${researchOos.avg_total_return_pct.toFixed(2)}%` : "—" },
              { label: "OOS Sharpe", value: researchOos.avg_sharpe_ratio != null ? researchOos.avg_sharpe_ratio.toFixed(2) : "—" },
              { label: "OOS Max DD", value: researchOos.avg_max_drawdown_pct != null ? `${researchOos.avg_max_drawdown_pct.toFixed(2)}%` : "—" },
              { label: "Validation", value: researchOos.pass_validation ? "PASS" : "FAIL" },
            ].map(({ label, value }) => (
              <div key={label} className="bg-sky-950/30 border border-sky-900/60 rounded-lg p-3 text-center">
                <div className="text-sm font-semibold text-white">{value}</div>
                <div className="text-xs text-sky-200/70 mt-0.5">{label}</div>
              </div>
            ))}
          </div>

          <div>
            <h3 className="text-xs text-sky-200/70 uppercase tracking-widest mb-2">10-Year Monthly Returns</h3>
            {researchHeatmap.years.length === 0 ? (
              <p className="text-sm text-sky-200/60">No research monthly-return series available for this variant.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="text-xs w-full">
                  <thead>
                    <tr>
                      <th className="text-left text-sky-200/70 pr-3 font-normal pb-1">Year</th>
                      {MONTHS.map((month) => (
                        <th key={month} className="text-center text-sky-200/70 font-normal w-10 pb-1">{month}</th>
                      ))}
                      <th className="text-right text-sky-200/70 font-normal pl-2 pb-1">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {researchHeatmap.years.map((year) => {
                      const yearTotal = Object.values(researchHeatmap.rows[year] ?? {}).reduce((sum, value) => sum + value, 0);
                      return (
                        <tr key={year}>
                          <td className="text-sky-100/80 pr-3 py-0.5 font-mono">{year}</td>
                          {Array.from({ length: 12 }, (_, idx) => {
                            const value = researchHeatmap.rows[year]?.[idx];
                            return (
                              <td key={idx} className="text-center py-0.5">
                                <span
                                  className="inline-block w-9 rounded text-center py-0.5 text-xs font-mono"
                                  style={{ background: heatColor(value), color: value == null ? "#94a3b8" : value >= 0 ? "#86efac" : "#fca5a5" }}
                                >
                                  {value == null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(1)}`}
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
                href={strategyHref(s.strategy_id, s.variant)}
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
