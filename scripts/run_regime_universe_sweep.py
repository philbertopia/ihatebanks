"""
Research-only correlated-pair sweeps for the current regime-credit winner.

This script intentionally does not write to the official backtest stores.
It builds isolated synthetic price caches, runs the current regime-credit
champion across configured cohorts, and writes cohort-specific comparison
reports under data/reports/.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
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
RESEARCH_CACHE_ROOT = DATA_DIR / "research_cache"
YF_CACHE_DIR = ROOT / "tmp_yf_cache"
BACKTEST_RUNS_PATH = DATA_DIR / "backtest_runs.json"
OFFICIAL_REFERENCE_START = "2020-01-01"
OFFICIAL_REFERENCE_END = "2025-12-31"

STRATEGY_ID = "openclaw_regime_credit_spread"
VARIANT = "regime_legacy_defensive"
STRATEGY_NAME = "OpenClaw Regime Credit Spread"

COHORT_SPECS: List[Dict[str, Any]] = [
    {
        "cohort_id": "wave1_etf",
        "label": "Wave 1 ETF Expansion",
        "requested_start": "2020-01-02",
        "end": "2025-12-31",
        "period_mode": "fixed",
        "report_json": "data/reports/regime_pair_sweep_wave1_etf.json",
        "report_markdown": "data/reports/regime_pair_sweep_wave1_etf.md",
        "cache_dir": "data/research_cache/regime_pair_sweep_wave1_etf",
        "pairs": [
            {"pair_id": "spy_qqq", "symbols": ["SPY", "QQQ"], "label": "SPY + QQQ", "baseline": True},
            {"pair_id": "qqq_iwm", "symbols": ["QQQ", "IWM"], "label": "QQQ + IWM", "baseline": False},
            {"pair_id": "qqq_smh", "symbols": ["QQQ", "SMH"], "label": "QQQ + SMH", "baseline": False},
            {"pair_id": "spy_rsp", "symbols": ["SPY", "RSP"], "label": "SPY + RSP", "baseline": False},
            {"pair_id": "spy_hyg", "symbols": ["SPY", "HYG"], "label": "SPY + HYG", "baseline": False},
            {"pair_id": "spy_xle", "symbols": ["SPY", "XLE"], "label": "SPY + XLE", "baseline": False},
        ],
    },
    {
        "cohort_id": "wave2_satellites",
        "label": "Wave 2 Crypto and Satellites",
        "requested_start": "2020-01-02",
        "end": "2025-12-31",
        "period_mode": "shared_start",
        "report_json": "data/reports/regime_pair_sweep_wave2_satellites.json",
        "report_markdown": "data/reports/regime_pair_sweep_wave2_satellites.md",
        "cache_dir": "data/research_cache/regime_pair_sweep_wave2_satellites",
        "pairs": [
            {"pair_id": "spy_qqq_short", "symbols": ["SPY", "QQQ"], "label": "SPY + QQQ (Short Window)", "baseline": True},
            {"pair_id": "spy_ibit", "symbols": ["SPY", "IBIT"], "label": "SPY + IBIT", "baseline": False},
            {"pair_id": "qqq_ibit", "symbols": ["QQQ", "IBIT"], "label": "QQQ + IBIT", "baseline": False},
            {"pair_id": "gld_ibit", "symbols": ["GLD", "IBIT"], "label": "GLD + IBIT", "baseline": False},
            {"pair_id": "qqq_msft", "symbols": ["QQQ", "MSFT"], "label": "QQQ + MSFT", "baseline": False},
            {"pair_id": "qqq_nvda", "symbols": ["QQQ", "NVDA"], "label": "QQQ + NVDA", "baseline": False},
            {"pair_id": "qqq_tsla", "symbols": ["QQQ", "TSLA"], "label": "QQQ + TSLA", "baseline": False},
        ],
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run research-only correlated-pair sweeps for the regime-credit champion."
    )
    parser.add_argument(
        "--cohort",
        choices=["all", "wave1_etf", "wave2_satellites"],
        default="all",
        help="Which cohort to run",
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
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    return json.loads(raw)


def cohort_symbols(cohort: Dict[str, Any]) -> List[str]:
    seen: List[str] = []
    for pair_def in cohort["pairs"]:
        for symbol in pair_def["symbols"]:
            normalized = str(symbol).upper()
            if normalized not in seen:
                seen.append(normalized)
    return seen


def download_adjusted_prices(symbols: Sequence[str], start_day: date, end_day: date) -> pd.DataFrame:
    YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(YF_CACHE_DIR.resolve()))

    raw = yf.download(
        list(symbols),
        start=start_day.isoformat(),
        end=(end_day + timedelta(days=1)).isoformat(),
        auto_adjust=True,
        progress=False,
    )
    if raw.empty:
        raise RuntimeError(f"yfinance returned no price data for symbols: {symbols}")

    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    if "Close" in close.columns and len(symbols) == 1:
        close = close.rename(columns={"Close": list(symbols)[0]})
    close.index = pd.to_datetime(close.index).date
    return close.sort_index()


def first_shared_valid_day(
    prices: pd.DataFrame,
    symbols: Sequence[str],
    requested_start: date,
    end_day: date,
) -> date:
    missing = [str(symbol).upper() for symbol in symbols if str(symbol).upper() not in prices.columns]
    if missing:
        raise RuntimeError(f"Missing downloaded price columns for symbols: {missing}")

    subset = prices.loc[:, [str(symbol).upper() for symbol in symbols]].copy()
    mask = (subset.index >= requested_start) & (subset.index <= end_day)
    subset = subset.loc[mask]
    valid_rows = subset.notna().all(axis=1)
    valid_days = list(subset.index[valid_rows])
    if not valid_days:
        raise RuntimeError(f"No shared valid price window found for symbols: {symbols}")
    return valid_days[0]


def build_shared_price_frame(
    prices: pd.DataFrame,
    symbols: Sequence[str],
    start_day: date,
    end_day: date,
) -> pd.DataFrame:
    subset = prices.loc[:, [str(symbol).upper() for symbol in symbols]].copy()
    mask = (subset.index >= start_day) & (subset.index <= end_day)
    subset = subset.loc[mask]
    subset = subset[subset.notna().all(axis=1)]
    if subset.empty:
        raise RuntimeError(f"Shared price frame is empty for symbols: {symbols}")
    return subset


def write_price_cache(prices: pd.DataFrame, cache_dir: Path) -> int:
    cache_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for day_idx, row in prices.iterrows():
        day_rows: List[Dict[str, Any]] = []
        for symbol, value in row.items():
            if pd.notna(value):
                day_rows.append(
                    {
                        "date": day_idx.isoformat(),
                        "underlying": str(symbol).upper(),
                        "underlying_price": float(value),
                    }
                )
        if not day_rows:
            continue
        pd.DataFrame(day_rows).to_parquet(cache_dir / f"{day_idx.isoformat()}.parquet", index=False)
        written += 1
    return written


def load_research_cache(cache_dir: Path) -> pd.DataFrame:
    parts: List[pd.DataFrame] = []
    for path in sorted(glob.glob(str(cache_dir / "*.parquet"))):
        frame = pd.read_parquet(path, columns=["date", "underlying", "underlying_price"])
        if not frame.empty:
            parts.append(frame)
    if not parts:
        return pd.DataFrame(columns=["date", "underlying", "underlying_price"])
    out = pd.concat(parts, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.date
    return out.sort_values(["date", "underlying"]).reset_index(drop=True)


def run_pair_period(
    frame: pd.DataFrame,
    start_day: date,
    end_day: date,
    symbols: Sequence[str],
) -> Dict[str, Any]:
    allowed_symbols = [str(symbol).upper() for symbol in symbols]
    context_symbols = ["SPY"] if "SPY" not in allowed_symbols else []
    output = run_openclaw_variant(
        data=frame,
        config={
            "allowed_symbols": allowed_symbols,
            "context_symbols": context_symbols,
        },
        start_date=start_day,
        end_date=end_day,
        strategy_id=STRATEGY_ID,
        assumptions_mode=VARIANT,
        universe_symbols=allowed_symbols,
    )
    return {
        "metrics": output.metrics,
        "component_metrics": output.component_metrics or {},
        "strategy_parameters": output.strategy_parameters,
        "equity_points": output.equity_points,
        "series": output.series,
    }


def run_pair_walkforward(
    frame: pd.DataFrame,
    start_day: date,
    end_day: date,
    symbols: Sequence[str],
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
        result = run_pair_period(frame, warm_start, window.test_end, symbols)
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


def build_pair_row(
    pair_def: Dict[str, Any],
    result: Dict[str, Any],
    oos_summary: Dict[str, Any],
    walkforward_windows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    metrics = result["metrics"]
    component_metrics = result["component_metrics"]
    return {
        "pair_id": pair_def["pair_id"],
        "label": pair_def["label"],
        "symbols": list(pair_def["symbols"]),
        "baseline": bool(pair_def["baseline"]),
        "strategy_id": STRATEGY_ID,
        "strategy_name": STRATEGY_NAME,
        "variant": VARIANT,
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
        "monthly_returns": result["series"].get("monthly_returns", []),
        "entry_counts_by_symbol": component_metrics.get("entry_counts_by_symbol", {}),
        "allowed_symbols": result["strategy_parameters"].get("allowed_symbols", []),
        "context_symbols": result["strategy_parameters"].get("context_symbols", []),
        "walkforward_summary": oos_summary,
        "walkforward_windows": walkforward_windows,
    }


def ranking_key(row: Dict[str, Any]) -> tuple:
    return (
        0 if row["pass_validation"] else 1,
        -float(row["avg_oos_total_return_pct"]),
        -float(row["avg_oos_sharpe_ratio"]),
        float(row["avg_oos_max_drawdown_pct"]),
        -float(row["total_return_pct"]),
    )


def _select_official_reference(start_day: date, end_day: date) -> Dict[str, Any] | None:
    runs = _load_json(BACKTEST_RUNS_PATH, [])
    if not isinstance(runs, list):
        return None

    candidates = [
        row
        for row in runs
        if str(row.get("strategy_id")) == STRATEGY_ID
        and str(row.get("variant")) == VARIANT
    ]
    if not candidates:
        return None

    wanted_start = start_day.isoformat()
    wanted_end = end_day.isoformat()
    canonical = [
        row
        for row in candidates
        if str(row.get("start_date")) == OFFICIAL_REFERENCE_START
        and str(row.get("end_date")) == OFFICIAL_REFERENCE_END
    ]
    exact = [
        row
        for row in candidates
        if str(row.get("start_date")) == wanted_start
        and str(row.get("end_date")) == wanted_end
    ]
    selected = canonical or exact or candidates
    selected.sort(key=lambda row: str(row.get("generated_at", "")), reverse=True)
    row = selected[0]
    metrics = row.get("metrics", {}) or {}
    oos = row.get("oos_summary", {}) or {}
    return {
        "strategy_id": row.get("strategy_id"),
        "strategy_name": row.get("strategy_name"),
        "variant": row.get("variant"),
        "start_date": row.get("start_date"),
        "end_date": row.get("end_date"),
        "total_return_pct": float(metrics.get("total_return_pct", 0.0) or 0.0),
        "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0) or 0.0),
        "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0) or 0.0),
        "total_trades": int(metrics.get("total_trades", 0) or 0),
        "put_entries": int(metrics.get("put_entries", 0) or 0),
        "call_entries": int(metrics.get("call_entries", 0) or 0),
        "avg_oos_total_return_pct": float(oos.get("avg_total_return_pct", 0.0) or 0.0),
        "avg_oos_sharpe_ratio": float(oos.get("avg_sharpe_ratio", 0.0) or 0.0),
        "avg_oos_max_drawdown_pct": float(oos.get("avg_max_drawdown_pct", 0.0) or 0.0),
        "pass_validation": bool(oos.get("pass_validation", False)),
    }


def _fmt_pct(value: Any) -> str:
    return f"{float(value):+.2f}%"


def _fmt_num(value: Any) -> str:
    return f"{float(value):.2f}"


def _fmt_monthly_returns(monthly_returns: Sequence[Dict[str, Any]]) -> str:
    if not monthly_returns:
        return "_No monthly returns recorded._"
    return ", ".join(
        f"{str(row.get('month'))}: {_fmt_pct(row.get('return_pct', 0.0))}"
        for row in monthly_returns
    )


def write_markdown_report(payload: Dict[str, Any], path: Path) -> None:
    ranking = payload["pair_ranking"]
    pairs = payload["pair_results"]
    winner = next(row for row in pairs if row["pair_id"] == ranking[0]["pair_id"])
    official = payload.get("official_reference")

    lines = [
        f"# {payload['cohort_label']}",
        "",
        "Research-only comparison of the current regime-credit champion across a correlated pair cohort using an isolated synthetic price cache.",
        "",
        f"- Requested period: {payload['requested_period']['start']} to {payload['requested_period']['end']}",
        f"- Actual period: {payload['actual_period']['start']} to {payload['actual_period']['end']}",
        f"- Walk-forward: train {payload['walkforward']['train_days']} / test {payload['walkforward']['test_days']} / step {payload['walkforward']['step_days']}",
        f"- Winner: `{winner['label']}`",
        "",
        "## Ranked Comparison",
        "",
        "| Pair | Return | Sharpe | Max DD | Trades | Put Entries | Call Entries | OOS Return | OOS Sharpe | OOS Max DD | PASS |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    for rank_row in ranking:
        row = next(item for item in pairs if item["pair_id"] == rank_row["pair_id"])
        lines.append(
            f"| `{row['label']}` | {_fmt_pct(row['total_return_pct'])} | {_fmt_num(row['sharpe_ratio'])} | "
            f"{_fmt_pct(row['max_drawdown_pct'])} | {row['total_trades']} | {row['put_entries']} | {row['call_entries']} | "
            f"{_fmt_pct(row['avg_oos_total_return_pct'])} | {_fmt_num(row['avg_oos_sharpe_ratio'])} | "
            f"{_fmt_pct(row['avg_oos_max_drawdown_pct'])} | {'PASS' if row['pass_validation'] else 'FAIL'} |"
        )

    lines.extend(["", "## Pair Details", ""])
    for row in pairs:
        lines.extend(
            [
                f"### {row['label']}",
                "",
                f"- Symbols: {', '.join(row['symbols'])}",
                f"- Allowed symbols: {', '.join(row['allowed_symbols'])}",
                f"- Context symbols: {', '.join(row['context_symbols']) if row['context_symbols'] else 'none'}",
                f"- Total return: {_fmt_pct(row['total_return_pct'])}",
                f"- Sharpe: {_fmt_num(row['sharpe_ratio'])}",
                f"- Max drawdown: {_fmt_pct(row['max_drawdown_pct'])}",
                f"- Total trades: {row['total_trades']}",
                f"- Put entries: {row['put_entries']}",
                f"- Call entries: {row['call_entries']}",
                f"- OOS return: {_fmt_pct(row['avg_oos_total_return_pct'])}",
                f"- OOS Sharpe: {_fmt_num(row['avg_oos_sharpe_ratio'])}",
                f"- OOS max drawdown: {_fmt_pct(row['avg_oos_max_drawdown_pct'])}",
                f"- Validation: {'PASS' if row['pass_validation'] else 'FAIL'}",
                "",
                "**Monthly Returns**",
                "",
                _fmt_monthly_returns(row["monthly_returns"]),
                "",
            ]
        )

    lines.extend(
        [
            "## Synthetic vs Official Reference",
            "",
            "The cohort baseline is ranked only against other synthetic cohort members. The official real-cache champion metrics below are shown for methodology context and are not part of the cohort ranking.",
            "",
        ]
    )
    if official is None:
        lines.append("_No official real-cache reference found in `data/backtest_runs.json`._")
    else:
        lines.extend(
            [
                f"- Official strategy: `{official['strategy_id']}|{official['variant']}`",
                f"- Official period: {official['start_date']} to {official['end_date']}",
                f"- Official total return: {_fmt_pct(official['total_return_pct'])}",
                f"- Official Sharpe: {_fmt_num(official['sharpe_ratio'])}",
                f"- Official max drawdown: {_fmt_pct(official['max_drawdown_pct'])}",
                f"- Official total trades: {official['total_trades']}",
                f"- Official OOS return: {_fmt_pct(official['avg_oos_total_return_pct'])}",
                f"- Official OOS Sharpe: {_fmt_num(official['avg_oos_sharpe_ratio'])}",
                f"- Official OOS max drawdown: {_fmt_pct(official['avg_oos_max_drawdown_pct'])}",
            ]
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_cohort(cohort: Dict[str, Any], train_days: int, test_days: int, step_days: int) -> Dict[str, Any]:
    requested_start = _date_from_arg(cohort["requested_start"])
    end_day = _date_from_arg(cohort["end"])
    symbols = cohort_symbols(cohort)

    print(f"Downloading adjusted prices for cohort {cohort['cohort_id']}: {', '.join(symbols)}")
    prices = download_adjusted_prices(symbols, requested_start, end_day)
    actual_start = requested_start
    if cohort["period_mode"] == "shared_start":
        actual_start = first_shared_valid_day(prices, symbols, requested_start, end_day)

    shared_prices = build_shared_price_frame(prices, symbols, actual_start, end_day)
    cache_dir = (ROOT / cohort["cache_dir"]).resolve()
    written = write_price_cache(shared_prices, cache_dir)
    print(f"Wrote {written} synthetic daily cache files to {cache_dir}")

    frame = load_research_cache(cache_dir)
    if frame.empty:
        raise RuntimeError(f"Synthetic research cache is empty for cohort {cohort['cohort_id']}")

    pair_rows: List[Dict[str, Any]] = []
    for pair_def in cohort["pairs"]:
        print(f"Running pair: {pair_def['label']}")
        result = run_pair_period(frame, actual_start, end_day, pair_def["symbols"])
        oos_summary, windows = run_pair_walkforward(
            frame,
            actual_start,
            end_day,
            pair_def["symbols"],
            train_days=train_days,
            test_days=test_days,
            step_days=step_days,
        )
        pair_rows.append(build_pair_row(pair_def, result, oos_summary, windows))

    ranking = [
        {
            "pair_id": row["pair_id"],
            "label": row["label"],
            "pass_validation": row["pass_validation"],
            "avg_oos_total_return_pct": row["avg_oos_total_return_pct"],
            "avg_oos_sharpe_ratio": row["avg_oos_sharpe_ratio"],
            "avg_oos_max_drawdown_pct": row["avg_oos_max_drawdown_pct"],
            "total_return_pct": row["total_return_pct"],
        }
        for row in sorted(pair_rows, key=ranking_key)
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cohort_id": cohort["cohort_id"],
        "cohort_label": cohort["label"],
        "requested_period": {
            "start": requested_start.isoformat(),
            "end": end_day.isoformat(),
        },
        "actual_period": {
            "start": actual_start.isoformat(),
            "end": end_day.isoformat(),
        },
        "walkforward": {
            "train_days": int(train_days),
            "test_days": int(test_days),
            "step_days": int(step_days),
        },
        "strategy": {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "variant": VARIANT,
        },
        "data_source_note": (
            "Research-only synthetic daily price cache generated from adjusted close history "
            f"for {', '.join(symbols)}. The sweep keeps the current regime-credit template "
            "unchanged and ranks only the synthetic pair results."
        ),
        "pair_definitions": [
            {
                "pair_id": pair_def["pair_id"],
                "label": pair_def["label"],
                "symbols": list(pair_def["symbols"]),
                "baseline": bool(pair_def["baseline"]),
            }
            for pair_def in cohort["pairs"]
        ],
        "pair_results": pair_rows,
        "pair_ranking": ranking,
        "winner": ranking[0] if ranking else None,
        "official_reference": _select_official_reference(requested_start, end_day),
        "notes": {
            "research_only": True,
            "official_metrics_unchanged": True,
            "cache_dir": str(cache_dir),
            "period_mode": cohort["period_mode"],
        },
    }

    report_json = (ROOT / cohort["report_json"]).resolve()
    report_md = (ROOT / cohort["report_markdown"]).resolve()
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown_report(payload, report_md)

    print(f"Wrote {report_json}")
    print(f"Wrote {report_md}")
    return payload


def main() -> None:
    args = parse_args()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    selected = COHORT_SPECS
    if args.cohort != "all":
        selected = [cohort for cohort in COHORT_SPECS if cohort["cohort_id"] == args.cohort]

    for cohort in selected:
        run_cohort(
            cohort=cohort,
            train_days=int(args.train_days),
            test_days=int(args.test_days),
            step_days=int(args.step_days),
        )


if __name__ == "__main__":
    main()
