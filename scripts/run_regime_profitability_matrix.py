"""
Research-only regime profitability matrix around the current regime-credit champion.

Writes report artifacts under data/reports/ and intentionally avoids the official
backtest and walk-forward stores.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import _metrics_from_equity_window, _trading_days_for_period, _warmup_start_day
from ovtlyr.backtester.openclaw_engines import run_openclaw_variant
from ovtlyr.backtester.walkforward import generate_walkforward_windows, summarize_oos_runs


DATA_DIR = ROOT / "data"
YF_CACHE_DIR = ROOT / "tmp_yf_cache"
CORE_STRATEGY_ID = "openclaw_regime_credit_spread"
CORE_VARIANT = "regime_legacy_defensive"
SYMBOLS = ["SPY", "QQQ"]
OFFICIAL_GUARDRAIL_MAX_DD = 2.0
BASE_BULL_RISK_PCT = 0.0150
BASE_BEAR_RISK_PCT = 0.0090
BASE_NEUTRAL_RISK_PCT = 0.0090

SCORE_LADDERS: Dict[str, List[Dict[str, float]]] = {
    "soft_65_75": [
        {"min_score": 0.0, "risk_mult": 0.75},
        {"min_score": 65.0, "risk_mult": 1.00},
        {"min_score": 75.0, "risk_mult": 1.15},
    ],
    "conviction_65_75_85": [
        {"min_score": 0.0, "risk_mult": 0.60},
        {"min_score": 65.0, "risk_mult": 0.95},
        {"min_score": 75.0, "risk_mult": 1.15},
        {"min_score": 85.0, "risk_mult": 1.25},
    ],
}

STRUCTURAL_CONFIGS: List[Dict[str, Any]] = [
    {"experiment_id": "base", "score_sizing": "none", "bull_risk_pct": 0.0150, "bear_risk_pct": 0.0090, "neutral_risk_pct": 0.0090},
    {"experiment_id": "score_soft", "score_sizing": "soft_65_75", "bull_risk_pct": 0.0150, "bear_risk_pct": 0.0090, "neutral_risk_pct": 0.0090},
    {"experiment_id": "score_conviction", "score_sizing": "conviction_65_75_85", "bull_risk_pct": 0.0150, "bear_risk_pct": 0.0090, "neutral_risk_pct": 0.0090},
    {"experiment_id": "side_bear_trim", "score_sizing": "none", "bull_risk_pct": 0.0150, "bear_risk_pct": 0.0075, "neutral_risk_pct": 0.0075},
    {"experiment_id": "side_bull_push", "score_sizing": "none", "bull_risk_pct": 0.0165, "bear_risk_pct": 0.0090, "neutral_risk_pct": 0.0090},
    {"experiment_id": "side_asymmetric_push", "score_sizing": "none", "bull_risk_pct": 0.0165, "bear_risk_pct": 0.0075, "neutral_risk_pct": 0.0075},
    {"experiment_id": "score_soft_side_bear_trim", "score_sizing": "soft_65_75", "bull_risk_pct": 0.0150, "bear_risk_pct": 0.0075, "neutral_risk_pct": 0.0075},
    {"experiment_id": "score_soft_side_asymmetric_push", "score_sizing": "soft_65_75", "bull_risk_pct": 0.0165, "bear_risk_pct": 0.0075, "neutral_risk_pct": 0.0075},
    {"experiment_id": "score_conviction_side_asymmetric_push", "score_sizing": "conviction_65_75_85", "bull_risk_pct": 0.0165, "bear_risk_pct": 0.0075, "neutral_risk_pct": 0.0075},
]
OVERLAY_PROFILES: List[Optional[str]] = [None, "regime_core_base", "regime_core_overlay"]


@dataclass(frozen=True)
class MissingInterval:
    start: date
    end: date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the regime profitability upgrade matrix.")
    parser.add_argument("--official-start", default="2020-01-02")
    parser.add_argument("--official-end", default="2025-12-31")
    parser.add_argument("--research-start", default="2016-01-01")
    parser.add_argument("--research-end", default="2025-12-31")
    parser.add_argument("--train-days", type=int, default=504)
    parser.add_argument("--test-days", type=int, default=126)
    parser.add_argument("--step-days", type=int, default=126)
    parser.add_argument("--output-base", default="data/reports/regime_profitability_matrix")
    parser.add_argument("--skip-research", action="store_true")
    return parser.parse_args()


def _date_from_arg(value: str) -> date:
    return date.fromisoformat(str(value))


def _fmt_pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:+.2f}%"


def _fmt_num(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _matrix_key(experiment_id: str, overlay_profile: Optional[str]) -> str:
    return f"{experiment_id}|{overlay_profile or 'none'}"


def _row_key(row: Dict[str, Any]) -> str:
    return _matrix_key(str(row["experiment_id"]), row.get("overlay_profile"))


def build_matrix_specs() -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []
    for structural in STRUCTURAL_CONFIGS:
        for overlay_profile in OVERLAY_PROFILES:
            specs.append(
                {
                    "experiment_id": structural["experiment_id"],
                    "overlay_profile": overlay_profile or "none",
                    "score_sizing": structural["score_sizing"],
                    "bull_risk_pct": float(structural["bull_risk_pct"]),
                    "bear_risk_pct": float(structural["bear_risk_pct"]),
                    "neutral_risk_pct": float(structural["neutral_risk_pct"]),
                }
            )
    return specs


def build_regime_research_overrides(spec: Dict[str, Any]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    score_sizing = str(spec.get("score_sizing", "none") or "none")
    if score_sizing != "none":
        overrides["score_weighted_sizing_enabled"] = True
        overrides["score_sizing_buckets"] = [dict(row) for row in SCORE_LADDERS[score_sizing]]
    if float(spec["bull_risk_pct"]) != BASE_BULL_RISK_PCT:
        overrides["bull_risk_pct_override"] = float(spec["bull_risk_pct"])
    if float(spec["bear_risk_pct"]) != BASE_BEAR_RISK_PCT:
        overrides["bear_risk_pct_override"] = float(spec["bear_risk_pct"])
    if float(spec["neutral_risk_pct"]) != BASE_NEUTRAL_RISK_PCT:
        overrides["neutral_risk_pct_override"] = float(spec["neutral_risk_pct"])
    return overrides


def load_price_cache(symbols: Sequence[str]) -> pd.DataFrame:
    parts: List[pd.DataFrame] = []
    for path in sorted(glob.glob(str(DATA_DIR / "cache" / "*.parquet"))):
        try:
            frame = pd.read_parquet(path, columns=["date", "underlying", "underlying_price"])
        except Exception:
            continue
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
    days = [d for d in _available_days(frame, symbols) if start_day <= d <= end_day]
    if not days:
        return [MissingInterval(start=start_day, end=end_day)]
    intervals: List[MissingInterval] = []
    if (days[0] - start_day).days > max_expected_gap_days:
        intervals.append(MissingInterval(start=start_day, end=days[0] - timedelta(days=1)))
    for prev_day, next_day in zip(days, days[1:]):
        if (next_day - prev_day).days > max_expected_gap_days:
            intervals.append(MissingInterval(start=prev_day + timedelta(days=1), end=next_day - timedelta(days=1)))
    if (end_day - days[-1]).days > max_expected_gap_days:
        intervals.append(MissingInterval(start=days[-1] + timedelta(days=1), end=end_day))
    return intervals


def download_gap_fill(symbols: Sequence[str], intervals: Sequence[MissingInterval]) -> pd.DataFrame:
    if not intervals:
        return pd.DataFrame(columns=["date", "underlying", "underlying_price"])
    if yf is None:
        raise RuntimeError("yfinance is unavailable for research gap fill")
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
            raise RuntimeError(f"yfinance returned no data for {interval.start} to {interval.end}")
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        if "Close" in close.columns and len(symbols) == 1:
            close = close.rename(columns={"Close": list(symbols)[0]})
        close.index = pd.to_datetime(close.index).date
        rows: List[Dict[str, Any]] = []
        for day_idx, row in close.iterrows():
            for symbol in symbols:
                value = row.get(symbol)
                if pd.notna(value):
                    rows.append({"date": day_idx, "underlying": symbol, "underlying_price": float(value)})
        if rows:
            parts.append(pd.DataFrame(rows))
    if not parts:
        return pd.DataFrame(columns=["date", "underlying", "underlying_price"])
    return pd.concat(parts, ignore_index=True).sort_values(["date", "underlying"]).reset_index(drop=True)


def merge_price_sources(cache_frame: pd.DataFrame, fill_frame: pd.DataFrame, intervals: Sequence[MissingInterval]) -> pd.DataFrame:
    if not intervals:
        return cache_frame.copy()
    keep_mask = pd.Series(True, index=cache_frame.index)
    for interval in intervals:
        keep_mask &= ~((cache_frame["date"] >= interval.start) & (cache_frame["date"] <= interval.end))
    out = pd.concat([cache_frame.loc[keep_mask], fill_frame], ignore_index=True)
    return out.sort_values(["date", "underlying"]).reset_index(drop=True)


def prepare_research_frame(cache_frame: pd.DataFrame, start_day: date, end_day: date) -> Dict[str, Any]:
    missing_intervals = detect_missing_intervals(cache_frame, start_day, end_day, SYMBOLS)
    if not missing_intervals:
        return {
            "status": "completed",
            "frame": cache_frame[(cache_frame["date"] >= start_day) & (cache_frame["date"] <= end_day)].copy(),
            "missing_intervals": [],
            "skip_reason": None,
        }
    try:
        fill_frame = download_gap_fill(SYMBOLS, missing_intervals)
        merged = merge_price_sources(cache_frame, fill_frame, missing_intervals)
        remaining = detect_missing_intervals(merged, start_day, end_day, SYMBOLS)
        if remaining:
            return {
                "status": "skipped_incomplete_coverage",
                "frame": None,
                "missing_intervals": [{"start": i.start.isoformat(), "end": i.end.isoformat()} for i in remaining],
                "skip_reason": "Incomplete price coverage after attempting research gap fill.",
            }
        return {
            "status": "completed",
            "frame": merged[(merged["date"] >= start_day) & (merged["date"] <= end_day)].copy(),
            "missing_intervals": [{"start": i.start.isoformat(), "end": i.end.isoformat()} for i in missing_intervals],
            "skip_reason": None,
        }
    except Exception as exc:
        return {
            "status": "skipped_incomplete_coverage",
            "frame": None,
            "missing_intervals": [{"start": i.start.isoformat(), "end": i.end.isoformat()} for i in missing_intervals],
            "skip_reason": str(exc),
        }


def run_matrix_period(frame: pd.DataFrame, start_day: date, end_day: date, spec: Dict[str, Any]) -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    if spec.get("overlay_profile") not in {None, "", "none"}:
        config["portfolio_overlay_profile"] = spec["overlay_profile"]
    overrides = build_regime_research_overrides(spec)
    if overrides:
        config["regime_research_overrides"] = overrides
    output = run_openclaw_variant(
        data=frame,
        config=config,
        start_date=start_day,
        end_date=end_day,
        strategy_id=CORE_STRATEGY_ID,
        assumptions_mode=CORE_VARIANT,
        universe_symbols=list(SYMBOLS),
    )
    return {
        "metrics": output.metrics,
        "equity_points": output.equity_points,
        "component_metrics": output.component_metrics or {},
        "trade_records": output.trade_records or [],
    }


def run_matrix_walkforward(
    frame: pd.DataFrame,
    start_day: date,
    end_day: date,
    spec: Dict[str, Any],
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
        result = run_matrix_period(frame, warm_start, window.test_end, spec)
        metrics = result["metrics"]
        if warm_start < window.test_start:
            metrics = _metrics_from_equity_window(result["equity_points"], start_day=window.test_start, end_day=window.test_end, base_metrics=metrics)
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
    summary = summarize_oos_runs(oos_metrics, sharpe_threshold=0.70, max_dd_threshold=30.0)
    return summary, rows


def _extract_full_period_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "total_return_pct": float(metrics.get("total_return_pct", 0.0) or 0.0),
        "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0) or 0.0),
        "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0) or 0.0),
        "total_trades": int(metrics.get("total_trades", 0) or 0),
    }


def run_window_suite(
    frame: pd.DataFrame,
    start_day: date,
    end_day: date,
    specs: Sequence[Dict[str, Any]],
    train_days: int,
    test_days: int,
    step_days: int,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for spec in specs:
        period = run_matrix_period(frame, start_day, end_day, spec)
        walkforward_summary, walkforward_windows = run_matrix_walkforward(frame, start_day, end_day, spec, train_days, test_days, step_days)
        rows.append(
            {
                "experiment_id": spec["experiment_id"],
                "overlay_profile": spec["overlay_profile"],
                "score_sizing": spec["score_sizing"],
                "bull_risk_pct": float(spec["bull_risk_pct"]),
                "bear_risk_pct": float(spec["bear_risk_pct"]),
                "neutral_risk_pct": float(spec["neutral_risk_pct"]),
                "research_overrides": build_regime_research_overrides(spec),
                "full_period": _extract_full_period_metrics(period["metrics"]),
                "walkforward_summary": walkforward_summary,
                "walkforward_windows": walkforward_windows,
                "component_metrics": period["component_metrics"],
                "trade_records": period["trade_records"],
            }
        )
    return rows


def _research_oos_return(row: Dict[str, Any]) -> float:
    research = row.get("research", {}) or {}
    if str(research.get("status")) != "completed":
        return float("-inf")
    return float(((research.get("walkforward_summary") or {}).get("avg_total_return_pct", 0.0)) or 0.0)


def rank_matrix_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: (
            0 if bool(row["official"]["walkforward_summary"].get("pass_validation", False)) else 1,
            0 if float(row["official"]["walkforward_summary"].get("avg_max_drawdown_pct", 0.0) or 0.0) <= OFFICIAL_GUARDRAIL_MAX_DD else 1,
            -float(row["official"]["walkforward_summary"].get("avg_total_return_pct", 0.0) or 0.0),
            -float(row["official"]["walkforward_summary"].get("avg_sharpe_ratio", 0.0) or 0.0),
            float(row["official"]["walkforward_summary"].get("avg_max_drawdown_pct", 0.0) or 0.0),
            -float(row["official"]["full_period"].get("total_return_pct", 0.0) or 0.0),
            -_research_oos_return(row),
        ),
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
        row["eligible"] = bool(row["official"]["walkforward_summary"].get("pass_validation", False)) and float(row["official"]["walkforward_summary"].get("avg_max_drawdown_pct", 0.0) or 0.0) <= OFFICIAL_GUARDRAIL_MAX_DD
    return ranked


def apply_base_deltas(rows: Sequence[Dict[str, Any]]) -> None:
    base_row = next((row for row in rows if _row_key(row) == _matrix_key("base", "none")), None)
    if base_row is None:
        raise ValueError("Base row base|none is required")
    base_official_oos = base_row["official"]["walkforward_summary"]
    base_official_full = base_row["official"]["full_period"]
    base_research = base_row.get("research", {}) or {}
    base_research_oos = (base_research.get("walkforward_summary") or {})
    for row in rows:
        official_oos = row["official"]["walkforward_summary"]
        deltas = {
            "official_oos_return_pct": float(official_oos.get("avg_total_return_pct", 0.0) or 0.0) - float(base_official_oos.get("avg_total_return_pct", 0.0) or 0.0),
            "official_oos_sharpe_ratio": float(official_oos.get("avg_sharpe_ratio", 0.0) or 0.0) - float(base_official_oos.get("avg_sharpe_ratio", 0.0) or 0.0),
            "official_oos_max_drawdown_pct": float(official_oos.get("avg_max_drawdown_pct", 0.0) or 0.0) - float(base_official_oos.get("avg_max_drawdown_pct", 0.0) or 0.0),
            "official_total_return_pct": float(row["official"]["full_period"].get("total_return_pct", 0.0) or 0.0) - float(base_official_full.get("total_return_pct", 0.0) or 0.0),
            "research_oos_return_pct": None,
        }
        if str((row.get("research", {}) or {}).get("status")) == "completed" and str(base_research.get("status")) == "completed":
            deltas["research_oos_return_pct"] = float(((row["research"]["walkforward_summary"] or {}).get("avg_total_return_pct", 0.0)) or 0.0) - float(base_research_oos.get("avg_total_return_pct", 0.0) or 0.0)
        row["deltas_vs_base"] = deltas


def determine_winner(rows: Sequence[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], str]:
    base_row = next((row for row in rows if _row_key(row) == _matrix_key("base", "none")), None)
    if base_row is None:
        raise ValueError("Base row base|none is required")
    eligible_rows = [row for row in rows if bool(row.get("eligible", False))]
    if not eligible_rows:
        return None, "No matrix candidate met the official validation and drawdown guardrail."
    leader = eligible_rows[0]
    base_oos_return = float(base_row["official"]["walkforward_summary"].get("avg_total_return_pct", 0.0) or 0.0)
    leader_oos_return = float(leader["official"]["walkforward_summary"].get("avg_total_return_pct", 0.0) or 0.0)
    if _row_key(leader) == _matrix_key("base", "none") or leader_oos_return <= base_oos_return:
        return None, "No improvement: the current champion configuration remains best under the official gate."
    return leader, f"Improvement found: {leader['experiment_id']} | {leader['overlay_profile']} beat the base official OOS return while remaining eligible."


def build_payload(
    official_rows: Sequence[Dict[str, Any]],
    research_rows: Optional[Sequence[Dict[str, Any]]],
    *,
    official_start: date,
    official_end: date,
    research_start: date,
    research_end: date,
    train_days: int,
    test_days: int,
    step_days: int,
    research_status: Dict[str, Any],
) -> Dict[str, Any]:
    official_map = {_row_key(row): row for row in official_rows}
    research_map = {_row_key(row): row for row in (research_rows or [])}
    combined: List[Dict[str, Any]] = []
    for key, official in official_map.items():
        research_row = research_map.get(key)
        combined.append(
            {
                "experiment_id": official["experiment_id"],
                "overlay_profile": official["overlay_profile"],
                "score_sizing": official["score_sizing"],
                "bull_risk_pct": official["bull_risk_pct"],
                "bear_risk_pct": official["bear_risk_pct"],
                "neutral_risk_pct": official["neutral_risk_pct"],
                "research_overrides": official["research_overrides"],
                "official": {
                    "full_period": official["full_period"],
                    "walkforward_summary": official["walkforward_summary"],
                    "walkforward_windows": official["walkforward_windows"],
                },
                "research": (
                    {
                        "status": "completed",
                        "full_period": research_row["full_period"],
                        "walkforward_summary": research_row["walkforward_summary"],
                        "walkforward_windows": research_row["walkforward_windows"],
                    }
                    if research_row is not None
                    else {
                        "status": research_status["status"],
                        "full_period": None,
                        "walkforward_summary": None,
                        "walkforward_windows": [],
                        "missing_intervals": research_status.get("missing_intervals", []),
                        "skip_reason": research_status.get("skip_reason"),
                    }
                ),
            }
        )
    apply_base_deltas(combined)
    ranked = rank_matrix_rows(combined)
    winner, conclusion = determine_winner(ranked)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy_id": CORE_STRATEGY_ID,
        "variant": CORE_VARIANT,
        "objective": {
            "metric": "official_oos_return_pct",
            "must_pass_validation": True,
            "official_max_drawdown_guardrail_pct": OFFICIAL_GUARDRAIL_MAX_DD,
        },
        "matrix": {
            "structural_configs": len(STRUCTURAL_CONFIGS),
            "overlay_profiles": ["none", "regime_core_base", "regime_core_overlay"],
            "runs_per_window": len(STRUCTURAL_CONFIGS) * len(OVERLAY_PROFILES),
        },
        "official_window": {
            "start": official_start.isoformat(),
            "end": official_end.isoformat(),
            "train_days": train_days,
            "test_days": test_days,
            "step_days": step_days,
            "status": "completed",
        },
        "research_window": {
            "start": research_start.isoformat(),
            "end": research_end.isoformat(),
            "train_days": train_days,
            "test_days": test_days,
            "step_days": step_days,
            "status": research_status["status"],
            "missing_intervals": research_status.get("missing_intervals", []),
            "skip_reason": research_status.get("skip_reason"),
        },
        "ranking": ranked,
        "winner": (
            {
                "experiment_id": winner["experiment_id"],
                "overlay_profile": winner["overlay_profile"],
                "official_oos_return_pct": winner["official"]["walkforward_summary"].get("avg_total_return_pct"),
                "official_oos_sharpe_ratio": winner["official"]["walkforward_summary"].get("avg_sharpe_ratio"),
                "official_oos_max_drawdown_pct": winner["official"]["walkforward_summary"].get("avg_max_drawdown_pct"),
            }
            if winner is not None
            else None
        ),
        "conclusion": conclusion,
    }


def write_json_report(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def write_markdown_report(path: Path, payload: Dict[str, Any]) -> None:
    lines = [
        "# Regime Profitability Upgrade Matrix",
        "",
        f"- Strategy: `{payload['strategy_id']}|{payload['variant']}`",
        f"- Official window: `{payload['official_window']['start']}` to `{payload['official_window']['end']}`",
        f"- Walk-forward: train `{payload['official_window']['train_days']}` / test `{payload['official_window']['test_days']}` / step `{payload['official_window']['step_days']}`",
        f"- Research window status: `{payload['research_window']['status']}`",
    ]
    if payload["research_window"].get("skip_reason"):
        lines.append(f"- Research skip reason: `{payload['research_window']['skip_reason']}`")
    if payload["winner"] is not None:
        winner = payload["winner"]
        lines.append(
            f"- Winner: `{winner['experiment_id']}|{winner['overlay_profile']}` "
            f"({_fmt_pct(winner['official_oos_return_pct'])} OOS, Sharpe {_fmt_num(winner['official_oos_sharpe_ratio'])}, DD {_fmt_pct(winner['official_oos_max_drawdown_pct'])})"
        )
    else:
        lines.append("- Winner: none")
    lines.extend(["", "## Conclusion", "", payload["conclusion"], "", "## Ranked Results", ""])
    lines.append("| Rank | Experiment | Overlay | Eligible | OOS Return | OOS Sharpe | OOS Max DD | PASS | Full Return | Research OOS | Delta vs Base OOS |")
    lines.append("| ---: | --- | --- | :---: | ---: | ---: | ---: | :---: | ---: | ---: | ---: |")
    for row in payload["ranking"]:
        official_oos = row["official"]["walkforward_summary"]
        research = row.get("research", {}) or {}
        research_oos = (research.get("walkforward_summary") or {}).get("avg_total_return_pct")
        lines.append(
            f"| {row['rank']} | `{row['experiment_id']}` | `{row['overlay_profile']}` | "
            f"{'Y' if row.get('eligible') else 'N'} | "
            f"{_fmt_pct(official_oos.get('avg_total_return_pct'))} | "
            f"{_fmt_num(official_oos.get('avg_sharpe_ratio'))} | "
            f"{_fmt_pct(official_oos.get('avg_max_drawdown_pct'))} | "
            f"{'PASS' if official_oos.get('pass_validation') else 'FAIL'} | "
            f"{_fmt_pct(row['official']['full_period'].get('total_return_pct'))} | "
            f"{_fmt_pct(research_oos) if research.get('status') == 'completed' else 'n/a'} | "
            f"{_fmt_pct((row.get('deltas_vs_base') or {}).get('official_oos_return_pct'))} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    official_start = _date_from_arg(args.official_start)
    official_end = _date_from_arg(args.official_end)
    research_start = _date_from_arg(args.research_start)
    research_end = _date_from_arg(args.research_end)
    output_base = Path(args.output_base)
    if not output_base.is_absolute():
        output_base = ROOT / output_base

    specs = build_matrix_specs()
    cache_frame = load_price_cache(SYMBOLS)
    if cache_frame.empty:
        raise RuntimeError("No cached price data found for SPY/QQQ")

    official_frame = cache_frame[(cache_frame["date"] >= official_start) & (cache_frame["date"] <= official_end)].copy()
    if official_frame.empty:
        raise RuntimeError("Official window has no cache data for SPY/QQQ")

    print(f"Running official matrix ({len(specs)} configs): {official_start} to {official_end}")
    official_rows = run_window_suite(official_frame, official_start, official_end, specs, int(args.train_days), int(args.test_days), int(args.step_days))

    research_rows: Optional[List[Dict[str, Any]]] = None
    if bool(args.skip_research):
        research_status = {"status": "skipped_by_flag", "missing_intervals": [], "skip_reason": "Research window skipped by CLI flag."}
    else:
        research_status = prepare_research_frame(cache_frame, research_start, research_end)
        if research_status["status"] == "completed":
            print(f"Running research matrix ({len(specs)} configs): {research_start} to {research_end}")
            research_rows = run_window_suite(research_status["frame"], research_start, research_end, specs, int(args.train_days), int(args.test_days), int(args.step_days))
        else:
            print(f"Skipping research window: {research_status.get('skip_reason')}")

    payload = build_payload(
        official_rows,
        research_rows,
        official_start=official_start,
        official_end=official_end,
        research_start=research_start,
        research_end=research_end,
        train_days=int(args.train_days),
        test_days=int(args.test_days),
        step_days=int(args.step_days),
        research_status=research_status,
    )

    json_path = output_base.with_suffix(".json")
    md_path = output_base.with_suffix(".md")
    write_json_report(json_path, payload)
    write_markdown_report(md_path, payload)
    print(f"Saved JSON report: {json_path}")
    print(f"Saved markdown report: {md_path}")
    print(payload["conclusion"])


if __name__ == "__main__":
    main()
