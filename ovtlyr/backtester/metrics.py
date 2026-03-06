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
        "initial_equity": initial,
        "final_equity": final,
        "total_return_pct": total_return,
    }
