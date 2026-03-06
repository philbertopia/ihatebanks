from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean
from typing import Dict, Iterable, List, Sequence


@dataclass
class WalkForwardWindow:
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    index: int


def generate_walkforward_windows(
    trading_days: Sequence[date],
    train_days: int,
    test_days: int,
    step_days: int,
) -> List[WalkForwardWindow]:
    days = sorted(set(trading_days))
    t = max(int(train_days), 1)
    v = max(int(test_days), 1)
    s = max(int(step_days), 1)
    out: List[WalkForwardWindow] = []
    if len(days) < (t + v):
        return out

    start = 0
    idx = 1
    while start + t + v <= len(days):
        train_slice = days[start : start + t]
        test_slice = days[start + t : start + t + v]
        out.append(
            WalkForwardWindow(
                train_start=train_slice[0],
                train_end=train_slice[-1],
                test_start=test_slice[0],
                test_end=test_slice[-1],
                index=idx,
            )
        )
        idx += 1
        start += s
    return out


def summarize_oos_runs(
    run_metrics: Iterable[Dict],
    sharpe_threshold: float = 0.70,
    max_dd_threshold: float = 30.0,
    return_threshold: float = 0.0,
) -> Dict:
    rows = list(run_metrics)
    if not rows:
        return {
            "windows": 0,
            "avg_total_return_pct": 0.0,
            "avg_sharpe_ratio": 0.0,
            "avg_max_drawdown_pct": 0.0,
            "pass_validation": False,
        }

    returns = [float(r.get("total_return_pct", 0.0) or 0.0) for r in rows]
    sharpes = [float(r.get("sharpe_ratio", 0.0) or 0.0) for r in rows]
    max_dds = [float(r.get("max_drawdown_pct", 0.0) or 0.0) for r in rows]

    avg_ret = mean(returns)
    avg_sharpe = mean(sharpes)
    avg_dd = mean(max_dds)
    pass_validation = (
        avg_sharpe >= sharpe_threshold
        and avg_dd <= max_dd_threshold
        and avg_ret > return_threshold
    )
    return {
        "windows": len(rows),
        "avg_total_return_pct": round(avg_ret, 6),
        "avg_sharpe_ratio": round(avg_sharpe, 6),
        "avg_max_drawdown_pct": round(avg_dd, 6),
        "pass_validation": bool(pass_validation),
        "criteria": {
            "sharpe_threshold": sharpe_threshold,
            "max_dd_threshold": max_dd_threshold,
            "return_threshold": return_threshold,
        },
    }

