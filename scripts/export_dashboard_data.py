"""
Export pre-computed dashboard JSON files for static hosting.

Run this after any backtest batch to update the public site data:
    python scripts/export_dashboard_data.py

Writes to dashboard/public/data/ so Next.js can serve them as static assets.
Deploy to Vercel with no backend needed.
"""

import json
import math
import os
from pathlib import Path
from statistics import mean

# --- Paths ---
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "dashboard" / "public" / "data"

BACKTEST_RUNS_PATH = DATA_DIR / "backtest_runs.json"
BACKTEST_RESULTS_PATH = DATA_DIR / "backtest_results.json"
BACKTEST_HISTORY_PATH = DATA_DIR / "backtest_history.json"
STRATEGY_CATALOG_PATH = DATA_DIR / "strategy_catalog.json"
WALKFORWARD_SUMMARY_PATH = DATA_DIR / "walkforward_summary.json"
WALKFORWARD_RUNS_PATH = DATA_DIR / "walkforward_runs.json"


# --- Helpers (mirrors stats.py) ---

def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def _json_safe(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _safe_num(value, default=0.0):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default


def _finite_num(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _coerce_drawdown_pct(value):
    x = _finite_num(value)
    if x is None:
        return None
    return min(max(x, 0.0), 100.0)


def _coerce_profit_factor(value):
    x = _finite_num(value)
    if x is None or x < 0:
        return None
    return x


def _period_span_days(run):
    from datetime import date
    def _parse(v):
        if not v:
            return None
        try:
            return date.fromisoformat(str(v)[:10])
        except Exception:
            return None
    s, e = _parse(run.get("start_date")), _parse(run.get("end_date"))
    if not s or not e:
        return 0
    return max((e - s).days, 0)


def _select_canonical_run(entries):
    if not entries:
        return {}
    def _key(run):
        return (
            _period_span_days(run),
            _safe_num(run.get("metrics", {}).get("total_trades", 0)),
            str(run.get("generated_at", "")),
        )
    return max(entries, key=_key)


# --- Aggregation (mirrors /api/stats/backtest/strategies) ---

def build_strategies(runs):
    grouped = {}
    for run in runs:
        key = f"{run.get('strategy_id', 'unknown')}|{run.get('variant', 'base')}"
        grouped.setdefault(key, []).append(run)

    result = []
    for key, entries in grouped.items():
        entries = sorted(entries, key=lambda r: r.get("generated_at", ""))
        canonical = _select_canonical_run(entries)
        latest = canonical
        metrics = [r.get("metrics", {}) for r in entries]
        latest_oos = latest.get("oos_summary", {}) or {}
        oos_rows = [
            e.get("oos_summary", {})
            for e in entries
            if isinstance(e.get("oos_summary"), dict) and e.get("oos_summary")
        ]

        returns   = [v for m in metrics if (v := _finite_num(m.get("total_return_pct", 0.0))) is not None]
        win_rates = [v for m in metrics if (v := _finite_num(m.get("win_rate", 0.0))) is not None]
        pfs       = [v for m in metrics if (v := _coerce_profit_factor(m.get("profit_factor", 0.0))) is not None]
        sharpes   = [v for m in metrics if (v := _finite_num(m.get("sharpe_ratio", 0.0))) is not None]
        max_dds   = [v for m in metrics if (v := _coerce_drawdown_pct(m.get("max_drawdown_pct", 0.0))) is not None]
        oos_returns = [v for m in oos_rows if (v := _finite_num(m.get("avg_total_return_pct", 0.0))) is not None]
        oos_sharpes = [v for m in oos_rows if (v := _finite_num(m.get("avg_sharpe_ratio", 0.0))) is not None]
        oos_dds     = [v for m in oos_rows if (v := _coerce_drawdown_pct(m.get("avg_max_drawdown_pct", 0.0))) is not None]

        result.append({
            "strategy_id": latest.get("strategy_id", "unknown"),
            "strategy_name": latest.get("strategy_name", latest.get("strategy_id", "unknown")),
            "variant": latest.get("variant", "base"),
            "engine_type": latest.get("engine_type", ""),
            "assumptions_mode": latest.get("assumptions_mode", latest.get("variant", "")),
            "universe_profile": latest.get("universe_profile", ""),
            "universe_size": int(_safe_num(latest.get("universe_size", 0))),
            "universe": latest.get("universe", ""),
            "runs": len(entries),
            "latest_run_id": latest.get("run_id"),
            "latest_generated_at": latest.get("generated_at"),
            "latest_period_key": latest.get("period_key"),
            "latest_start_date": latest.get("start_date"),
            "latest_end_date": latest.get("end_date"),
            "latest_total_return_pct": _finite_num(latest.get("metrics", {}).get("total_return_pct", 0.0)),
            "latest_win_rate": _finite_num(latest.get("metrics", {}).get("win_rate", 0.0)),
            "latest_profit_factor": _coerce_profit_factor(latest.get("metrics", {}).get("profit_factor", 0.0)),
            "latest_sharpe_ratio": _finite_num(latest.get("metrics", {}).get("sharpe_ratio", 0.0)),
            "latest_max_drawdown_pct": _coerce_drawdown_pct(latest.get("metrics", {}).get("max_drawdown_pct", 0.0)),
            "latest_oos_return_pct": _finite_num(latest_oos.get("avg_total_return_pct")),
            "latest_oos_sharpe_ratio": _finite_num(latest_oos.get("avg_sharpe_ratio")),
            "latest_oos_max_drawdown_pct": _coerce_drawdown_pct(latest_oos.get("avg_max_drawdown_pct")),
            "oos_pass_validation": bool(latest_oos.get("pass_validation", False)) if latest_oos else False,
            "oos_criteria": latest_oos.get("criteria") if latest_oos else None,
            "has_oos_summary": bool(latest_oos),
            "best_total_return_pct": max(returns) if returns else None,
            "worst_total_return_pct": min(returns) if returns else None,
            "avg_total_return_pct": mean(returns) if returns else None,
            "avg_win_rate": mean(win_rates) if win_rates else 0.0,
            "avg_profit_factor": mean(pfs) if pfs else 0.0,
            "avg_sharpe_ratio": mean(sharpes) if sharpes else 0.0,
            "avg_max_drawdown_pct": mean(max_dds) if max_dds else 0.0,
            "avg_oos_return_pct": mean(oos_returns) if oos_returns else 0.0,
            "avg_oos_sharpe_ratio": mean(oos_sharpes) if oos_sharpes else 0.0,
            "avg_oos_max_drawdown_pct": mean(oos_dds) if oos_dds else 0.0,
            "has_component_metrics": any(bool(e.get("component_metrics")) for e in entries),
        })

    return _json_safe(sorted(result, key=lambda r: (r["strategy_id"], r["variant"])))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load source files
    runs = _load_json(BACKTEST_RUNS_PATH, [])
    if not isinstance(runs, list):
        runs = []
    catalog = _load_json(STRATEGY_CATALOG_PATH, [])
    wf_summary = _load_json(WALKFORWARD_SUMMARY_PATH, {})
    wf_runs = _load_json(WALKFORWARD_RUNS_PATH, [])
    if not isinstance(wf_runs, list):
        wf_runs = []

    # 2. strategies.json — aggregated per strategy+variant
    strategies = build_strategies(runs)
    with open(OUT_DIR / "strategies.json", "w") as f:
        json.dump(strategies, f, indent=2)
    print(f"strategies.json   ->{len(strategies)} strategies")

    # 2b. backtest_latest.json + backtest_history.json for /backtest page
    latest = _load_json(BACKTEST_RESULTS_PATH, {})
    history = _load_json(BACKTEST_HISTORY_PATH, {})
    with open(OUT_DIR / "backtest_latest.json", "w") as f:
        json.dump(_json_safe(latest), f, indent=2)
    with open(OUT_DIR / "backtest_history.json", "w") as f:
        json.dump(_json_safe(history), f, indent=2)
    print("backtest_latest.json ->1 record")
    print(f"backtest_history.json ->{len(history) if isinstance(history, dict) else 0} records")

    # 3. runs.json — full run list sorted by recency
    runs_sorted = sorted(runs, key=lambda r: r.get("generated_at", ""), reverse=True)
    with open(OUT_DIR / "runs.json", "w") as f:
        json.dump(_json_safe(runs_sorted), f, indent=2)
    print(f"runs.json         ->{len(runs_sorted)} runs")

    # 4. catalog.json — strategy catalog passthrough
    with open(OUT_DIR / "catalog.json", "w") as f:
        json.dump(_json_safe(catalog), f, indent=2)
    print(f"catalog.json      ->{len(catalog) if isinstance(catalog, list) else 1} entries")

    # 5. walkforward.json — walk-forward summary
    wf_runs_sorted = sorted(wf_runs, key=lambda r: r.get("generated_at", ""), reverse=True)
    with open(OUT_DIR / "walkforward.json", "w") as f:
        json.dump(_json_safe(wf_summary), f, indent=2)
    with open(OUT_DIR / "walkforward_runs.json", "w") as f:
        json.dump(_json_safe(wf_runs_sorted), f, indent=2)
    print(f"walkforward.json  ->{len(wf_summary) if isinstance(wf_summary, dict) else 0} summaries")
    print(f"walkforward_runs.json ->{len(wf_runs_sorted)} runs")

    print(f"\nAll files written to {OUT_DIR}")
    print("Commit dashboard/public/data/ and push to redeploy on Vercel.")


if __name__ == "__main__":
    main()
