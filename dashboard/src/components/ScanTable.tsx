"use client";
import { useMemo } from "react";
import { ScanResult, fmtPct } from "@/lib/api";

interface Props {
  results: ScanResult[];
  limit?: number;
}

export default function ScanTable({ results, limit }: Props) {
  const display = useMemo(
    () => (limit ? results.slice(0, limit) : results),
    [results, limit]
  );

  const grouped = useMemo(
    () =>
      display.reduce<Record<string, ScanResult[]>>((acc, r) => {
        (acc[r.underlying] ??= []).push(r);
        return acc;
      }, {}),
    [display]
  );

  if (!display.length) {
    return <div className="text-center py-8 text-gray-500">No scan results</div>;
  }

  return (
    <div className="space-y-6">
      {Object.entries(grouped)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([symbol, items]) => (
          <div key={symbol}>
            <div className="flex items-center gap-2 mb-2">
              <h3 className="font-semibold text-white">{symbol}</h3>
              <span className="text-xs text-gray-500">{items.length} qualifying</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                    <th className="pb-2 pr-4">Contract</th>
                    <th className="pb-2 pr-4">Expiry</th>
                    <th className="pb-2 pr-4">DTE</th>
                    <th className="pb-2 pr-4">Delta</th>
                    <th className="pb-2 pr-4">Ask</th>
                    <th className="pb-2 pr-4">Ext%</th>
                    <th className="pb-2 pr-4">Spread%</th>
                    <th className="pb-2 pr-4">Score</th>
                    <th className="pb-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/50">
                  {items.map((r) => (
                    <tr key={r.id} className="hover:bg-gray-800/30 transition-colors">
                      <td className="py-2 pr-4 font-mono text-xs text-gray-300">
                        {r.contract_symbol.slice(-15)}
                      </td>
                      <td className="py-2 pr-4 text-gray-400">{r.expiration_date}</td>
                      <td className="py-2 pr-4 text-gray-400">{r.dte}d</td>
                      <td className="py-2 pr-4 font-mono font-semibold text-pink-300">
                        {r.delta.toFixed(3)}
                      </td>
                      <td className="py-2 pr-4 font-mono text-gray-300">${r.ask.toFixed(2)}</td>
                      <td className="py-2 pr-4 text-gray-400">{fmtPct(r.extrinsic_pct)}</td>
                      <td className="py-2 pr-4 text-gray-400">{fmtPct(r.spread_pct)}</td>
                      <td className="py-2 pr-4">
                        <span className="text-amber-400 font-mono font-semibold">
                          {r.score?.toFixed(1) ?? "—"}
                        </span>
                      </td>
                      <td className="py-2">
                        {r.action_taken === "opened" ? (
                          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-green-900 text-green-300">
                            OPENED
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-gray-700 text-gray-400">
                            candidate
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
    </div>
  );
}
