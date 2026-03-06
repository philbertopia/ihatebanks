"use client";

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  color?: "green" | "red" | "amber" | "blue" | "default";
  loading?: boolean;
}

const colorMap = {
  green: "text-green-400",
  red: "text-red-400",
  amber: "text-amber-400",
  blue: "text-pink-300",
  default: "text-white",
};

export default function StatCard({ label, value, sub, color = "default", loading }: Props) {
  return (
    <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 flex flex-col gap-1">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">{label}</p>
      {loading ? (
        <div className="h-8 w-24 bg-gray-700 rounded animate-pulse mt-1" />
      ) : (
        <p className={`text-2xl font-bold font-mono ${colorMap[color]}`}>{value}</p>
      )}
      {sub && <p className="text-xs text-gray-500">{sub}</p>}
    </div>
  );
}
