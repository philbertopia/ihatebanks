"""
Generate a research-only comparison of portfolio overlays around the current
regime-switch champion.

This script intentionally does not write to the official backtest stores.
It runs the current champion with four overlay profiles, compares them against
existing supporting benchmarks, and writes report artifacts under data/reports/.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import _metrics_from_equity_window, _trading_days_for_period, _warmup_start_day
from ovtlyr.backtester.openclaw_engines import run_openclaw_variant
from ovtlyr.backtester.walkforward import generate_walkforward_windows, summarize_oos_runs


DATA_DIR = ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
BACKTEST_RUNS_PATH = DATA_DIR / "backtest_runs.json"

CORE_STRATEGY_ID = "openclaw_regime_credit_spread"
CORE_VARIANT = "regime_legacy_defensive"
CORE_STRATEGY_NAME = "OpenClaw Regime Credit Spread"
DEFAULT_OVERLAY_CONFIGS = [
    "regime_core_base",
    "regime_core_drawdown",
    "regime_core_killswitch",
    "regime_core_overlay",
]
DEFAULT_BENCHMARKS = [
    ("openclaw_regime_credit_spread", "regime_legacy_defensive"),
    ("openclaw_regime_credit_spread", "regime_balanced"),
    ("openclaw_regime_credit_spread", "regime_defensive"),
    ("openclaw_put_credit_spread", "legacy_replica"),
    ("openclaw_call_credit_spread", "ccs_defensive"),
]
PRICE_SYMBOLS = ["SPY", "QQQ", "VIX", "^VIX"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a research-only regime portfolio upgrade comparison."
    )
    parser.add_argument("--start", default="2020-01-02", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2025-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--output-base",
        default="data/reports/regime_portfolio_upgrade",
        help="Output path without extension",
    )
    parser.add_argument("--train-days", type=int, default=504)
    parser.add_argument("--test-days", type=int, default=126)
    parser.add_argument("--step-days", type=int, default=126)
    return parser.parse_args()


def _date_from_arg(value: str) -> date:
    return date.fromisoformat(str(value))


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as handle:
        raw = handle.read().strip()
    if not raw:
        return default
    return json.loads(raw)


def load_price_cache(symbols: Sequence[str]) -> pd.DataFrame:
    parts: List[pd.DataFrame] = []
    for path in sorted(glob.glob(str(DATA_DIR / "cache" / "*.parquet"))):
        try:
            frame = pd.read_parquet(path, columns=["date", "underlying", "underlying_price"])
        except Exception:
            print(f"Skipping unreadable parquet during research load: {Path(path).name}")
            continue
        frame = frame[frame["underlying"].isin(symbols)]
        if not frame.empty:
            parts.append(frame)
    if not parts:
        return pd.DataFrame(columns=["date", "underlying", "underlying_price"])
    out = pd.concat(parts, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.date
    return out.sort_values(["date", "underlying"]).reset_index(drop=True)


def run_overlay_period(
    frame: pd.DataFrame,
    start_day: date,
    end_day: date,
    overlay_profile: str,
) -> Dict[str, Any]:
    output = run_openclaw_variant(
        data=frame,
        config={"portfolio_overlay_profile": overlay_profile},
        start_date=start_day,
        end_date=end_day,
        strategy_id=CORE_STRATEGY_ID,
        assumptions_mode=CORE_VARIANT,
        universe_symbols=["SPY", "QQQ"],
    )
    return {
        "metrics": output.metrics,
        "equity_points": output.equity_points,
        "component_metrics": output.component_metrics or {},
        "strategy_parameters": output.strategy_parameters,
    }


def run_overlay_walkforward(
    frame: pd.DataFrame,
    start_day: date,
    end_day: date,
    overlay_profile: str,
    train_days: int,
    test_days: int,
    step_days: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    trading_days = _trading_days_for_period(frame, start_day, end_day)
    windows = generate_walkforward_windows(trading_days, train_days, test_days, step_days)
    oos_metrics: List[Dict[str, Any]] = []
    rows: List[Dict[str, Any]] = []

    for window in windows:
        warm_start = _warmup_start_day(trading_days, window.test_start, lookback_days=260)
        result = run_overlay_period(frame, warm_start, window.test_end, overlay_profile)
        metrics = result["metrics"]
        if warm_start < window.test_start:
            metrics = _metrics_from_equity_window(
                result["equity_points"],
                start_day=window.test_start,
                end_day=window.test_end,
                base_metrics=metrics,
            )
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
        sharpe_threshold=0.70,
        max_dd_threshold=30.0,
    )
    return summary, rows


def _select_latest_run(
    runs: Sequence[Dict[str, Any]],
    strategy_id: str,
    variant: str,
    start_day: date,
    end_day: date,
) -> Dict[str, Any] | None:
    wanted_start = start_day.isoformat()
    wanted_end = end_day.isoformat()
    all_candidates = [
        row
        for row in runs
        if str(row.get("strategy_id")) == strategy_id
        and str(row.get("variant")) == variant
    ]
    if not all_candidates:
        return None
    exact = [
        row
        for row in all_candidates
        if str(row.get("start_date")) == wanted_start
        and str(row.get("end_date")) == wanted_end
    ]
    candidates = exact or all_candidates

    def _span_days(row: Dict[str, Any]) -> int:
        try:
            start = date.fromisoformat(str(row.get("start_date")))
            end = date.fromisoformat(str(row.get("end_date")))
        except Exception:
            return 0
        return max((end - start).days, 0)

    candidates.sort(
        key=lambda row: (
            _span_days(row),
            str(row.get("generated_at", "")),
        ),
        reverse=True,
    )
    return candidates[0]


def load_benchmark_rows(
    start_day: date,
    end_day: date,
) -> List[Dict[str, Any]]:
    runs = _load_json(BACKTEST_RUNS_PATH, [])
    if not isinstance(runs, list):
        runs = []

    rows: List[Dict[str, Any]] = []
    for strategy_id, variant in DEFAULT_BENCHMARKS:
        latest = _select_latest_run(runs, strategy_id, variant, start_day, end_day)
        if latest is None:
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "variant": variant,
                    "missing": True,
                }
            )
            continue
        metrics = latest.get("metrics", {}) or {}
        oos = latest.get("oos_summary", {}) or {}
        rows.append(
            {
                "strategy_id": strategy_id,
                "strategy_name": latest.get("strategy_name", strategy_id),
                "variant": variant,
                "missing": False,
                "total_return_pct": float(metrics.get("total_return_pct", 0.0) or 0.0),
                "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0) or 0.0),
                "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0) or 0.0),
                "total_trades": int(metrics.get("total_trades", 0) or 0),
                "avg_oos_total_return_pct": float(oos.get("avg_total_return_pct", 0.0) or 0.0),
                "avg_oos_sharpe_ratio": float(oos.get("avg_sharpe_ratio", 0.0) or 0.0),
                "avg_oos_max_drawdown_pct": float(oos.get("avg_max_drawdown_pct", 0.0) or 0.0),
                "pass_validation": bool(oos.get("pass_validation", False)),
            }
        )
    return rows


def build_overlay_row(
    overlay_profile: str,
    result: Dict[str, Any],
    oos_summary: Dict[str, Any],
    windows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    metrics = result["metrics"]
    component_metrics = result.get("component_metrics", {}) or {}
    return {
        "portfolio_config_id": overlay_profile,
        "strategy_id": CORE_STRATEGY_ID,
        "variant": CORE_VARIANT,
        "strategy_name": CORE_STRATEGY_NAME,
        "total_return_pct": float(metrics.get("total_return_pct", 0.0) or 0.0),
        "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0) or 0.0),
        "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0) or 0.0),
        "win_rate": float(metrics.get("win_rate", 0.0) or 0.0),
        "profit_factor": float(metrics.get("profit_factor", 0.0) or 0.0),
        "total_trades": int(metrics.get("total_trades", 0) or 0),
        "put_entries": int(metrics.get("put_entries", 0) or 0),
        "call_entries": int(metrics.get("call_entries", 0) or 0),
        "avg_oos_total_return_pct": float(oos_summary.get("avg_total_return_pct", 0.0) or 0.0),
        "avg_oos_sharpe_ratio": float(oos_summary.get("avg_sharpe_ratio", 0.0) or 0.0),
        "avg_oos_max_drawdown_pct": float(oos_summary.get("avg_max_drawdown_pct", 0.0) or 0.0),
        "pass_validation": bool(oos_summary.get("pass_validation", False)),
        "overlay_metrics": {
            "portfolio_overlay_profile": component_metrics.get("portfolio_overlay_profile"),
            "portfolio_overlay_mode_counts": component_metrics.get("portfolio_overlay_mode_counts"),
            "portfolio_overlay_reason_counts": component_metrics.get("portfolio_overlay_reason_counts"),
            "portfolio_overlay_block_days": component_metrics.get("portfolio_overlay_block_days"),
            "portfolio_overlay_throttle_days": component_metrics.get("portfolio_overlay_throttle_days"),
            "portfolio_overlay_avg_new_risk_pct": component_metrics.get("portfolio_overlay_avg_new_risk_pct"),
            "portfolio_overlay_max_new_risk_pct": component_metrics.get("portfolio_overlay_max_new_risk_pct"),
        },
        "walkforward_summary": oos_summary,
        "walkforward_windows": windows,
    }


def ranking_key(row: Dict[str, Any]) -> tuple:
    return (
        0 if row["pass_validation"] else 1,
        -float(row["avg_oos_total_return_pct"]),
        -float(row["avg_oos_sharpe_ratio"]),
        float(row["avg_oos_max_drawdown_pct"]),
        -float(row["total_return_pct"]),
    )


def choose_preferred_config(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    ordered = sorted(rows, key=ranking_key)
    base = next(row for row in rows if row["portfolio_config_id"] == "regime_core_base")
    leader = ordered[0]

    if leader["portfolio_config_id"] == "regime_core_base":
        return {
            "portfolio_config_id": base["portfolio_config_id"],
            "adopt_overlay": False,
            "reason": "plain_core_remains_preferred",
        }

    oos_return_floor = float(base["avg_oos_total_return_pct"]) * 0.85
    if (
        leader["pass_validation"]
        and float(leader["avg_oos_max_drawdown_pct"]) <= 10.0
        and float(leader["avg_oos_total_return_pct"]) >= oos_return_floor
    ):
        return {
            "portfolio_config_id": leader["portfolio_config_id"],
            "adopt_overlay": True,
            "reason": "overlay_meets_promotion_rule",
        }

    return {
        "portfolio_config_id": base["portfolio_config_id"],
        "adopt_overlay": False,
        "reason": "overlay_failed_promotion_rule",
    }


def _fmt_pct(value: Any) -> str:
    return f"{float(value):+.2f}%"


def _fmt_num(value: Any) -> str:
    return f"{float(value):.2f}"


def write_markdown_report(payload: Dict[str, Any], path: Path) -> None:
    rows = payload["overlay_configs"]
    ranking = payload["overlay_ranking"]
    preferred = payload["preferred_config"]
    benchmarks = payload["benchmarks"]
    core = next(row for row in rows if row["portfolio_config_id"] == "regime_core_base")
    leader = next(row for row in rows if row["portfolio_config_id"] == ranking[0]["portfolio_config_id"])

    lines = [
        "# Regime Portfolio Upgrade",
        "",
        "Research-only comparison of portfolio overlays around `openclaw_regime_credit_spread|regime_legacy_defensive`.",
        "",
        f"- Period: {payload['period']['start']} to {payload['period']['end']}",
        f"- Walk-forward: train {payload['walkforward']['train_days']} / test {payload['walkforward']['test_days']} / step {payload['walkforward']['step_days']}",
        f"- Preferred config: `{preferred['portfolio_config_id']}` ({preferred['reason']})",
        "",
        "## Overlay Configs",
        "",
        "| Config | Return | Sharpe | Max DD | Trades | OOS Return | OOS Sharpe | OOS Max DD | PASS |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    for row in ranking:
        detail = next(item for item in rows if item["portfolio_config_id"] == row["portfolio_config_id"])
        lines.append(
            f"| `{detail['portfolio_config_id']}` | {_fmt_pct(detail['total_return_pct'])} | {_fmt_num(detail['sharpe_ratio'])} | "
            f"{_fmt_pct(detail['max_drawdown_pct'])} | {detail['total_trades']} | {_fmt_pct(detail['avg_oos_total_return_pct'])} | "
            f"{_fmt_num(detail['avg_oos_sharpe_ratio'])} | {_fmt_pct(detail['avg_oos_max_drawdown_pct'])} | "
            f"{'PASS' if detail['pass_validation'] else 'FAIL'} |"
        )

    lines.extend(
        [
            "",
            "## Comparison vs Plain Core",
            "",
            f"- Plain core OOS return: {_fmt_pct(core['avg_oos_total_return_pct'])}",
            f"- Plain core OOS Sharpe: {_fmt_num(core['avg_oos_sharpe_ratio'])}",
            f"- Plain core OOS max drawdown: {_fmt_pct(core['avg_oos_max_drawdown_pct'])}",
            f"- Top overlay candidate: `{leader['portfolio_config_id']}` with OOS return {_fmt_pct(leader['avg_oos_total_return_pct'])}, "
            f"OOS Sharpe {_fmt_num(leader['avg_oos_sharpe_ratio'])}, OOS max drawdown {_fmt_pct(leader['avg_oos_max_drawdown_pct'])}",
            "",
            "## Supporting Benchmarks",
            "",
            "| Strategy | Return | Sharpe | Max DD | Trades | OOS Return | OOS Sharpe | OOS Max DD | PASS |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |",
        ]
    )
    for row in benchmarks:
        if row.get("missing"):
            lines.append(f"| `{row['strategy_id']}|{row['variant']}` | missing |  |  |  |  |  |  |  |")
            continue
        lines.append(
            f"| `{row['strategy_id']}|{row['variant']}` | {_fmt_pct(row['total_return_pct'])} | {_fmt_num(row['sharpe_ratio'])} | "
            f"{_fmt_pct(row['max_drawdown_pct'])} | {row['total_trades']} | {_fmt_pct(row['avg_oos_total_return_pct'])} | "
            f"{_fmt_num(row['avg_oos_sharpe_ratio'])} | {_fmt_pct(row['avg_oos_max_drawdown_pct'])} | "
            f"{'PASS' if row['pass_validation'] else 'FAIL'} |"
        )

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    args = parse_args()
    start_day = _date_from_arg(args.start)
    end_day = _date_from_arg(args.end)
    output_base = (ROOT / args.output_base).resolve()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    frame = load_price_cache(PRICE_SYMBOLS)
    if frame.empty:
        raise RuntimeError("No SPY/QQQ price cache available for regime portfolio research")

    rows: List[Dict[str, Any]] = []
    for profile_id in DEFAULT_OVERLAY_CONFIGS:
        print(f"Running overlay profile: {profile_id}")
        result = run_overlay_period(frame, start_day, end_day, profile_id)
        oos_summary, windows = run_overlay_walkforward(
            frame,
            start_day,
            end_day,
            profile_id,
            train_days=int(args.train_days),
            test_days=int(args.test_days),
            step_days=int(args.step_days),
        )
        rows.append(build_overlay_row(profile_id, result, oos_summary, windows))

    ranking = [
        {
            "portfolio_config_id": row["portfolio_config_id"],
            "pass_validation": row["pass_validation"],
            "avg_oos_total_return_pct": row["avg_oos_total_return_pct"],
            "avg_oos_sharpe_ratio": row["avg_oos_sharpe_ratio"],
            "avg_oos_max_drawdown_pct": row["avg_oos_max_drawdown_pct"],
            "total_return_pct": row["total_return_pct"],
        }
        for row in sorted(rows, key=ranking_key)
    ]
    preferred = choose_preferred_config(rows)
    benchmarks = load_benchmark_rows(start_day, end_day)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": {
            "start": start_day.isoformat(),
            "end": end_day.isoformat(),
        },
        "walkforward": {
            "train_days": int(args.train_days),
            "test_days": int(args.test_days),
            "step_days": int(args.step_days),
        },
        "core_strategy": {
            "strategy_id": CORE_STRATEGY_ID,
            "variant": CORE_VARIANT,
            "strategy_name": CORE_STRATEGY_NAME,
        },
        "overlay_configs": rows,
        "overlay_ranking": ranking,
        "preferred_config": preferred,
        "benchmarks": benchmarks,
        "notes": {
            "research_only": True,
            "official_metrics_unchanged": True,
        },
    }

    with open(output_base.with_suffix(".json"), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    write_markdown_report(payload, output_base.with_suffix(".md"))

    print(f"Wrote {output_base.with_suffix('.json')}")
    print(f"Wrote {output_base.with_suffix('.md')}")


if __name__ == "__main__":
    main()
