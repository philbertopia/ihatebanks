import json
import math
import os
import sqlite3
from statistics import mean
from datetime import date
from fastapi import APIRouter, HTTPException
from typing import List

from ovtlyr.api.server.models import PortfolioStats, DailyStats
from ovtlyr.database.repository import Repository
from ovtlyr.reporting.stats import get_portfolio_stats

BACKTEST_RESULTS_PATH = "data/backtest_results.json"
BACKTEST_HISTORY_PATH = "data/backtest_history.json"
BACKTEST_RUNS_PATH = "data/backtest_runs.json"
STRATEGY_CATALOG_PATH = "data/strategy_catalog.json"
WALKFORWARD_SUMMARY_PATH = "data/walkforward_summary.json"
WALKFORWARD_RUNS_PATH = "data/walkforward_runs.json"

router = APIRouter()
DB_PATH = "db/ovtlyr.db"


def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def _json_safe(value):
    """
    Recursively convert JSON-unsafe floats (inf, -inf, nan) to None so
    Starlette/FastAPI can serialize responses without raising ValueError.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _safe_num(value, default: float = 0.0, pos_inf: float | None = None, neg_inf: float | None = None) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default

    if math.isfinite(x):
        return x
    if x > 0 and pos_inf is not None:
        return pos_inf
    if x < 0 and neg_inf is not None:
        return neg_inf
    return default


def _finite_num(value) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _coerce_drawdown_pct(value) -> float | None:
    x = _finite_num(value)
    if x is None:
        return None
    # Drawdown is reported in percent and should stay in [0, 100] for a long-only
    # cash account view. Clamp to avoid pathological run artifacts distorting ranks.
    return min(max(x, 0.0), 100.0)


def _coerce_profit_factor(value) -> float | None:
    x = _finite_num(value)
    if x is None:
        return None
    if x < 0:
        return None
    return x


def _parse_ymd(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _normalize_initial_capital(value, default: float = 100_000.0) -> float:
    try:
        capital = float(value)
    except (TypeError, ValueError):
        capital = float(default)
    if capital <= 0:
        capital = float(default)
    return round(capital, 2)


def _capital_token(value) -> str:
    capital = _normalize_initial_capital(value)
    if capital.is_integer():
        return str(int(capital))
    return f"{capital:.2f}".replace(".", "p")


def _period_span_days(run: dict) -> int:
    start = _parse_ymd(run.get("start_date"))
    end = _parse_ymd(run.get("end_date"))
    if not start or not end:
        return 0
    return max((end - start).days, 0)


def _select_canonical_run(entries: list[dict]) -> dict:
    if not entries:
        return {}

    def _key(run: dict):
        span = _period_span_days(run)
        trades = _safe_num(run.get("metrics", {}).get("total_trades", 0), default=0.0)
        generated = str(run.get("generated_at", ""))
        return (span, trades, generated)

    return max(entries, key=_key)


@router.get("/stats/portfolio", response_model=PortfolioStats)
def get_portfolio():
    repo = Repository(DB_PATH)
    stats = get_portfolio_stats(repo)
    return PortfolioStats(
        open_positions=stats.get("open_positions", 0) or 0,
        portfolio_delta=stats.get("portfolio_delta", 0.0) or 0.0,
        total_unrealized_pnl=stats.get("total_unrealized_pnl", 0.0) or 0.0,
        total_realized_pnl=stats.get("total_realized_pnl", 0.0) or 0.0,
        total_closed=stats.get("total_closed", 0) or 0,
        winners=stats.get("winners", 0) or 0,
        losers=stats.get("losers", 0) or 0,
        win_rate=stats.get("win_rate", 0.0) or 0.0,
        profit_factor=min(stats.get("profit_factor", 0.0) or 0.0, 9999.0),
        gross_profit=stats.get("gross_profit", 0.0) or 0.0,
        gross_loss=stats.get("gross_loss", 0.0) or 0.0,
        avg_pnl=stats.get("avg_pnl"),
    )


@router.get("/stats/daily", response_model=List[DailyStats])
def get_daily_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT stat_date, open_positions, positions_opened, positions_rolled,
                   positions_closed, total_pnl_unrealized, total_pnl_realized, portfolio_delta
            FROM daily_stats
            ORDER BY stat_date DESC
            LIMIT 90
            """
        ).fetchall()
    finally:
        conn.close()

    return [
        DailyStats(
            stat_date=r["stat_date"],
            open_positions=r["open_positions"] or 0,
            positions_opened=r["positions_opened"] or 0,
            positions_rolled=r["positions_rolled"] or 0,
            positions_closed=r["positions_closed"] or 0,
            total_pnl_unrealized=r["total_pnl_unrealized"] or 0.0,
            total_pnl_realized=r["total_pnl_realized"] or 0.0,
            portfolio_delta=r["portfolio_delta"] or 0.0,
        )
        for r in rows
    ]


@router.get("/stats/backtest")
def get_backtest_results():
    """Return the most recent backtest results saved by `python main.py backtest`."""
    if not os.path.exists(BACKTEST_RESULTS_PATH):
        raise HTTPException(status_code=404, detail="No backtest results found. Run: python main.py backtest")
    return _json_safe(_load_json(BACKTEST_RESULTS_PATH, {}))


@router.get("/stats/backtest/history")
def get_backtest_history():
    """Return historical backtest snapshots keyed by strategy/variant/period."""
    return _json_safe(_load_json(BACKTEST_HISTORY_PATH, {}))


@router.get("/stats/backtest/runs")
def get_backtest_runs():
    """Return chronological run log for all strategies/variants."""
    runs = _load_json(BACKTEST_RUNS_PATH, [])
    if not isinstance(runs, list):
        return []
    runs = sorted(runs, key=lambda r: r.get("generated_at", ""), reverse=True)
    return _json_safe(runs)


