from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

from ovtlyr.backtester.intraday_options_engine import IntradayReport


def _row_md(rank: int, row: Dict) -> str:
    option_details = f"{row['option_type'].upper()} {row['expiry']} {row['strike']:.2f}"
    vol_stats = (
        f"buy_vol={row['buy_volume']} | OI={row['open_interest']} | "
        f"Vol/OI={row['vol_oi_ratio']:.2f} ({row['unusual_factor']:.2f}x)"
    )
    greeks = (
        f"d={row['delta']:.3f} g={row['gamma']:.4f} "
        f"th={row['theta']:.4f} v={row['vega']:.4f} iv={row['implied_volatility']:.3f}"
    )
    entry = (
        f"bid={row['bid']:.2f} ask={row['ask']:.2f} prev={row['previous_close']:.2f} "
        f"delta={row['delta']:.3f} -> limit={row['entry_limit']:.2f}"
    )
    exit_plan = row.get("exit_plan", {})
    exit_text = (
        f"target {exit_plan.get('target_pct', 0):.1f}% | "
        f"stop {exit_plan.get('stop_pct', 0):.1f}% | "
        f"trail {exit_plan.get('trailing_activation_pct', 0):.1f}%/{exit_plan.get('trailing_pct', 0):.1f}%"
    )
    risk_flags = ", ".join(row.get("risk_flags", [])) or "None"
    return (
        f"| {rank} | {row['ticker']} | {option_details} | {row['composite_edge_score']:.2f} | "
        f"{row['itm_depth_pct']:.2f}% | {row['atr14']:.2f} ({row['atr_pct']:.2f}%) | "
        f"{vol_stats} | {greeks} | {entry} | {exit_text} | {risk_flags} |"
    )


def build_intraday_markdown(report: IntradayReport) -> str:
    lines: List[str] = []
    lines.append(f"# Intraday Options Candidates — {report.report_date}")
    lines.append("")
    lines.append(f"- Strategy: `{report.strategy_id}` / `{report.variant}`")
    lines.append(
        f"- Contracts scanned: **{report.total_contracts}** | Qualified: **{report.qualified_contracts}** "
        f"(target minimum: {report.min_qualifiers})"
    )
    lines.append(
        f"- Execution window: `{report.execution_window.get('entry_time')}` to "
        f"`{report.execution_window.get('exit_time')}` ET"
    )
    if report.warning:
        lines.append(f"- Warning: {report.warning}")
    lines.append(
        f"- Data quality: observed={report.data_quality_breakdown.get('observed', 0)}, "
        f"mixed={report.data_quality_breakdown.get('mixed', 0)}, "
        f"modeled={report.data_quality_breakdown.get('modeled', 0)}"
    )
    lines.append("")
    lines.append("## Top 15 Ranked Contracts")
    lines.append("")
    lines.append(
        "| Rank | Ticker | Option Details | Edge Score | ITM Depth | ATR-14 | June 4 Stats | Greeks | Entry Recommendation | Exit Plan | Risk Flags |"
    )
    lines.append("|---:|---|---|---:|---:|---|---|---|---|---|---|")
    for i, row in enumerate(report.top_picks, start=1):
        lines.append(_row_md(i, row))

    lines.append("")
    lines.append("## Rationales")
    lines.append("")
    for i, row in enumerate(report.top_picks, start=1):
        lines.append(
            f"{i}. **{row['ticker']} {row['option_type'].upper()} {row['expiry']} {row['strike']:.2f}** "
            f"(Edge {row['composite_edge_score']:.2f})"
        )
        for bullet in row.get("rationale", []):
            lines.append(f"- {bullet}")

    lines.append("")
    lines.append("## Methodology Notes")
    lines.append("")
    lines.append(
        "Candidates are filtered using ATR, ITM status, DTE window, spread/OI quality, and unusual-flow proxy rules. "
        "Composite Edge Score weights are: Vol/OI 40%, ITM depth 20%, ATR% 20%, historical similar-setup win-rate 20%."
    )
    lines.append(
        "Data sources in this phase use the current OVTLYR stack only: Alpaca option snapshots where available plus "
        "synthetic-model fallbacks (OI/volume proxies, previous close proxy) when missing."
    )
    return "\n".join(lines) + "\n"


def write_intraday_report_files(report: IntradayReport, output_dir: str = "data/reports") -> Tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    date_key = str(report.report_date)
    variant = str(report.variant)
    md_path = os.path.join(output_dir, f"intraday_{date_key}_{variant}.md")
    json_path = os.path.join(output_dir, f"intraday_{date_key}_{variant}.json")

    markdown = build_intraday_markdown(report)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "strategy_id": report.strategy_id,
                "strategy_name": report.strategy_name,
                "variant": report.variant,
                "report_date": report.report_date,
                "total_contracts": report.total_contracts,
                "qualified_contracts": report.qualified_contracts,
                "min_qualifiers": report.min_qualifiers,
                "warning": report.warning,
                "data_quality_breakdown": report.data_quality_breakdown,
                "execution_window": report.execution_window,
                "top_picks": report.top_picks,
            },
            f,
            indent=2,
        )

    return md_path, json_path
