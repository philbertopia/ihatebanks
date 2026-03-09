"""
Generate a research-only 10-year comparison for the regime credit spread family.

This script intentionally does not write to the official backtest run stores.
It loads only the SPY/QQQ underlying price data needed by the regime engine,
fills the known 2016-2019 cache gap with adjusted-close history from yfinance,
and writes research artifacts under data/reports/.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import _metrics_from_equity_window, _trading_days_for_period, _warmup_start_day
from ovtlyr.backtester.openclaw_engines import run_openclaw_variant
from ovtlyr.backtester.walkforward import generate_walkforward_windows, summarize_oos_runs


DATA_DIR = ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
YF_CACHE_DIR = ROOT / "tmp_yf_cache"

SYMBOLS = ["SPY", "QQQ"]
DEFAULT_VARIANTS = [
    "regime_legacy_defensive",
    "regime_balanced",
    "regime_defensive",
    "regime_vix_baseline",
    "regime_legacy_defensive_bear_only",
    "regime_vix_baseline_bear_only",
]


@dataclass(frozen=True)
class MissingInterval:
    start: date
    end: date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a research-only 10-year regime credit spread comparison."
    )
    parser.add_argument("--start", default="2016-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2025-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--output-base",
        default="data/reports/regime_credit_spread_10y_2016_2025",
        help="Output path without extension",
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        default=DEFAULT_VARIANTS,
        help="Regime credit spread variants to compare",
    )
    parser.add_argument("--train-days", type=int, default=504)
    parser.add_argument("--test-days", type=int, default=126)
    parser.add_argument("--step-days", type=int, default=126)
    return parser.parse_args()


def _date_from_arg(value: str) -> date:
    return date.fromisoformat(str(value))


def load_price_cache(symbols: Sequence[str]) -> pd.DataFrame:
    parts: List[pd.DataFrame] = []
    for path in sorted(glob.glob(str(DATA_DIR / "cache" / "*.parquet"))):
        frame = pd.read_parquet(path, columns=["date", "underlying", "underlying_price"])
        frame = frame[frame["underlying"].isin(symbols)]
        if not frame.empty:
            parts.append(frame)
    if not parts:
        return pd.DataFrame(columns=["date", "underlying", "underlying_price"])
    out = pd.concat(parts, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.date
    return out.sort_values(["date", "underlying"]).reset_index(drop=True)


def _available_days(frame: pd.DataFrame) -> List[date]:
    if frame.empty:
        return []
    grouped = frame.groupby("date")["underlying"].nunique()
    return sorted(d for d, count in grouped.items() if int(count) >= len(SYMBOLS))


def detect_missing_intervals(
    frame: pd.DataFrame,
    start_day: date,
    end_day: date,
    max_expected_gap_days: int = 7,
) -> List[MissingInterval]:
    days = [d for d in _available_days(frame) if start_day <= d <= end_day]
    if not days:
        return [MissingInterval(start=start_day, end=end_day)]

    intervals: List[MissingInterval] = []
    if (days[0] - start_day).days > max_expected_gap_days:
        intervals.append(MissingInterval(start=start_day, end=days[0] - timedelta(days=1)))

    for prev_day, next_day in zip(days, days[1:]):
        if (next_day - prev_day).days > max_expected_gap_days:
            intervals.append(
                MissingInterval(
                    start=prev_day + timedelta(days=1),
                    end=next_day - timedelta(days=1),
                )
            )

    if (end_day - days[-1]).days > max_expected_gap_days:
        intervals.append(MissingInterval(start=days[-1] + timedelta(days=1), end=end_day))
    return intervals


def download_gap_fill(symbols: Sequence[str], intervals: Sequence[MissingInterval]) -> pd.DataFrame:
    if not intervals:
        return pd.DataFrame(columns=["date", "underlying", "underlying_price"])

    YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(YF_CACHE_DIR.resolve()))

    parts: List[pd.DataFrame] = []
    for interval in intervals:
        raw = yf.download(
            list(symbols),
            start=interval.start.isoformat(),
            end=(interval.end + timedelta(days=1)).isoformat(),
            auto_adjust=True,
            progress=False,
        )
        if raw.empty:
            raise RuntimeError(
                f"yfinance returned no data for missing interval {interval.start} to {interval.end}"
            )
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        if not isinstance(close.columns, pd.Index):
            raise RuntimeError("Unexpected yfinance close-price shape")
        if "Close" in close.columns and len(symbols) == 1:
            close = close.rename(columns={"Close": list(symbols)[0]})
        close.index = pd.to_datetime(close.index).date

        rows: List[Dict[str, Any]] = []
        for day_idx, row in close.iterrows():
            for symbol in symbols:
                value = row.get(symbol)
                if pd.notna(value):
                    rows.append(
                        {
                            "date": day_idx,
                            "underlying": symbol,
                            "underlying_price": float(value),
                        }
                    )
        if rows:
            parts.append(pd.DataFrame(rows))

    if not parts:
        return pd.DataFrame(columns=["date", "underlying", "underlying_price"])
    return pd.concat(parts, ignore_index=True).sort_values(["date", "underlying"]).reset_index(drop=True)


def merge_price_sources(
    cache_frame: pd.DataFrame,
    fill_frame: pd.DataFrame,
    intervals: Sequence[MissingInterval],
) -> pd.DataFrame:
    if not intervals:
        return cache_frame.copy()

    keep_mask = pd.Series(True, index=cache_frame.index)
    for interval in intervals:
        in_interval = (cache_frame["date"] >= interval.start) & (cache_frame["date"] <= interval.end)
        keep_mask &= ~in_interval

    out = pd.concat([cache_frame.loc[keep_mask], fill_frame], ignore_index=True)
    return out.sort_values(["date", "underlying"]).reset_index(drop=True)


def run_variant_period(
    frame: pd.DataFrame,
    start_day: date,
    end_day: date,
    variant: str,
) -> Dict[str, Any]:
    output = run_openclaw_variant(
        data=frame,
        config={},
        start_date=start_day,
        end_date=end_day,
        strategy_id="openclaw_regime_credit_spread",
        assumptions_mode=variant,
        universe_symbols=list(SYMBOLS),
    )
    return {
        "metrics": output.metrics,
        "equity_points": output.equity_points,
    }


def run_variant_walkforward(
    frame: pd.DataFrame,
    start_day: date,
    end_day: date,
    variant: str,
    train_days: int,
    test_days: int,
    step_days: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    trading_days = _trading_days_for_period(frame, start_day, end_day)
    windows = generate_walkforward_windows(trading_days, train_days, test_days, step_days)
    oos_metrics: List[Dict[str, Any]] = []
    window_rows: List[Dict[str, Any]] = []

    for window in windows:
        warm_start = _warmup_start_day(trading_days, window.test_start, lookback_days=260)
        result = run_variant_period(frame, warm_start, window.test_end, variant)
        metrics = result["metrics"]
        if warm_start < window.test_start:
            metrics = _metrics_from_equity_window(
                result["equity_points"],
                start_day=window.test_start,
                end_day=window.test_end,
                base_metrics=metrics,
            )
        oos_metrics.append(metrics)
        window_rows.append(
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
        sharpe_threshold=0.70,
        max_dd_threshold=30.0,
    )
    return summary, window_rows


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


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def write_json_report(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_json_safe(payload), handle, indent=2)


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


def write_markdown_report(path: Path, payload: Dict[str, Any]) -> None:
    ranking = payload["ranking"]
    winner = payload["winner"]
    variants = payload["variants"]
    filled = payload["filled_intervals"]

    lines: List[str] = []
    lines.append("# Regime Credit Spread 10-Year Research")
    lines.append("")
    lines.append(f"- Generated: `{payload['generated_at']}`")
    lines.append(
        f"- Period: `{payload['period']['start']}` to `{payload['period']['end']}` "
        f"({payload['trading_days']} trading days)"
    )
    lines.append("- Strategy family: `openclaw_regime_credit_spread`")
    lines.append("- Scope: research-only, local workspace")
    lines.append(f"- Winner: `{winner['variant']}`")
    lines.append("")
    lines.append("## Data Source Note")
    lines.append("")
    lines.append(payload["data_note"])
    lines.append("")
    if filled:
        lines.append("Filled intervals:")
        for interval in filled:
            lines.append(f"- `{interval['start']}` to `{interval['end']}`")
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
    for row in variants:
        metrics = row["full_period"]["metrics"]
        oos = row["walkforward_summary"]
        lines.append(f"### `{row['variant']}`")
        lines.append("")
        lines.append(
            f"- Full period: return {_fmt_pct(metrics.get('total_return_pct'))}, "
            f"Sharpe {_fmt_num(metrics.get('sharpe_ratio'))}, "
            f"max drawdown {_fmt_pct(metrics.get('max_drawdown_pct'))}, "
            f"trades {int(metrics.get('total_trades', 0) or 0)}, "
            f"win rate {_fmt_pct(metrics.get('win_rate'))}"
        )
        lines.append(
            f"- Walk-forward: OOS return {_fmt_pct(oos.get('avg_total_return_pct'))}, "
            f"OOS Sharpe {_fmt_num(oos.get('avg_sharpe_ratio'))}, "
            f"OOS max drawdown {_fmt_pct(oos.get('avg_max_drawdown_pct'))}, "
            f"{'PASS' if oos.get('pass_validation') else 'FAIL'}"
        )
        lines.append("")
    lines.append("## Per-Window OOS Detail")
    lines.append("")
    for row in variants:
        lines.append(f"### `{row['variant']}` windows")
        lines.append("")
        lines.append("| Window | Test Start | Test End | Return | Sharpe | Max DD |")
        lines.append("|---:|---|---|---:|---:|---:|")
        for window in row["walkforward_windows"]:
            metrics = window["metrics"]
            lines.append(
                f"| {window['window_index']} | `{window['test_start']}` | `{window['test_end']}` | "
                f"{_fmt_pct(metrics.get('total_return_pct'))} | {_fmt_num(metrics.get('sharpe_ratio'))} | "
                f"{_fmt_pct(metrics.get('max_drawdown_pct'))} |"
            )
        lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "This report is intentionally separate from the official dashboard metrics. "
        "The regime engine uses only SPY and QQQ price history, so filling the missing "
        "2016-2019 span with adjusted closes is defensible for research, but it is not "
        "the same thing as promoting that data source into the main cached backtest pipeline."
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

    cache_frame = load_price_cache(SYMBOLS)
    missing_intervals = detect_missing_intervals(cache_frame, start_day, end_day)
    fill_frame = download_gap_fill(SYMBOLS, missing_intervals)
    research_frame = merge_price_sources(cache_frame, fill_frame, missing_intervals)
    trading_days = _trading_days_for_period(research_frame, start_day, end_day)

    variant_rows: List[Dict[str, Any]] = []
    for variant in args.variants:
        full_period = run_variant_period(research_frame, start_day, end_day, variant)
        walkforward_summary, walkforward_windows = run_variant_walkforward(
            research_frame,
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
                "full_period": {"metrics": full_period["metrics"]},
                "walkforward_summary": walkforward_summary,
                "walkforward_windows": walkforward_windows,
            }
        )

    ranking = build_ranking(variant_rows)
    winner_variant = ranking[0]["variant"] if ranking else ""
    winner = next((row for row in variant_rows if row["variant"] == winner_variant), None)

    filled_note = (
        "Continuous 10-year research run using local SPY/QQQ cache plus adjusted-close "
        "gap fill from yfinance for missing ETF price history. This output is research-only "
        "and does not update official dashboard backtest metrics."
    )
    if missing_intervals:
        interval_note = ", ".join(f"{i.start} to {i.end}" for i in missing_intervals)
        data_note = f"{filled_note} Filled interval(s): {interval_note}."
    else:
        data_note = (
            "Continuous 10-year research run using only the local SPY/QQQ cache. "
            "This output is research-only and does not update official dashboard backtest metrics."
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy_id": "openclaw_regime_credit_spread",
        "period": {"start": start_day.isoformat(), "end": end_day.isoformat()},
        "variants_requested": list(args.variants),
        "train_days": int(args.train_days),
        "test_days": int(args.test_days),
        "step_days": int(args.step_days),
        "trading_days": len(trading_days),
        "symbols": list(SYMBOLS),
        "data_note": data_note,
        "filled_intervals": [
            {"start": interval.start.isoformat(), "end": interval.end.isoformat()}
            for interval in missing_intervals
        ],
        "variants": variant_rows,
        "ranking": ranking,
        "winner": winner,
    }

    json_path = output_base.with_suffix(".json")
    md_path = output_base.with_suffix(".md")
    write_json_report(json_path, payload)
    write_markdown_report(md_path, payload)

    print(f"Saved JSON report: {json_path}")
    print(f"Saved markdown report: {md_path}")
    if winner:
        metrics = winner["full_period"]["metrics"]
        oos = winner["walkforward_summary"]
        print(
            "Winner: "
            f"{winner['variant']} | "
            f"Return={metrics.get('total_return_pct', 0.0):+.2f}% | "
            f"OOS Sharpe={oos.get('avg_sharpe_ratio', 0.0):.2f} | "
            f"OOS DD={oos.get('avg_max_drawdown_pct', 0.0):.2f}%"
        )


if __name__ == "__main__":
    main()
