from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, List, Tuple


def compute_drawdown_curve(equity_curve: List[float]) -> List[float]:
    """Return drawdown series in percent (non-positive values)."""
    if not equity_curve:
        return []
    peak = max(equity_curve[0], 0.0)
    out: List[float] = []
    for v in equity_curve:
        safe_v = max(v, 0.0)
        if safe_v > peak:
            peak = safe_v
        dd = ((safe_v - peak) / peak) * 100 if peak > 0 else 0.0
        out.append(round(min(dd, 0.0), 4))
    return out


def compute_rolling_win_rate(
    trade_pnls: List[float],
    window: int = 20,
) -> List[float]:
    """Rolling win-rate in percent over trade outcomes."""
    if not trade_pnls:
        return []
    out: List[float] = []
    for i in range(len(trade_pnls)):
        start = max(0, i - window + 1)
        chunk = trade_pnls[start : i + 1]
        wins = sum(1 for p in chunk if p > 0)
        out.append(round((wins / len(chunk)) * 100, 4))
    return out


def compute_monthly_returns(
    daily_equity_points: List[Tuple[date, float]],
) -> List[Dict[str, float]]:
    """
    Build monthly returns from daily equity points.
    Returns items: {month: 'YYYY-MM', return_pct: float}
    """
    if not daily_equity_points:
        return []

    # Keep first and last equity for each month
    first_equity: Dict[str, float] = {}
    last_equity: Dict[str, float] = {}
    for d, equity in daily_equity_points:
        key = d.strftime("%Y-%m")
        if key not in first_equity:
            first_equity[key] = equity
        last_equity[key] = equity

    out: List[Dict[str, float]] = []
    for key in sorted(last_equity.keys()):
        start = first_equity[key]
        end = last_equity[key]
        pct = ((end - start) / start) * 100 if start > 0 else 0.0
        out.append({"month": key, "return_pct": round(pct, 4)})
    return out
