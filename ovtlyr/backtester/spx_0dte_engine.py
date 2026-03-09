"""
SPX 0DTE short put spread backtest engine.

Runs only on SPXW expiry days (calendar from spx_expiry). Proxy path uses daily
cache: one snapshot per day, simulated intraday exit path from open→close.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ovtlyr.backtester.execution_model import (
    spread_fill_credit_entry,
    spread_fill_debit_exit,
)
from ovtlyr.backtester.metrics import compute_metrics, compute_metrics_sub_periods
from ovtlyr.backtester.spx_expiry import (
    SPX_MULTIPLIER,
    has_same_day_expiry,
    spxw_expiry_calendar,
    sub_period_key,
)
from ovtlyr.strategy.risk_controls import load_macro_calendar, macro_window_block


# Default fee per contract (round-trip proxy including ORF)
DEFAULT_FEE_PER_CONTRACT = 0.65


def _put_spread_value_intrinsic(spot: float, short_strike: float, long_strike: float) -> float:
    """Spread value (cost to buy back) from intrinsic only; 0DTE ≈ intrinsic."""
    short_val = max(short_strike - spot, 0.0)
    long_val = max(long_strike - spot, 0.0)
    return max(short_val - long_val, 0.0)


def _simulate_intraday_exit(
    open_price: float,
    close_price: float,
    short_strike: float,
    long_strike: float,
    width: float,
    credit: float,
    tp_pct: float,
    stop_mult: float,
    n_steps: int = 30,
) -> Tuple[str, float]:
    """
    Simulate path open→close; return (exit_reason, spread_value_at_exit).
    exit_reason: "tp" | "stop" | "time"
    """
    tp_threshold = credit * (1.0 - tp_pct)  # close when spread_value <= this
    stop_threshold = min(credit * stop_mult, width * 0.55)
    for i in range(n_steps + 1):
        t = i / n_steps
        spot = open_price + t * (close_price - open_price)
        spread_val = _put_spread_value_intrinsic(spot, short_strike, long_strike)
        if spread_val <= tp_threshold:
            return ("tp", spread_val)
        if spread_val >= stop_threshold:
            return ("stop", spread_val)
    spread_val_close = _put_spread_value_intrinsic(close_price, short_strike, long_strike)
    return ("time", spread_val_close)


@dataclass
class Spx0DteParams:
    """Parameter set for one variant."""
    delta_lo: float
    delta_hi: float
    width_points: float
    risk_pct: float
    tp_pct: float
    stop_mult: float
    fill_mode: str
    base_pct_of_spread: float
    event_day_filter: bool
    daily_max_loss_pct: float
    min_credit_ratio: float
    fee_per_contract: float
    time_exit_et: str  # "15:45"
    underlying_proxy: str  # "SPY" for proxy


def _spx_0dte_params(variant: str) -> Spx0DteParams:
    """Resolve variant name to params. Add more variants as needed."""
    base = {
        "delta_lo": 0.10,
        "delta_hi": 0.15,
        "width_points": 10.0,
        "risk_pct": 0.005,
        "tp_pct": 0.60,
        "stop_mult": 1.5,
        "fill_mode": "base",
        "base_pct_of_spread": 0.15,
        "event_day_filter": True,
        "daily_max_loss_pct": 0.01,
        "min_credit_ratio": 0.15,
        "fee_per_contract": DEFAULT_FEE_PER_CONTRACT,
        "time_exit_et": "15:45",
        "underlying_proxy": "SPY",
    }
    if variant == "conservative":
        return Spx0DteParams(**{**base, "delta_lo": 0.05, "delta_hi": 0.10, "width_points": 5.0, "risk_pct": 0.003, "tp_pct": 0.50, "fill_mode": "conservative"})
    if variant == "balanced":
        return Spx0DteParams(**base)
    if variant == "aggressive":
        return Spx0DteParams(**{**base, "delta_lo": 0.15, "delta_hi": 0.25, "width_points": 15.0, "tp_pct": 0.70, "fill_mode": "optimistic"})
    # default balanced
    return Spx0DteParams(**base)


def run_spx_0dte_put_spread(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    variant: str = "balanced",
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run SPX 0DTE short put spread backtest (proxy path: daily cache + simulated exit).

    Returns dict with: metrics, equity_curve, equity_points, trade_pnls, closed_trades,
    strategy_parameters, sub_period_metrics (optional).
    """
    config = config or {}
    params = _spx_0dte_params(variant)
    underlying = params.underlying_proxy

    # Price series: date -> close (use underlying_price from cache, one per day)
    if "date" not in data.columns or "underlying" not in data.columns or "underlying_price" not in data.columns:
        return _empty_result(variant, params)

    data_dates = pd.to_datetime(data["date"]).dt.date
    mask = (data["underlying"] == underlying) & (data_dates >= start_date) & (data_dates <= end_date)
    price_df = data.loc[mask, ["date", "underlying_price"]].drop_duplicates(subset=["date"], keep="last")
    price_df["date"] = pd.to_datetime(price_df["date"]).dt.date
    price_series = price_df.set_index("date")["underlying_price"].astype(float).sort_index()

    if price_series.empty or len(price_series) < 2:
        return _empty_result(variant, params)

    # Option chain: need put, delta, bid, ask, strike, expiration_date, dte
    required = {"date", "underlying", "option_type", "strike", "expiration_date", "dte", "bid", "ask"}
    if not required.issubset(set(data.columns)):
        return _empty_result(variant, params)

    chain = data[
        (data["underlying"] == underlying)
        & (data["option_type"] == "put")
        & (data_dates >= start_date)
        & (data_dates <= end_date)
    ].copy()
    chain["date"] = pd.to_datetime(chain["date"]).dt.date
    if "delta" not in chain.columns:
        chain["delta"] = 0.0
    chain["delta"] = chain["delta"].astype(float).abs()  # put delta negative; use abs for targeting

    expiry_days = spxw_expiry_calendar(start_date, end_date)
    macro_events = load_macro_calendar(config.get("macro_calendar_path", "config/macro_calendar.yaml"))

    initial_capital = 100_000.0
    cash = initial_capital
    equity_curve: List[float] = [initial_capital]
    equity_points: List[Tuple[date, float]] = []
    closed_trades: List[Dict[str, Any]] = []
    trade_pnls: List[float] = []
    daily_pnl_series: List[Tuple[date, float]] = []
    peak_equity = initial_capital
    daily_loss_cap_hit = False

    dates_sorted = sorted(price_series.index)
    for i, day in enumerate(dates_sorted):
        if day not in expiry_days:
            equity_curve.append(cash)
            equity_points.append((day, cash))
            continue
        if params.event_day_filter and macro_window_block(day, macro_events, 0.0):
            equity_curve.append(cash)
            equity_points.append((day, cash))
            continue
        if daily_loss_cap_hit:
            daily_loss_cap_hit = False
            equity_curve.append(cash)
            equity_points.append((day, cash))
            continue

        day_chain = chain[chain["date"] == day]
        # 0DTE: expiration same calendar day
        day_chain = day_chain[day_chain["dte"] == 0]
        if day_chain.empty:
            equity_curve.append(cash)
            equity_points.append((day, cash))
            continue

        px_today = float(price_series.loc[day])
        px_prev = float(price_series.iloc[i - 1]) if i > 0 else px_today

        # Select short put by delta (chain deltas already .abs(); target e.g. 0.125 for 12.5-delta put)
        target_delta = (params.delta_lo + params.delta_hi) / 2.0
        day_chain = day_chain.copy()
        day_chain["delta_dist"] = (day_chain["delta"] - target_delta).abs()
        short_row = day_chain.nsmallest(1, "delta_dist")
        if short_row.empty:
            equity_curve.append(cash)
            equity_points.append((day, cash))
            continue
        short_row = short_row.iloc[0]
        short_strike = float(short_row["strike"])
        long_strike = round(short_strike - params.width_points, 2)
        if long_strike < 0:
            equity_curve.append(cash)
            equity_points.append((day, cash))
            continue

        long_candidates = day_chain[day_chain["strike"] <= long_strike]
        if long_candidates.empty:
            long_candidates = day_chain[day_chain["strike"] == long_strike]
        if long_candidates.empty:
            long_candidates = day_chain[day_chain["strike"] <= short_strike].nsmallest(1, "strike")
        if long_candidates.empty:
            equity_curve.append(cash)
            equity_points.append((day, cash))
            continue
        long_row = long_candidates.iloc[0]
        long_strike = float(long_row["strike"])
        width = short_strike - long_strike
        if width <= 0:
            equity_curve.append(cash)
            equity_points.append((day, cash))
            continue

        entry_credit = spread_fill_credit_entry(
            short_put_bid=float(short_row["bid"]),
            short_put_ask=float(short_row["ask"]),
            long_put_bid=float(long_row["bid"]),
            long_put_ask=float(long_row["ask"]),
            fill_mode=params.fill_mode,
            base_pct_of_spread=params.base_pct_of_spread,
        )
        if entry_credit < 0 or entry_credit >= width:
            equity_curve.append(cash)
            equity_points.append((day, cash))
            continue
        if (entry_credit / width) < params.min_credit_ratio:
            equity_curve.append(cash)
            equity_points.append((day, cash))
            continue

        max_loss_per_contract = (width - entry_credit) * SPX_MULTIPLIER + 2 * params.fee_per_contract
        risk_budget_d = cash * params.risk_pct
        n_raw = int(risk_budget_d / max_loss_per_contract)
        n = max(1, n_raw)

        fee_total = 2 * params.fee_per_contract * n
        exit_reason, spread_val_exit = _simulate_intraday_exit(
            open_price=px_prev,
            close_price=px_today,
            short_strike=short_strike,
            long_strike=long_strike,
            width=width,
            credit=entry_credit,
            tp_pct=params.tp_pct,
            stop_mult=params.stop_mult,
        )
        exit_debit = spread_fill_debit_exit(
            short_put_bid=float(short_row["bid"]),
            short_put_ask=float(short_row["ask"]),
            long_put_bid=float(long_row["bid"]),
            long_put_ask=float(long_row["ask"]),
            fill_mode=params.fill_mode,
            base_pct_of_spread=params.base_pct_of_spread,
        )
        pnl_per_contract = (entry_credit - exit_debit) * SPX_MULTIPLIER - 2 * params.fee_per_contract
        realized = pnl_per_contract * n
        cash += realized
        peak_equity = max(peak_equity, cash)
        if params.daily_max_loss_pct > 0 and realized < -cash * params.daily_max_loss_pct:
            daily_loss_cap_hit = True

        equity_curve.append(cash)
        equity_points.append((day, cash))
        trade_pnls.append(realized)
        daily_pnl_series.append((day, realized))
        closed_trades.append({
            "underlying": underlying,
            "entry_date": day.isoformat(),
            "close_date": day.isoformat(),
            "entry_price": entry_credit,
            "close_price": exit_debit,
            "qty": n,
            "realized_pnl": realized,
            "exit_reason": exit_reason,
            "short_strike": short_strike,
            "long_strike": long_strike,
            "width": width,
            "sub_period": sub_period_key(day),
        })

    metrics = compute_metrics(closed_trades, equity_curve)
    sub_period_metrics = compute_metrics_sub_periods(closed_trades, initial_capital) if closed_trades else {}
    strategy_params = {
        "delta_lo": params.delta_lo,
        "delta_hi": params.delta_hi,
        "width_points": params.width_points,
        "risk_pct": params.risk_pct,
        "tp_pct": params.tp_pct,
        "stop_mult": params.stop_mult,
        "fill_mode": params.fill_mode,
        "event_day_filter": params.event_day_filter,
        "underlying_proxy": params.underlying_proxy,
    }
    return {
        "metrics": metrics,
        "equity_curve": equity_curve,
        "equity_points": equity_points,
        "trade_pnls": trade_pnls,
        "closed_trades": closed_trades,
        "strategy_parameters": strategy_params,
        "daily_pnl_series": daily_pnl_series,
        "sub_period_metrics": sub_period_metrics,
    }


def _empty_result(variant: str, params: Spx0DteParams) -> Dict[str, Any]:
    initial = 100_000.0
    m = compute_metrics([], [initial])
    return {
        "metrics": m,
        "equity_curve": [initial],
        "equity_points": [],
        "trade_pnls": [],
        "closed_trades": [],
        "strategy_parameters": {
            "delta_lo": params.delta_lo,
            "delta_hi": params.delta_hi,
            "width_points": params.width_points,
            "risk_pct": params.risk_pct,
            "tp_pct": params.tp_pct,
            "fill_mode": params.fill_mode,
            "underlying_proxy": params.underlying_proxy,
        },
        "daily_pnl_series": [],
        "sub_period_metrics": {},
    }
