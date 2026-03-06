"""
OpenClaw strategy-family backtest engines.

This module provides three strategy families, each with two assumptions modes:
  - openclaw_stock_options (legacy_replica, realistic_priced)
  - openclaw_put_credit_spread
      (legacy_replica, realistic_priced, pcs_income_plus,
       pcs_balanced_plus, pcs_conservative_turnover)
  - openclaw_tqqq_swing (legacy_replica, realistic_priced)
  - openclaw_hybrid (legacy_replica, realistic_priced)
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ovtlyr.backtester.engine import BacktestEngine
from ovtlyr.backtester.execution_model import summarize_execution_realism
from ovtlyr.backtester.metrics import compute_metrics
from ovtlyr.backtester.position_sizing import cap_symbol_notional, vol_target_contracts
from ovtlyr.backtester.series import (
    compute_drawdown_curve,
    compute_monthly_returns,
    compute_rolling_win_rate,
)
from ovtlyr.strategy.risk_controls import (
    kill_switch_state,
    load_macro_calendar,
    macro_window_block,
)

BASE_ASSUMPTION_MODES = {"legacy_replica", "realistic_priced"}
PUT_CREDIT_SPREAD_MODES = {
    "legacy_replica",
    "realistic_priced",
    "pcs_trend_baseline",
    "pcs_trend_defensive",
    "pcs_income_plus",
    "pcs_balanced_plus",
    "pcs_conservative_turnover",
    "pcs_vix_optimal",
}
CALL_CREDIT_SPREAD_MODES = {
    "ccs_baseline",
    "ccs_vix_regime",
    "ccs_defensive",
}
INTRADAY_MODES = {
    "baseline",
    "conservative",
    "aggressive",
    "oos_hardened",
    "wf_v1_liquidity_guard",
    "wf_v2_flow_strict",
    "wf_v3_regime_strict",
    "wf_v4_validated_candidate",
}

RESEARCH_MONTHLY_MODES = {"baseline", "defensive"}


def _with_execution_defaults(output: EngineOutput) -> EngineOutput:
    """
    Ensure all OpenClaw outputs expose execution-realism keys, even when a
    specific engine does not model microstructure fills in detail yet.
    """
    m = output.metrics
    required = {
        "avg_slippage_bps",
        "spread_cost_pct",
        "fill_rate",
        "partial_fill_rate",
        "slippage_cost_total",
    }
    if required.issubset(set(m.keys())):
        return output

    attempted = len(output.trade_pnls)
    defaults = summarize_execution_realism(
        slippage_bps=[],
        spread_cost_total=0.0,
        slippage_cost_total=0.0,
        filled=attempted,
        partial=0,
        attempted=attempted,
    )
    m.update(defaults)
    return output


@dataclass
class EngineOutput:
    strategy_id: str
    strategy_name: str
    variant: str
    engine_type: str
    assumptions_mode: str
    universe: str
    strategy_parameters: Dict[str, Any]
    metrics: Dict[str, Any]
    equity_curve: List[float]
    equity_points: List[Tuple[date, float]]
    trade_pnls: List[float]
    component_metrics: Optional[Dict[str, Any]] = None
    intraday_report: Optional[List[Dict[str, Any]]] = None
    candidate_count_total: int = 0
    candidate_count_qualified: int = 0
    data_quality_breakdown: Optional[Dict[str, int]] = None
    rejection_counts: Optional[Dict[str, int]] = None
    execution_window: Optional[Dict[str, str]] = None

    @property
    def series(self) -> Dict[str, Any]:
        return {
            "equity_curve": [float(v) for v in self.equity_curve],
            "drawdown_curve": compute_drawdown_curve(self.equity_curve),
            "rolling_win_rate": compute_rolling_win_rate(self.trade_pnls, window=20),
            "monthly_returns": compute_monthly_returns(self.equity_points),
        }


def run_openclaw_variant(
    data: pd.DataFrame,
    config: Dict[str, Any],
    start_date: date,
    end_date: date,
    strategy_id: str,
    assumptions_mode: str,
    universe_symbols: Optional[List[str]] = None,
) -> EngineOutput:
    if strategy_id == "openclaw_stock_options":
        if assumptions_mode not in BASE_ASSUMPTION_MODES:
            raise ValueError(
                f"Unsupported assumptions mode for {strategy_id}: {assumptions_mode}"
            )
        return _with_execution_defaults(
            _run_openclaw_stock_options(data, config, start_date, end_date, assumptions_mode)
        )
    if strategy_id == "openclaw_put_credit_spread":
        if assumptions_mode not in PUT_CREDIT_SPREAD_MODES:
            raise ValueError(
                f"Unsupported assumptions mode for {strategy_id}: {assumptions_mode}"
            )
        return _with_execution_defaults(
            _run_openclaw_put_credit_spread(data, start_date, end_date, assumptions_mode)
        )
    if strategy_id == "openclaw_call_credit_spread":
        if assumptions_mode not in CALL_CREDIT_SPREAD_MODES:
            raise ValueError(
                f"Unsupported assumptions mode for {strategy_id}: {assumptions_mode}"
            )
        return _with_execution_defaults(
            _run_openclaw_call_credit_spread(data, start_date, end_date, assumptions_mode)
        )
    if strategy_id == "openclaw_tqqq_swing":
        if assumptions_mode not in BASE_ASSUMPTION_MODES:
            raise ValueError(
                f"Unsupported assumptions mode for {strategy_id}: {assumptions_mode}"
            )
        return _with_execution_defaults(
            _run_openclaw_tqqq_swing(data, start_date, end_date, assumptions_mode)
        )
    if strategy_id == "openclaw_hybrid":
        if assumptions_mode not in BASE_ASSUMPTION_MODES:
            raise ValueError(
                f"Unsupported assumptions mode for {strategy_id}: {assumptions_mode}"
            )
        return _with_execution_defaults(
            _run_openclaw_hybrid(data, config, start_date, end_date, assumptions_mode)
        )
    if strategy_id == "intraday_open_close_options":
        if assumptions_mode not in INTRADAY_MODES:
            raise ValueError(
                f"Unsupported assumptions mode for {strategy_id}: {assumptions_mode}"
            )
        return _with_execution_defaults(
            _run_intraday_open_close_options(
                data,
                start_date,
                end_date,
                assumptions_mode,
                universe_symbols=universe_symbols,
                config=config,
            )
        )
    if strategy_id == "research_buywrite_spy":
        if assumptions_mode not in RESEARCH_MONTHLY_MODES:
            raise ValueError(
                f"Unsupported assumptions mode for {strategy_id}: {assumptions_mode}"
            )
        return _with_execution_defaults(
            _run_research_buywrite_spy(data, start_date, end_date, assumptions_mode)
        )
    if strategy_id == "research_putwrite_spy":
        if assumptions_mode not in RESEARCH_MONTHLY_MODES:
            raise ValueError(
                f"Unsupported assumptions mode for {strategy_id}: {assumptions_mode}"
            )
        return _with_execution_defaults(
            _run_research_putwrite_spy(data, start_date, end_date, assumptions_mode)
        )
    if strategy_id == "research_collar_spy":
        if assumptions_mode not in RESEARCH_MONTHLY_MODES:
            raise ValueError(
                f"Unsupported assumptions mode for {strategy_id}: {assumptions_mode}"
            )
        return _with_execution_defaults(
            _run_research_collar_spy(data, start_date, end_date, assumptions_mode)
        )

    raise ValueError(f"Unsupported OpenClaw strategy_id: {strategy_id}")


def _run_openclaw_stock_options(
    data: pd.DataFrame,
    config: Dict[str, Any],
    start_date: date,
    end_date: date,
    assumptions_mode: str,
) -> EngineOutput:
    cfg = copy.deepcopy(config)
    strat = cfg.setdefault("strategy", {})
    exe = cfg.setdefault("execution", {})
    exe["max_positions"] = 10
    exe["contracts_per_trade"] = 1
    # OpenClaw stock-options engine has its own regime filtering; disable the
    # stock-replacement trend gate so settings.yaml doesn't bleed through.
    strat["require_symbol_bullish_trend"] = False
    strat["sit_in_cash_when_bearish"] = False

    if assumptions_mode == "legacy_replica":
        strat.update(
            {
                "target_delta": 0.85,
                "delta_tolerance": 0.10,
                "min_delta": 0.65,
                "max_extrinsic_pct": 0.35,
                "max_spread_pct": 0.12,
                "min_dte": 20,
                "max_dte": 75,
            }
        )
    else:
        strat.update(
            {
                "target_delta": 0.82,
                "delta_tolerance": 0.08,
                "min_delta": 0.68,
                "max_extrinsic_pct": 0.25,
                "max_spread_pct": 0.08,
                "min_dte": 25,
                "max_dte": 60,
            }
        )

    engine = BacktestEngine(data, cfg)
    metrics = engine.run(start_date, end_date)

    trading_days = _trading_days(data, start_date, end_date)
    equity_curve = [float(v) for v in engine.equity_curve]
    equity_points = _equity_points_from_curve(trading_days, equity_curve)
    trades = _closed_trade_pnls(engine.closed_trades)

    if assumptions_mode == "realistic_priced":
        metrics, equity_curve, trades = _apply_realistic_pricing_overlay(
            metrics=metrics,
            equity_curve=equity_curve,
            trade_pnls=trades,
        )
        equity_points = _equity_points_from_curve(trading_days, equity_curve)

    return EngineOutput(
        strategy_id="openclaw_stock_options",
        strategy_name="OpenClaw Stock Options",
        variant=assumptions_mode,
        engine_type="openclaw_stock_options_engine",
        assumptions_mode=assumptions_mode,
        universe="AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,SPY,QQQ,AMD",
        strategy_parameters={
            "target_delta": strat.get("target_delta"),
            "delta_tolerance": strat.get("delta_tolerance"),
            "min_delta": strat.get("min_delta"),
            "max_extrinsic_pct": strat.get("max_extrinsic_pct"),
            "max_spread_pct": strat.get("max_spread_pct"),
            "min_dte": strat.get("min_dte"),
            "max_dte": strat.get("max_dte"),
            "max_positions": exe.get("max_positions"),
        },
        metrics=metrics,
        equity_curve=equity_curve,
        equity_points=equity_points,
        trade_pnls=trades,
    )


def _run_openclaw_put_credit_spread(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    assumptions_mode: str,
) -> EngineOutput:
    prices = _build_underlying_close_frame(data, start_date, end_date, symbols=["SPY", "QQQ"])
    if prices.empty:
        raise ValueError("No SPY/QQQ data available for openclaw_put_credit_spread")

    params = _put_credit_params(assumptions_mode)
    risk_pct = params["risk_pct"]
    short_dist_pct = params["short_dist_pct"]
    width_pct = params["width_pct"]
    credit_ratio = params["credit_ratio"]
    dte_days = int(params["dte_days"])
    take_profit_ratio = params["take_profit_ratio"]
    stop_mult = params["stop_mult"]
    min_hold_days = int(params["min_hold_days"])
    force_close_dte = int(params["force_close_dte"])
    iv_low = params["iv_low"]
    iv_high = params["iv_high"]
    fee_per_contract = params["fee_per_contract"]
    max_qty = int(params["max_qty"])
    target_annual_vol = float(params.get("target_annual_vol", 0.18))
    max_symbol_notional_pct = float(params.get("max_symbol_notional_pct", 0.20))
    # VIX proxy gate (optional — only active when vix_gate_enabled is set in params)
    pcs_vix_gate = bool(params.get("vix_gate_enabled", False))
    pcs_vix_min = float(params.get("vix_min_threshold", 0.0))
    pcs_vix_max = float(params.get("vix_max_threshold", 999.0))

    returns = prices.pct_change()
    hv20 = returns.rolling(20).std() * (252 ** 0.5)
    ma20 = prices.rolling(20).mean()
    ma50 = prices.rolling(50).mean()
    ma200 = prices.rolling(200).mean()

    initial_capital = 100_000.0
    cash = initial_capital
    open_positions: List[Dict[str, Any]] = []
    trades: List[Dict[str, Any]] = []
    equity_curve: List[float] = [initial_capital]
    equity_points: List[Tuple[date, float]] = []
    macro_events = load_macro_calendar("config/macro_calendar.yaml")
    kill_state: Dict[str, Any] = {}
    macro_block_days = 0
    kill_block_days = 0

    all_days = list(prices.index)
    for day in all_days:
        day_prices = prices.loc[day]
        macro_blocked = macro_window_block(day.date() if hasattr(day, "date") else day, macro_events, 6)
        if macro_blocked:
            macro_block_days += 1

        realized_today = 0.0
        current_unrealized = 0.0
        remaining_positions: List[Dict[str, Any]] = []

        for pos in open_positions:
            px = float(day_prices[pos["symbol"]])
            held_days = (day - pos["entry_date"]).days
            dte_left = (pos["expiry_date"] - day).days
            intrinsic = max(pos["short_strike"] - px, 0.0) - max(pos["long_strike"] - px, 0.0)
            intrinsic = min(max(intrinsic, 0.0), pos["width"])
            hv_today = float(hv20.loc[day, pos["symbol"]]) if pd.notna(hv20.loc[day, pos["symbol"]]) else pos["entry_hv"]
            vol_ratio = (hv_today / pos["entry_hv"]) if pos["entry_hv"] > 0 else 1.0
            adverse_move = ((px - pos["entry_underlying"]) / pos["entry_underlying"]) if pos["entry_underlying"] > 0 else 0.0

            time_ratio = max(min(dte_left / max(pos["dte_days"], 1), 1.0), 0.0)
            if px >= pos["short_strike"]:
                spread_value = pos["credit"] * (0.5 * time_ratio)
            elif px <= pos["long_strike"]:
                spread_value = pos["width"] - (pos["credit"] * 0.1 * time_ratio)
            else:
                spread_value = intrinsic + (pos["credit"] * 0.4 * time_ratio)
            vol_penalty = max(vol_ratio - 1.0, 0.0) * 0.25 * pos["width"]
            adverse_penalty = max((-adverse_move) - (short_dist_pct * 0.5), 0.0) * 3.0 * pos["width"]
            spread_value += (vol_penalty + adverse_penalty)
            spread_value = min(max(spread_value, 0.0), pos["width"])

            pnl_per_contract = (pos["credit"] - spread_value) * 100.0
            unrealized = pnl_per_contract * pos["qty"]
            current_unrealized += unrealized

            take_profit_hit = pnl_per_contract >= (pos["credit"] * 100.0 * pos["take_profit_ratio"])
            stop_hit = spread_value >= max((pos["credit"] * pos["stop_mult"]), (pos["width"] * 0.55))
            breach = px <= pos["long_strike"]
            time_exit = dte_left <= pos["force_close_dte"]
            expiry_exit = day >= pos["expiry_date"]

            should_close = False
            reason = "hold"
            if take_profit_hit and held_days >= pos["min_hold_days"]:
                should_close = True
                reason = "take_profit"
            elif stop_hit:
                should_close = True
                reason = "stop_loss"
            elif breach:
                should_close = True
                reason = "long_strike_breach"
            elif time_exit:
                should_close = True
                reason = "time_exit"
            elif expiry_exit:
                should_close = True
                reason = "expiry"

            if should_close:
                fees = fee_per_contract * pos["qty"]
                realized = unrealized - fees
                realized_today += realized
                trades.append(
                    {
                        "underlying": pos["symbol"],
                        "entry_date": pos["entry_date"].isoformat(),
                        "close_date": day.isoformat(),
                        "entry_price": pos["credit"],
                        "close_price": spread_value,
                        "qty": pos["qty"],
                        "realized_pnl": round(realized, 4),
                        "close_reason": reason,
                    }
                )
            else:
                remaining_positions.append(pos)

        open_positions = remaining_positions
        cash += realized_today
        kill_state = kill_switch_state(
            recent_trades=trades,
            lookback_trades=30,
            expectancy_floor_r=-0.15,
            cooldown_days=5,
            today=day.date() if hasattr(day, "date") else day,
            existing_state=kill_state,
        )
        if kill_state.get("active"):
            kill_block_days += 1

        for symbol in ["SPY", "QQQ"]:
            if macro_blocked or kill_state.get("active"):
                continue
            if symbol in [p["symbol"] for p in open_positions]:
                continue

            px = float(day_prices[symbol])
            if not (pd.notna(px) and px > 0):
                continue
            if pd.isna(ma200.loc[day, symbol]) or pd.isna(ma50.loc[day, symbol]) or pd.isna(ma20.loc[day, symbol]):
                continue
            if pd.isna(hv20.loc[day, symbol]):
                continue

            bullish_regime = (px > float(ma200.loc[day, symbol])) and (float(ma20.loc[day, symbol]) > float(ma50.loc[day, symbol]))
            iv_proxy = float(hv20.loc[day, symbol])
            iv_regime_ok = iv_low <= iv_proxy <= iv_high
            if not (bullish_regime and iv_regime_ok):
                continue

            # VIX proxy gate (pcs_vix_optimal variant): use SPY HV20 as VIX proxy
            if pcs_vix_gate:
                spy_hv = float(hv20.loc[day, "SPY"]) if "SPY" in hv20.columns and pd.notna(hv20.loc[day, "SPY"]) else iv_proxy
                if spy_hv < pcs_vix_min or spy_hv > pcs_vix_max:
                    continue

            short_strike = round(px * (1.0 - short_dist_pct), 2)
            width = round(max(px * width_pct, 1.0), 2)
            long_strike = round(short_strike - width, 2)
            credit = round(width * credit_ratio, 2)

            max_loss_per_contract = max((width - credit) * 100.0, 1.0)
            qty_risk = int((cash * risk_pct) // max_loss_per_contract)
            qty_vol = vol_target_contracts(
                equity=cash,
                option_price=max(credit, 0.25),
                underlying_annual_vol=max(iv_proxy, 0.05),
                target_annual_vol=target_annual_vol,
                max_contracts=max_qty,
            )
            qty = max(1, min(qty_risk, qty_vol, max_qty))
            qty = cap_symbol_notional(
                contracts=qty,
                option_price=max(short_strike, px),
                equity=cash,
                max_symbol_notional_pct=max_symbol_notional_pct,
            )
            qty = max(1, min(qty, max_qty))

            open_positions.append(
                {
                    "symbol": symbol,
                    "entry_date": day,
                    "expiry_date": day + timedelta(days=dte_days),
                    "dte_days": dte_days,
                    "short_strike": short_strike,
                    "long_strike": long_strike,
                    "width": width,
                    "credit": credit,
                    "qty": qty,
                    "take_profit_ratio": take_profit_ratio,
                    "stop_mult": stop_mult,
                    "min_hold_days": min_hold_days,
                    "force_close_dte": force_close_dte,
                    "entry_underlying": px,
                    "entry_hv": iv_proxy,
                }
            )

        end_unrealized = 0.0
        for pos in open_positions:
            px = float(day_prices[pos["symbol"]])
            intrinsic = max(pos["short_strike"] - px, 0.0) - max(pos["long_strike"] - px, 0.0)
            intrinsic = min(max(intrinsic, 0.0), pos["width"])
            dte_left = (pos["expiry_date"] - day).days
            time_ratio = max(min(dte_left / max(pos["dte_days"], 1), 1.0), 0.0)
            hv_today = float(hv20.loc[day, pos["symbol"]]) if pd.notna(hv20.loc[day, pos["symbol"]]) else pos["entry_hv"]
            vol_ratio = (hv_today / pos["entry_hv"]) if pos["entry_hv"] > 0 else 1.0
            adverse_move = ((px - pos["entry_underlying"]) / pos["entry_underlying"]) if pos["entry_underlying"] > 0 else 0.0
            spread_value = intrinsic + (pos["credit"] * 0.3 * time_ratio)
            spread_value += max(vol_ratio - 1.0, 0.0) * 0.20 * pos["width"]
            spread_value += max((-adverse_move) - (short_dist_pct * 0.5), 0.0) * 2.5 * pos["width"]
            spread_value = min(max(spread_value, 0.0), pos["width"])
            pnl_per_contract = (pos["credit"] - spread_value) * 100.0
            end_unrealized += pnl_per_contract * pos["qty"]

        equity = cash + end_unrealized
        equity_curve.append(float(equity))
        equity_points.append((day, float(equity)))

    if open_positions:
        last_day = all_days[-1]
        day_prices = prices.loc[last_day]
        realized_tail = 0.0
        for pos in open_positions:
            px = float(day_prices[pos["symbol"]])
            if px >= pos["short_strike"]:
                spread_value = 0.0
            elif px <= pos["long_strike"]:
                spread_value = pos["width"]
            else:
                spread_value = pos["short_strike"] - px
            pnl_per_contract = (pos["credit"] - spread_value) * 100.0
            realized = (pnl_per_contract * pos["qty"]) - (fee_per_contract * pos["qty"])
            realized_tail += realized
            trades.append(
                {
                    "underlying": pos["symbol"],
                    "entry_date": pos["entry_date"].isoformat(),
                    "close_date": last_day.isoformat(),
                    "entry_price": pos["credit"],
                    "close_price": spread_value,
                    "qty": pos["qty"],
                    "realized_pnl": round(realized, 4),
                    "close_reason": "period_end",
                }
            )
        cash += realized_tail
        if equity_curve:
            equity_curve[-1] = float(cash)
            if equity_points:
                equity_points[-1] = (equity_points[-1][0], float(cash))

    metrics = compute_metrics(trades, equity_curve)
    metrics["rolls_executed"] = 0
    metrics["trading_days"] = len(prices.index)
    metrics["macro_block_days"] = macro_block_days
    metrics["kill_switch_block_days"] = kill_block_days
    metrics["kill_switch_active"] = bool(kill_state.get("active"))
    metrics["kill_switch_expectancy_r"] = float(kill_state.get("expectancy_r", 0.0))
    trade_pnls = [float(t.get("realized_pnl", 0.0)) for t in trades]

    return EngineOutput(
        strategy_id="openclaw_put_credit_spread",
        strategy_name="OpenClaw Put Credit Spread",
        variant=assumptions_mode,
        engine_type="openclaw_put_credit_spread_engine",
        assumptions_mode=assumptions_mode,
        universe="SPY,QQQ",
        strategy_parameters={
            "variant_profile": assumptions_mode,
            "risk_pct": risk_pct,
            "short_dist_pct": short_dist_pct,
            "width_pct": width_pct,
            "credit_ratio": credit_ratio,
            "dte_days": dte_days,
            "take_profit_ratio": take_profit_ratio,
            "stop_mult": stop_mult,
            "force_close_dte": force_close_dte,
            "iv_low": iv_low,
            "iv_high": iv_high,
            "fee_per_contract": fee_per_contract,
            "target_annual_vol": target_annual_vol,
            "max_symbol_notional_pct": max_symbol_notional_pct,
        },
        metrics=metrics,
        equity_curve=[float(v) for v in equity_curve],
        equity_points=equity_points,
        trade_pnls=trade_pnls,
    )


def _put_credit_params(mode: str) -> Dict[str, Any]:
    profiles: Dict[str, Dict[str, Any]] = {
        "legacy_replica": {
            "risk_pct": 0.015,
            "short_dist_pct": 0.045,
            "width_pct": 0.050,
            "credit_ratio": 0.33,
            "dte_days": 35.0,
            "take_profit_ratio": 0.50,
            "stop_mult": 2.20,
            "min_hold_days": 3.0,
            "force_close_dte": 10.0,
            "iv_low": 0.12,
            "iv_high": 0.90,
            "fee_per_contract": 2.0,
            "max_qty": 3.0,
        },
        "realistic_priced": {
            "risk_pct": 0.010,
            "short_dist_pct": 0.060,
            "width_pct": 0.060,
            "credit_ratio": 0.26,
            "dte_days": 35.0,
            "take_profit_ratio": 0.50,
            "stop_mult": 2.00,
            "min_hold_days": 3.0,
            "force_close_dte": 10.0,
            "iv_low": 0.18,
            "iv_high": 0.55,
            "fee_per_contract": 4.0,
            "max_qty": 2.0,
            "target_annual_vol": 0.16,
            "max_symbol_notional_pct": 0.20,
        },
        "pcs_trend_baseline": {
            "risk_pct": 0.012,
            "short_dist_pct": 0.055,
            "width_pct": 0.055,
            "credit_ratio": 0.29,
            "dte_days": 35.0,
            "take_profit_ratio": 0.50,
            "stop_mult": 2.00,
            "min_hold_days": 3.0,
            "force_close_dte": 10.0,
            "iv_low": 0.14,
            "iv_high": 0.60,
            "fee_per_contract": 3.0,
            "max_qty": 3.0,
            "target_annual_vol": 0.18,
            "max_symbol_notional_pct": 0.20,
        },
        "pcs_trend_defensive": {
            "risk_pct": 0.009,
            "short_dist_pct": 0.065,
            "width_pct": 0.060,
            "credit_ratio": 0.25,
            "dte_days": 35.0,
            "take_profit_ratio": 0.45,
            "stop_mult": 1.90,
            "min_hold_days": 3.0,
            "force_close_dte": 12.0,
            "iv_low": 0.16,
            "iv_high": 0.50,
            "fee_per_contract": 4.0,
            "max_qty": 2.0,
            "target_annual_vol": 0.14,
            "max_symbol_notional_pct": 0.16,
        },
        # Higher turnover with slightly better premium and more opportunity flow.
        "pcs_income_plus": {
            "risk_pct": 0.0125,
            "short_dist_pct": 0.060,
            "width_pct": 0.060,
            "credit_ratio": 0.28,
            "dte_days": 35.0,
            "take_profit_ratio": 0.40,
            "stop_mult": 2.00,
            "min_hold_days": 3.0,
            "force_close_dte": 10.0,
            "iv_low": 0.18,
            "iv_high": 0.65,
            "fee_per_contract": 4.0,
            "max_qty": 3.0,
        },
        # More aggressive sizing and premium target with slightly tighter loss guard.
        "pcs_balanced_plus": {
            "risk_pct": 0.015,
            "short_dist_pct": 0.060,
            "width_pct": 0.060,
            "credit_ratio": 0.30,
            "dte_days": 35.0,
            "take_profit_ratio": 0.40,
            "stop_mult": 1.90,
            "min_hold_days": 3.0,
            "force_close_dte": 10.0,
            "iv_low": 0.18,
            "iv_high": 0.65,
            "fee_per_contract": 4.0,
            "max_qty": 3.0,
        },
        # Keep sizing conservative but harvest winners faster and de-risk earlier.
        "pcs_conservative_turnover": {
            "risk_pct": 0.010,
            "short_dist_pct": 0.060,
            "width_pct": 0.060,
            "credit_ratio": 0.26,
            "dte_days": 35.0,
            "take_profit_ratio": 0.35,
            "stop_mult": 2.00,
            "min_hold_days": 3.0,
            "force_close_dte": 14.0,
            "iv_low": 0.18,
            "iv_high": 0.55,
            "fee_per_contract": 4.0,
            "max_qty": 2.0,
        },
        # Legacy params + HV30 gate: require moderate volatility (10-40%) for healthy premium
        "pcs_vix_optimal": {
            "risk_pct": 0.015,
            "short_dist_pct": 0.045,
            "width_pct": 0.050,
            "credit_ratio": 0.33,
            "dte_days": 35.0,
            "take_profit_ratio": 0.50,
            "stop_mult": 2.20,
            "min_hold_days": 3.0,
            "force_close_dte": 10.0,
            "iv_low": 0.12,
            "iv_high": 0.90,
            "fee_per_contract": 2.0,
            "max_qty": 3.0,
            # VIX proxy gate: avoid entries when HV30 < 10% (too calm) or > 40% (panic)
            "vix_gate_enabled": True,
            "vix_min_threshold": 0.10,
            "vix_max_threshold": 0.40,
        },
    }
    if mode not in profiles:
        raise ValueError(f"Unsupported put-credit-spread mode: {mode}")
    return profiles[mode]


def _call_credit_params(mode: str) -> Dict[str, Any]:
    """Parameters for call credit spread variants."""
    profiles: Dict[str, Dict[str, Any]] = {
        # Baseline: sell 4.5% OTM call, buy 5% OTM call above that — neutral/bearish regime
        "ccs_baseline": {
            "risk_pct": 0.012,
            "short_dist_pct": 0.045,  # short call 4.5% OTM above spot
            "width_pct": 0.050,       # long call 5% further OTM
            "credit_ratio": 0.33,     # collect ~33% of width
            "dte_days": 35.0,
            "take_profit_ratio": 0.50,
            "stop_mult": 2.20,
            "min_hold_days": 3.0,
            "force_close_dte": 10.0,
            "iv_low": 0.14,
            "iv_high": 0.60,
            "fee_per_contract": 3.0,
            "max_qty": 3.0,
            "target_annual_vol": 0.18,
            "max_symbol_notional_pct": 0.20,
        },
        # VIX regime: only enter when vol elevated (expensive calls = better premium)
        "ccs_vix_regime": {
            "risk_pct": 0.012,
            "short_dist_pct": 0.045,
            "width_pct": 0.050,
            "credit_ratio": 0.33,
            "dte_days": 35.0,
            "take_profit_ratio": 0.50,
            "stop_mult": 2.20,
            "min_hold_days": 3.0,
            "force_close_dte": 10.0,
            "iv_low": 0.18,  # require elevated vol (HV20 > 18%)
            "iv_high": 0.60,
            "fee_per_contract": 3.0,
            "max_qty": 3.0,
            "target_annual_vol": 0.18,
            "max_symbol_notional_pct": 0.20,
        },
        # Defensive: 6% OTM short strike, lower delta, tighter sizing
        "ccs_defensive": {
            "risk_pct": 0.009,
            "short_dist_pct": 0.060,  # short call 6% OTM — lower delta
            "width_pct": 0.050,
            "credit_ratio": 0.28,
            "dte_days": 35.0,
            "take_profit_ratio": 0.45,
            "stop_mult": 2.00,
            "min_hold_days": 3.0,
            "force_close_dte": 12.0,
            "iv_low": 0.16,
            "iv_high": 0.55,
            "fee_per_contract": 4.0,
            "max_qty": 2.0,
            "target_annual_vol": 0.14,
            "max_symbol_notional_pct": 0.16,
        },
    }
    if mode not in profiles:
        raise ValueError(f"Unsupported call-credit-spread mode: {mode}")
    return profiles[mode]


def _run_openclaw_call_credit_spread(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    assumptions_mode: str,
) -> EngineOutput:
    """
    Call Credit Spread (CCS) engine — bearish/neutral mirror of PCS.

    Sell OTM call (above spot) + buy further OTM call as cap.
    Collect premium when underlying stays below short strike.
    """
    prices = _build_underlying_close_frame(data, start_date, end_date, symbols=["SPY", "QQQ"])
    if prices.empty:
        raise ValueError("No SPY/QQQ data available for openclaw_call_credit_spread")

    params = _call_credit_params(assumptions_mode)
    risk_pct = params["risk_pct"]
    short_dist_pct = params["short_dist_pct"]
    width_pct = params["width_pct"]
    credit_ratio = params["credit_ratio"]
    dte_days = int(params["dte_days"])
    take_profit_ratio = params["take_profit_ratio"]
    stop_mult = params["stop_mult"]
    min_hold_days = int(params["min_hold_days"])
    force_close_dte = int(params["force_close_dte"])
    iv_low = params["iv_low"]
    iv_high = params["iv_high"]
    fee_per_contract = params["fee_per_contract"]
    max_qty = int(params["max_qty"])
    target_annual_vol = float(params.get("target_annual_vol", 0.18))
    max_symbol_notional_pct = float(params.get("max_symbol_notional_pct", 0.20))

    returns = prices.pct_change()
    hv20 = returns.rolling(20).std() * (252 ** 0.5)
    ma20 = prices.rolling(20).mean()
    ma50 = prices.rolling(50).mean()
    ma200 = prices.rolling(200).mean()

    initial_capital = 100_000.0
    cash = initial_capital
    open_positions: List[Dict[str, Any]] = []
    trades: List[Dict[str, Any]] = []
    equity_curve: List[float] = [initial_capital]
    equity_points: List[Tuple[date, float]] = []
    macro_events = load_macro_calendar("config/macro_calendar.yaml")
    kill_state: Dict[str, Any] = {}
    macro_block_days = 0
    kill_block_days = 0

    all_days = list(prices.index)
    for day in all_days:
        day_prices = prices.loc[day]
        macro_blocked = macro_window_block(day.date() if hasattr(day, "date") else day, macro_events, 6)
        if macro_blocked:
            macro_block_days += 1

        realized_today = 0.0
        current_unrealized = 0.0
        remaining_positions: List[Dict[str, Any]] = []

        for pos in open_positions:
            px = float(day_prices[pos["symbol"]])
            held_days = (day - pos["entry_date"]).days
            dte_left = (pos["expiry_date"] - day).days

            # Call spread intrinsic: max(px - short_strike, 0) - max(px - long_strike, 0)
            intrinsic = max(px - pos["short_strike"], 0.0) - max(px - pos["long_strike"], 0.0)
            intrinsic = min(max(intrinsic, 0.0), pos["width"])

            hv_today = float(hv20.loc[day, pos["symbol"]]) if pd.notna(hv20.loc[day, pos["symbol"]]) else pos["entry_hv"]
            vol_ratio = (hv_today / pos["entry_hv"]) if pos["entry_hv"] > 0 else 1.0
            # Adverse move for CCS = stock going UP (calls going against us)
            adverse_move = ((px - pos["entry_underlying"]) / pos["entry_underlying"]) if pos["entry_underlying"] > 0 else 0.0

            time_ratio = max(min(dte_left / max(pos["dte_days"], 1), 1.0), 0.0)
            if px <= pos["short_strike"]:
                spread_value = pos["credit"] * (0.5 * time_ratio)
            elif px >= pos["long_strike"]:
                spread_value = pos["width"] - (pos["credit"] * 0.1 * time_ratio)
            else:
                spread_value = intrinsic + (pos["credit"] * 0.4 * time_ratio)
            vol_penalty = max(vol_ratio - 1.0, 0.0) * 0.25 * pos["width"]
            # For CCS, adverse move is upward (positive adverse_move)
            adverse_penalty = max(adverse_move - (short_dist_pct * 0.5), 0.0) * 3.0 * pos["width"]
            spread_value += (vol_penalty + adverse_penalty)
            spread_value = min(max(spread_value, 0.0), pos["width"])

            pnl_per_contract = (pos["credit"] - spread_value) * 100.0
            unrealized = pnl_per_contract * pos["qty"]
            current_unrealized += unrealized

            take_profit_hit = pnl_per_contract >= (pos["credit"] * 100.0 * pos["take_profit_ratio"])
            stop_hit = spread_value >= max((pos["credit"] * pos["stop_mult"]), (pos["width"] * 0.55))
            breach = px >= pos["long_strike"]  # CCS: breached when stock goes above long strike
            time_exit = dte_left <= pos["force_close_dte"]
            expiry_exit = day >= pos["expiry_date"]

            should_close = False
            reason = "hold"
            if take_profit_hit and held_days >= pos["min_hold_days"]:
                should_close = True
                reason = "take_profit"
            elif stop_hit:
                should_close = True
                reason = "stop_loss"
            elif breach:
                should_close = True
                reason = "long_strike_breach"
            elif time_exit:
                should_close = True
                reason = "time_exit"
            elif expiry_exit:
                should_close = True
                reason = "expiry"

            if should_close:
                fees = fee_per_contract * pos["qty"]
                realized = unrealized - fees
                realized_today += realized
                trades.append(
                    {
                        "underlying": pos["symbol"],
                        "entry_date": pos["entry_date"].isoformat(),
                        "close_date": day.isoformat(),
                        "entry_price": pos["credit"],
                        "close_price": spread_value,
                        "qty": pos["qty"],
                        "realized_pnl": round(realized, 4),
                        "close_reason": reason,
                    }
                )
            else:
                remaining_positions.append(pos)

        open_positions = remaining_positions
        cash += realized_today
        kill_state = kill_switch_state(
            recent_trades=trades,
            lookback_trades=30,
            expectancy_floor_r=-0.15,
            cooldown_days=5,
            today=day.date() if hasattr(day, "date") else day,
            existing_state=kill_state,
        )
        if kill_state.get("active"):
            kill_block_days += 1

        for symbol in ["SPY", "QQQ"]:
            if macro_blocked or kill_state.get("active"):
                continue
            if symbol in [p["symbol"] for p in open_positions]:
                continue

            px = float(day_prices[symbol])
            if not (pd.notna(px) and px > 0):
                continue
            if pd.isna(ma200.loc[day, symbol]) or pd.isna(ma50.loc[day, symbol]) or pd.isna(ma20.loc[day, symbol]):
                continue
            if pd.isna(hv20.loc[day, symbol]):
                continue

            # CCS regime: do NOT require bullish trend — we're bearish/neutral
            # Enter when: IV is in range (calls are priced reasonably)
            # Avoid entering in strongly bullish trending markets (would crush short calls)
            iv_proxy = float(hv20.loc[day, symbol])
            iv_regime_ok = iv_low <= iv_proxy <= iv_high
            if not iv_regime_ok:
                continue

            # CCS: avoid entering if market is in a strong bullish rally
            # (price far above MA50 = momentum against us)
            ma50_val = float(ma50.loc[day, symbol])
            if pd.notna(ma50_val) and ma50_val > 0:
                pct_above_ma50 = (px - ma50_val) / ma50_val
                if pct_above_ma50 > 0.08:  # >8% above MA50 = overbought momentum, skip
                    continue

            # CCS strikes: short call ABOVE spot, long call further above
            short_strike = round(px * (1.0 + short_dist_pct), 2)
            width = round(max(px * width_pct, 1.0), 2)
            long_strike = round(short_strike + width, 2)
            credit = round(width * credit_ratio, 2)

            max_loss_per_contract = max((width - credit) * 100.0, 1.0)
            qty_risk = int((cash * risk_pct) // max_loss_per_contract)
            qty_vol = vol_target_contracts(
                equity=cash,
                option_price=max(credit, 0.25),
                underlying_annual_vol=max(iv_proxy, 0.05),
                target_annual_vol=target_annual_vol,
                max_contracts=max_qty,
            )
            qty = max(1, min(qty_risk, qty_vol, max_qty))
            qty = cap_symbol_notional(
                contracts=qty,
                option_price=max(short_strike, px),
                equity=cash,
                max_symbol_notional_pct=max_symbol_notional_pct,
            )
            qty = max(1, min(qty, max_qty))

            open_positions.append(
                {
                    "symbol": symbol,
                    "entry_date": day,
                    "expiry_date": day + timedelta(days=dte_days),
                    "dte_days": dte_days,
                    "short_strike": short_strike,
                    "long_strike": long_strike,
                    "width": width,
                    "credit": credit,
                    "qty": qty,
                    "take_profit_ratio": take_profit_ratio,
                    "stop_mult": stop_mult,
                    "min_hold_days": min_hold_days,
                    "force_close_dte": force_close_dte,
                    "entry_underlying": px,
                    "entry_hv": iv_proxy,
                }
            )

        end_unrealized = 0.0
        for pos in open_positions:
            px = float(day_prices[pos["symbol"]])
            intrinsic = max(px - pos["short_strike"], 0.0) - max(px - pos["long_strike"], 0.0)
            intrinsic = min(max(intrinsic, 0.0), pos["width"])
            dte_left = (pos["expiry_date"] - day).days
            time_ratio = max(min(dte_left / max(pos["dte_days"], 1), 1.0), 0.0)
            hv_today = float(hv20.loc[day, pos["symbol"]]) if pd.notna(hv20.loc[day, pos["symbol"]]) else pos["entry_hv"]
            vol_ratio = (hv_today / pos["entry_hv"]) if pos["entry_hv"] > 0 else 1.0
            adverse_move = ((px - pos["entry_underlying"]) / pos["entry_underlying"]) if pos["entry_underlying"] > 0 else 0.0
            spread_value = intrinsic + (pos["credit"] * 0.3 * time_ratio)
            spread_value += max(vol_ratio - 1.0, 0.0) * 0.20 * pos["width"]
            spread_value += max(adverse_move - (short_dist_pct * 0.5), 0.0) * 2.5 * pos["width"]
            spread_value = min(max(spread_value, 0.0), pos["width"])
            pnl_per_contract = (pos["credit"] - spread_value) * 100.0
            end_unrealized += pnl_per_contract * pos["qty"]

        equity = cash + end_unrealized
        equity_curve.append(float(equity))
        equity_points.append((day, float(equity)))

    if open_positions:
        last_day = all_days[-1]
        day_prices = prices.loc[last_day]
        realized_tail = 0.0
        for pos in open_positions:
            px = float(day_prices[pos["symbol"]])
            if px <= pos["short_strike"]:
                spread_value = 0.0
            elif px >= pos["long_strike"]:
                spread_value = pos["width"]
            else:
                spread_value = px - pos["short_strike"]
            pnl_per_contract = (pos["credit"] - spread_value) * 100.0
            realized = (pnl_per_contract * pos["qty"]) - (fee_per_contract * pos["qty"])
            realized_tail += realized
            trades.append(
                {
                    "underlying": pos["symbol"],
                    "entry_date": pos["entry_date"].isoformat(),
                    "close_date": last_day.isoformat(),
                    "entry_price": pos["credit"],
                    "close_price": spread_value,
                    "qty": pos["qty"],
                    "realized_pnl": round(realized, 4),
                    "close_reason": "period_end",
                }
            )
        cash += realized_tail
        if equity_curve:
            equity_curve[-1] = float(cash)
            if equity_points:
                equity_points[-1] = (equity_points[-1][0], float(cash))

    metrics = compute_metrics(trades, equity_curve)
    metrics["rolls_executed"] = 0
    metrics["trading_days"] = len(prices.index)
    metrics["macro_block_days"] = macro_block_days
    metrics["kill_switch_block_days"] = kill_block_days
    metrics["kill_switch_active"] = bool(kill_state.get("active"))
    metrics["kill_switch_expectancy_r"] = float(kill_state.get("expectancy_r", 0.0))
    trade_pnls = [float(t.get("realized_pnl", 0.0)) for t in trades]

    return EngineOutput(
        strategy_id="openclaw_call_credit_spread",
        strategy_name="OpenClaw Call Credit Spread",
        variant=assumptions_mode,
        engine_type="openclaw_call_credit_spread_engine",
        assumptions_mode=assumptions_mode,
        universe="SPY,QQQ",
        strategy_parameters={
            "variant_profile": assumptions_mode,
            "risk_pct": risk_pct,
            "short_dist_pct": short_dist_pct,
            "width_pct": width_pct,
            "credit_ratio": credit_ratio,
            "dte_days": dte_days,
            "take_profit_ratio": take_profit_ratio,
            "stop_mult": stop_mult,
            "force_close_dte": force_close_dte,
            "iv_low": iv_low,
            "iv_high": iv_high,
            "fee_per_contract": fee_per_contract,
            "target_annual_vol": target_annual_vol,
            "max_symbol_notional_pct": max_symbol_notional_pct,
        },
        metrics=metrics,
        equity_curve=[float(v) for v in equity_curve],
        equity_points=equity_points,
        trade_pnls=trade_pnls,
    )


def _run_openclaw_tqqq_swing(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    assumptions_mode: str,
) -> EngineOutput:
    df = _build_tqqq_price_frame(data, start_date, end_date)
    if df.empty:
        raise ValueError("No TQQQ/QQQ data available for openclaw_tqqq_swing")

    legacy = assumptions_mode == "legacy_replica"

    pullback_low = -15.0
    pullback_high = -8.0 if legacy else -10.0
    ma_tolerance = 0.03 if legacy else 0.02
    allocation = 0.25 if legacy else 0.20
    fee_rate = 0.0008 if legacy else 0.0015
    stop_loss = -12.0 if legacy else -10.0
    profit_target = 30.0 if legacy else 25.0

    close = df["close"]
    ma10 = close.rolling(10).mean()
    ma21 = close.rolling(21).mean()
    ma50 = close.rolling(50).mean()
    high20 = close.rolling(20).max().shift(1)
    high252 = close.rolling(252).max().shift(1)
    abs_ret = close.pct_change().abs().fillna(0.0)
    dist_day = (close < close.shift(1)) & (abs_ret > abs_ret.shift(1))
    dist_count = dist_day.rolling(25).sum().fillna(0.0)

    initial_capital = 100_000.0
    cash = initial_capital
    units = 0.0
    in_position = False
    entry_price = 0.0
    entry_date = None
    entry_fee = 0.0
    trades: List[Dict[str, Any]] = []
    equity_curve: List[float] = [initial_capital]
    equity_points: List[Tuple[date, float]] = []

    for i in range(len(df)):
        px = float(close.iloc[i])
        day = df.index[i]

        if i < 55:
            eq = cash + (units * px if in_position else 0.0)
            equity_curve.append(eq)
            equity_points.append((day, eq))
            continue

        if not in_position:
            pullback = ((px - high20.iloc[i]) / high20.iloc[i]) * 100 if high20.iloc[i] else 0.0
            in_pullback = pullback_low <= pullback <= pullback_high
            near_ma21 = abs((px - ma21.iloc[i]) / ma21.iloc[i]) <= ma_tolerance if ma21.iloc[i] else False
            near_ma50 = abs((px - ma50.iloc[i]) / ma50.iloc[i]) <= ma_tolerance if ma50.iloc[i] else False
            rising = px > float(close.iloc[i - 1])

            if in_pullback and (near_ma21 or near_ma50) and rising:
                spend = cash * allocation
                entry_fee = max(spend * fee_rate, 1.0)
                spend_after_fee = max(spend - entry_fee, 0.0)
                units = spend_after_fee / px if px > 0 else 0.0
                cash -= spend
                in_position = units > 0
                entry_price = px
                entry_date = day
        else:
            gain_pct = ((px - entry_price) / entry_price) * 100 if entry_price > 0 else 0.0
            at_52w = px >= (float(high252.iloc[i]) * 0.98) if high252.iloc[i] else False
            ma10_break = px < float(ma10.iloc[i]) if ma10.iloc[i] else False
            three_down = (
                i >= 3
                and px < float(close.iloc[i - 1])
                and float(close.iloc[i - 1]) < float(close.iloc[i - 2])
                and float(close.iloc[i - 2]) < float(close.iloc[i - 3])
            )

            should_exit = False
            reason = "hold"

            if gain_pct <= stop_loss:
                should_exit = True
                reason = "stop_loss"
            elif at_52w and dist_count.iloc[i] >= (4 if legacy else 3):
                should_exit = True
                reason = "52w_dist"
            elif ma10_break and dist_count.iloc[i] >= (3 if legacy else 2):
                should_exit = True
                reason = "ma_break_dist"
            elif three_down:
                should_exit = True
                reason = "three_down"
            elif gain_pct >= profit_target and dist_count.iloc[i] >= (3 if legacy else 2):
                should_exit = True
                reason = "profit_take"
            elif i == len(df) - 1:
                should_exit = True
                reason = "period_end"

            if should_exit:
                gross = units * px
                exit_fee = max(gross * fee_rate, 1.0)
                proceeds = gross - exit_fee
                cash += proceeds
                realized = proceeds - ((units * entry_price) + entry_fee)

                trades.append(
                    {
                        "underlying": "TQQQ",
                        "entry_date": entry_date.isoformat() if entry_date else day.isoformat(),
                        "close_date": day.isoformat(),
                        "entry_price": entry_price,
                        "close_price": px,
                        "qty": round(units, 6),
                        "realized_pnl": round(realized, 4),
                        "close_reason": reason,
                    }
                )

                units = 0.0
                in_position = False
                entry_price = 0.0
                entry_date = None
                entry_fee = 0.0

        eq = cash + (units * px if in_position else 0.0)
        equity_curve.append(eq)
        equity_points.append((day, eq))

    metrics = compute_metrics(trades, equity_curve)
    metrics["rolls_executed"] = 0
    metrics["trading_days"] = len(df)

    trade_pnls = [float(t.get("realized_pnl", 0.0)) for t in trades]

    return EngineOutput(
        strategy_id="openclaw_tqqq_swing",
        strategy_name="OpenClaw TQQQ Swing",
        variant=assumptions_mode,
        engine_type="openclaw_tqqq_swing_engine",
        assumptions_mode=assumptions_mode,
        universe="TQQQ (or synthetic from QQQ)",
        strategy_parameters={
            "pullback_low_pct": pullback_low,
            "pullback_high_pct": pullback_high,
            "ma_tolerance": ma_tolerance,
            "allocation_pct": allocation * 100.0,
            "stop_loss_pct": stop_loss,
            "profit_target_pct": profit_target,
            "fee_rate": fee_rate,
        },
        metrics=metrics,
        equity_curve=[float(v) for v in equity_curve],
        equity_points=equity_points,
        trade_pnls=trade_pnls,
    )


def _run_openclaw_hybrid(
    data: pd.DataFrame,
    config: Dict[str, Any],
    start_date: date,
    end_date: date,
    assumptions_mode: str,
) -> EngineOutput:
    stock = _run_openclaw_stock_options(data, config, start_date, end_date, assumptions_mode)
    tqqq = _run_openclaw_tqqq_swing(data, start_date, end_date, assumptions_mode)

    stock_w = 0.75
    tqqq_w = 0.25
    initial = 100_000.0

    combined_points = _combine_equity_points(
        stock_points=stock.equity_points,
        tqqq_points=tqqq.equity_points,
        stock_weight=stock_w,
        tqqq_weight=tqqq_w,
        initial_equity=initial,
    )

    equity_curve = [initial] + [v for _, v in combined_points]
    scaled_trade_pnls = [p * stock_w for p in stock.trade_pnls] + [p * tqqq_w for p in tqqq.trade_pnls]
    pseudo_trades = _pseudo_trades_from_pnls(scaled_trade_pnls)
    metrics = compute_metrics(pseudo_trades, equity_curve)
    metrics["rolls_executed"] = int(stock.metrics.get("rolls_executed", 0))
    metrics["trading_days"] = len(combined_points)
    stock_trades = int(stock.metrics.get("total_trades", 0))
    tqqq_trades = int(tqqq.metrics.get("total_trades", 0))
    total_trades = stock_trades + tqqq_trades
    if total_trades > 0:
        weighted_hold = (
            (float(stock.metrics.get("avg_hold_days", 0.0)) * stock_trades)
            + (float(tqqq.metrics.get("avg_hold_days", 0.0)) * tqqq_trades)
        ) / total_trades
        metrics["avg_hold_days"] = weighted_hold

    stock_leg_pnl = initial * stock_w * ((stock.metrics.get("final_equity", initial) / initial) - 1.0)
    tqqq_leg_pnl = initial * tqqq_w * ((tqqq.metrics.get("final_equity", initial) / initial) - 1.0)
    total_leg_pnl = stock_leg_pnl + tqqq_leg_pnl
    stock_contrib = (stock_leg_pnl / total_leg_pnl * 100.0) if total_leg_pnl != 0 else 0.0
    tqqq_contrib = (tqqq_leg_pnl / total_leg_pnl * 100.0) if total_leg_pnl != 0 else 0.0

    component_metrics = {
        "stock": {
            "total_return_pct": round(stock.metrics.get("total_return_pct", 0.0), 4),
            "final_equity": round(stock.metrics.get("final_equity", initial), 4),
            "win_rate": round(stock.metrics.get("win_rate", 0.0), 4),
            "profit_factor": round(stock.metrics.get("profit_factor", 0.0), 4),
            "weight": stock_w,
            "pnl_contribution": round(stock_leg_pnl, 4),
            "contribution_pct": round(stock_contrib, 4),
        },
        "tqqq": {
            "total_return_pct": round(tqqq.metrics.get("total_return_pct", 0.0), 4),
            "final_equity": round(tqqq.metrics.get("final_equity", initial), 4),
            "win_rate": round(tqqq.metrics.get("win_rate", 0.0), 4),
            "profit_factor": round(tqqq.metrics.get("profit_factor", 0.0), 4),
            "weight": tqqq_w,
            "pnl_contribution": round(tqqq_leg_pnl, 4),
            "contribution_pct": round(tqqq_contrib, 4),
        },
    }

    return EngineOutput(
        strategy_id="openclaw_hybrid",
        strategy_name="OpenClaw Hybrid",
        variant=assumptions_mode,
        engine_type="openclaw_hybrid_engine",
        assumptions_mode=assumptions_mode,
        universe=f"{stock.universe} + {tqqq.universe}",
        strategy_parameters={
            "stock_leg_weight": stock_w,
            "tqqq_leg_weight": tqqq_w,
            "stock_leg_mode": assumptions_mode,
            "tqqq_leg_mode": assumptions_mode,
        },
        metrics=metrics,
        equity_curve=[float(v) for v in equity_curve],
        equity_points=combined_points,
        trade_pnls=[float(v) for v in scaled_trade_pnls],
        component_metrics=component_metrics,
    )


def _run_intraday_open_close_options(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    assumptions_mode: str,
    universe_symbols: Optional[List[str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> EngineOutput:
    from ovtlyr.backtester.intraday_options_engine import run_intraday_open_close_options

    if universe_symbols:
        symbols = [str(s).strip().upper() for s in universe_symbols if str(s).strip()]
    else:
        universe = (
            "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,SPY,QQQ,AMD,AVGO,ORCL,CRM,ADBE,CSCO,"
            "QCOM,INTU,AMAT,TXN,IBM,NOW,NFLX,ACN,HD,MCD,NKE,BKNG,COST,JPM,V,MA,BAC,GS,"
            "LLY,JNJ,ABBV,TMO,MRK,DHR,UNH,ISRG,XOM,CVX,WMT,PG,KO,PEP,GE,CAT,LIN"
        )
        symbols = [s.strip() for s in universe.split(",") if s.strip()]
    universe = ",".join(symbols)

    output = run_intraday_open_close_options(
        data=data,
        start_date=start_date,
        end_date=end_date,
        assumptions_mode=assumptions_mode,
        universe_symbols=symbols,
        config=config or {},
    )

    return EngineOutput(
        strategy_id="intraday_open_close_options",
        strategy_name="Intraday Open-Close Options",
        variant=assumptions_mode,
        engine_type="intraday_open_close_options_engine",
        assumptions_mode=assumptions_mode,
        universe=universe,
        strategy_parameters=output["strategy_parameters"],
        metrics=output["metrics"],
        equity_curve=output["equity_curve"],
        equity_points=output["equity_points"],
        trade_pnls=output["trade_pnls"],
        component_metrics=None,
        intraday_report=output.get("intraday_report") or [],
        candidate_count_total=int(output.get("candidate_count_total", 0)),
        candidate_count_qualified=int(output.get("candidate_count_qualified", 0)),
        data_quality_breakdown=output.get("data_quality_breakdown") or {
            "observed": 0,
            "mixed": 0,
            "modeled": 0,
        },
        rejection_counts=output.get("rejection_counts") or {},
        execution_window=output.get("execution_window") or {"entry_time": "09:35", "exit_time": "15:55"},
    )


def _option_mark_call(
    px: float,
    strike: float,
    time_value_at_entry: float,
    dte_left: int,
    dte_total: int,
) -> float:
    intrinsic = max(px - strike, 0.0)
    t_ratio = max(min(dte_left / max(dte_total, 1), 1.0), 0.0)
    return max(intrinsic + (max(time_value_at_entry, 0.0) * t_ratio), 0.01)


def _option_mark_put(
    px: float,
    strike: float,
    time_value_at_entry: float,
    dte_left: int,
    dte_total: int,
) -> float:
    intrinsic = max(strike - px, 0.0)
    t_ratio = max(min(dte_left / max(dte_total, 1), 1.0), 0.0)
    return max(intrinsic + (max(time_value_at_entry, 0.0) * t_ratio), 0.01)


def _run_research_buywrite_spy(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    assumptions_mode: str,
) -> EngineOutput:
    return _run_research_monthly_options(
        data=data,
        start_date=start_date,
        end_date=end_date,
        assumptions_mode=assumptions_mode,
        strategy_id="research_buywrite_spy",
        strategy_name="Research BuyWrite SPY",
        mode="buywrite",
    )


def _run_research_putwrite_spy(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    assumptions_mode: str,
) -> EngineOutput:
    return _run_research_monthly_options(
        data=data,
        start_date=start_date,
        end_date=end_date,
        assumptions_mode=assumptions_mode,
        strategy_id="research_putwrite_spy",
        strategy_name="Research PutWrite SPY",
        mode="putwrite",
    )


def _run_research_collar_spy(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    assumptions_mode: str,
) -> EngineOutput:
    return _run_research_monthly_options(
        data=data,
        start_date=start_date,
        end_date=end_date,
        assumptions_mode=assumptions_mode,
        strategy_id="research_collar_spy",
        strategy_name="Research Collar SPY",
        mode="collar",
    )


def _run_research_monthly_options(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    assumptions_mode: str,
    strategy_id: str,
    strategy_name: str,
    mode: str,
) -> EngineOutput:
    prices = _build_underlying_close_frame(data, start_date, end_date, symbols=["SPY"])
    if prices.empty or "SPY" not in prices.columns:
        raise ValueError(f"No SPY data available for {strategy_id}")

    close = prices["SPY"].astype(float).dropna()
    if close.empty:
        raise ValueError(f"No SPY close data for {strategy_id}")

    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    hv20 = close.pct_change().rolling(20).std() * (252 ** 0.5)

    defensive = assumptions_mode == "defensive"
    dte_days = 35
    min_hold_days = 5 if defensive else 3
    put_short_pct = 0.06 if defensive else 0.05
    call_otm_pct = 0.03 if defensive else 0.02
    buywrite_call_prem_pct = 0.010 if defensive else 0.012
    collar_call_prem_pct = 0.008 if defensive else 0.009
    collar_put_prem_pct = 0.010 if defensive else 0.008
    putwrite_prem_pct = 0.012 if defensive else 0.014
    putwrite_alloc = 0.70 if defensive else 0.80
    fee_per_contract = 2.0 if defensive else 1.5

    initial_capital = 100_000.0
    cash = initial_capital
    equity_curve: List[float] = [initial_capital]
    equity_points: List[Tuple[date, float]] = []
    trades: List[Dict[str, Any]] = []

    pos: Optional[Dict[str, Any]] = None

    for i, day in enumerate(close.index):
        px = float(close.loc[day])

        # 1) Manage open position mark/exits
        if pos is not None:
            held_days = (day - pos["entry_date"]).days
            dte_left = (pos["expiry_date"] - day).days
            trend_bear = (
                pd.notna(ma20.loc[day])
                and pd.notna(ma50.loc[day])
                and pd.notna(ma200.loc[day])
                and (px < float(ma200.loc[day]))
                and (float(ma20.loc[day]) < float(ma50.loc[day]))
            )

            should_close = False
            reason = "hold"
            if dte_left <= 0:
                should_close = True
                reason = "expiry"
            elif held_days >= min_hold_days and trend_bear:
                should_close = True
                reason = "trend_break"

            if should_close:
                realized = 0.0
                if mode in {"buywrite", "collar"}:
                    shares = int(pos["shares"])
                    call_val = _option_mark_call(
                        px=px,
                        strike=float(pos["call_strike"]),
                        time_value_at_entry=float(pos["call_time0"]),
                        dte_left=dte_left,
                        dte_total=int(pos["dte_days"]),
                    )
                    stock_leg = shares * (px - float(pos["entry_px"]))
                    call_leg = shares * (float(pos["call_premium"]) - call_val)
                    cash += shares * px
                    cash -= shares * call_val
                    realized = stock_leg + call_leg

                    close_price = call_val
                    if mode == "collar":
                        put_val = _option_mark_put(
                            px=px,
                            strike=float(pos["put_strike"]),
                            time_value_at_entry=float(pos["put_time0"]),
                            dte_left=dte_left,
                            dte_total=int(pos["dte_days"]),
                        )
                        put_leg = shares * (put_val - float(pos["put_premium"]))
                        cash += shares * put_val
                        realized += put_leg
                        close_price = call_val - put_val

                    contracts = max(shares // 100, 1)
                    fees = contracts * fee_per_contract
                    cash -= fees
                    realized -= fees
                else:
                    contracts = int(pos["contracts"])
                    put_val = _option_mark_put(
                        px=px,
                        strike=float(pos["put_strike"]),
                        time_value_at_entry=float(pos["put_time0"]),
                        dte_left=dte_left,
                        dte_total=int(pos["dte_days"]),
                    )
                    realized = contracts * 100.0 * (float(pos["put_premium"]) - put_val)
                    fees = contracts * fee_per_contract
                    realized -= fees
                    cash -= contracts * 100.0 * put_val
                    cash -= fees
                    close_price = put_val

                trades.append(
                    {
                        "underlying": "SPY",
                        "entry_date": pos["entry_date"].isoformat(),
                        "close_date": day.isoformat(),
                        "entry_price": float(pos["entry_px"]),
                        "close_price": float(close_price),
                        "qty": int(pos.get("shares", pos.get("contracts", 0))),
                        "realized_pnl": round(realized, 4),
                        "close_reason": reason,
                    }
                )
                pos = None

        # 2) Open new position if flat and regime is favorable
        if pos is None and i >= 200:
            if pd.isna(ma20.loc[day]) or pd.isna(ma50.loc[day]) or pd.isna(ma200.loc[day]):
                pass
            else:
                trend_bull = (px > float(ma200.loc[day])) and (float(ma20.loc[day]) > float(ma50.loc[day]))
                hv = float(hv20.loc[day]) if pd.notna(hv20.loc[day]) else 0.0
                vol_ok = 0.08 <= hv <= (0.45 if defensive else 0.60)

                if trend_bull and vol_ok:
                    expiry_date = day + timedelta(days=dte_days)
                    if mode in {"buywrite", "collar"}:
                        shares = int(cash // px)
                        if shares >= 100:
                            call_strike = round(px * (1.0 + call_otm_pct), 2)
                            call_premium = round(px * (buywrite_call_prem_pct if mode == "buywrite" else collar_call_prem_pct), 2)
                            call_intr = max(px - call_strike, 0.0)
                            call_time0 = max(call_premium - call_intr, 0.0)

                            cash -= shares * px
                            cash += shares * call_premium

                            put_strike = None
                            put_premium = 0.0
                            put_time0 = 0.0
                            if mode == "collar":
                                put_strike = round(px * (1.0 - put_short_pct), 2)
                                put_premium = round(px * collar_put_prem_pct, 2)
                                put_intr = max(put_strike - px, 0.0)
                                put_time0 = max(put_premium - put_intr, 0.0)
                                cash -= shares * put_premium

                            pos = {
                                "entry_date": day,
                                "expiry_date": expiry_date,
                                "dte_days": dte_days,
                                "entry_px": px,
                                "shares": shares,
                                "call_strike": call_strike,
                                "call_premium": call_premium,
                                "call_time0": call_time0,
                                "put_strike": put_strike,
                                "put_premium": put_premium,
                                "put_time0": put_time0,
                            }
                    else:
                        put_strike = round(px * (1.0 - put_short_pct), 2)
                        collateral_per_contract = put_strike * 100.0
                        contracts = int((cash * putwrite_alloc) // max(collateral_per_contract, 1.0))
                        if contracts >= 1:
                            put_premium = round(px * putwrite_prem_pct, 2)
                            put_intr = max(put_strike - px, 0.0)
                            put_time0 = max(put_premium - put_intr, 0.0)
                            cash += contracts * 100.0 * put_premium
                            pos = {
                                "entry_date": day,
                                "expiry_date": expiry_date,
                                "dte_days": dte_days,
                                "entry_px": px,
                                "contracts": contracts,
                                "put_strike": put_strike,
                                "put_premium": put_premium,
                                "put_time0": put_time0,
                            }

        # 3) Daily equity mark
        if pos is None:
            equity = cash
        elif mode in {"buywrite", "collar"}:
            shares = int(pos["shares"])
            dte_left = (pos["expiry_date"] - day).days
            call_val = _option_mark_call(
                px=px,
                strike=float(pos["call_strike"]),
                time_value_at_entry=float(pos["call_time0"]),
                dte_left=dte_left,
                dte_total=int(pos["dte_days"]),
            )
            equity = cash + (shares * px) - (shares * call_val)
            if mode == "collar":
                put_val = _option_mark_put(
                    px=px,
                    strike=float(pos["put_strike"]),
                    time_value_at_entry=float(pos["put_time0"]),
                    dte_left=dte_left,
                    dte_total=int(pos["dte_days"]),
                )
                equity += shares * put_val
        else:
            contracts = int(pos["contracts"])
            dte_left = (pos["expiry_date"] - day).days
            put_val = _option_mark_put(
                px=px,
                strike=float(pos["put_strike"]),
                time_value_at_entry=float(pos["put_time0"]),
                dte_left=dte_left,
                dte_total=int(pos["dte_days"]),
            )
            equity = cash - (contracts * 100.0 * put_val)

        equity_curve.append(float(equity))
        equity_points.append((day, float(equity)))

    # End-of-period liquidation
    if pos is not None:
        day = close.index[-1]
        px = float(close.iloc[-1])
        dte_left = (pos["expiry_date"] - day).days
        if mode in {"buywrite", "collar"}:
            shares = int(pos["shares"])
            call_val = _option_mark_call(px, float(pos["call_strike"]), float(pos["call_time0"]), dte_left, int(pos["dte_days"]))
            cash += shares * px
            cash -= shares * call_val
            realized = shares * (px - float(pos["entry_px"])) + shares * (float(pos["call_premium"]) - call_val)
            close_price = call_val
            if mode == "collar":
                put_val = _option_mark_put(px, float(pos["put_strike"]), float(pos["put_time0"]), dte_left, int(pos["dte_days"]))
                cash += shares * put_val
                realized += shares * (put_val - float(pos["put_premium"]))
                close_price = call_val - put_val
            fees = max(shares // 100, 1) * fee_per_contract
            cash -= fees
            realized -= fees
        else:
            contracts = int(pos["contracts"])
            put_val = _option_mark_put(px, float(pos["put_strike"]), float(pos["put_time0"]), dte_left, int(pos["dte_days"]))
            cash -= contracts * 100.0 * put_val
            fees = contracts * fee_per_contract
            cash -= fees
            realized = contracts * 100.0 * (float(pos["put_premium"]) - put_val) - fees
            close_price = put_val

        trades.append(
            {
                "underlying": "SPY",
                "entry_date": pos["entry_date"].isoformat(),
                "close_date": day.isoformat(),
                "entry_price": float(pos["entry_px"]),
                "close_price": float(close_price),
                "qty": int(pos.get("shares", pos.get("contracts", 0))),
                "realized_pnl": round(realized, 4),
                "close_reason": "period_end",
            }
        )
        if equity_curve:
            equity_curve[-1] = float(cash)
        if equity_points:
            equity_points[-1] = (equity_points[-1][0], float(cash))

    metrics = compute_metrics(trades, equity_curve)
    metrics["rolls_executed"] = 0
    metrics["trading_days"] = len(close.index)
    trade_pnls = [float(t.get("realized_pnl", 0.0)) for t in trades]

    return EngineOutput(
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        variant=assumptions_mode,
        engine_type=f"{strategy_id}_engine",
        assumptions_mode=assumptions_mode,
        universe="SPY",
        strategy_parameters={
            "mode": mode,
            "dte_days": dte_days,
            "defensive": defensive,
            "put_short_pct": put_short_pct,
            "call_otm_pct": call_otm_pct,
            "putwrite_alloc": putwrite_alloc,
            "fee_per_contract": fee_per_contract,
        },
        metrics=metrics,
        equity_curve=[float(v) for v in equity_curve],
        equity_points=equity_points,
        trade_pnls=trade_pnls,
    )


def _apply_realistic_pricing_overlay(
    metrics: Dict[str, Any],
    equity_curve: List[float],
    trade_pnls: List[float],
) -> Tuple[Dict[str, Any], List[float], List[float]]:
    if not trade_pnls:
        return metrics, equity_curve, trade_pnls

    per_trade_cost = 65.0
    total_cost = per_trade_cost * len(trade_pnls)
    adjusted_pnls = [p - per_trade_cost for p in trade_pnls]

    adjusted_curve = [float(v) for v in equity_curve]
    if len(adjusted_curve) > 1:
        for i in range(1, len(adjusted_curve)):
            frac = i / (len(adjusted_curve) - 1)
            adjusted_curve[i] = round(adjusted_curve[i] - (total_cost * frac), 4)

    pseudo_trades = _pseudo_trades_from_pnls(adjusted_pnls)
    adjusted_metrics = compute_metrics(pseudo_trades, adjusted_curve)
    adjusted_metrics["rolls_executed"] = int(metrics.get("rolls_executed", 0))
    adjusted_metrics["trading_days"] = int(metrics.get("trading_days", 0))
    adjusted_metrics["avg_hold_days"] = float(metrics.get("avg_hold_days", 0.0))
    adjusted_metrics["assumption_costs"] = round(total_cost, 4)

    return adjusted_metrics, adjusted_curve, adjusted_pnls


def _build_tqqq_price_frame(data: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    frame = data.copy()
    if "date" not in frame.columns or "underlying" not in frame.columns:
        return pd.DataFrame()

    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame[(frame["date"] >= start_date) & (frame["date"] <= end_date)]

    tqqq = (
        frame[frame["underlying"] == "TQQQ"][["date", "underlying_price"]]
        .dropna()
        .drop_duplicates("date")
        .sort_values("date")
    )
    if not tqqq.empty:
        out = tqqq.rename(columns={"underlying_price": "close"}).set_index("date")
        return out

    qqq = (
        frame[frame["underlying"] == "QQQ"][["date", "underlying_price"]]
        .dropna()
        .drop_duplicates("date")
        .sort_values("date")
    )
    if qqq.empty:
        return pd.DataFrame()

    qqq["ret"] = qqq["underlying_price"].pct_change().fillna(0.0)
    synthetic = []
    px = 100.0
    for r in qqq["ret"].tolist():
        px = max(px * (1.0 + (3.0 * r)), 1.0)
        synthetic.append(px)
    qqq["close"] = synthetic

    return qqq[["date", "close"]].set_index("date")


def _build_underlying_close_frame(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    symbols: List[str],
) -> pd.DataFrame:
    frame = data.copy()
    if "date" not in frame.columns or "underlying" not in frame.columns or "underlying_price" not in frame.columns:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame[(frame["date"] >= start_date) & (frame["date"] <= end_date)]
    frame = frame[frame["underlying"].isin(symbols)][["date", "underlying", "underlying_price"]].dropna()
    if frame.empty:
        return pd.DataFrame()
    daily = (
        frame.groupby(["date", "underlying"], as_index=False)["underlying_price"]
        .mean()
        .pivot(index="date", columns="underlying", values="underlying_price")
        .sort_index()
        .ffill()
    )
    for sym in symbols:
        if sym not in daily.columns:
            daily[sym] = pd.NA
    return daily[symbols].dropna(how="all")


def _trading_days(data: pd.DataFrame, start_date: date, end_date: date) -> List[date]:
    out = []
    for v in sorted(data["date"].unique()):
        d = date.fromisoformat(str(v))
        if start_date <= d <= end_date:
            out.append(d)
    return out


def _equity_points_from_curve(trading_days: List[date], equity_curve: List[float]) -> List[Tuple[date, float]]:
    points: List[Tuple[date, float]] = []
    # equity_curve starts with initial capital, then one value per trading day.
    usable = min(len(trading_days), max(len(equity_curve) - 1, 0))
    for i in range(usable):
        points.append((trading_days[i], float(equity_curve[i + 1])))
    return points


def _closed_trade_pnls(trades: List[Dict[str, Any]]) -> List[float]:
    out = []
    for t in trades:
        try:
            out.append(float(t.get("realized_pnl", 0.0)))
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def _pseudo_trades_from_pnls(pnls: List[float]) -> List[Dict[str, Any]]:
    base = datetime(2020, 1, 1)
    out = []
    for i, pnl in enumerate(pnls):
        entry = base.replace(day=((i % 28) + 1))
        close = entry
        out.append(
            {
                "realized_pnl": float(pnl),
                "entry_date": entry.isoformat(),
                "close_date": close.isoformat(),
            }
        )
    return out


def _combine_equity_points(
    stock_points: List[Tuple[date, float]],
    tqqq_points: List[Tuple[date, float]],
    stock_weight: float,
    tqqq_weight: float,
    initial_equity: float,
) -> List[Tuple[date, float]]:
    stock_map = {d: float(v) for d, v in stock_points}
    tqqq_map = {d: float(v) for d, v in tqqq_points}
    all_dates = sorted(set(stock_map.keys()) | set(tqqq_map.keys()))

    out: List[Tuple[date, float]] = []
    last_stock = initial_equity
    last_tqqq = initial_equity

    for d in all_dates:
        if d in stock_map:
            last_stock = stock_map[d]
        if d in tqqq_map:
            last_tqqq = tqqq_map[d]

        stock_ratio = last_stock / initial_equity if initial_equity > 0 else 1.0
        tqqq_ratio = last_tqqq / initial_equity if initial_equity > 0 else 1.0
        combined = initial_equity * ((stock_weight * stock_ratio) + (tqqq_weight * tqqq_ratio))
        out.append((d, float(combined)))

    return out
