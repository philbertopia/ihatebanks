"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  useBacktestStrategyComparison,
  useStrategyCatalog,
  type BacktestStrategyComparison,
} from "@/lib/api";

const FAMILIES = [
  { key: "all", label: "All Strategies" },
  { key: "openclaw_put_credit_spread", label: "Put Credit Spread" },
  { key: "openclaw_call_credit_spread", label: "Call Credit Spread" },
  { key: "intraday_open_close_options", label: "Intraday O/C" },
  { key: "stock_replacement", label: "Stock Replacement" },
  { key: "_wheel", label: "Wheel" },
  { key: "_leaps", label: "LEAPS" },
];

const SORT_KEYS = [
  { key: "oosSharpe", label: "OOS Sharpe" },
  { key: "oosDrawdown", label: "OOS Max DD" },
  { key: "oosReturn", label: "OOS Return" },
  { key: "return", label: "Return" },
  { key: "sharpe", label: "Sharpe" },
  { key: "winRate", label: "Win Rate" },
  { key: "drawdown", label: "Max DD" },
  { key: "profitFactor", label: "Profit Factor" },
] as const;

type SortKey = (typeof SORT_KEYS)[number]["key"];

function strategyFamily(id: string, variant?: string): string {
  if (id.includes("call_credit_spread")) return "CCS";
  if (id.includes("put_credit_spread")) return "PCS";
  if (id.includes("intraday_open_close_options")) return "Intraday";
  if (id.includes("stock_options")) return "Stock Opts";
  if (id.includes("tqqq_swing")) return "TQQQ";
  if (id.includes("hybrid")) return "Hybrid";
  if (id.includes("stock_replacement")) {
    if (variant?.startsWith("wheel_")) return "Wheel";
    if (variant?.startsWith("leaps_")) return "LEAPS";
    return "Stock Repl";
  }
  return "Custom";
}

function familyColor(id: string, variant?: string): string {
  if (id.includes("call_credit_spread")) return "bg-rose-900/50 text-rose-300 border-rose-700";
  if (id.includes("put_credit_spread")) return "bg-purple-900/50 text-purple-300 border-purple-700";
  if (id.includes("intraday_open_close_options")) return "bg-cyan-900/50 text-cyan-300 border-cyan-700";
  if (id.includes("stock_options")) return "bg-pink-900/50 text-pink-300 border-pink-700";
  if (id.includes("tqqq_swing")) return "bg-yellow-900/50 text-yellow-300 border-yellow-700";
  if (id.includes("hybrid")) return "bg-teal-900/50 text-teal-300 border-teal-700";
  if (id.includes("stock_replacement")) {
    if (variant?.startsWith("wheel_")) return "bg-amber-900/50 text-amber-300 border-amber-700";
    if (variant?.startsWith("leaps_")) return "bg-sky-900/50 text-sky-300 border-sky-700";
    return "bg-orange-900/50 text-orange-300 border-orange-700";
  }
  return "bg-gray-700 text-gray-300 border-gray-600";
}

function universeLabel(c: BacktestStrategyComparison): string {
  if (!c.universe_profile) return "—";
  const size = c.universe_size ? ` (${c.universe_size})` : "";
  return `${c.universe_profile}${size}`;
}

function sanitizeDrawdown(value: number | undefined | null): number | null {
  if (value == null || !Number.isFinite(value)) return null;
  return Math.min(Math.max(value, 0), 100);
}

