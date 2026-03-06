"""
Wheel Strategy Backtest

The Wheel = CSP → If assigned, sell covered calls → If called, repeat
"""

import logging
from datetime import date, timedelta
from typing import Dict, List, Any, Optional

import pandas as pd

from ovtlyr.scanner.filters import filter_candidates
from ovtlyr.utils.math_utils import compute_intrinsic_value

logger = logging.getLogger(__name__)


def run_wheel_backtest(
    data: pd.DataFrame,
    config: Dict[str, Any],
    start_date: date,
    end_date: date,
) -> Dict[str, Any]:
    """
    Run wheel strategy backtest.

    Wheel flow:
    1. Sell CSP (cash-secured put)
    2. If assigned (put expires ITM) → own stock
    3. Sell covered call against stock
    4. If called (call expires ITM) → stock sold, repeat from step 1
    """
    strategy = config.get("strategy", {})

    # CSP params
    put_target_delta = strategy.get("target_delta", -0.20)
    put_delta_tol = strategy.get("delta_tolerance", 0.10)
    put_min_dte = strategy.get("min_dte", 30)
    put_max_dte = strategy.get("max_dte", 60)

    # Covered call params
    call_target_delta = strategy.get("wheel_call_delta", 0.30)
    call_min_dte = strategy.get("wheel_call_min_dte", 20)
    call_max_dte = strategy.get("wheel_call_max_dte", 45)

    initial_capital = 100000
    cash = initial_capital

    # Track positions
    # CSP positions: {underlying, strike, qty, entry_credit, entry_date, expiration_date}
    csp_positions: List[Dict] = []
    # Stock positions: {underlying, shares, entry_price, entry_date}
    stock_positions: List[Dict] = []
    # Covered call positions: {underlying, strike, qty, premium_received, entry_date, expiration_date}
    cc_positions: List[Dict] = []

    closed_trades = []
    equity_curve = [cash]

    trading_days = sorted(data["date"].unique())
    trading_days = [
        d for d in trading_days if start_date <= date.fromisoformat(str(d)) <= end_date
    ]

    for day_str in trading_days:
        today = date.fromisoformat(str(day_str))
        day_data = data[data["date"] == day_str]

        # === Handle CSP Expirations ===
        expired_csp = []
        for pos in list(csp_positions):
            try:
                exp = date.fromisoformat(str(pos["expiration_date"]))
            except:
                continue

            if exp <= today:
                # Get underlying price
                sym_data = day_data[day_data["underlying"] == pos["underlying"]]
                if sym_data.empty:
                    continue
                S = float(sym_data["underlying_price"].iloc[0])

                # Check if ITM (assigned)
                if S < pos["strike"]:
                    # Assigned! Buy stock
                    shares = pos["qty"] * 100
                    cost = S * shares
                    if cash >= cost:
                        cash -= cost
                        stock_positions.append(
                            {
                                "underlying": pos["underlying"],
                                "shares": shares,
                                "entry_price": S,
                                "entry_date": today.isoformat(),
                            }
                        )
                        logger.debug(
                            f"[WHEEL] Assigned {pos['underlying']} @ ${S:.2f}, now own {shares} shares"
                        )

                # Close CSP position
                intrinsic = max(pos["strike"] - S, 0)  # Put intrinsic
                cost_to_close = intrinsic * pos["qty"] * 100
                realized = pos["entry_credit"] - cost_to_close
                cash -= cost_to_close

                closed_trades.append(
                    {
                        "type": "csp",
                        "underlying": pos["underlying"],
                        "entry_date": pos["entry_date"],
                        "close_date": today.isoformat(),
                        "strike": pos["strike"],
                        "entry_credit": pos["entry_credit"],
                        "close_price": intrinsic,
                        "realized_pnl": realized,
                        "assigned": S < pos["strike"],
                    }
                )
                expired_csp.append(pos)

        for pos in expired_csp:
            csp_positions.remove(pos)

        # === Handle Covered Call Expirations ===
        expired_cc = []
        for pos in list(cc_positions):
            try:
                exp = date.fromisoformat(str(pos["expiration_date"]))
            except:
                continue

            if exp <= today:
                sym_data = day_data[day_data["underlying"] == pos["underlying"]]
                if sym_data.empty:
                    continue
                S = float(sym_data["underlying_price"].iloc[0])

                # Check if ITM (called away)
                if S > pos["strike"]:
                    # Called away! Sell stock
                    shares = pos["qty"] * 100
                    proceeds = S * shares
                    cash += proceeds

                    # Find and close stock position
                    for sp in stock_positions:
                        if sp["underlying"] == pos["underlying"]:
                            stock_pnl = (S - sp["entry_price"]) * sp["shares"]
                            closed_trades.append(
                                {
                                    "type": "stock",
                                    "underlying": pos["underlying"],
                                    "entry_date": sp["entry_date"],
                                    "close_date": today.isoformat(),
                                    "entry_price": sp["entry_price"],
                                    "close_price": S,
                                    "shares": sp["shares"],
                                    "realized_pnl": stock_pnl,
                                }
                            )
                            stock_positions.remove(sp)
                            logger.debug(
                                f"[WHEEL] Called away {pos['underlying']} @ ${S:.2f}, sold {shares} shares"
                            )
                            break

                # Close covered call
                intrinsic = max(S - pos["strike"], 0)  # Call intrinsic
                cost_to_close = intrinsic * pos["qty"] * 100
                realized = pos["premium_received"] - cost_to_close
                cash -= cost_to_close

                closed_trades.append(
                    {
                        "type": "covered_call",
                        "underlying": pos["underlying"],
                        "entry_date": pos["entry_date"],
                        "close_date": today.isoformat(),
                        "strike": pos["strike"],
                        "premium_received": pos["premium_received"],
                        "close_price": intrinsic,
                        "realized_pnl": realized,
                        "called_away": S > pos["strike"],
                    }
                )
                expired_cc.append(pos)

        for pos in expired_cc:
            cc_positions.remove(pos)

        # === Enter New CSPs (if not wheeling) ===
        # Skip if we have too many CSPs
        max_csp = 10
        if len(csp_positions) < max_csp:
            seen_underlyings = {p["underlying"] for p in csp_positions}
            seen_underlyings.update(p["underlying"] for p in stock_positions)
            seen_underlyings.update(p["underlying"] for p in cc_positions)

            for underlying in day_data["underlying"].unique():
                if underlying in seen_underlyings:
                    continue
                if len(csp_positions) >= max_csp:
                    break

                # Skip if we already have stock (wheel mode - don't open new CSPs on wheeling stocks)
                if stock_positions:
                    has_stock = any(
                        sp["underlying"] == underlying for sp in stock_positions
                    )
                    if has_stock:
                        continue

                sym_data = day_data[day_data["underlying"] == underlying]
                if sym_data.empty:
                    continue

                # Filter for puts with target delta
                puts = sym_data[sym_data["option_type"] == "put"]
                if puts.empty:
                    continue

                # Find put matching delta target
                puts = puts[
                    (puts["delta"] >= put_target_delta - put_delta_tol)
                    & (puts["delta"] <= put_target_delta + put_delta_tol)
                    & (puts["dte"] >= put_min_dte)
                    & (puts["dte"] <= put_max_dte)
                ]

                if puts.empty:
                    continue

                put = puts.iloc[0]
                strike = float(put["strike"])
                credit = float(put["bid"]) * 100
                collateral = strike * 100

                if cash >= collateral:
                    cash += credit
                    csp_positions.append(
                        {
                            "underlying": underlying,
                            "strike": strike,
                            "qty": 1,
                            "entry_credit": credit,
                            "entry_date": today.isoformat(),
                            "expiration_date": put["expiration_date"],
                        }
                    )
                    logger.debug(
                        f"[WHEEL] Opened CSP {underlying} ${strike} credit=${credit:.2f}"
                    )

        # === Enter Covered Calls (if we have stock) ===
        max_cc = 5
        if len(cc_positions) < max_cc and stock_positions:
            seen_cc_underlyings = {p["underlying"] for p in cc_positions}

            for sp in list(stock_positions):
                underlying = sp["underlying"]
                if underlying in seen_cc_underlyings:
                    continue
                if len(cc_positions) >= max_cc:
                    break

                sym_data = day_data[day_data["underlying"] == underlying]
                if sym_data.empty:
                    continue

                # Filter for calls with target delta
                calls = sym_data[sym_data["option_type"] == "call"]
                if calls.empty:
                    continue

                calls = calls[
                    (calls["delta"] >= call_target_delta - 0.05)
                    & (calls["delta"] <= call_target_delta + 0.05)
                    & (calls["dte"] >= call_min_dte)
                    & (calls["dte"] <= call_max_dte)
                ]

                if calls.empty:
                    continue

                call = calls.iloc[0]
                strike = float(call["strike"])
                premium = float(call["bid"]) * 100

                # Sell covered call (receive premium, need to buy to close later)
                cash += premium
                cc_positions.append(
                    {
                        "underlying": underlying,
                        "strike": strike,
                        "qty": 1,
                        "premium_received": premium,
                        "entry_date": today.isoformat(),
                        "expiration_date": call["expiration_date"],
                    }
                )
                logger.debug(
                    f"[WHEEL] Opened CC {underlying} ${strike} premium=${premium:.2f}"
                )

        # === Compute Equity (mark-to-market) ===
        # Use current market price for stock positions so the equity curve
        # reflects true economic value, not just cost basis.
        last_prices = {
            str(row["underlying"]): float(row["underlying_price"])
            for _, row in day_data.drop_duplicates("underlying").iterrows()
        }
        stock_value = sum(
            sp["shares"] * last_prices.get(sp["underlying"], sp["entry_price"])
            for sp in stock_positions
        )
        equity = cash + stock_value
        equity_curve.append(equity)

    # Close any remaining positions at end
    final_equity = equity_curve[-1]

    # Max drawdown
    peak = equity_curve[0]
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100.0 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # Sharpe ratio (annualized, 5% risk-free rate)
    daily_rets = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        if prev > 0:
            daily_rets.append((equity_curve[i] - prev) / prev)
    sharpe = 0.0
    if len(daily_rets) > 1:
        mean_ret = sum(daily_rets) / len(daily_rets)
        variance = sum((r - mean_ret) ** 2 for r in daily_rets) / len(daily_rets)
        std_ret = variance ** 0.5
        rf_daily = 0.05 / 252
        if std_ret > 0:
            sharpe = ((mean_ret - rf_daily) / std_ret) * (252 ** 0.5)

    # Average hold time per trade
    hold_days_list = []
    for t in closed_trades:
        try:
            e = date.fromisoformat(str(t["entry_date"]))
            c = date.fromisoformat(str(t["close_date"]))
            hold_days_list.append((c - e).days)
        except Exception:
            pass
    avg_hold_days = sum(hold_days_list) / len(hold_days_list) if hold_days_list else 0.0

    total_pnl = sum(t.get("realized_pnl", 0) for t in closed_trades)
    winners = [t for t in closed_trades if t.get("realized_pnl", 0) > 0]
    losers = [t for t in closed_trades if t.get("realized_pnl", 0) < 0]
    gross_profit = sum(t.get("realized_pnl", 0) for t in winners)
    gross_loss = sum(t.get("realized_pnl", 0) for t in losers)

    return {
        "total_trades": len(closed_trades),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": len(winners) / len(closed_trades) * 100 if closed_trades else 0,
        "total_realized_pnl": total_pnl,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": abs(gross_profit / gross_loss) if gross_loss != 0 else float("inf"),
        "avg_win": gross_profit / len(winners) if winners else 0,
        "avg_loss": gross_loss / len(losers) if losers else 0,
        "avg_hold_days": avg_hold_days,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": round(sharpe, 4),
        "initial_equity": initial_capital,
        "final_equity": final_equity,
        "total_return_pct": (final_equity - initial_capital) / initial_capital * 100,
        "trading_days": len(trading_days),
        "rolls_executed": 0,
        # Extra fields consumed by main.py to build equity curve + series
        "equity_curve": equity_curve,
        "closed_trades": closed_trades,
    }


