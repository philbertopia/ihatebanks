"use client";
import { fmtUsd } from "@/lib/api";

interface Props {
  value: number | null | undefined;
  className?: string;
}

export default function PnLBadge({ value, className = "" }: Props) {
  if (value == null) return <span className={`text-gray-400 ${className}`}>—</span>;
  const color = value > 0 ? "text-green-400" : value < 0 ? "text-red-400" : "text-gray-300";
  return <span className={`font-mono font-semibold ${color} ${className}`}>{fmtUsd(value)}</span>;
}