function RankBadge({ rank, isChampion }: { rank: number; isChampion?: boolean }) {
  if (isChampion) {
    return (
      <span className="inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold bg-yellow-500 text-black">
        1
      </span>
    );
  }
  const colors: Record<number, string> = {
    1: "bg-yellow-500 text-black",
    2: "bg-gray-400 text-black",
    3: "bg-amber-700 text-white",
  };
  return (
    <span
      className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
        colors[rank] ?? "bg-gray-700 text-gray-300"
      }`}
    >
      {rank}
    </span>
  );
}

function ReturnCell({ value }: { value: number }) {
  const color = value >= 50 ? "text-green-400" : value >= 0 ? "text-green-300" : "text-red-400";
  return (
    <span className={`font-mono font-bold ${color}`}>
      {value >= 0 ? "+" : ""}
      {value.toFixed(1)}%
    </span>
  );
}

function MetricCell({ value, suffix = "", decimals = 2 }: { value: number | undefined | null; suffix?: string; decimals?: number }) {
  if (value == null || !Number.isFinite(value)) return <span className="text-gray-500">—</span>;
  return (
    <span className="font-mono text-gray-200">
      {value.toFixed(decimals)}
      {suffix}
    </span>
  );
}

function DrawdownCell({ value }: { value: number | undefined | null }) {
  const dd = sanitizeDrawdown(value);
  if (dd == null) return <span className="text-gray-500">—</span>;
  const color = dd < 5 ? "text-green-400" : dd < 20 ? "text-yellow-400" : "text-red-400";
  return <span className={`font-mono ${color}`}>{dd.toFixed(1)}%</span>;
}

function WinRateCell({ value }: { value: number | undefined | null }) {
  if (value == null) return <span className="text-gray-500">—</span>;
  const color = value >= 90 ? "text-green-400" : value >= 60 ? "text-green-300" : value >= 40 ? "text-yellow-400" : "text-red-400";
  return <span className={`font-mono ${color}`}>{value.toFixed(1)}%</span>;
}

export default function StrategiesPage() {
  const { data: comparisons, isLoading, error } = useBacktestStrategyComparison();
  const { data: catalog } = useStrategyCatalog();
  const [family, setFamily] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("oosSharpe");
  const [sortAsc, setSortAsc] = useState(false);

  // Build a lookup of champion status, universe_note, and status from catalog
  const catalogMap = useMemo(() => {
    const map = new Map<string, { champion: boolean; universe_note?: string; status?: string }>();
    for (const entry of catalog ?? []) {
      map.set(`${entry.strategy_id}|${entry.variant}`, {
        champion: entry.champion === true,
        universe_note: entry.universe_note,
        status: entry.status,
      });
    }
    return map;
  }, [catalog]);

  const sorted = useMemo(() => {
    if (!comparisons) return [];
    let rows = comparisons.filter((c) => {
      const meta = catalogMap.get(`${c.strategy_id}|${c.variant}`);
      // Only show catalog-registered, non-archived strategies
      if (catalog && !meta) return false;
      if (meta?.status === "archived") return false;
      if (family === "all") return true;
      if (family === "_wheel") return c.strategy_id === "stock_replacement" && c.variant?.startsWith("wheel_");
      if (family === "_leaps") return c.strategy_id === "stock_replacement" && c.variant?.startsWith("leaps_");
      return c.strategy_id === family;
    });

    rows = rows.slice().sort((a, b) => {
      let av = 0, bv = 0;
      switch (sortKey) {
        case "oosSharpe":
          av = a.latest_oos_sharpe_ratio ?? -999;
          bv = b.latest_oos_sharpe_ratio ?? -999;
          if (av === bv) {
            const ddA = -(a.latest_oos_max_drawdown_pct ?? 999);
            const ddB = -(b.latest_oos_max_drawdown_pct ?? 999);
            if (ddA !== ddB) return sortAsc ? ddA - ddB : ddB - ddA;
            const retA = a.latest_oos_return_pct ?? -999;
            const retB = b.latest_oos_return_pct ?? -999;
            return sortAsc ? retA - retB : retB - retA;
          }
          break;
        case "oosDrawdown":
          av = -(a.latest_oos_max_drawdown_pct ?? 999);
          bv = -(b.latest_oos_max_drawdown_pct ?? 999);
          break;
        case "oosReturn":
          av = a.latest_oos_return_pct ?? -999;
          bv = b.latest_oos_return_pct ?? -999;
          break;
        case "return":
          av = a.latest_total_return_pct ?? 0;
          bv = b.latest_total_return_pct ?? 0;
          break;
        case "sharpe":
          av = a.latest_sharpe_ratio ?? 0;
          bv = b.latest_sharpe_ratio ?? 0;
          break;
        case "winRate":
          av = a.latest_win_rate ?? 0;
          bv = b.latest_win_rate ?? 0;
          break;
        case "drawdown":
          av = -(a.latest_max_drawdown_pct ?? 0);
          bv = -(b.latest_max_drawdown_pct ?? 0);
          break;
        case "profitFactor":
          av = a.latest_profit_factor ?? 0;
          bv = b.latest_profit_factor ?? 0;
          break;
      }
      return sortAsc ? av - bv : bv - av;
    });

    return rows;
  }, [comparisons, family, sortKey, sortAsc]);

  // Find champion strategy
  const champion = useMemo(() => {
    if (!comparisons || !catalog) return null;
    for (const entry of catalog) {
      if (entry.champion) {
        return comparisons.find(
          (c) => c.strategy_id === entry.strategy_id && c.variant === entry.variant
        ) ?? null;
      }
    }
    return sorted[0] ?? null;
  }, [comparisons, catalog, sorted]);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  const sortIcon = (key: SortKey) =>
    sortKey === key ? (sortAsc ? " ^" : " v") : "";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white mb-1">Strategy Leaderboard</h2>
          <p className="text-sm text-gray-500">
            Ranked by OOS Sharpe, then OOS Max DD, then OOS Return.
          </p>
        </div>
        <Link
          href="/backtest"
          className="text-xs text-pink-300 hover:text-pink-200 border border-pink-800 rounded px-3 py-1.5"
        >
          Detailed charts →
        </Link>
      </div>

      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          Could not load strategy data. Please try refreshing the page.
        </div>
      )}

      {!error && !isLoading && sorted.length === 0 && (
        <div className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-6 text-center text-sm text-gray-400">
          No strategies found. Run a backtest first: <code className="font-mono text-gray-300">python main.py backtest</code>
        </div>
      )}

      {/* Champion Banner */}
      {champion && (
        <div className="bg-gradient-to-r from-yellow-900/40 to-amber-900/20 border border-yellow-700/60 rounded-xl p-5">
          <div className="flex items-start gap-4 flex-wrap">
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-2xl">👑</span>
              <span className="text-yellow-400 font-bold text-sm uppercase tracking-wider">Champion Strategy</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 flex-wrap mb-1">
                <p className="text-white font-bold text-lg leading-tight">{champion.strategy_name}</p>
                <span className="font-mono text-yellow-300/70 text-sm">{champion.variant}</span>
                <span className={`text-[11px] px-2 py-0.5 rounded border ${familyColor(champion.strategy_id, champion.variant)}`}>
                  {strategyFamily(champion.strategy_id, champion.variant)}
                </span>
              </div>
              <div className="flex gap-5 flex-wrap text-sm mt-2">
                <div>
                  <span className="text-gray-400 text-xs">Return</span>
                  <p className="text-green-400 font-mono font-bold text-xl">
                    +{(champion.latest_total_return_pct ?? 0).toFixed(1)}%
                  </p>
                </div>
                <div>
                  <span className="text-gray-400 text-xs">Win Rate</span>
                  <p className="text-green-300 font-mono font-bold text-xl">
                    {(champion.latest_win_rate ?? 0).toFixed(1)}%
                  </p>
                </div>
                <div>
                  <span className="text-gray-400 text-xs">Sharpe</span>
                  <p className="text-pink-300 font-mono font-bold text-xl">
                    {(champion.latest_sharpe_ratio ?? 0).toFixed(2)}
                  </p>
                </div>
                <div>
                  <span className="text-gray-400 text-xs">Max DD</span>
                  <p className="text-yellow-300 font-mono font-bold text-xl">
                    {(sanitizeDrawdown(champion.latest_max_drawdown_pct) ?? 0).toFixed(1)}%
                  </p>
                </div>
              </div>
              {catalogMap.get(`${champion.strategy_id}|${champion.variant}`)?.universe_note && (
                <p className="text-yellow-200/60 text-xs mt-2">
                  {catalogMap.get(`${champion.strategy_id}|${champion.variant}`)?.universe_note}
                </p>
              )}
            </div>
            <Link
              href={`/strategies/${champion.variant}`}
              className="shrink-0 px-4 py-2 bg-yellow-600 hover:bg-yellow-500 text-black text-xs font-bold rounded-lg transition-colors"
            >
              View Charts →
            </Link>
          </div>
        </div>
      )}

      {/* Summary banner — top 4 */}
      {sorted.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {sorted.slice(0, 4).map((c, i) => {
            const isChampion = catalogMap.get(`${c.strategy_id}|${c.variant}`)?.champion === true;
            return (
              <div
                key={c.strategy_id + c.variant}
                className={`rounded-xl p-4 border ${
                  isChampion
                    ? "bg-yellow-900/20 border-yellow-700/50"
                    : "bg-gray-800 border-gray-700"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <RankBadge rank={i + 1} isChampion={isChampion} />
                  {isChampion && <span className="text-yellow-400 text-xs font-bold">CHAMPION</span>}
                  {!isChampion && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${familyColor(c.strategy_id, c.variant)}`}>
                      {strategyFamily(c.strategy_id, c.variant)}
                    </span>
                  )}
                </div>
                <p className="text-white text-xs font-semibold leading-tight truncate">
                  {c.strategy_name}
                </p>
                <p className="text-gray-500 text-[11px] font-mono truncate">{c.variant}</p>
                <p className={`text-xl font-bold font-mono mt-2 ${(c.latest_total_return_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {(c.latest_total_return_pct ?? 0) >= 0 ? "+" : ""}
                  {(c.latest_total_return_pct ?? 0).toFixed(1)}%
                </p>
                <div className="flex gap-3 mt-1 text-[11px] text-gray-400">
                  <span>WR: {(c.latest_win_rate ?? 0).toFixed(0)}%</span>
                  <span>SR: {(c.latest_sharpe_ratio ?? 0).toFixed(2)}</span>
                  <span>DD: {(sanitizeDrawdown(c.latest_max_drawdown_pct) ?? 0).toFixed(1)}%</span>
                </div>
                <div className="flex gap-2 mt-1 text-[10px] text-gray-500">
                  <span>
                    OOS SR: {c.latest_oos_sharpe_ratio == null ? "—" : c.latest_oos_sharpe_ratio.toFixed(2)}
                  </span>
                  <span>
                    OOS DD: {sanitizeDrawdown(c.latest_oos_max_drawdown_pct) == null ? "—" : `${(sanitizeDrawdown(c.latest_oos_max_drawdown_pct) ?? 0).toFixed(1)}%`}
                  </span>
                  <span className={!c.has_oos_summary ? "text-gray-500" : c.oos_pass_validation ? "text-green-400" : "text-red-400"}>
                    {!c.has_oos_summary ? "OOS N/A" : c.oos_pass_validation ? "Validated" : "Not Validated"}
                  </span>
                </div>
                {c.universe_profile && (
                  <p className="text-[10px] text-gray-500 mt-1 font-mono">
                    {universeLabel(c)}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Key Findings */}
      <div className="bg-gray-800/60 border border-pink-800/50 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-pink-300 mb-3 uppercase tracking-wider">Key Findings — 2020–2025 Backtest</h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 text-xs text-gray-400">
          <div className="bg-gray-900/50 rounded-lg p-3 border border-purple-900/50">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] px-1.5 py-0.5 rounded border bg-purple-900/50 text-purple-300 border-purple-700">PCS</span>
              <p className="text-green-400 font-bold text-base font-mono">+139% · SR 3.87</p>
            </div>
            <p className="text-gray-200 font-medium mb-1">Put Credit Spread — Champion</p>
            <p>Best risk-adjusted strategy: 98.6% win rate, only 2.1% max drawdown. Sells 4.5% OTM put spreads on SPY/QQQ during bullish regimes. Rides theta decay with 50% profit exits.</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-3 border border-rose-900/50">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] px-1.5 py-0.5 rounded border bg-rose-900/50 text-rose-300 border-rose-700">CCS</span>
              <p className="text-green-400 font-bold text-base font-mono">+142% · SR 3.80</p>
            </div>
            <p className="text-gray-200 font-medium mb-1">Call Credit Spread — Bearish Mirror</p>
            <p>Sells OTM calls above spot (4.5% OTM) — the bearish/neutral mirror of PCS. Performs best in rangebound markets. Avoids entering when price is &gt;8% above MA50. Near-zero drawdown at 1.2%.</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-3 border border-amber-900/50">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] px-1.5 py-0.5 rounded border bg-amber-900/50 text-amber-300 border-amber-700">Wheel</span>
              <p className="text-green-400 font-bold text-base font-mono">+165% · SR 0.69</p>
            </div>
            <p className="text-gray-200 font-medium mb-1">Wheel Strategy — Mechanical Income</p>
            <p>Sell CSP → get assigned → sell covered calls → get called away → repeat. Collects premium at every stage. Aggressive variant (d40) delivers +185%. Higher directional exposure than credit spreads.</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-3 border border-gray-700">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] px-1.5 py-0.5 rounded border bg-orange-900/50 text-orange-300 border-orange-700">Stock Repl</span>
              <p className="text-green-400 font-bold text-base font-mono">+323.8%</p>
            </div>
            <p className="text-gray-200 font-medium mb-1">full_filter_20pos — Diversification Wins</p>
            <p>Raising max positions 10→20 with the top_50 universe turned +71.1% into +323.8% — a 4× uplift from diversification alone. All 4 signal gates (VIX + breadth + order block + sector trend) remain active.</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-3 border border-gray-700">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] px-1.5 py-0.5 rounded border bg-orange-900/50 text-orange-300 border-orange-700">Stock Repl</span>
              <p className="text-pink-300 font-bold text-base font-mono">SR 0.70 · DD 41.4%</p>
            </div>
            <p className="text-gray-200 font-medium mb-1">full_filter_iv_rank — Best Sharpe</p>
            <p>IV rank gate (only enter when options are in the cheapest 40th percentile of their own 252-day history) cuts max drawdown by 15pp vs baseline. Best risk-adjusted stock replacement variant.</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-3 border border-gray-700">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] px-1.5 py-0.5 rounded border bg-orange-900/50 text-orange-300 border-orange-700">Stock Repl</span>
              <p className="text-green-300 font-bold text-base font-mono">+320.5% · DD 40.8%</p>
            </div>
            <p className="text-gray-200 font-medium mb-1">full_filter_iv_rs — Best Overall</p>
            <p>IV rank + relative strength combined: near-identical return to baseline (+320.5% vs +323.8%) but 15.6pp lower max drawdown. Best blend of return and risk in the stock replacement family.</p>
          </div>
        </div>
      </div>

      {/* Family filter */}
      <div className="flex flex-wrap gap-2">
        {FAMILIES.map((f) => (
          <button
            key={f.key}
            onClick={() => setFamily(f.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              family === f.key
                ? "bg-pink-600 border-pink-500 text-white"
                : "bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Leaderboard table */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        {isLoading && (
          <p className="text-gray-500 p-6 text-sm">Loading strategies...</p>
        )}
        {error && (
          <p className="text-red-400 p-6 text-sm">Could not connect to API — is Python server running?</p>
        )}
        {!isLoading && !error && sorted.length === 0 && (
          <div className="p-6 text-gray-500 text-sm">
            No strategy data found. Run:{" "}
            <code className="bg-gray-900 px-1 rounded text-xs">
              python main.py backtest-batch --start 2020-01-01 --end 2025-12-31
            </code>
          </div>
        )}
        {sorted.length > 0 && (
          <>
            <div className="md:hidden p-3 space-y-3">
              {sorted.map((c, idx) => {
                const isChampion = catalogMap.get(`${c.strategy_id}|${c.variant}`)?.champion === true;
                return (
                  <div key={`m-${c.strategy_id}-${c.variant}`} className="bg-gray-900 border border-gray-700 rounded-lg p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <RankBadge rank={idx + 1} isChampion={isChampion} />
                          <p className="text-white font-semibold leading-tight">{c.strategy_name}</p>
                        </div>
                        <p className="text-xs text-gray-500 font-mono mt-1">{c.variant}</p>
                        <p className="text-[11px] text-gray-400 mt-1">{universeLabel(c)}</p>
                      </div>
                      <div className="text-right">
                        <p className={`font-mono text-lg font-bold ${(c.latest_total_return_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {(c.latest_total_return_pct ?? 0) >= 0 ? "+" : ""}
                          {(c.latest_total_return_pct ?? 0).toFixed(1)}%
                        </p>
                        <p className="text-[11px] text-gray-400">SR {(c.latest_sharpe_ratio ?? 0).toFixed(2)}</p>
                        <p className="text-[11px] text-gray-400">DD {(sanitizeDrawdown(c.latest_max_drawdown_pct) ?? 0).toFixed(1)}%</p>
                      </div>
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <span className={`text-xs font-semibold ${!c.has_oos_summary ? "text-gray-500" : c.oos_pass_validation ? "text-green-400" : "text-red-400"}`}>
                        {!c.has_oos_summary ? "OOS: N/A" : c.oos_pass_validation ? "OOS: PASS" : "OOS: FAIL"}
                      </span>
                      <Link href={`/strategies/${c.variant}`} className="text-xs text-pink-300 underline underline-offset-2">
                        View Details →
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-gray-700 text-gray-400 text-xs uppercase tracking-wider bg-gray-900/50">
                  <th className="py-3 pl-5 pr-3 w-10">#</th>
                  <th className="py-3 pr-4">Strategy</th>
                  <th className="py-3 pr-4">Family</th>
                  <th className="py-3 pr-4">Universe</th>
                  <th className="py-3 pr-4">Period</th>
                  <th
                    className="py-3 pr-4 cursor-pointer hover:text-white select-none"
                    onClick={() => handleSort("oosSharpe")}
                  >
                    OOS Sharpe{sortIcon("oosSharpe")}
                  </th>
                  <th
                    className="py-3 pr-4 cursor-pointer hover:text-white select-none"
                    onClick={() => handleSort("oosDrawdown")}
                  >
                    OOS Max DD{sortIcon("oosDrawdown")}
                  </th>
                  <th
                    className="py-3 pr-4 cursor-pointer hover:text-white select-none"
                    onClick={() => handleSort("oosReturn")}
                  >
                    OOS Return{sortIcon("oosReturn")}
                  </th>
                  <th
                    className="py-3 pr-4 cursor-pointer hover:text-white select-none"
                    onClick={() => handleSort("return")}
                  >
                    Return{sortIcon("return")}
                  </th>
                  <th
                    className="py-3 pr-4 cursor-pointer hover:text-white select-none"
                    onClick={() => handleSort("winRate")}
                  >
                    Win Rate{sortIcon("winRate")}
                  </th>
                  <th
                    className="py-3 pr-4 cursor-pointer hover:text-white select-none"
                    onClick={() => handleSort("profitFactor")}
                  >
                    PF{sortIcon("profitFactor")}
                  </th>
                  <th
                    className="py-3 pr-4 cursor-pointer hover:text-white select-none"
                    onClick={() => handleSort("sharpe")}
                  >
                    Sharpe{sortIcon("sharpe")}
                  </th>
                  <th
                    className="py-3 pr-4 cursor-pointer hover:text-white select-none"
                    onClick={() => handleSort("drawdown")}
                  >
                    Max DD{sortIcon("drawdown")}
                  </th>
                  <th className="py-3 pr-4">Validated</th>
                  <th className="py-3 pr-4">Runs</th>
                  <th className="py-3 pr-5">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700/50">
                {sorted.map((c, idx) => {
                  const isChampion = catalogMap.get(`${c.strategy_id}|${c.variant}`)?.champion === true;
                  const uNote = catalogMap.get(`${c.strategy_id}|${c.variant}`)?.universe_note;
                  return (
                    <tr
                      key={c.strategy_id + c.variant}
                      className={`transition-colors ${
                        isChampion ? "bg-yellow-900/10 hover:bg-yellow-900/20" : "hover:bg-gray-700/30"
                      }`}
                    >
                      <td className="py-3 pl-5 pr-3">
                        <div className="flex items-center gap-1.5">
                          <RankBadge rank={idx + 1} isChampion={isChampion} />
                          {isChampion && <span className="text-yellow-400 text-[10px]">👑</span>}
                        </div>
                      </td>
                      <td className="py-3 pr-4">
                        <p className="text-white font-semibold text-sm leading-tight">{c.strategy_name}</p>
                        <p className="text-gray-500 font-mono text-[11px]">{c.variant}</p>
                      </td>
                      <td className="py-3 pr-4">
                        <span className={`text-[11px] px-2 py-0.5 rounded border ${familyColor(c.strategy_id, c.variant)}`}>
                          {strategyFamily(c.strategy_id, c.variant)}
                        </span>
                      </td>
                      <td className="py-3 pr-4">
                        <span className="text-xs font-mono text-gray-300">{universeLabel(c)}</span>
                        {uNote && (
                          <p className="text-[10px] text-gray-500 leading-tight mt-0.5 max-w-[180px]">{uNote}</p>
                        )}
                      </td>
                      <td className="py-3 pr-4 text-gray-400 font-mono text-xs whitespace-nowrap">
                        {c.latest_start_date?.slice(0, 7)} – {c.latest_end_date?.slice(0, 7)}
                      </td>
                      <td className="py-3 pr-4">
                        <MetricCell value={c.latest_oos_sharpe_ratio} />
                      </td>
                      <td className="py-3 pr-4">
                        <DrawdownCell value={c.latest_oos_max_drawdown_pct} />
                      </td>
                      <td className="py-3 pr-4">
                        <MetricCell value={c.latest_oos_return_pct} suffix="%" decimals={1} />
                      </td>
                      <td className="py-3 pr-4">
                        <ReturnCell value={c.latest_total_return_pct ?? 0} />
                      </td>
                      <td className="py-3 pr-4">
                        <WinRateCell value={c.latest_win_rate} />
                      </td>
                      <td className="py-3 pr-4">
                        <MetricCell value={c.latest_profit_factor} />
                      </td>
                      <td className="py-3 pr-4">
                        <MetricCell value={c.latest_sharpe_ratio} />
                      </td>
                      <td className="py-3 pr-4">
                        <DrawdownCell value={c.latest_max_drawdown_pct} />
                      </td>
                      <td className="py-3 pr-4">
                        <span
                          className={`text-xs font-semibold ${!c.has_oos_summary ? "text-gray-500" : c.oos_pass_validation ? "text-green-400" : "text-red-400"}`}
                          title={c.oos_criteria ? `Criteria: Sharpe ≥ ${c.oos_criteria.sharpe_threshold}, MaxDD ≤ ${c.oos_criteria.max_dd_threshold}%, Return > ${c.oos_criteria.return_threshold ?? 0}%` : undefined}
                        >
                          {!c.has_oos_summary ? "N/A" : c.oos_pass_validation ? "PASS" : "FAIL"}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-gray-400 font-mono text-xs">{c.runs}</td>
                      <td className="py-3 pr-5">
                        <Link
                          href={`/strategies/${c.variant}`}
                          className="text-xs text-pink-300 hover:text-pink-200 underline underline-offset-2"
                        >
                          View →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          </>
        )}
      </div>

      {/* Universe explainer */}
      <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-3">Strategy Guide</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs text-gray-400">
          <div>
            <p className="text-gray-200 font-medium mb-1">Put & Call Credit Spreads (PCS / CCS)</p>
            <p>Both spread strategies trade <strong className="text-gray-100">SPY and QQQ only</strong> — not affected by universe selection. PCS sells OTM puts below spot (bullish bias). CCS sells OTM calls above spot (bearish/neutral bias). Both collect premium with defined max loss via the long leg. Best Sharpe ratios of all strategies (3–4+).</p>
          </div>
          <div>
            <p className="text-gray-200 font-medium mb-1">Wheel Strategy</p>
            <p>The wheel cycles between CSP and covered call phases using the <strong className="text-gray-100">top_50 universe</strong>. Sell puts → if assigned own shares → sell calls → if called away repeat. Collects premium in both phases. Higher directional exposure than credit spreads but still benefits from theta decay.</p>
          </div>
          <div>
            <p className="text-gray-200 font-medium mb-1">Stock Replacement</p>
            <p>Buys deep ITM calls on individual stocks. The <strong className="text-gray-100">top_50 universe</strong> with max 20 positions significantly outperforms the default 10-symbol universe — diversification across more setups compounds returns. Full signal gates (VIX + breadth + IV rank + relative strength) improve risk-adjusted returns.</p>
          </div>
          <div>
            <p className="text-gray-200 font-medium mb-1">LEAPS</p>
            <p>Long-duration deep ITM calls (180–400 DTE, 0.80–0.85 delta). Near-pure intrinsic value tracking — minimal theta decay relative to intrinsic. Buy once, hold 6–12 months. Requires cache regeneration: <code className="font-mono bg-gray-900 px-1 rounded">python main.py generate</code> to add 180–400 DTE option data.</p>
          </div>
        </div>
      </div>

      {/* Risk-Adjusted vs Raw Return note */}
      <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-3">Reading the Leaderboard</h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 text-xs text-gray-400">
          <div>
            <p className="text-gray-200 font-medium mb-1">Sharpe Ratio</p>
            <p>Risk-adjusted return per unit of volatility. Above 1.0 is good, above 2.0 is excellent. The Sharpe ratio penalises strategies with large drawdowns even if raw return is high.</p>
          </div>
          <div>
            <p className="text-gray-200 font-medium mb-1">Max Drawdown</p>
            <p>The largest peak-to-trough decline during the test period. A 50%+ drawdown means your capital was cut in half at some point — even if you recovered later.</p>
          </div>
          <div>
            <p className="text-gray-200 font-medium mb-1">Profit Factor</p>
            <p>Gross profit divided by gross loss. Above 1.5 is solid. A strategy with 100% win rate and small losses can still have a low profit factor if wins are tiny.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