def compute_metrics(trades: List[Dict], equity_curve: List[float]) -> Dict[str, Any]:
    """Compute performance metrics from trades and equity curve."""
    if not trades:
        return {
            "total_trades": 0,
            "winners": 0,
            "losers": 0,
            "win_rate": 0,
            "total_realized_pnl": 0,
            "gross_profit": 0,
            "gross_loss": 0,
            "profit_factor": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "max_drawdown_pct": 0,
            "sharpe_ratio": 0,
        }

    winners = [t for t in trades if t.get("realized_pnl", 0) > 0]
    losers = [t for t in trades if t.get("realized_pnl", 0) < 0]

    total_pnl = sum(t.get("realized_pnl", 0) for t in trades)
    gross_profit = sum(t.get("realized_pnl", 0) for t in winners)
    gross_loss = sum(t.get("realized_pnl", 0) for t in losers)

    # Max drawdown
    peak = equity_curve[0]
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    return {
        "total_trades": len(trades),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": len(winners) / len(trades) * 100,
        "total_realized_pnl": total_pnl,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": abs(gross_profit / gross_loss)
        if gross_loss != 0
        else float("inf"),
        "avg_win": gross_profit / len(winners) if winners else 0,
        "avg_loss": gross_loss / len(losers) if losers else 0,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": 0,  # TODO
    }
