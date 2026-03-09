"""
Generate a research-only 10-year comparison for wheel strategy variants.

This script does not write into the official dashboard run stores. It loads the
local option-chain cache, filters it to the requested universe profile, runs a
full-period wheel backtest plus walk-forward validation for each requested
variant, and writes reports under data/reports/.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import _filter_backtest_data_to_universe, _trading_days_for_period, load_config
from ovtlyr.backtester.data_collector import BacktestDataCollector
from ovtlyr.backtester.stock_replacement_profiles import apply_stock_replacement_variant
from ovtlyr.backtester.walkforward import generate_walkforward_windows, summarize_oos_runs
from ovtlyr.backtester.wheel_engine import run_wheel_backtest
from ovtlyr.universe.profiles import load_universe


DEFAULT_VARIANTS = [
    "wheel_d20_c30",
    "wheel_d30_c20",
    "wheel_d30_c30",
    "wheel_d40_c20",
    "wheel_d40_c30",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a research-only 10-year wheel strategy comparison."
    )
    parser.add_argument("--start", default="2016-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2025-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--universe",
        default="top_50",
        help="Universe profile name to filter cached data before the sweep",
    )
    parser.add_argument(
        "--output-base",
        default="data/reports/wheel_10y_research_2016_2025",
        help="Output path without extension",
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        default=DEFAULT_VARIANTS,
        help="Wheel variants to compare",
    )
    parser.add_argument("--train-days", type=int, default=756)
    parser.add_argument("--test-days", type=int, default=252)
    parser.add_argument("--step-days", type=int, default=252)
    return parser.parse_args()


def _date_from_arg(value: str) -> date:
    return date.fromisoformat(str(value))


def _round_obj(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, list):
        return [_round_obj(v) for v in value]
    if isinstance(value, dict):
        return {k: _round_obj(v) for k, v in value.items()}
    return value


def _fmt_pct(value: Any) -> str:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "n/a"
    sign = "+" if num >= 0 else ""
    return f"{sign}{num:.2f}%"


def _fmt_num(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def run_variant_period(data, config: Dict[str, Any], start_day: date, end_day: date, variant: str):
    wheel_config = apply_stock_replacement_variant(config, variant)
    metrics = run_wheel_backtest(data, wheel_config, start_day, end_day)
    return {
        "metrics": {k: v for k, v in metrics.items() if k not in ("equity_curve", "closed_trades")},
    }


def run_variant_walkforward(
    data,
    config: Dict[str, Any],
    start_day: date,
    end_day: date,
    variant: str,
    train_days: int,
    test_days: int,
    step_days: int,
):
    trading_days = _trading_days_for_period(data, start_day, end_day)
    windows = generate_walkforward_windows(trading_days, train_days, test_days, step_days)
    oos_metrics: List[Dict[str, Any]] = []
    rows: List[Dict[str, Any]] = []

    for window in windows:
        metrics = run_variant_period(data, config, window.test_start, window.test_end, variant)["metrics"]
        oos_metrics.append(metrics)
        rows.append(
            {
                "window_index": window.index,
                "train_start": window.train_start.isoformat(),
                "train_end": window.train_end.isoformat(),
                "test_start": window.test_start.isoformat(),
                "test_end": window.test_end.isoformat(),
                "metrics": metrics,
            }
        )

    summary = summarize_oos_runs(
        oos_metrics,
        sharpe_threshold=0.40,
        max_dd_threshold=35.0,
    )
    return summary, rows


def build_ranking(results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in results:
        metrics = row["full_period"]["metrics"]
        oos = row["walkforward_summary"]
        rows.append(
            {
                "variant": row["variant"],
                "pass_validation": bool(oos.get("pass_validation", False)),
                "avg_oos_sharpe_ratio": float(oos.get("avg_sharpe_ratio", 0.0) or 0.0),
                "avg_oos_max_drawdown_pct": float(oos.get("avg_max_drawdown_pct", 0.0) or 0.0),
                "avg_oos_total_return_pct": float(oos.get("avg_total_return_pct", 0.0) or 0.0),
                "total_return_pct": float(metrics.get("total_return_pct", 0.0) or 0.0),
                "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0) or 0.0),
                "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0) or 0.0),
                "total_trades": int(metrics.get("total_trades", 0) or 0),
                "win_rate": float(metrics.get("win_rate", 0.0) or 0.0),
                "avg_hold_days": float(metrics.get("avg_hold_days", 0.0) or 0.0),
            }
        )

    ranked = sorted(
        rows,
        key=lambda row: (
            0 if row["pass_validation"] else 1,
            -row["avg_oos_sharpe_ratio"],
            row["avg_oos_max_drawdown_pct"],
            -row["avg_oos_total_return_pct"],
            -row["total_return_pct"],
        ),
    )
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
    return ranked


def write_json_report(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_round_obj(payload), indent=2), encoding="utf-8")


def write_markdown_report(path: Path, payload: Dict[str, Any]) -> None:
    ranking = payload["ranking"]
    winner = payload["winner"]

    lines: List[str] = []
    lines.append("# Wheel Strategy 10-Year Research")
    lines.append("")
    lines.append(f"- Generated: `{payload['generated_at']}`")
    lines.append(
        f"- Period: `{payload['period']['start']}` to `{payload['period']['end']}` "
        f"({payload['trading_days']} trading days)"
    )
    lines.append(f"- Universe profile: `{payload['universe_profile']}` ({payload['universe_size']} symbols)")
    lines.append("- Strategy family: `stock_replacement` wheel variants")
    lines.append("- Scope: research-only, local workspace")
    lines.append(f"- Winner: `{winner['variant']}`")
    lines.append("")
    lines.append("## Ranking")
    lines.append("")
    lines.append("| Rank | Variant | Return | Sharpe | Max DD | Trades | OOS Return | OOS Sharpe | OOS DD | Pass |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in ranking:
        lines.append(
            f"| {row['rank']} | `{row['variant']}` | {_fmt_pct(row['total_return_pct'])} | "
            f"{_fmt_num(row['sharpe_ratio'])} | {_fmt_pct(row['max_drawdown_pct'])} | "
            f"{row['total_trades']} | {_fmt_pct(row['avg_oos_total_return_pct'])} | "
            f"{_fmt_num(row['avg_oos_sharpe_ratio'])} | {_fmt_pct(row['avg_oos_max_drawdown_pct'])} | "
            f"{'PASS' if row['pass_validation'] else 'FAIL'} |"
        )
    lines.append("")
    lines.append("## Variant Summaries")
    lines.append("")
    for row in payload["variants"]:
        metrics = row["full_period"]["metrics"]
        oos = row["walkforward_summary"]
        lines.append(f"### `{row['variant']}`")
        lines.append("")
        lines.append(
            f"- Full period: return {_fmt_pct(metrics.get('total_return_pct'))}, "
            f"Sharpe {_fmt_num(metrics.get('sharpe_ratio'))}, "
            f"max drawdown {_fmt_pct(metrics.get('max_drawdown_pct'))}, "
            f"trades {int(metrics.get('total_trades', 0) or 0)}, "
            f"win rate {_fmt_pct(metrics.get('win_rate'))}, "
            f"avg hold {_fmt_num(metrics.get('avg_hold_days'))} days"
        )
        lines.append(
            f"- Walk-forward: OOS return {_fmt_pct(oos.get('avg_total_return_pct'))}, "
            f"OOS Sharpe {_fmt_num(oos.get('avg_sharpe_ratio'))}, "
            f"OOS max drawdown {_fmt_pct(oos.get('avg_max_drawdown_pct'))}, "
            f"{'PASS' if oos.get('pass_validation') else 'FAIL'}"
        )
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    start_day = _date_from_arg(args.start)
    end_day = _date_from_arg(args.end)
    output_base = Path(args.output_base)
    if not output_base.is_absolute():
        output_base = ROOT / output_base

    config = load_config()
    collector = BacktestDataCollector(None, config)
    data = collector.load_cached_data(start=start_day, end=end_day)
    if data.empty:
        raise RuntimeError("No cached data found for the requested period.")

    universe_symbols = load_universe(str(args.universe))
    filtered = _filter_backtest_data_to_universe(data, universe_symbols)
    if filtered.empty:
        raise RuntimeError(f"No cached rows matched universe '{args.universe}'.")

    trading_days = _trading_days_for_period(filtered, start_day, end_day)
    variant_rows: List[Dict[str, Any]] = []
    for variant in args.variants:
        full_period = run_variant_period(filtered, config, start_day, end_day, variant)
        walkforward_summary, walkforward_windows = run_variant_walkforward(
            filtered,
            config,
            start_day,
            end_day,
            variant,
            train_days=int(args.train_days),
            test_days=int(args.test_days),
            step_days=int(args.step_days),
        )
        variant_rows.append(
            {
                "variant": variant,
                "full_period": full_period,
                "walkforward_summary": walkforward_summary,
                "walkforward_windows": walkforward_windows,
            }
        )

    ranking = build_ranking(variant_rows)
    winner_variant = ranking[0]["variant"] if ranking else ""
    winner = next((row for row in variant_rows if row["variant"] == winner_variant), None)
    if winner is None:
        raise RuntimeError("No wheel variants produced results.")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy_id": "stock_replacement",
        "family_label": "Wheel Strategy",
        "period": {"start": start_day.isoformat(), "end": end_day.isoformat()},
        "universe_profile": str(args.universe),
        "universe_size": len(set(filtered["underlying"].astype(str))),
        "variants_requested": list(args.variants),
        "train_days": int(args.train_days),
        "test_days": int(args.test_days),
        "step_days": int(args.step_days),
        "trading_days": len(trading_days),
        "data_note": "Uses the local option-chain cache only, filtered to the requested universe profile before the wheel engine runs. This report is research-only and does not update official dashboard backtest metrics.",
        "ranking": ranking,
        "winner": {
            "variant": winner["variant"],
            "full_period": winner["full_period"],
            "walkforward_summary": winner["walkforward_summary"],
        },
        "variants": variant_rows,
    }

    json_path = output_base.with_suffix(".json")
    md_path = output_base.with_suffix(".md")
    write_json_report(json_path, payload)
    write_markdown_report(md_path, payload)
    print(f"Saved JSON report: {json_path}")
    print(f"Saved markdown report: {md_path}")
    print(
        "Winner: "
        f"{winner['variant']} | "
        f"Return={_fmt_pct(winner['full_period']['metrics'].get('total_return_pct'))} | "
        f"OOS Sharpe={_fmt_num(winner['walkforward_summary'].get('avg_sharpe_ratio'))} | "
        f"OOS DD={_fmt_pct(winner['walkforward_summary'].get('avg_max_drawdown_pct'))}"
    )


if __name__ == "__main__":
    main()