@router.get("/stats/backtest/walkforward")
def get_walkforward_summary():
    """Return latest walk-forward summaries keyed by strategy|variant|universe profile."""
    return _json_safe(_load_json(WALKFORWARD_SUMMARY_PATH, {}))


@router.get("/stats/backtest/walkforward/runs")
def get_walkforward_runs():
    """Return full walk-forward run log."""
    rows = _load_json(WALKFORWARD_RUNS_PATH, [])
    if not isinstance(rows, list):
        rows = []
    rows = sorted(rows, key=lambda r: r.get("generated_at", ""), reverse=True)
    return _json_safe(rows)


@router.get("/stats/backtest/strategies")
def get_backtest_strategy_comparison():
    """Aggregate runs by strategy+variant+capital for side-by-side comparison."""
    runs = _load_json(BACKTEST_RUNS_PATH, [])
    if not isinstance(runs, list):
        runs = []

    grouped = {}
    for run in runs:
        strategy_id = run.get("strategy_id", "unknown")
        variant = run.get("variant", "base")
        key = f"{strategy_id}|{variant}|cap{_capital_token(run.get('initial_capital'))}"
        grouped.setdefault(key, []).append(run)

    result = []
    for key, entries in grouped.items():
        entries = sorted(entries, key=lambda r: r.get("generated_at", ""))
        # Prefer longest-period runs, then higher trade-count runs, then latest.
        # This avoids short diagnostic runs displacing full-period campaign stats.
        canonical = _select_canonical_run(entries)
        latest = canonical
        metrics = [r.get("metrics", {}) for r in entries]
        latest_oos = latest.get("oos_summary", {}) or {}
        oos_rows = [
            e.get("oos_summary", {})
            for e in entries
            if isinstance(e.get("oos_summary"), dict) and e.get("oos_summary")
        ]

        returns = [v for m in metrics if (v := _finite_num(m.get("total_return_pct", 0.0))) is not None]
        win_rates = [v for m in metrics if (v := _finite_num(m.get("win_rate", 0.0))) is not None]
        pfs = [v for m in metrics if (v := _coerce_profit_factor(m.get("profit_factor", 0.0))) is not None]
        sharpes = [v for m in metrics if (v := _finite_num(m.get("sharpe_ratio", 0.0))) is not None]
        max_dds = [v for m in metrics if (v := _coerce_drawdown_pct(m.get("max_drawdown_pct", 0.0))) is not None]
        oos_returns = [v for m in oos_rows if (v := _finite_num(m.get("avg_total_return_pct", 0.0))) is not None]
        oos_sharpes = [v for m in oos_rows if (v := _finite_num(m.get("avg_sharpe_ratio", 0.0))) is not None]
        oos_dds = [v for m in oos_rows if (v := _coerce_drawdown_pct(m.get("avg_max_drawdown_pct", 0.0))) is not None]

        result.append({
            "strategy_id": latest.get("strategy_id", "unknown"),
            "strategy_name": latest.get("strategy_name", latest.get("strategy_id", "unknown")),
            "variant": latest.get("variant", "base"),
            "initial_capital": _normalize_initial_capital(latest.get("initial_capital")),
            "engine_type": latest.get("engine_type", ""),
            "assumptions_mode": latest.get("assumptions_mode", latest.get("variant", "")),
            "universe_profile": latest.get("universe_profile", ""),
            "universe_size": int(_safe_num(latest.get("universe_size", 0), default=0.0)),
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
            "feature_time_mode": latest.get("feature_time_mode"),
            "data_quality_policy": latest.get("data_quality_policy"),
            "rejection_counts": latest.get("rejection_counts", {}),
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

    return _json_safe(
        sorted(
            result,
            key=lambda r: (
                r["strategy_id"],
                r["variant"],
                _normalize_initial_capital(r.get("initial_capital")),
            ),
        )
    )


@router.get("/stats/backtest/catalog")
def get_strategy_catalog():
    """Return documented strategy variants and hypotheses to test."""
    catalog = _load_json(STRATEGY_CATALOG_PATH, [])
    if isinstance(catalog, list):
        return catalog
    return []


@router.get("/stats/backtest/latest-candidates")
def get_latest_backtest_candidates(strategy_id: str = "", variant: str = ""):
    """
    Return the latest intraday candidate snapshot.
    Optional query params:
      - strategy_id
      - variant
    """
    runs = _load_json(BACKTEST_RUNS_PATH, [])
    if not isinstance(runs, list):
        runs = []

    if strategy_id:
        runs = [r for r in runs if str(r.get("strategy_id", "")) == str(strategy_id)]
    if variant:
        runs = [r for r in runs if str(r.get("variant", "")) == str(variant)]

    runs = sorted(runs, key=lambda r: r.get("generated_at", ""), reverse=True)
    if not runs:
        latest = _load_json(BACKTEST_RESULTS_PATH, {})
    else:
        latest = runs[0]

    out = {
        "run_id": latest.get("run_id"),
        "strategy_id": latest.get("strategy_id"),
        "variant": latest.get("variant"),
        "generated_at": latest.get("generated_at"),
        "strategy_parameters": latest.get("strategy_parameters", {}),
        "feature_time_mode": latest.get("feature_time_mode"),
        "data_quality_policy": latest.get("data_quality_policy"),
        "execution_window": latest.get("execution_window"),
        "candidate_count_total": latest.get("candidate_count_total", 0),
        "candidate_count_qualified": latest.get("candidate_count_qualified", 0),
        "data_quality_breakdown": latest.get("data_quality_breakdown", {}),
        "rejection_counts": latest.get("rejection_counts", {}),
        "intraday_report": latest.get("intraday_report", []),
    }
    return _json_safe(out)
