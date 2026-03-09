import math
from typing import List, Dict, Any


def compute_metrics(trades: List[Dict], equity_curve: List[float]) -> Dict[str, Any]:
    """
    Compute performance metrics from a list of closed trade dicts and an equity curve.

    Each trade dict must have: realized_pnl, entry_date, close_date
    """
    if not trades:
        return {
            "total_trades": 0,
            "total_return_pct": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "avg_hold_days": 0.0,
        }

    pnls = [t.get("realized_pnl", 0) for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]

    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    # Hold time
    hold_days = []
    for t in trades:
        try:
            from datetime import datetime
            entry = datetime.fromisoformat(str(t.get("entry_date", "")))
            close = datetime.fromisoformat(str(t.get("close_date", "")))
            # Keep fractional hold time so same-day/intraday exits are visible.
            hold_days.append((close - entry).total_seconds() / 86400.0)
        except Exception:
            pass

    # Max drawdown from equity curve
    max_drawdown = 0.0
    if len(equity_curve) > 1:
        peak = max(equity_curve[0], 0.0)
        for val in equity_curve:
            # For drawdown, treat negative account values as fully depleted.
            # This avoids >100% drawdowns from pathological accounting artifacts.
            safe_val = max(val, 0.0)
            if safe_val > peak:
                peak = safe_val
            dd = (peak - safe_val) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, dd)

    # Sharpe ratio (annualized, daily returns, risk-free ~5%)
    sharpe = 0.0
    if len(equity_curve) > 2:
        import numpy as np
        daily_returns = [
            (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
            for i in range(1, len(equity_curve))
            if equity_curve[i - 1] != 0
        ]
        if daily_returns:
            mean_ret = sum(daily_returns) / len(daily_returns)
            std_ret = (sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
            annual_rf = 0.05 / 252
            sharpe = ((mean_ret - annual_rf) / std_ret * (252 ** 0.5)) if std_ret > 0 else 0.0

    initial = equity_curve[0] if equity_curve else 1
    final = equity_curve[-1] if equity_curve else 1
    total_return = (final - initial) / initial * 100 if initial > 0 else 0.0

    # Sortino (downside deviation), skew, kurtosis, CVaR, bad-day concentration
    sortino = 0.0
    skew_val = 0.0
    kurtosis_val = 0.0
    cvar_95 = 0.0
    bad_day_pct_loss = 0.0
    best_day_pct_profit = 0.0
    if len(equity_curve) > 2:
        import numpy as np
        daily_returns = np.array([
            (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
            for i in range(1, len(equity_curve))
            if equity_curve[i - 1] != 0
        ])
        if len(daily_returns) > 0:
            mean_ret = float(np.mean(daily_returns))
            downside_returns = daily_returns[daily_returns < 0]
            downside_std = float(np.std(downside_returns)) if len(downside_returns) > 1 else 0.0
            annual_rf = 0.05 / 252
            sortino = ((mean_ret - annual_rf) / downside_std * (252 ** 0.5)) if downside_std > 0 else 0.0
            skew_val = float(_sample_skew(daily_returns)) if len(daily_returns) >= 3 else 0.0
            kurtosis_val = float(_sample_kurtosis(daily_returns)) if len(daily_returns) >= 4 else 0.0
            sorted_returns = np.sort(daily_returns)
            tail_idx = max(0, int(len(sorted_returns) * 0.05))
            cvar_95 = float(np.mean(sorted_returns[:tail_idx])) if tail_idx > 0 else float(sorted_returns[0]) if len(sorted_returns) else 0.0
    if pnls:
        import numpy as np
        pnl_arr = np.array(pnls)
        total_loss = abs(float(np.sum(pnl_arr[pnl_arr < 0])))
        total_profit = float(np.sum(pnl_arr[pnl_arr > 0]))
        worst_n = min(5, len(pnl_arr))
        worst_days_pnl = np.sort(pnl_arr)[:worst_n]
        bad_day_pct_loss = (float(np.sum(worst_days_pnl)) / total_loss * 100.0) if total_loss > 0 else 0.0
        best_n = min(5, len(pnl_arr))
        best_days_pnl = np.sort(pnl_arr)[-best_n:]
        best_day_pct_profit = (float(np.sum(best_days_pnl)) / total_profit * 100.0) if total_profit > 0 else 0.0

    return {
        "total_trades": len(trades),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": len(winners) / len(trades) * 100 if trades else 0.0,
        "total_realized_pnl": sum(pnls),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "avg_win": sum(winners) / len(winners) if winners else 0.0,
        "avg_loss": sum(losers) / len(losers) if losers else 0.0,
        "avg_hold_days": sum(hold_days) / len(hold_days) if hold_days else 0.0,
        "max_drawdown_pct": max_drawdown * 100,
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "skew": round(skew_val, 4),
        "kurtosis": round(kurtosis_val, 4),
        "cvar_95_pct": round(cvar_95 * 100, 4) if cvar_95 != 0 else 0.0,
        "bad_day_concentration_pct": round(bad_day_pct_loss, 2),
        "best_day_concentration_pct": round(best_day_pct_profit, 2),
        "initial_equity": initial,
        "final_equity": final,
        "total_return_pct": total_return,
    }


def _sample_skew(a) -> float:
    """Sample skewness (NumPy only)."""
    try:
        import numpy as np
        a = np.asarray(a, dtype=float)
        a = a[~np.isnan(a)]
        n = len(a)
        if n < 3:
            return 0.0
        m = np.mean(a)
        s = np.std(a)
        if s == 0:
            return 0.0
        return float(np.mean(((a - m) / s) ** 3))
    except Exception:
        return 0.0


def _sample_kurtosis(a) -> float:
    """Excess kurtosis (Fisher, 0 for normal). NumPy only."""
    try:
        import numpy as np
        a = np.asarray(a, dtype=float)
        a = a[~np.isnan(a)]
        n = len(a)
        if n < 4:
            return 0.0
        m = np.mean(a)
        s = np.std(a)
        if s == 0:
            return 0.0
        return float(np.mean(((a - m) / s) ** 4) - 3.0)
    except Exception:
        return 0.0


def compute_metrics_sub_periods(
    trades: List[Dict],
    initial_equity: float,
) -> Dict[str, Dict[str, Any]]:
    """
    Compute metrics per sub-period. Each trade dict must have "sub_period" and "realized_pnl".
    """
    from collections import defaultdict
    by_period = defaultdict(list)
    for t in trades:
        k = t.get("sub_period") or "unknown"
        by_period[k].append(t)
    out = {}
    for period, period_trades in by_period.items():
        if not period_trades:
            continue
        period_trades_sorted = sorted(period_trades, key=lambda x: (x.get("entry_date", ""), x.get("close_date", "")))
        period_equity = [initial_equity]
        cum = initial_equity
        for t in period_trades_sorted:
            cum += t.get("realized_pnl", 0)
            period_equity.append(cum)
        out[period] = compute_metrics(period_trades_sorted, period_equity)
    return out
