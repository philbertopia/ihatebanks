"""
Generate research-only 10-year comparisons for the strongest credit-spread families.

This script intentionally does not write to the official backtest run stores.
It reuses the SPY/QQQ underlying-price-only methodology from the regime-family
research runner, fills the known cache gap with adjusted-close history from
yfinance, and writes separate research artifacts for local website display.
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
PUBLIC_DATA_DIR = ROOT / "dashboard" / "public" / "data"
YF_CACHE_DIR = ROOT / "tmp_yf_cache"

SYMBOLS = ["SPY", "QQQ"]
SPARSE_SAMPLE_TRADE_THRESHOLD = 100

FAMILY_SPECS: List[Dict[str, Any]] = [
    {
        "strategy_id": "openclaw_regime_credit_spread",
        "strategy_name": "OpenClaw Regime Credit Spread",
        "family_label": "Regime Credit Spread",
        "variants": [
            "regime_legacy_defensive",
            "regime_defensive",
            "regime_balanced",
        ],
    },
    {
        "strategy_id": "openclaw_put_credit_spread",
        "strategy_name": "OpenClaw Put Credit Spread",
        "family_label": "Put Credit Spread",
        "variants": [
            "legacy_replica",
            "pcs_trend_baseline",
            "pcs_vix_optimal",
        ],
    },
    {
        "strategy_id": "openclaw_call_credit_spread",
        "strategy_name": "OpenClaw Call Credit Spread",
        "family_label": "Call Credit Spread",
        "variants": [
            "ccs_defensive",
            "ccs_baseline",
            "ccs_vix_regime",
        ],
    },
]


@dataclass(frozen=True)
class MissingInterval:
    start: date
    end: date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate research-only 10-year comparisons for the top credit-spread variants."
    )
    parser.add_argument("--start", default="2016-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2025-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--report-json",
        default="data/reports/credit_spread_10y_research.json",
        help="Report JSON output path",
    )
    parser.add_argument(
        "--report-markdown",
        default="data/reports/credit_spread_10y_research.md",
        help="Report markdown output path",
    )
    parser.add_argument(
        "--public-json",
        default="dashboard/public/data/research_10y_credit_spreads.json",
        help="Public research JSON output path",
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


def _available_days(frame: pd.DataFrame, symbols: Sequence[str]) -> List[date]:
    if frame.empty:
        return []
    grouped = frame.groupby("date")["underlying"].nunique()
    return sorted(day for day, count in grouped.items() if int(count) >= len(symbols))


def detect_missing_intervals(
    frame: pd.DataFrame,
    start_day: date,
    end_day: date,
    symbols: Sequence[str],
    max_expected_gap_days: int = 7,
) -> List[MissingInterval]:
    days = [day for day in _available_days(frame, symbols) if start_day <= day <= end_day]
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


def family_specs_lookup() -> Dict[str, Dict[str, Any]]:
    return {spec["strategy_id"]: spec for spec in FAMILY_SPECS}


def run_variant_period(
    frame: pd.DataFrame,
    start_day: date,
    end_day: date,
    strategy_id: str,
    strategy_name: str,
    family_label: str,
    variant: str,
) -> Dict[str, Any]:
    output = run_openclaw_variant(
        data=frame,
        config={},
        start_date=start_day,
        end_date=end_day,
        strategy_id=strategy_id,
        assumptions_mode=variant,
        universe_symbols=list(SYMBOLS),
    )
    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "family_label": family_label,
        "variant": variant,
        "strategy_key": f"{strategy_id}|{variant}",
        "metrics": output.metrics,
        "monthly_returns": output.series["monthly_returns"],
        "equity_points": output.equity_points,
    }


def run_variant_walkforward(
    frame: pd.DataFrame,
    start_day: date,
    end_day: date,
    strategy_id: str,
    strategy_name: str,
    family_label: str,
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
        result = run_variant_period(
            frame=frame,
            start_day=warm_start,
            end_day=window.test_end,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            family_label=family_label,
            variant=variant,
        )
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


def _sample_warning(metrics: Dict[str, Any]) -> Tuple[bool, str | None]:
    trades = int(metrics.get("total_trades", 0) or 0)
    if trades >= SPARSE_SAMPLE_TRADE_THRESHOLD:
        return False, None
    return True, (
        f"Only {trades} trades over the full 10-year run. Treat this as too sparse to trust "
        f"as a practical production candidate."
    )


def _ranking_rows(results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in results:
        metrics = row["full_period"]["metrics"]
        oos = row["walkforward_summary"]
        sample_warning, sample_warning_reason = _sample_warning(metrics)
        rows.append(
            {
                "strategy_id": row["strategy_id"],
                "strategy_name": row["strategy_name"],
                "family_label": row["family_label"],
                "variant": row["variant"],
                "strategy_key": row["strategy_key"],
                "pass_validation": bool(oos.get("pass_validation", False)),
                "avg_oos_sharpe_ratio": float(oos.get("avg_sharpe_ratio", 0.0) or 0.0),
                "avg_oos_max_drawdown_pct": float(oos.get("avg_max_drawdown_pct", 0.0) or 0.0),
                "avg_oos_total_return_pct": float(oos.get("avg_total_return_pct", 0.0) or 0.0),
                "total_return_pct": float(metrics.get("total_return_pct", 0.0) or 0.0),
                "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0) or 0.0),
                "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0) or 0.0),
                "total_trades": int(metrics.get("total_trades", 0) or 0),
                "win_rate": float(metrics.get("win_rate", 0.0) or 0.0),
                "sample_warning": sample_warning,
                "sample_warning_reason": sample_warning_reason,
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


def write_json(path: Path, payload: Dict[str, Any]) -> None:
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


def write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Credit Spread 10-Year Research")
    lines.append("")
    lines.append(f"- Generated: `{payload['generated_at']}`")
    lines.append(
        f"- Period: `{payload['period']['start']}` to `{payload['period']['end']}` "
        f"({payload['trading_days']} trading days)"
    )
    lines.append("- Scope: research-only, local workspace")
    lines.append(
        "- Covered families: `openclaw_regime_credit_spread`, "
        "`openclaw_put_credit_spread`, `openclaw_call_credit_spread`"
    )
    lines.append("")
    lines.append("## Data Source Note")
    lines.append("")
    lines.append(payload["data_note"])
    lines.append("")
    if payload["filled_intervals"]:
        lines.append("Filled intervals:")
        for interval in payload["filled_intervals"]:
            lines.append(f"- `{interval['start']}` to `{interval['end']}`")
        lines.append("")
    lines.append(
        f"Sparse-sample warning threshold: fewer than `{payload['sample_warning_trade_threshold']}` "
        "trades over the full 10-year run."
    )
    lines.append("")

    for family in payload["families"]:
        lines.append(f"## {family['family_label']}")
        lines.append("")
        lines.append(
            f"Leader: `{family['leader']['strategy_key']}`"
            if family.get("leader")
            else "Leader: n/a"
        )
        if family.get("practical_leader") and family["practical_leader"] != family.get("leader"):
            lines.append(f"Practical leader: `{family['practical_leader']['strategy_key']}`")
        lines.append("")
        lines.append("| Rank | Variant | Return | Sharpe | Max DD | Trades | OOS Return | OOS Sharpe | OOS DD | Pass | Warning |")
        lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
        for row in family["ranking"]:
            lines.append(
                f"| {row['rank']} | `{row['variant']}` | {_fmt_pct(row['total_return_pct'])} | "
                f"{_fmt_num(row['sharpe_ratio'])} | {_fmt_pct(row['max_drawdown_pct'])} | "
                f"{row['total_trades']} | {_fmt_pct(row['avg_oos_total_return_pct'])} | "
                f"{_fmt_num(row['avg_oos_sharpe_ratio'])} | {_fmt_pct(row['avg_oos_max_drawdown_pct'])} | "
                f"{'PASS' if row['pass_validation'] else 'FAIL'} | "
                f"{'Sparse sample' if row['sample_warning'] else ''} |"
            )
        lines.append("")

    lines.append("## Covered Variants")
    lines.append("")
    for row in payload["variants"]:
        metrics = row["full_period"]["metrics"]
        oos = row["walkforward_summary"]
        lines.append(f"### `{row['strategy_key']}`")
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
        if row["sample_warning"]:
            lines.append(f"- Warning: {row['sample_warning_reason']}")
        lines.append("")

    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "This report is intentionally separate from the official dashboard metrics. "
        "These families can be extended defensibly with filled SPY/QQQ ETF price history "
        "because the engines consume underlying prices rather than full option chains, "
        "but that still does not make the extended dataset equivalent to the official "
        "persisted backtest pipeline."
    )
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_payload(
    start_day: date,
    end_day: date,
    train_days: int,
    test_days: int,
    step_days: int,
    trading_days: Sequence[date],
    missing_intervals: Sequence[MissingInterval],
    variant_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    families: List[Dict[str, Any]] = []
    variants_by_key: Dict[str, Dict[str, Any]] = {}

    for row in variant_rows:
        variants_by_key[row["strategy_key"]] = row

    for spec in FAMILY_SPECS:
        family_results = [row for row in variant_rows if row["strategy_id"] == spec["strategy_id"]]
        ranking = _ranking_rows(family_results)
        leader = ranking[0] if ranking else None
        practical_leader = next((row for row in ranking if not row["sample_warning"]), leader)
        families.append(
            {
                "strategy_id": spec["strategy_id"],
                "strategy_name": spec["strategy_name"],
                "family_label": spec["family_label"],
                "covered_variants": list(spec["variants"]),
                "leader": leader,
                "practical_leader": practical_leader,
                "ranking": ranking,
            }
        )

    filled_note = (
        "Continuous 10-year research run using the local SPY/QQQ cache plus adjusted-close "
        "gap fill from yfinance for missing ETF price history. This output is research-only "
        "and does not update the official dashboard backtest metrics."
    )
    if missing_intervals:
        interval_note = ", ".join(f"{interval.start} to {interval.end}" for interval in missing_intervals)
        data_note = f"{filled_note} Filled interval(s): {interval_note}."
    else:
        data_note = (
            "Continuous 10-year research run using only the local SPY/QQQ cache. "
            "This output is research-only and does not update the official dashboard backtest metrics."
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": {"start": start_day.isoformat(), "end": end_day.isoformat()},
        "train_days": int(train_days),
        "test_days": int(test_days),
        "step_days": int(step_days),
        "trading_days": len(trading_days),
        "symbols": list(SYMBOLS),
        "data_note": data_note,
        "filled_intervals": [
            {"start": interval.start.isoformat(), "end": interval.end.isoformat()}
            for interval in missing_intervals
        ],
        "sample_warning_trade_threshold": SPARSE_SAMPLE_TRADE_THRESHOLD,
        "families": families,
        "variants": list(variant_rows),
        "variants_by_key": variants_by_key,
        "covered_strategy_keys": sorted(variants_by_key.keys()),
    }


def main() -> None:
    args = parse_args()
    start_day = _date_from_arg(args.start)
    end_day = _date_from_arg(args.end)

    report_json = Path(args.report_json)
    if not report_json.is_absolute():
        report_json = ROOT / report_json
    report_markdown = Path(args.report_markdown)
    if not report_markdown.is_absolute():
        report_markdown = ROOT / report_markdown
    public_json = Path(args.public_json)
    if not public_json.is_absolute():
        public_json = ROOT / public_json

    cache_frame = load_price_cache(SYMBOLS)
    missing_intervals = detect_missing_intervals(cache_frame, start_day, end_day, SYMBOLS)
    fill_frame = download_gap_fill(SYMBOLS, missing_intervals)
    research_frame = merge_price_sources(cache_frame, fill_frame, missing_intervals)
    trading_days = _trading_days_for_period(research_frame, start_day, end_day)

    variant_rows: List[Dict[str, Any]] = []
    for spec in FAMILY_SPECS:
        for variant in spec["variants"]:
            full_period = run_variant_period(
                frame=research_frame,
                start_day=start_day,
                end_day=end_day,
                strategy_id=spec["strategy_id"],
                strategy_name=spec["strategy_name"],
                family_label=spec["family_label"],
                variant=variant,
            )
            walkforward_summary, walkforward_windows = run_variant_walkforward(
                frame=research_frame,
                start_day=start_day,
                end_day=end_day,
                strategy_id=spec["strategy_id"],
                strategy_name=spec["strategy_name"],
                family_label=spec["family_label"],
                variant=variant,
                train_days=int(args.train_days),
                test_days=int(args.test_days),
                step_days=int(args.step_days),
            )
            sample_warning, sample_warning_reason = _sample_warning(full_period["metrics"])
            variant_rows.append(
                {
                    "strategy_id": spec["strategy_id"],
                    "strategy_name": spec["strategy_name"],
                    "family_label": spec["family_label"],
                    "variant": variant,
                    "strategy_key": f"{spec['strategy_id']}|{variant}",
                    "sample_warning": sample_warning,
                    "sample_warning_reason": sample_warning_reason,
                    "full_period": {
                        "metrics": full_period["metrics"],
                        "monthly_returns": full_period["monthly_returns"],
                    },
                    "walkforward_summary": walkforward_summary,
                    "walkforward_windows": walkforward_windows,
                }
            )

    payload = build_payload(
        start_day=start_day,
        end_day=end_day,
        train_days=int(args.train_days),
        test_days=int(args.test_days),
        step_days=int(args.step_days),
        trading_days=trading_days,
        missing_intervals=missing_intervals,
        variant_rows=variant_rows,
    )

    write_json(report_json, payload)
    write_json(public_json, payload)
    write_markdown(report_markdown, payload)

    print(f"Saved report JSON: {report_json}")
    print(f"Saved report markdown: {report_markdown}")
    print(f"Saved public JSON: {public_json}")
    for family in payload["families"]:
        leader = family.get("leader")
        if not leader:
            continue
        print(
            f"{family['family_label']}: "
            f"{leader['variant']} | "
            f"Return={leader['total_return_pct']:+.2f}% | "
            f"OOS Sharpe={leader['avg_oos_sharpe_ratio']:.2f} | "
            f"OOS DD={leader['avg_oos_max_drawdown_pct']:.2f}%"
        )


if __name__ == "__main__":
    main()
