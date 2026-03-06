"use client";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { DailyStats, fmtUsd } from "@/lib/api";

interface Props {
  data: DailyStats[];
  compact?: boolean;
}

export default function EquityCurve({ data, compact = false }: Props) {
  if (!data.length) {
    return (
      <div className={`flex items-center justify-center ${compact ? "h-32" : "h-64"} text-gray-500`}>
        No data yet — run <code className="mx-1 text-xs bg-gray-800 px-1 rounded">python main.py collect</code> daily to build history
      </div>
    );
  }

  // Sort ascending and compute cumulative realized P&L
  const sorted = [...data].sort((a, b) => a.stat_date.localeCompare(b.stat_date));
  let cumulative = 0;
  const chartData = sorted.map((d) => {
    cumulative += d.total_pnl_realized;
    return {
      date: d.stat_date.slice(5), // MM-DD
      realized: Math.round(cumulative),
      unrealized: Math.round(d.total_pnl_unrealized),
    };
  });

  const h = compact ? 120 : 260;

  return (
    <ResponsiveContainer width="100%" height={h}>
      <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis
          dataKey="date"
          tick={{ fill: "#6b7280", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "#6b7280", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${v >= 0 ? "" : "-"}${Math.abs(v).toLocaleString()}`}
        />
        <Tooltip
          contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }}
          labelStyle={{ color: "#9ca3af" }}
          formatter={(v: number | undefined, name: string | undefined) => [fmtUsd(v ?? 0), name === "realized" ? "Cum. Realized" : "Unrealized"]}
        />
        <ReferenceLine y={0} stroke="#4b5563" />
        <Line
          type="monotone"
          dataKey="realized"
          stroke="#22c55e"
          strokeWidth={2}
          dot={false}
          name="realized"
        />
        {!compact && (
          <Line
            type="monotone"
            dataKey="unrealized"
            stroke="#60a5fa"
            strokeWidth={1.5}
            dot={false}
            strokeDasharray="4 2"
            name="unrealized"
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
