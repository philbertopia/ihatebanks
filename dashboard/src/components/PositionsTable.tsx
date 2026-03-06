"use client";
import { Position, fmtUsd, fmtDelta, fmtPct, daysToExpiry } from "@/lib/api";
import PnLBadge from "./PnLBadge";

interface Props {
  positions: Position[];
  compact?: boolean;
}

export default function PositionsTable({ positions, compact = false }: Props) {
  if (!positions.length) {
    return (
      <div className="text-center py-12 text-gray-500">No open positions</div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left">
        <thead>
          <tr className="border-b border-gray-700 text-gray-400 text-xs uppercase tracking-wider">
            <th className="pb-3 pr-4">Symbol</th>
            {!compact && <th className="pb-3 pr-4">Contract</th>}
            <th className="pb-3 pr-4">Strike</th>
            <th className="pb-3 pr-4">Expiry</th>
            <th className="pb-3 pr-4">DTE</th>
            <th className="pb-3 pr-4">Delta</th>
            <th className="pb-3 pr-4">Entry</th>
            <th className="pb-3 pr-4">Current</th>
            {!compact && <th className="pb-3 pr-4">Ext%</th>}
            <th className="pb-3">P&L</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800">
          {positions.map((p) => {
            const delta = p.current_delta ?? p.entry_delta ?? 0;
            const dte = daysToExpiry(p.expiration_date);
            const isWarning = delta < 0.70;
            const isCritical = delta < 0.65 || dte <= 7;
            return (
              <tr
                key={p.id}
                className={`transition-colors ${
                  isCritical
                    ? "bg-red-950/30"
                    : isWarning
                    ? "bg-amber-950/20"
                    : "hover:bg-gray-800/50"
                }`}
              >
                <td className="py-3 pr-4 font-semibold text-white">{p.underlying}</td>
                {!compact && (
                  <td className="py-3 pr-4 font-mono text-xs text-gray-300">
                    {p.contract_symbol.slice(-15)}
                  </td>
                )}
                <td className="py-3 pr-4 text-gray-300">${p.strike.toFixed(0)}</td>
                <td className="py-3 pr-4 text-gray-300">{p.expiration_date}</td>
                <td className={`py-3 pr-4 font-mono ${dte <= 7 ? "text-red-400 font-bold" : "text-gray-300"}`}>
                  {dte}d
                </td>
                <td className={`py-3 pr-4 font-mono font-semibold ${
                  isCritical ? "text-red-400" : isWarning ? "text-amber-400" : "text-pink-300"
                }`}>
                  {fmtDelta(delta)}
                </td>
                <td className="py-3 pr-4 font-mono text-gray-300">${p.entry_price.toFixed(2)}</td>
                <td className="py-3 pr-4 font-mono text-gray-300">
                  {p.current_price != null ? `$${p.current_price.toFixed(2)}` : "—"}
                </td>
                {!compact && (
                  <td className="py-3 pr-4 text-gray-400">
                    {fmtPct(p.entry_extrinsic_pct)}
                  </td>
                )}
                <td className="py-3">
                  <PnLBadge value={p.unrealized_pnl} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
