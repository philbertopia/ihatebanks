"""
OpenClaw strategy-family backtest engines.

This module provides several strategy families, each with one or more
assumptions modes:
  - openclaw_stock_options (legacy_replica, realistic_priced)
  - openclaw_put_credit_spread
      (legacy_replica, realistic_priced, pcs_income_plus,
       pcs_balanced_plus, pcs_conservative_turnover, qqq_falling_knife)
  - research_small_account_options
      (spy_iron_condor_proxy, msft_bull_call_spread,
       aapl_bull_put_45_21, aapl_long_call_low_iv)
  - research_index_swing_options
      (pullback_baseline_30_45, pullback_defensive_30_45,
       pullback_baseline_45_60, pullback_defensive_45_60)
  - openclaw_regime_credit_spread
      (regime_balanced, regime_defensive, regime_legacy_defensive,
       regime_vix_baseline, regime_legacy_defensive_bear_only,
       regime_vix_baseline_bear_only, timed_legacy_defensive_*)
  - openclaw_tqqq_swing (legacy_replica, realistic_priced)
  - openclaw_hybrid (legacy_replica, realistic_priced)
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
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
    "qqq_falling_knife",
}
CALL_CREDIT_SPREAD_MODES = {
    "ccs_baseline",
    "ccs_vix_regime",
    "ccs_defensive",
    # Single-stock / multi-stock extensions (2026-03)
    "single_stock_aapl",
    "single_stock_nvda",
    "multi_stock_basket",
}
REGIME_CREDIT_SPREAD_MODES = {
    "regime_balanced",
    "regime_defensive",
    "regime_legacy_defensive",
    "regime_vix_baseline",
    "regime_legacy_defensive_bear_only",
    "regime_vix_baseline_bear_only",
    "timed_legacy_defensive_40_7_r075",
    "timed_legacy_defensive_40_10_r100",
    "timed_legacy_defensive_50_10_r100",
    "timed_legacy_defensive_60_10_r100",
    "timed_legacy_defensive_50_14_r125",
    "timed_legacy_defensive_bear_only_40_10_r100",
    "timed_legacy_defensive_bear_only_50_10_r100",
    "timed_legacy_defensive_bear_only_50_7_r075",
}
INTRADAY_MODES = {
    "baseline",
    "conservative",
    "aggressive",
    "conservative_v2",
    "oos_hardened",
    "wf_v1_liquidity_guard",
    "wf_v2_flow_strict",
    "wf_v3_regime_strict",
    "wf_v4_validated_candidate",
}

RESEARCH_MONTHLY_MODES = {"baseline", "defensive"}
SMALL_ACCOUNT_RESEARCH_MODES = {
    "spy_iron_condor_proxy",
    "msft_bull_call_spread",
    "aapl_bull_put_45_21",
    "aapl_long_call_low_iv",
}
INDEX_SWING_RESEARCH_MODES = {
    "pullback_baseline_30_45",
    "pullback_defensive_30_45",
    "pullback_baseline_45_60",
    "pullback_defensive_45_60",
    "pullback_baseline_30_45_v2",
    "pullback_defensive_30_45_v2",
    "pullback_baseline_45_60_v2",
    "pullback_defensive_45_60_v2",
}


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
    if strategy_id == "openclaw_regime_credit_spread":
        if assumptions_mode not in REGIME_CREDIT_SPREAD_MODES:
            raise ValueError(
                f"Unsupported assumptions mode for {strategy_id}: {assumptions_mode}"
            )
        return _with_execution_defaults(
            _run_openclaw_regime_credit_spread(data, start_date, end_date, assumptions_mode)
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
    if strategy_id == "research_small_account_options":
        if assumptions_mode not in SMALL_ACCOUNT_RESEARCH_MODES:
            raise ValueError(
                f"Unsupported assumptions mode for {strategy_id}: {assumptions_mode}"
            )
        return _with_execution_defaults(
            _run_research_small_account_options(
                data=data,
                start_date=start_date,
                end_date=end_date,
                assumptions_mode=assumptions_mode,
            )
        )
    if strategy_id == "research_index_swing_options":
        if assumptions_mode not in INDEX_SWING_RESEARCH_MODES:
            raise ValueError(
                f"Unsupported assumptions mode for {strategy_id}: {assumptions_mode}"
            )
        return _with_execution_defaults(
            _run_research_index_swing_options(
                data=data,
                start_date=start_date,
                end_date=end_date,
                assumptions_mode=assumptions_mode,
            )
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
    allowed_symbols = [str(s).upper() for s in params.get("allowed_symbols", ["SPY", "QQQ"])]
    require_ma200_support = bool(params.get("require_ma200_support", True))
    require_ma20_above_ma50 = bool(params.get("require_ma20_above_ma50", True))
    rsi_period = int(params.get("rsi_period", 14))
    rsi_entry_max = params.get("rsi_entry_max")
    require_selloff_trigger = bool(params.get("require_selloff_trigger", False))
    selloff_day_return_max = float(params.get("selloff_day_return_max", 0.0))
    selloff_3d_return_max = float(params.get("selloff_3d_return_max", 0.0))
    require_pullback_from_high = bool(params.get("require_pullback_from_high", False))
    pullback_lookback_days = int(params.get("pullback_lookback_days", 20))
    pullback_from_high_min = float(params.get("pullback_from_high_min", 0.0))

    returns = prices.pct_change()
    hv20 = returns.rolling(20).std() * (252 ** 0.5)
    ma20 = prices.rolling(20).mean()
    ma50 = prices.rolling(50).mean()
    ma200 = prices.rolling(200).mean()
    day_return = prices.pct_change(1)
    return_3d = prices.pct_change(3)
    rsi = _wilder_rsi_frame(prices, period=rsi_period)
    prior_high = prices.shift(1).rolling(
        pullback_lookback_days, min_periods=pullback_lookback_days
    ).max()

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
    signal_counts_by_symbol = {symbol: 0 for symbol in allowed_symbols}
    entry_counts_by_symbol = {symbol: 0 for symbol in allowed_symbols}

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

        for symbol in allowed_symbols:
            if symbol not in prices.columns:
                continue
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

            ma200_ok = (not require_ma200_support) or (px > float(ma200.loc[day, symbol]))
            ma20_ma50_ok = (not require_ma20_above_ma50) or (
                float(ma20.loc[day, symbol]) > float(ma50.loc[day, symbol])
            )
            bullish_regime = ma200_ok and ma20_ma50_ok
            iv_proxy = float(hv20.loc[day, symbol])
            iv_regime_ok = iv_low <= iv_proxy <= iv_high
            if not (bullish_regime and iv_regime_ok):
                continue

            # VIX proxy gate (pcs_vix_optimal variant): use SPY HV20 as VIX proxy
            if pcs_vix_gate:
                spy_hv = float(hv20.loc[day, "SPY"]) if "SPY" in hv20.columns and pd.notna(hv20.loc[day, "SPY"]) else iv_proxy
                if spy_hv < pcs_vix_min or spy_hv > pcs_vix_max:
                    continue

            if rsi_entry_max is not None:
                if pd.isna(rsi.loc[day, symbol]) or float(rsi.loc[day, symbol]) > float(rsi_entry_max):
                    continue

            if require_selloff_trigger:
                day_ret = day_return.loc[day, symbol]
                ret_3d = return_3d.loc[day, symbol]
                selloff_ok = False
                if pd.notna(day_ret) and float(day_ret) <= selloff_day_return_max:
                    selloff_ok = True
                if pd.notna(ret_3d) and float(ret_3d) <= selloff_3d_return_max:
                    selloff_ok = True
                if not selloff_ok:
                    continue

            if require_pullback_from_high:
                if pd.isna(prior_high.loc[day, symbol]) or float(prior_high.loc[day, symbol]) <= 0:
                    continue
                pullback = 1.0 - (px / float(prior_high.loc[day, symbol]))
                if pullback < pullback_from_high_min:
                    continue

            signal_counts_by_symbol[symbol] += 1

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
            entry_counts_by_symbol[symbol] += 1

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
    component_metrics = {
        "allowed_symbols": allowed_symbols,
        "signal_counts_by_symbol": {
            symbol: int(signal_counts_by_symbol.get(symbol, 0)) for symbol in allowed_symbols
        },
        "entry_counts_by_symbol": {
            symbol: int(entry_counts_by_symbol.get(symbol, 0)) for symbol in allowed_symbols
        },
        "entry_filter_summary": {
            "require_ma200_support": require_ma200_support,
            "require_ma20_above_ma50": require_ma20_above_ma50,
            "rsi_period": rsi_period,
            "rsi_entry_max": rsi_entry_max,
            "require_selloff_trigger": require_selloff_trigger,
            "selloff_day_return_max": selloff_day_return_max,
            "selloff_3d_return_max": selloff_3d_return_max,
            "require_pullback_from_high": require_pullback_from_high,
            "pullback_lookback_days": pullback_lookback_days,
            "pullback_from_high_min": pullback_from_high_min,
        },
    }

    return EngineOutput(
        strategy_id="openclaw_put_credit_spread",
        strategy_name="OpenClaw Put Credit Spread",
        variant=assumptions_mode,
        engine_type="openclaw_put_credit_spread_engine",
        assumptions_mode=assumptions_mode,
        universe=",".join(allowed_symbols),
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
            "allowed_symbols": allowed_symbols,
            "require_ma200_support": require_ma200_support,
            "require_ma20_above_ma50": require_ma20_above_ma50,
            "rsi_period": rsi_period,
            "rsi_entry_max": rsi_entry_max,
            "require_selloff_trigger": require_selloff_trigger,
            "selloff_day_return_max": selloff_day_return_max,
            "selloff_3d_return_max": selloff_3d_return_max,
            "require_pullback_from_high": require_pullback_from_high,
            "pullback_lookback_days": pullback_lookback_days,
            "pullback_from_high_min": pullback_from_high_min,
        },
        metrics=metrics,
        equity_curve=[float(v) for v in equity_curve],
        equity_points=equity_points,
        trade_pnls=trade_pnls,
        component_metrics=component_metrics,
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
        "qqq_falling_knife": {
            "risk_pct": 0.030,
            "short_dist_pct": 0.060,
            "width_pct": 0.040,
            "credit_ratio": 0.18,
            "dte_days": 28.0,
            "take_profit_ratio": 0.50,
            "stop_mult": 1.90,
            "min_hold_days": 2.0,
            "force_close_dte": 7.0,
            "iv_low": 0.18,
            "iv_high": 0.80,
            "fee_per_contract": 3.0,
            "max_qty": 2.0,
            "target_annual_vol": 0.18,
            "max_symbol_notional_pct": 0.18,
            "allowed_symbols": ["QQQ"],
            "require_ma200_support": True,
            "require_ma20_above_ma50": False,
            "rsi_period": 14.0,
            "rsi_entry_max": 45.0,
            "require_selloff_trigger": True,
            "selloff_day_return_max": -0.010,
            "selloff_3d_return_max": -0.020,
            "require_pullback_from_high": True,
            "pullback_lookback_days": 20.0,
            "pullback_from_high_min": 0.020,
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
        # ── Single-stock / multi-stock variants (2026-03) ────────────────────
        # Higher-IV individual stocks generate more premium per trade.
        # Use tighter strikes and wider spreads vs SPY/QQQ to manage idiosyncratic risk.
        "single_stock_aapl": {
            "risk_pct": 0.010,
            "short_dist_pct": 0.035,   # 3.5% OTM (closer than SPY due to lower vol)
            "width_pct": 0.050,
            "credit_ratio": 0.33,
            "dte_days": 35.0,
            "take_profit_ratio": 0.50,
            "stop_mult": 2.20,
            "min_hold_days": 3.0,
            "force_close_dte": 10.0,
            "iv_low": 0.20,
            "iv_high": 0.80,
            "fee_per_contract": 3.0,
            "max_qty": 3.0,
            "target_annual_vol": 0.18,
            "max_symbol_notional_pct": 0.40,
            "allowed_symbols": ["AAPL"],
        },
        "single_stock_nvda": {
            "risk_pct": 0.008,         # smaller per-trade risk — NVDA is high-vol
            "short_dist_pct": 0.050,   # 5% OTM — wider because IV is ~3x SPY
            "width_pct": 0.080,        # 8% wide spread
            "credit_ratio": 0.33,
            "dte_days": 35.0,
            "take_profit_ratio": 0.50,
            "stop_mult": 2.20,
            "min_hold_days": 3.0,
            "force_close_dte": 10.0,
            "iv_low": 0.30,
            "iv_high": 1.20,           # NVDA often > 80% IV — allow high end
            "fee_per_contract": 3.0,
            "max_qty": 2.0,
            "target_annual_vol": 0.18,
            "max_symbol_notional_pct": 0.40,
            "allowed_symbols": ["NVDA"],
        },
        "multi_stock_basket": {
            "risk_pct": 0.010,
            "short_dist_pct": 0.040,   # 4% OTM across mixed-vol basket
            "width_pct": 0.060,
            "credit_ratio": 0.33,
            "dte_days": 35.0,
            "take_profit_ratio": 0.50,
            "stop_mult": 2.20,
            "min_hold_days": 3.0,
            "force_close_dte": 10.0,
            "iv_low": 0.18,
            "iv_high": 1.00,
            "fee_per_contract": 3.0,
            "max_qty": 2.0,
            "target_annual_vol": 0.18,
            "max_symbol_notional_pct": 0.15,  # 4 stocks — lower per-stock cap
            "allowed_symbols": ["AAPL", "MSFT", "NVDA", "JPM"],
        },
    }
    if mode not in profiles:
        raise ValueError(f"Unsupported call-credit-spread mode: {mode}")
    return profiles[mode]


def _regime_credit_params(mode: str) -> Dict[str, Any]:
    profiles: Dict[str, Dict[str, Any]] = {
        "regime_balanced": {
            "bull_mode": "legacy_replica",
            "bear_mode": "ccs_baseline",
            "neutral_mode": "ccs_baseline",
            "allow_neutral_call_entries": True,
            "max_call_pct_above_ma50": 0.08,
        },
        "regime_defensive": {
            "bull_mode": "pcs_vix_optimal",
            "bear_mode": "ccs_defensive",
            "neutral_mode": "ccs_defensive",
            "allow_neutral_call_entries": True,
            "max_call_pct_above_ma50": 0.05,
        },
        "regime_legacy_defensive": {
            "bull_mode": "legacy_replica",
            "bear_mode": "ccs_defensive",
            "neutral_mode": "ccs_defensive",
            "allow_neutral_call_entries": True,
            "max_call_pct_above_ma50": 0.05,
        },
        "regime_vix_baseline": {
            "bull_mode": "pcs_vix_optimal",
            "bear_mode": "ccs_baseline",
            "neutral_mode": "ccs_baseline",
            "allow_neutral_call_entries": True,
            "max_call_pct_above_ma50": 0.08,
        },
        "regime_legacy_defensive_bear_only": {
            "bull_mode": "legacy_replica",
            "bear_mode": "ccs_defensive",
            "neutral_mode": "ccs_defensive",
            "allow_neutral_call_entries": False,
            "max_call_pct_above_ma50": 0.05,
        },
        "regime_vix_baseline_bear_only": {
            "bull_mode": "pcs_vix_optimal",
            "bear_mode": "ccs_baseline",
            "neutral_mode": "ccs_baseline",
            "allow_neutral_call_entries": False,
            "max_call_pct_above_ma50": 0.08,
        },
    }
    def _timed_profile(
        *,
        take_profit_ratio: float,
        force_close_dte: int,
        risk_pct_scale: float,
        bear_only: bool = False,
    ) -> Dict[str, Any]:
        return {
            "bull_mode": "legacy_replica",
            "bear_mode": "ccs_defensive",
            "neutral_mode": "ccs_defensive",
            "allow_neutral_call_entries": not bear_only,
            "max_call_pct_above_ma50": 0.05,
            "timing_enabled": True,
            "timed_bear_only": bear_only,
            "take_profit_ratio_override": take_profit_ratio,
            "force_close_dte_override": force_close_dte,
            "risk_pct_scale": risk_pct_scale,
            "bull_pullback_return_min": -0.04,
            "bull_pullback_return_max": -0.0075,
            "bull_pullback_rsi_max": 50.0,
            "bear_rally_fade_return_min": 0.0075,
            "bear_rally_fade_return_max": 0.04,
            "bear_rally_fade_rsi_min": 55.0,
            "neutral_rally_fade_return_min": 0.01,
            "neutral_rally_fade_return_max": 0.045,
            "neutral_rally_fade_rsi_min": 58.0,
            "neutral_close_vs_ma20_min_pct": 0.01,
        }
    profiles.update(
        {
            "timed_legacy_defensive_40_7_r075": _timed_profile(
                take_profit_ratio=0.40,
                force_close_dte=7,
                risk_pct_scale=0.75,
            ),
            "timed_legacy_defensive_40_10_r100": _timed_profile(
                take_profit_ratio=0.40,
                force_close_dte=10,
                risk_pct_scale=1.00,
            ),
            "timed_legacy_defensive_50_10_r100": _timed_profile(
                take_profit_ratio=0.50,
                force_close_dte=10,
                risk_pct_scale=1.00,
            ),
            "timed_legacy_defensive_60_10_r100": _timed_profile(
                take_profit_ratio=0.60,
                force_close_dte=10,
                risk_pct_scale=1.00,
            ),
            "timed_legacy_defensive_50_14_r125": _timed_profile(
                take_profit_ratio=0.50,
                force_close_dte=14,
                risk_pct_scale=1.25,
            ),
            "timed_legacy_defensive_bear_only_40_10_r100": _timed_profile(
                take_profit_ratio=0.40,
                force_close_dte=10,
                risk_pct_scale=1.00,
                bear_only=True,
            ),
            "timed_legacy_defensive_bear_only_50_10_r100": _timed_profile(
                take_profit_ratio=0.50,
                force_close_dte=10,
                risk_pct_scale=1.00,
                bear_only=True,
            ),
            "timed_legacy_defensive_bear_only_50_7_r075": _timed_profile(
                take_profit_ratio=0.50,
                force_close_dte=7,
                risk_pct_scale=0.75,
                bear_only=True,
            ),
        }
    )
    if mode not in profiles:
        raise ValueError(f"Unsupported regime-credit-spread mode: {mode}")
    profile = copy.deepcopy(profiles[mode])
    defaults = {
        "timing_enabled": False,
        "timed_bear_only": False,
        "take_profit_ratio_override": None,
        "force_close_dte_override": None,
        "risk_pct_scale": 1.0,
        "bull_pullback_return_min": -0.04,
        "bull_pullback_return_max": -0.0075,
        "bull_pullback_rsi_max": 50.0,
        "bear_rally_fade_return_min": 0.0075,
        "bear_rally_fade_return_max": 0.04,
        "bear_rally_fade_rsi_min": 55.0,
        "neutral_rally_fade_return_min": 0.01,
        "neutral_rally_fade_return_max": 0.045,
        "neutral_rally_fade_rsi_min": 58.0,
        "neutral_close_vs_ma20_min_pct": 0.01,
    }
    for key, value in defaults.items():
        profile.setdefault(key, value)
    return profile


def _apply_regime_credit_overrides(base_params: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    params = copy.deepcopy(base_params)
    params["risk_pct"] = float(params["risk_pct"]) * float(profile.get("risk_pct_scale", 1.0))
    if profile.get("take_profit_ratio_override") is not None:
        params["take_profit_ratio"] = float(profile["take_profit_ratio_override"])
    if profile.get("force_close_dte_override") is not None:
        params["force_close_dte"] = float(profile["force_close_dte_override"])
    return params


def _credit_timing_signals(
    profile: Dict[str, Any],
    regime: str,
    ret3: float,
    rsi_val: float,
    px: float,
    ma20_val: float,
    ma50_val: float,
) -> Dict[str, bool]:
    if not (pd.notna(ret3) and pd.notna(rsi_val) and pd.notna(px) and pd.notna(ma20_val) and pd.notna(ma50_val)):
        return {
            "bull_pullback": False,
            "bear_rally_fade": False,
            "neutral_rally_fade": False,
        }

    bull_pullback = (
        regime == "bull"
        and float(profile["bull_pullback_return_min"]) <= float(ret3) <= float(profile["bull_pullback_return_max"])
        and float(rsi_val) <= float(profile["bull_pullback_rsi_max"])
        and float(px) >= float(ma50_val)
    )
    bear_rally_fade = (
        regime == "bear"
        and float(profile["bear_rally_fade_return_min"]) <= float(ret3) <= float(profile["bear_rally_fade_return_max"])
        and float(rsi_val) >= float(profile["bear_rally_fade_rsi_min"])
    )
    neutral_rally_fade = (
        regime == "neutral"
        and float(profile["neutral_rally_fade_return_min"]) <= float(ret3) <= float(profile["neutral_rally_fade_return_max"])
        and float(rsi_val) >= float(profile["neutral_rally_fade_rsi_min"])
        and float(px) >= (float(ma20_val) * (1.0 + float(profile["neutral_close_vs_ma20_min_pct"])))
    )
    return {
        "bull_pullback": bull_pullback,
        "bear_rally_fade": bear_rally_fade,
        "neutral_rally_fade": neutral_rally_fade,
    }


def _classify_credit_regime(
    px: float,
    ma20_val: float,
    ma50_val: float,
    ma200_val: float,
) -> str:
    if not all(pd.notna(v) and float(v) > 0 for v in (px, ma20_val, ma50_val, ma200_val)):
        return "unknown"
    if px > ma200_val and ma20_val > ma50_val:
        return "bull"
    if px < ma200_val and ma20_val < ma50_val:
        return "bear"
    return "neutral"


def _research_index_swing_params(mode: str) -> Dict[str, Any]:
    profiles: Dict[str, Dict[str, Any]] = {
        "pullback_baseline_30_45": {
            "debit_min_dte": 30,
            "debit_max_dte": 45,
            "debit_target_dte": 37,
            "max_debit_dollars": 1200.0,
            "take_profit_max_gain_ratio": 0.50,
            "stop_loss_debit_pct": 0.35,
            "force_close_dte": 10,
            "risk_pct": 0.0125,
            "max_contracts_per_symbol": 2,
            "max_concurrent_positions": 2,
            "pcs_mode": "legacy_replica",
            "ccs_mode": "ccs_baseline",
            "bull_pullback_return_min": -0.04,
            "bull_pullback_return_max": -0.0075,
            "bull_pullback_rsi_max": 48.0,
            "rally_fade_return_min": 0.0075,
            "rally_fade_return_max": 0.04,
            "rally_fade_rsi_min": 55.0,
            "neutral_overextended_min_pct": 0.01,
            "low_iv_max": 40.0,
            "pcs_iv_min": 40.0,
            "ccs_iv_min": 55.0,
            "allow_bull_overextension_ccs": False,
            "bull_overextended_min_pct_above_ma20": 0.03,
            "bull_overextended_min_pct_above_ma50": 0.02,
            "bull_ccs_iv_min": 65.0,
        },
        "pullback_defensive_30_45": {
            "debit_min_dte": 30,
            "debit_max_dte": 45,
            "debit_target_dte": 37,
            "max_debit_dollars": 900.0,
            "take_profit_max_gain_ratio": 0.40,
            "stop_loss_debit_pct": 0.25,
            "force_close_dte": 14,
            "risk_pct": 0.0090,
            "max_contracts_per_symbol": 2,
            "max_concurrent_positions": 2,
            "pcs_mode": "pcs_vix_optimal",
            "ccs_mode": "ccs_defensive",
            "bull_pullback_return_min": -0.04,
            "bull_pullback_return_max": -0.0075,
            "bull_pullback_rsi_max": 48.0,
            "rally_fade_return_min": 0.0075,
            "rally_fade_return_max": 0.04,
            "rally_fade_rsi_min": 55.0,
            "neutral_overextended_min_pct": 0.01,
            "low_iv_max": 40.0,
            "pcs_iv_min": 40.0,
            "ccs_iv_min": 55.0,
            "allow_bull_overextension_ccs": False,
            "bull_overextended_min_pct_above_ma20": 0.03,
            "bull_overextended_min_pct_above_ma50": 0.02,
            "bull_ccs_iv_min": 65.0,
        },
        "pullback_baseline_45_60": {
            "debit_min_dte": 45,
            "debit_max_dte": 60,
            "debit_target_dte": 52,
            "max_debit_dollars": 1200.0,
            "take_profit_max_gain_ratio": 0.50,
            "stop_loss_debit_pct": 0.35,
            "force_close_dte": 10,
            "risk_pct": 0.0125,
            "max_contracts_per_symbol": 2,
            "max_concurrent_positions": 2,
            "pcs_mode": "legacy_replica",
            "ccs_mode": "ccs_baseline",
            "bull_pullback_return_min": -0.04,
            "bull_pullback_return_max": -0.0075,
            "bull_pullback_rsi_max": 48.0,
            "rally_fade_return_min": 0.0075,
            "rally_fade_return_max": 0.04,
            "rally_fade_rsi_min": 55.0,
            "neutral_overextended_min_pct": 0.01,
            "low_iv_max": 40.0,
            "pcs_iv_min": 40.0,
            "ccs_iv_min": 55.0,
            "allow_bull_overextension_ccs": False,
            "bull_overextended_min_pct_above_ma20": 0.03,
            "bull_overextended_min_pct_above_ma50": 0.02,
            "bull_ccs_iv_min": 65.0,
        },
        "pullback_defensive_45_60": {
            "debit_min_dte": 45,
            "debit_max_dte": 60,
            "debit_target_dte": 52,
            "max_debit_dollars": 900.0,
            "take_profit_max_gain_ratio": 0.40,
            "stop_loss_debit_pct": 0.25,
            "force_close_dte": 14,
            "risk_pct": 0.0090,
            "max_contracts_per_symbol": 2,
            "max_concurrent_positions": 2,
            "pcs_mode": "pcs_vix_optimal",
            "ccs_mode": "ccs_defensive",
            "bull_pullback_return_min": -0.04,
            "bull_pullback_return_max": -0.0075,
            "bull_pullback_rsi_max": 48.0,
            "rally_fade_return_min": 0.0075,
            "rally_fade_return_max": 0.04,
            "rally_fade_rsi_min": 55.0,
            "neutral_overextended_min_pct": 0.01,
            "low_iv_max": 40.0,
            "pcs_iv_min": 40.0,
            "ccs_iv_min": 55.0,
            "allow_bull_overextension_ccs": False,
            "bull_overextended_min_pct_above_ma20": 0.03,
            "bull_overextended_min_pct_above_ma50": 0.02,
            "bull_ccs_iv_min": 65.0,
        },
        "pullback_baseline_30_45_v2": {
            "debit_min_dte": 30,
            "debit_max_dte": 45,
            "debit_target_dte": 37,
            "max_debit_dollars": 1200.0,
            "take_profit_max_gain_ratio": 0.50,
            "stop_loss_debit_pct": 0.35,
            "force_close_dte": 10,
            "risk_pct": 0.0125,
            "max_contracts_per_symbol": 2,
            "max_concurrent_positions": 2,
            "pcs_mode": "legacy_replica",
            "ccs_mode": "ccs_baseline",
            "bull_pullback_return_min": -0.06,
            "bull_pullback_return_max": -0.005,
            "bull_pullback_rsi_max": 52.0,
            "rally_fade_return_min": 0.005,
            "rally_fade_return_max": 0.05,
            "rally_fade_rsi_min": 52.0,
            "neutral_overextended_min_pct": 0.005,
            "low_iv_max": 25.0,
            "pcs_iv_min": 25.0,
            "ccs_iv_min": 45.0,
            "allow_bull_overextension_ccs": True,
            "bull_overextended_min_pct_above_ma20": 0.02,
            "bull_overextended_min_pct_above_ma50": 0.015,
            "bull_ccs_iv_min": 60.0,
        },
        "pullback_defensive_30_45_v2": {
            "debit_min_dte": 30,
            "debit_max_dte": 45,
            "debit_target_dte": 37,
            "max_debit_dollars": 900.0,
            "take_profit_max_gain_ratio": 0.40,
            "stop_loss_debit_pct": 0.25,
            "force_close_dte": 14,
            "risk_pct": 0.0090,
            "max_contracts_per_symbol": 2,
            "max_concurrent_positions": 2,
            "pcs_mode": "pcs_vix_optimal",
            "ccs_mode": "ccs_defensive",
            "bull_pullback_return_min": -0.06,
            "bull_pullback_return_max": -0.005,
            "bull_pullback_rsi_max": 52.0,
            "rally_fade_return_min": 0.005,
            "rally_fade_return_max": 0.05,
            "rally_fade_rsi_min": 52.0,
            "neutral_overextended_min_pct": 0.005,
            "low_iv_max": 25.0,
            "pcs_iv_min": 25.0,
            "ccs_iv_min": 45.0,
            "allow_bull_overextension_ccs": True,
            "bull_overextended_min_pct_above_ma20": 0.02,
            "bull_overextended_min_pct_above_ma50": 0.015,
            "bull_ccs_iv_min": 55.0,
        },
        "pullback_baseline_45_60_v2": {
            "debit_min_dte": 45,
            "debit_max_dte": 60,
            "debit_target_dte": 52,
            "max_debit_dollars": 1200.0,
            "take_profit_max_gain_ratio": 0.50,
            "stop_loss_debit_pct": 0.35,
            "force_close_dte": 10,
            "risk_pct": 0.0125,
            "max_contracts_per_symbol": 2,
            "max_concurrent_positions": 2,
            "pcs_mode": "legacy_replica",
            "ccs_mode": "ccs_baseline",
            "bull_pullback_return_min": -0.06,
            "bull_pullback_return_max": -0.005,
            "bull_pullback_rsi_max": 52.0,
            "rally_fade_return_min": 0.005,
            "rally_fade_return_max": 0.05,
            "rally_fade_rsi_min": 52.0,
            "neutral_overextended_min_pct": 0.005,
            "low_iv_max": 25.0,
            "pcs_iv_min": 25.0,
            "ccs_iv_min": 45.0,
            "allow_bull_overextension_ccs": True,
            "bull_overextended_min_pct_above_ma20": 0.02,
            "bull_overextended_min_pct_above_ma50": 0.015,
            "bull_ccs_iv_min": 60.0,
        },
        "pullback_defensive_45_60_v2": {
            "debit_min_dte": 45,
            "debit_max_dte": 60,
            "debit_target_dte": 52,
            "max_debit_dollars": 900.0,
            "take_profit_max_gain_ratio": 0.40,
            "stop_loss_debit_pct": 0.25,
            "force_close_dte": 14,
            "risk_pct": 0.0090,
            "max_contracts_per_symbol": 2,
            "max_concurrent_positions": 2,
            "pcs_mode": "pcs_vix_optimal",
            "ccs_mode": "ccs_defensive",
            "bull_pullback_return_min": -0.06,
            "bull_pullback_return_max": -0.005,
            "bull_pullback_rsi_max": 52.0,
            "rally_fade_return_min": 0.005,
            "rally_fade_return_max": 0.05,
            "rally_fade_rsi_min": 52.0,
            "neutral_overextended_min_pct": 0.005,
            "low_iv_max": 25.0,
            "pcs_iv_min": 25.0,
            "ccs_iv_min": 45.0,
            "allow_bull_overextension_ccs": True,
            "bull_overextended_min_pct_above_ma20": 0.02,
            "bull_overextended_min_pct_above_ma50": 0.015,
            "bull_ccs_iv_min": 55.0,
        },
    }
    if mode not in profiles:
        raise ValueError(f"Unsupported research-index-swing mode: {mode}")
    return profiles[mode]


def _classify_index_swing_regime(
    px: float,
    ma20_val: float,
    ma50_val: float,
    ma200_val: float,
) -> str:
    if not all(pd.notna(v) and float(v) > 0 for v in (px, ma20_val, ma50_val, ma200_val)):
        return "unknown"
    if px > ma200_val and ma20_val > ma50_val and px >= ma50_val:
        return "bull"
    if px < ma200_val and ma20_val < ma50_val:
        return "bear"
    return "neutral"


def _route_index_swing_structure(
    profile: Dict[str, Any],
    regime: str,
    bull_pullback_trigger: bool,
    rally_fade_trigger: bool,
    iv_percentile: float,
    neutral_overextended: bool = False,
    bull_overextended: bool = False,
) -> str:
    if pd.isna(iv_percentile):
        return "cash"
    low_iv_max = float(profile.get("low_iv_max", 40.0))
    pcs_iv_min = float(profile.get("pcs_iv_min", low_iv_max))
    ccs_iv_min = float(profile.get("ccs_iv_min", 55.0))
    bull_ccs_iv_min = float(profile.get("bull_ccs_iv_min", ccs_iv_min))
    if regime == "bull" and bull_pullback_trigger:
        return "bull_call_spread" if float(iv_percentile) < low_iv_max else (
            "put_credit_spread" if float(iv_percentile) >= pcs_iv_min else "cash"
        )
    if regime == "bear" and rally_fade_trigger and float(iv_percentile) >= ccs_iv_min:
        return "call_credit_spread"
    if (
        regime == "neutral"
        and rally_fade_trigger
        and neutral_overextended
        and float(iv_percentile) >= ccs_iv_min
    ):
        return "call_credit_spread"
    if (
        regime == "bull"
        and bool(profile.get("allow_bull_overextension_ccs", False))
        and rally_fade_trigger
        and bull_overextended
        and float(iv_percentile) >= bull_ccs_iv_min
    ):
        return "call_credit_spread"
    return "cash"


def _credit_spread_intrinsic(
    side: str,
    px: float,
    short_strike: float,
    long_strike: float,
    width: float,
) -> float:
    if side == "put":
        intrinsic = max(short_strike - px, 0.0) - max(long_strike - px, 0.0)
    else:
        intrinsic = max(px - short_strike, 0.0) - max(px - long_strike, 0.0)
    return min(max(intrinsic, 0.0), width)


def _credit_spread_adverse_move(side: str, px: float, entry_underlying: float) -> float:
    if entry_underlying <= 0:
        return 0.0
    raw_move = (px - entry_underlying) / entry_underlying
    return -raw_move if side == "put" else raw_move


def _credit_spread_active_value(
    pos: Dict[str, Any],
    px: float,
    hv_today: float,
    day: Any,
) -> float:
    intrinsic = _credit_spread_intrinsic(
        pos["side"],
        px,
        pos["short_strike"],
        pos["long_strike"],
        pos["width"],
    )
    dte_left = (pos["expiry_date"] - day).days
    time_ratio = max(min(dte_left / max(pos["dte_days"], 1), 1.0), 0.0)
    if pos["side"] == "put":
        if px >= pos["short_strike"]:
            spread_value = pos["credit"] * (0.5 * time_ratio)
        elif px <= pos["long_strike"]:
            spread_value = pos["width"] - (pos["credit"] * 0.1 * time_ratio)
        else:
            spread_value = intrinsic + (pos["credit"] * 0.4 * time_ratio)
    else:
        if px <= pos["short_strike"]:
            spread_value = pos["credit"] * (0.5 * time_ratio)
        elif px >= pos["long_strike"]:
            spread_value = pos["width"] - (pos["credit"] * 0.1 * time_ratio)
        else:
            spread_value = intrinsic + (pos["credit"] * 0.4 * time_ratio)

    vol_ratio = (hv_today / pos["entry_hv"]) if pos["entry_hv"] > 0 else 1.0
    adverse_move = _credit_spread_adverse_move(pos["side"], px, pos["entry_underlying"])
    spread_value += max(vol_ratio - 1.0, 0.0) * 0.25 * pos["width"]
    spread_value += max(adverse_move - (pos["short_dist_pct"] * 0.5), 0.0) * 3.0 * pos["width"]
    return min(max(spread_value, 0.0), pos["width"])


def _credit_spread_mark_value(
    pos: Dict[str, Any],
    px: float,
    hv_today: float,
    day: Any,
) -> float:
    intrinsic = _credit_spread_intrinsic(
        pos["side"],
        px,
        pos["short_strike"],
        pos["long_strike"],
        pos["width"],
    )
    dte_left = (pos["expiry_date"] - day).days
    time_ratio = max(min(dte_left / max(pos["dte_days"], 1), 1.0), 0.0)
    vol_ratio = (hv_today / pos["entry_hv"]) if pos["entry_hv"] > 0 else 1.0
    adverse_move = _credit_spread_adverse_move(pos["side"], px, pos["entry_underlying"])
    spread_value = intrinsic + (pos["credit"] * 0.3 * time_ratio)
    spread_value += max(vol_ratio - 1.0, 0.0) * 0.20 * pos["width"]
    spread_value += max(adverse_move - (pos["short_dist_pct"] * 0.5), 0.0) * 2.5 * pos["width"]
    return min(max(spread_value, 0.0), pos["width"])


def _credit_spread_period_end_value(pos: Dict[str, Any], px: float) -> float:
    if pos["side"] == "put":
        if px >= pos["short_strike"]:
            return 0.0
        if px <= pos["long_strike"]:
            return pos["width"]
        return pos["short_strike"] - px
    if px <= pos["short_strike"]:
        return 0.0
    if px >= pos["long_strike"]:
        return pos["width"]
    return px - pos["short_strike"]


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
    params = _call_credit_params(assumptions_mode)
    allowed_symbols = [str(s).upper() for s in params.get("allowed_symbols", ["SPY", "QQQ"])]
    prices = _build_underlying_close_frame(data, start_date, end_date, symbols=allowed_symbols)
    if prices.empty:
        raise ValueError(f"No price data available for openclaw_call_credit_spread ({allowed_symbols})")
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

        for symbol in allowed_symbols:
            if macro_blocked or kill_state.get("active"):
                continue
            if symbol not in prices.columns:
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
        universe=",".join(allowed_symbols),
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


def _run_openclaw_regime_credit_spread(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    assumptions_mode: str,
) -> EngineOutput:
    prices = _build_underlying_close_frame(data, start_date, end_date, symbols=["SPY", "QQQ"])
    if prices.empty:
        raise ValueError("No SPY/QQQ data available for openclaw_regime_credit_spread")

    profile = _regime_credit_params(assumptions_mode)
    bull_mode = str(profile["bull_mode"])
    bear_mode = str(profile["bear_mode"])
    neutral_mode = str(profile["neutral_mode"])
    bull_params = _apply_regime_credit_overrides(_put_credit_params(bull_mode), profile)
    bear_params = _apply_regime_credit_overrides(_call_credit_params(bear_mode), profile)
    neutral_params = _apply_regime_credit_overrides(_call_credit_params(neutral_mode), profile)
    timing_enabled = bool(profile.get("timing_enabled", False))
    timed_bear_only = bool(profile.get("timed_bear_only", False))
    allow_neutral_call_entries = bool(profile.get("allow_neutral_call_entries", True)) and not timed_bear_only
    max_call_pct_above_ma50 = float(profile.get("max_call_pct_above_ma50", 0.08))

    returns = prices.pct_change()
    returns_3d = prices.pct_change(3)
    hv20 = returns.rolling(20).std() * (252 ** 0.5)
    ma20 = prices.rolling(20).mean()
    ma50 = prices.rolling(50).mean()
    ma200 = prices.rolling(200).mean()
    rsi14 = _wilder_rsi_frame(prices, period=14)

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
    regime_counts = {"bull": 0, "bear": 0, "neutral": 0}
    entry_counts = {"put": 0, "call": 0}
    timing_signal_counts = {
        "bull_pullback": 0,
        "bear_rally_fade": 0,
        "neutral_rally_fade": 0,
    }
    timed_entry_counts = {"put": 0, "call": 0}

    all_days = list(prices.index)
    for day in all_days:
        day_prices = prices.loc[day]
        macro_blocked = macro_window_block(day.date() if hasattr(day, "date") else day, macro_events, 6)
        if macro_blocked:
            macro_block_days += 1

        realized_today = 0.0
        remaining_positions: List[Dict[str, Any]] = []

        for pos in open_positions:
            px = float(day_prices[pos["symbol"]])
            held_days = (day - pos["entry_date"]).days
            hv_today = (
                float(hv20.loc[day, pos["symbol"]])
                if pd.notna(hv20.loc[day, pos["symbol"]])
                else pos["entry_hv"]
            )
            spread_value = _credit_spread_active_value(pos, px, hv_today, day)
            pnl_per_contract = (pos["credit"] - spread_value) * 100.0
            unrealized = pnl_per_contract * pos["qty"]

            take_profit_hit = pnl_per_contract >= (pos["credit"] * 100.0 * pos["take_profit_ratio"])
            stop_hit = spread_value >= max((pos["credit"] * pos["stop_mult"]), (pos["width"] * 0.55))
            if pos["side"] == "put":
                breach = px <= pos["long_strike"]
            else:
                breach = px >= pos["long_strike"]
            dte_left = (pos["expiry_date"] - day).days
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
                fees = pos["fee_per_contract"] * pos["qty"]
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
                        "spread_side": pos["side"],
                        "entry_regime": pos["entry_regime"],
                        "profile_mode": pos["profile_mode"],
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
            if (
                pd.isna(ma200.loc[day, symbol])
                or pd.isna(ma50.loc[day, symbol])
                or pd.isna(ma20.loc[day, symbol])
                or pd.isna(hv20.loc[day, symbol])
            ):
                continue

            ma20_val = float(ma20.loc[day, symbol])
            ma50_val = float(ma50.loc[day, symbol])
            ma200_val = float(ma200.loc[day, symbol])
            regime = _classify_credit_regime(px, ma20_val, ma50_val, ma200_val)
            if regime == "unknown":
                continue
            regime_counts[regime] += 1
            ret3 = float(returns_3d.loc[day, symbol])
            rsi_val = float(rsi14.loc[day, symbol])
            timing_signals = _credit_timing_signals(
                profile=profile,
                regime=regime,
                ret3=ret3,
                rsi_val=rsi_val,
                px=px,
                ma20_val=ma20_val,
                ma50_val=ma50_val,
            )
            for key, value in timing_signals.items():
                if value:
                    timing_signal_counts[key] += 1

            params: Optional[Dict[str, Any]] = None
            side = ""
            profile_mode = ""
            if regime == "bull":
                side = "put"
                params = bull_params
                profile_mode = bull_mode
            elif regime == "bear":
                side = "call"
                params = bear_params
                profile_mode = bear_mode
            elif allow_neutral_call_entries:
                side = "call"
                params = neutral_params
                profile_mode = neutral_mode
            if not params:
                continue
            if timing_enabled:
                if side == "put" and not timing_signals["bull_pullback"]:
                    continue
                if side == "call" and regime == "bear" and not timing_signals["bear_rally_fade"]:
                    continue
                if side == "call" and regime == "neutral" and not timing_signals["neutral_rally_fade"]:
                    continue

            iv_proxy = float(hv20.loc[day, symbol])
            if not (float(params["iv_low"]) <= iv_proxy <= float(params["iv_high"])):
                continue

            if side == "put" and bool(params.get("vix_gate_enabled", False)):
                spy_hv = (
                    float(hv20.loc[day, "SPY"])
                    if "SPY" in hv20.columns and pd.notna(hv20.loc[day, "SPY"])
                    else iv_proxy
                )
                if spy_hv < float(params.get("vix_min_threshold", 0.0)):
                    continue
                if spy_hv > float(params.get("vix_max_threshold", 999.0)):
                    continue

            if side == "call" and pd.notna(ma50_val) and ma50_val > 0:
                pct_above_ma50 = (px - ma50_val) / ma50_val
                if pct_above_ma50 > max_call_pct_above_ma50:
                    continue

            short_dist_pct = float(params["short_dist_pct"])
            width_pct = float(params["width_pct"])
            credit_ratio = float(params["credit_ratio"])
            dte_days = int(params["dte_days"])
            take_profit_ratio = float(params["take_profit_ratio"])
            stop_mult = float(params["stop_mult"])
            min_hold_days = int(params["min_hold_days"])
            force_close_dte = int(params["force_close_dte"])
            fee_per_contract = float(params["fee_per_contract"])
            max_qty = int(params["max_qty"])
            target_annual_vol = float(params.get("target_annual_vol", 0.18))
            max_symbol_notional_pct = float(params.get("max_symbol_notional_pct", 0.20))

            short_strike = round(px * (1.0 - short_dist_pct), 2) if side == "put" else round(px * (1.0 + short_dist_pct), 2)
            width = round(max(px * width_pct, 1.0), 2)
            long_strike = round(short_strike - width, 2) if side == "put" else round(short_strike + width, 2)
            credit = round(width * credit_ratio, 2)

            max_loss_per_contract = max((width - credit) * 100.0, 1.0)
            qty_risk = int((cash * float(params["risk_pct"])) // max_loss_per_contract)
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
                    "side": side,
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
                    "short_dist_pct": short_dist_pct,
                    "fee_per_contract": fee_per_contract,
                    "entry_regime": regime,
                    "profile_mode": profile_mode,
                }
            )
            entry_counts[side] += 1
            if timing_enabled:
                timed_entry_counts[side] += 1

        end_unrealized = 0.0
        for pos in open_positions:
            px = float(day_prices[pos["symbol"]])
            hv_today = (
                float(hv20.loc[day, pos["symbol"]])
                if pd.notna(hv20.loc[day, pos["symbol"]])
                else pos["entry_hv"]
            )
            spread_value = _credit_spread_mark_value(pos, px, hv_today, day)
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
            spread_value = _credit_spread_period_end_value(pos, px)
            pnl_per_contract = (pos["credit"] - spread_value) * 100.0
            realized = (pnl_per_contract * pos["qty"]) - (pos["fee_per_contract"] * pos["qty"])
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
                    "spread_side": pos["side"],
                    "entry_regime": pos["entry_regime"],
                    "profile_mode": pos["profile_mode"],
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
    metrics["put_entries"] = int(entry_counts["put"])
    metrics["call_entries"] = int(entry_counts["call"])
    metrics["bullish_regime_days"] = int(regime_counts["bull"])
    metrics["bearish_regime_days"] = int(regime_counts["bear"])
    metrics["neutral_regime_days"] = int(regime_counts["neutral"])
    trade_pnls = [float(t.get("realized_pnl", 0.0)) for t in trades]

    closed_put_trades = sum(1 for t in trades if t.get("spread_side") == "put")
    closed_call_trades = sum(1 for t in trades if t.get("spread_side") == "call")
    component_metrics = {
        "bull_profile_mode": bull_mode,
        "bear_profile_mode": bear_mode,
        "neutral_profile_mode": neutral_mode,
        "allow_neutral_call_entries": allow_neutral_call_entries,
        "timing_enabled": timing_enabled,
        "timed_bear_only": timed_bear_only,
        "entry_counts": {
            "put": int(entry_counts["put"]),
            "call": int(entry_counts["call"]),
        },
        "timing_signal_counts": {
            "bull_pullback": int(timing_signal_counts["bull_pullback"]),
            "bear_rally_fade": int(timing_signal_counts["bear_rally_fade"]),
            "neutral_rally_fade": int(timing_signal_counts["neutral_rally_fade"]),
        },
        "timed_entry_counts": {
            "put": int(timed_entry_counts["put"]),
            "call": int(timed_entry_counts["call"]),
        },
        "closed_trade_counts": {
            "put": int(closed_put_trades),
            "call": int(closed_call_trades),
        },
        "regime_days": {
            "bull": int(regime_counts["bull"]),
            "bear": int(regime_counts["bear"]),
            "neutral": int(regime_counts["neutral"]),
        },
        "timing_thresholds": {
            "bull_pullback_return_min": float(profile["bull_pullback_return_min"]),
            "bull_pullback_return_max": float(profile["bull_pullback_return_max"]),
            "bull_pullback_rsi_max": float(profile["bull_pullback_rsi_max"]),
            "bear_rally_fade_return_min": float(profile["bear_rally_fade_return_min"]),
            "bear_rally_fade_return_max": float(profile["bear_rally_fade_return_max"]),
            "bear_rally_fade_rsi_min": float(profile["bear_rally_fade_rsi_min"]),
            "neutral_rally_fade_return_min": float(profile["neutral_rally_fade_return_min"]),
            "neutral_rally_fade_return_max": float(profile["neutral_rally_fade_return_max"]),
            "neutral_rally_fade_rsi_min": float(profile["neutral_rally_fade_rsi_min"]),
            "neutral_close_vs_ma20_min_pct": float(profile["neutral_close_vs_ma20_min_pct"]),
        },
        "management_overrides": {
            "take_profit_ratio_override": (
                None
                if profile.get("take_profit_ratio_override") is None
                else float(profile["take_profit_ratio_override"])
            ),
            "force_close_dte_override": (
                None
                if profile.get("force_close_dte_override") is None
                else int(profile["force_close_dte_override"])
            ),
            "risk_pct_scale": float(profile.get("risk_pct_scale", 1.0)),
        },
    }

    return EngineOutput(
        strategy_id="openclaw_regime_credit_spread",
        strategy_name="OpenClaw Regime Credit Spread",
        variant=assumptions_mode,
        engine_type="openclaw_regime_credit_spread_engine",
        assumptions_mode=assumptions_mode,
        universe="SPY,QQQ",
        strategy_parameters={
            "variant_profile": assumptions_mode,
            "bull_profile_mode": bull_mode,
            "bear_profile_mode": bear_mode,
            "neutral_profile_mode": neutral_mode,
            "allow_neutral_call_entries": allow_neutral_call_entries,
            "timing_enabled": timing_enabled,
            "timed_bear_only": timed_bear_only,
            "max_call_pct_above_ma50": max_call_pct_above_ma50,
            "bull_params": bull_params,
            "bear_params": bear_params,
            "neutral_params": neutral_params,
            "timing_thresholds": component_metrics["timing_thresholds"],
            "management_overrides": component_metrics["management_overrides"],
        },
        metrics=metrics,
        equity_curve=[float(v) for v in equity_curve],
        equity_points=equity_points,
        trade_pnls=trade_pnls,
        component_metrics=component_metrics,
    )


def _run_research_index_swing_options(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    assumptions_mode: str,
) -> EngineOutput:
    symbols = ["SPY", "QQQ"]
    frame = _prepare_option_research_frame(data, start_date, end_date, symbols=symbols)
    if frame.empty:
        raise ValueError("No SPY/QQQ option-chain data available for research_index_swing_options")

    prices = _build_underlying_close_frame(data, start_date, end_date, symbols=symbols)
    if prices.empty:
        raise ValueError("No SPY/QQQ price data available for research_index_swing_options")

    profile = _research_index_swing_params(assumptions_mode)
    pcs_mode = str(profile["pcs_mode"])
    ccs_mode = str(profile["ccs_mode"])
    pcs_params = _put_credit_params(pcs_mode)
    ccs_params = _call_credit_params(ccs_mode)

    returns_1d = prices.pct_change()
    returns_3d = prices.pct_change(3)
    hv20 = returns_1d.rolling(20).std() * (252 ** 0.5)
    ma20 = prices.rolling(20).mean()
    ma50 = prices.rolling(50).mean()
    ma200 = prices.rolling(200).mean()
    rsi14 = _wilder_rsi_frame(prices, period=14)
    iv_percentiles = {
        symbol: _build_daily_iv_percentile(
            frame,
            symbol,
            min_dte=int(profile["debit_min_dte"]),
            max_dte=int(profile["debit_max_dte"]),
            lookback_days=252,
        )
        for symbol in symbols
    }
    grouped = {d: g.copy() for d, g in frame.groupby("date")}

    initial_capital = 100_000.0
    cash = initial_capital
    open_positions: List[Dict[str, Any]] = []
    trades: List[Dict[str, Any]] = []
    equity_curve: List[float] = [initial_capital]
    equity_points: List[Tuple[date, float]] = []

    structure_entry_counts = {
        "bull_call_spread": 0,
        "put_credit_spread": 0,
        "call_credit_spread": 0,
    }
    closed_trade_counts = {
        "bull_call_spread": 0,
        "put_credit_spread": 0,
        "call_credit_spread": 0,
    }
    entry_counts_by_symbol = {symbol: 0 for symbol in symbols}
    regime_counts = {"bull": 0, "bear": 0, "neutral": 0}
    signal_counts = {"bull_pullback": 0, "rally_fade": 0}
    overextension_counts = {"neutral": 0, "bull": 0}
    entry_ivps: List[float] = []

    for day in prices.index:
        day_prices = prices.loc[day]
        day_slice = grouped.get(day, pd.DataFrame())
        realized_today = 0.0
        remaining_positions: List[Dict[str, Any]] = []

        for pos in open_positions:
            symbol = str(pos["symbol"])
            px = float(day_prices[symbol])
            held_days = (day - pos["entry_date"]).days
            dte_left = max((pos["expiry_date"] - day).days, 0)
            symbol_slice = day_slice[day_slice["underlying"] == symbol]

            should_close = False
            reason = "hold"
            realized = 0.0

            if pos["structure"] == "bull_call_spread":
                current_value = _bull_call_spread_close_value_dollars(pos, symbol_slice, day)
                take_profit_hit = (
                    current_value
                    >= pos["entry_debit_dollars"]
                    + (pos["max_gain_dollars"] * pos["take_profit_max_gain_ratio"])
                )
                stop_hit = current_value <= (
                    pos["entry_debit_dollars"] * (1.0 - pos["stop_loss_debit_pct"])
                )
                bearish_break = (
                    pd.notna(ma50.loc[day, symbol])
                    and (
                        px < float(ma50.loc[day, symbol])
                        or (
                            pd.notna(ma20.loc[day, symbol])
                            and float(ma20.loc[day, symbol]) < float(ma50.loc[day, symbol])
                        )
                    )
                )
                if take_profit_hit and held_days >= pos["min_hold_days"]:
                    should_close = True
                    reason = "take_profit"
                elif stop_hit:
                    should_close = True
                    reason = "stop_loss"
                elif bearish_break and held_days >= pos["min_hold_days"]:
                    should_close = True
                    reason = "trend_break"
                elif dte_left <= pos["force_close_dte"]:
                    should_close = True
                    reason = "time_exit"
                elif dte_left <= 0:
                    should_close = True
                    reason = "expiry"

                if should_close:
                    exit_fees = pos["exit_fee_per_spread"] * pos["qty"]
                    cash += (current_value * pos["qty"]) - exit_fees
                    realized = (
                        ((current_value - pos["entry_debit_dollars"]) * pos["qty"])
                        - pos["entry_fees_total"]
                        - exit_fees
                    )
                else:
                    remaining_positions.append(pos)
            else:
                hv_today = (
                    float(hv20.loc[day, symbol])
                    if pd.notna(hv20.loc[day, symbol])
                    else pos["entry_hv"]
                )
                spread_value = _credit_spread_active_value(pos, px, hv_today, day)
                pnl_per_contract = (pos["credit"] - spread_value) * 100.0
                take_profit_hit = pnl_per_contract >= (
                    pos["credit"] * 100.0 * pos["take_profit_ratio"]
                )
                stop_hit = spread_value >= max(
                    (pos["credit"] * pos["stop_mult"]),
                    (pos["width"] * 0.55),
                )
                if pos["side"] == "put":
                    breach = px <= pos["long_strike"]
                else:
                    breach = px >= pos["long_strike"]

                if take_profit_hit and held_days >= pos["min_hold_days"]:
                    should_close = True
                    reason = "take_profit"
                elif stop_hit:
                    should_close = True
                    reason = "stop_loss"
                elif breach:
                    should_close = True
                    reason = "long_strike_breach"
                elif dte_left <= pos["force_close_dte"]:
                    should_close = True
                    reason = "time_exit"
                elif dte_left <= 0:
                    should_close = True
                    reason = "expiry"

                if should_close:
                    exit_fees = pos["fee_per_contract"] * pos["qty"]
                    realized = (pnl_per_contract * pos["qty"]) - exit_fees
                    cash += realized
                else:
                    remaining_positions.append(pos)

            if should_close:
                closed_trade_counts[pos["structure"]] += 1
                trades.append(
                    {
                        "underlying": symbol,
                        "entry_date": pos["entry_date"].isoformat(),
                        "close_date": day.isoformat(),
                        "entry_price": round(pos["entry_price_display"], 4),
                        "close_price": round(
                            (current_value / 100.0)
                            if pos["structure"] == "bull_call_spread"
                            else spread_value,
                            4,
                        ),
                        "qty": int(pos["qty"]),
                        "realized_pnl": round(realized, 4),
                        "close_reason": reason,
                        "structure": pos["structure"],
                        "entry_regime": pos["entry_regime"],
                        "entry_iv_percentile": round(pos["entry_iv_percentile"], 4),
                    }
                )

        open_positions = remaining_positions

        current_symbols = {str(p["symbol"]) for p in open_positions}
        open_count = len(open_positions)
        for symbol in symbols:
            if open_count >= int(profile["max_concurrent_positions"]):
                break
            if symbol in current_symbols:
                continue
            px = float(day_prices[symbol])
            if not (pd.notna(px) and px > 0):
                continue
            if any(pd.isna(series.loc[day, symbol]) for series in (ma20, ma50, ma200, rsi14, returns_3d, hv20)):
                continue

            ma20_val = float(ma20.loc[day, symbol])
            ma50_val = float(ma50.loc[day, symbol])
            ma200_val = float(ma200.loc[day, symbol])
            regime = _classify_index_swing_regime(px, ma20_val, ma50_val, ma200_val)
            if regime == "unknown":
                continue
            regime_counts[regime] += 1

            ret3 = float(returns_3d.loc[day, symbol])
            rsi_val = float(rsi14.loc[day, symbol])
            bull_pullback = (
                float(profile["bull_pullback_return_min"]) <= ret3 <= float(profile["bull_pullback_return_max"])
            ) and (rsi_val <= float(profile["bull_pullback_rsi_max"]))
            neutral_overextended = (
                px >= (ma20_val * (1.0 + float(profile["neutral_overextended_min_pct"])))
                if ma20_val > 0
                else False
            )
            bull_overextended = (
                ma20_val > 0
                and ma50_val > 0
                and px >= (ma20_val * (1.0 + float(profile.get("bull_overextended_min_pct_above_ma20", 0.03))))
                and px >= (ma50_val * (1.0 + float(profile.get("bull_overextended_min_pct_above_ma50", 0.02))))
            )
            rally_fade = (
                float(profile["rally_fade_return_min"]) <= ret3 <= float(profile["rally_fade_return_max"])
            ) and (rsi_val >= float(profile["rally_fade_rsi_min"]))
            if regime == "neutral":
                rally_fade = rally_fade and neutral_overextended

            if bull_pullback:
                signal_counts["bull_pullback"] += 1
            if rally_fade:
                signal_counts["rally_fade"] += 1
            if neutral_overextended:
                overextension_counts["neutral"] += 1
            if bull_overextended:
                overextension_counts["bull"] += 1

            iv_series = iv_percentiles.get(symbol, pd.Series(dtype=float))
            iv_percentile = float(iv_series.get(day)) if day in iv_series.index else float("nan")
            structure = _route_index_swing_structure(
                profile=profile,
                regime=regime,
                bull_pullback_trigger=bull_pullback,
                rally_fade_trigger=rally_fade,
                iv_percentile=iv_percentile,
                neutral_overextended=neutral_overextended,
                bull_overextended=bull_overextended,
            )
            if structure == "cash":
                continue

            if structure == "bull_call_spread":
                symbol_slice = day_slice[day_slice["underlying"] == symbol]
                if symbol_slice.empty:
                    continue
                candidate = _select_bull_call_spread(
                    day_slice=symbol_slice,
                    underlying=symbol,
                    target_dte=int(profile["debit_target_dte"]),
                    min_dte=int(profile["debit_min_dte"]),
                    max_dte=int(profile["debit_max_dte"]),
                    target_long_delta=0.60,
                    min_long_delta=0.45,
                    max_long_delta=0.75,
                    target_short_delta=0.35,
                    min_short_delta=0.20,
                    max_short_delta=0.50,
                    min_debit_dollars=150.0,
                    max_debit_dollars=float(profile["max_debit_dollars"]),
                    max_spread_pct=0.12,
                    min_open_interest=200,
                )
                if candidate is None:
                    continue
                qty = int((cash * float(profile["risk_pct"])) // candidate["entry_debit_dollars"])
                qty = max(1, min(qty, int(profile["max_contracts_per_symbol"])))
                entry_fees_total = candidate["entry_fees_dollars"] * qty
                cash -= (candidate["entry_debit_dollars"] * qty) + entry_fees_total
                open_positions.append(
                    {
                        **candidate,
                        "symbol": symbol,
                        "structure": "bull_call_spread",
                        "entry_date": day,
                        "qty": qty,
                        "entry_regime": regime,
                        "entry_iv_percentile": iv_percentile,
                        "take_profit_max_gain_ratio": float(profile["take_profit_max_gain_ratio"]),
                        "stop_loss_debit_pct": float(profile["stop_loss_debit_pct"]),
                        "force_close_dte": int(profile["force_close_dte"]),
                        "min_hold_days": 3,
                        "exit_fee_per_spread": candidate["entry_fees_dollars"],
                        "entry_fees_total": entry_fees_total,
                        "entry_price_display": candidate["entry_debit_dollars"] / 100.0,
                    }
                )
            else:
                params = pcs_params if structure == "put_credit_spread" else ccs_params
                iv_proxy = float(hv20.loc[day, symbol])
                if not (float(params["iv_low"]) <= iv_proxy <= float(params["iv_high"])):
                    continue
                if structure == "put_credit_spread" and bool(params.get("vix_gate_enabled", False)):
                    spy_hv = (
                        float(hv20.loc[day, "SPY"])
                        if "SPY" in hv20.columns and pd.notna(hv20.loc[day, "SPY"])
                        else iv_proxy
                    )
                    if spy_hv < float(params.get("vix_min_threshold", 0.0)):
                        continue
                    if spy_hv > float(params.get("vix_max_threshold", 999.0)):
                        continue
                if structure == "call_credit_spread" and ma50_val > 0:
                    max_call_pct_above_ma50 = 0.05 if ccs_mode == "ccs_defensive" else 0.08
                    if ((px - ma50_val) / ma50_val) > max_call_pct_above_ma50:
                        continue

                short_dist_pct = float(params["short_dist_pct"])
                width_pct = float(params["width_pct"])
                credit_ratio = float(params["credit_ratio"])
                dte_days = int(params["dte_days"])
                short_strike = (
                    round(px * (1.0 - short_dist_pct), 2)
                    if structure == "put_credit_spread"
                    else round(px * (1.0 + short_dist_pct), 2)
                )
                width = round(max(px * width_pct, 1.0), 2)
                long_strike = (
                    round(short_strike - width, 2)
                    if structure == "put_credit_spread"
                    else round(short_strike + width, 2)
                )
                credit = round(width * credit_ratio, 2)
                max_loss_per_contract = max((width - credit) * 100.0, 1.0)
                qty_risk = int((cash * float(profile["risk_pct"])) // max_loss_per_contract)
                qty_vol = vol_target_contracts(
                    equity=cash,
                    option_price=max(credit, 0.25),
                    underlying_annual_vol=max(iv_proxy, 0.05),
                    target_annual_vol=float(params.get("target_annual_vol", 0.18)),
                    max_contracts=int(profile["max_contracts_per_symbol"]),
                )
                qty = max(1, min(qty_risk, qty_vol, int(profile["max_contracts_per_symbol"])))
                qty = cap_symbol_notional(
                    contracts=qty,
                    option_price=max(short_strike, px),
                    equity=cash,
                    max_symbol_notional_pct=float(params.get("max_symbol_notional_pct", 0.20)),
                )
                if qty < 1:
                    continue

                open_positions.append(
                    {
                        "symbol": symbol,
                        "structure": structure,
                        "side": "put" if structure == "put_credit_spread" else "call",
                        "entry_date": day,
                        "expiry_date": day + timedelta(days=dte_days),
                        "dte_days": dte_days,
                        "short_strike": short_strike,
                        "long_strike": long_strike,
                        "width": width,
                        "credit": credit,
                        "qty": qty,
                        "take_profit_ratio": float(params["take_profit_ratio"]),
                        "stop_mult": float(params["stop_mult"]),
                        "min_hold_days": int(params["min_hold_days"]),
                        "force_close_dte": int(params["force_close_dte"]),
                        "entry_underlying": px,
                        "entry_hv": iv_proxy,
                        "short_dist_pct": short_dist_pct,
                        "fee_per_contract": float(params["fee_per_contract"]),
                        "entry_regime": regime,
                        "entry_iv_percentile": iv_percentile,
                        "entry_price_display": credit,
                    }
                )

            open_count += 1
            current_symbols.add(symbol)
            entry_counts_by_symbol[symbol] += 1
            structure_entry_counts[structure] += 1
            entry_ivps.append(iv_percentile)

        unrealized_total = 0.0
        for pos in open_positions:
            symbol = str(pos["symbol"])
            px = float(day_prices[symbol])
            if pos["structure"] == "bull_call_spread":
                symbol_slice = day_slice[day_slice["underlying"] == symbol]
                unrealized_total += _bull_call_spread_close_value_dollars(pos, symbol_slice, day) * pos["qty"]
            else:
                hv_today = (
                    float(hv20.loc[day, symbol])
                    if pd.notna(hv20.loc[day, symbol])
                    else pos["entry_hv"]
                )
                spread_value = _credit_spread_mark_value(pos, px, hv_today, day)
                pnl_per_contract = (pos["credit"] - spread_value) * 100.0
                unrealized_total += pnl_per_contract * pos["qty"]

        equity = cash + unrealized_total
        equity_curve.append(float(equity))
        equity_points.append((day, float(equity)))

    if open_positions and equity_points:
        last_day = equity_points[-1][0]
        last_prices = prices.loc[last_day]
        day_slice = grouped.get(last_day, pd.DataFrame())
        for pos in open_positions:
            symbol = str(pos["symbol"])
            px = float(last_prices[symbol])
            if pos["structure"] == "bull_call_spread":
                symbol_slice = day_slice[day_slice["underlying"] == symbol]
                current_value = _bull_call_spread_close_value_dollars(pos, symbol_slice, last_day)
                exit_fees = pos["exit_fee_per_spread"] * pos["qty"]
                cash += (current_value * pos["qty"]) - exit_fees
                realized = (
                    ((current_value - pos["entry_debit_dollars"]) * pos["qty"])
                    - pos["entry_fees_total"]
                    - exit_fees
                )
                close_price = current_value / 100.0
            else:
                spread_value = _credit_spread_period_end_value(pos, px)
                realized = ((pos["credit"] - spread_value) * 100.0 * pos["qty"]) - (
                    pos["fee_per_contract"] * pos["qty"]
                )
                cash += realized
                close_price = spread_value
            closed_trade_counts[pos["structure"]] += 1
            trades.append(
                {
                    "underlying": symbol,
                    "entry_date": pos["entry_date"].isoformat(),
                    "close_date": last_day.isoformat(),
                    "entry_price": round(pos["entry_price_display"], 4),
                    "close_price": round(close_price, 4),
                    "qty": int(pos["qty"]),
                    "realized_pnl": round(realized, 4),
                    "close_reason": "period_end",
                    "structure": pos["structure"],
                    "entry_regime": pos["entry_regime"],
                    "entry_iv_percentile": round(pos["entry_iv_percentile"], 4),
                }
            )
        equity_curve[-1] = float(cash)
        equity_points[-1] = (last_day, float(cash))

    metrics = compute_metrics(trades, equity_curve)
    metrics["rolls_executed"] = 0
    metrics["trading_days"] = len(prices.index)
    metrics["bull_call_entries"] = int(structure_entry_counts["bull_call_spread"])
    metrics["put_entries"] = int(structure_entry_counts["put_credit_spread"])
    metrics["call_entries"] = int(structure_entry_counts["call_credit_spread"])
    metrics["avg_entry_iv_percentile"] = (
        round(sum(entry_ivps) / len(entry_ivps), 4) if entry_ivps else 0.0
    )

    trade_pnls = _closed_trade_pnls(trades)
    component_metrics = {
        "structure_entry_counts": {
            key: int(value) for key, value in structure_entry_counts.items()
        },
        "closed_trade_counts": {
            key: int(value) for key, value in closed_trade_counts.items()
        },
        "entry_counts_by_symbol": {
            key: int(value) for key, value in entry_counts_by_symbol.items()
        },
        "signal_counts": {key: int(value) for key, value in signal_counts.items()},
        "overextension_counts": {key: int(value) for key, value in overextension_counts.items()},
        "regime_days": {key: int(value) for key, value in regime_counts.items()},
        "pcs_mode": pcs_mode,
        "ccs_mode": ccs_mode,
        "debit_dte_range": [
            int(profile["debit_min_dte"]),
            int(profile["debit_max_dte"]),
        ],
        "routing_thresholds": {
            "low_iv_max": float(profile["low_iv_max"]),
            "pcs_iv_min": float(profile["pcs_iv_min"]),
            "ccs_iv_min": float(profile["ccs_iv_min"]),
            "bull_ccs_iv_min": float(profile["bull_ccs_iv_min"]),
            "bull_pullback_return_min": float(profile["bull_pullback_return_min"]),
            "bull_pullback_return_max": float(profile["bull_pullback_return_max"]),
            "bull_pullback_rsi_max": float(profile["bull_pullback_rsi_max"]),
            "rally_fade_return_min": float(profile["rally_fade_return_min"]),
            "rally_fade_return_max": float(profile["rally_fade_return_max"]),
            "rally_fade_rsi_min": float(profile["rally_fade_rsi_min"]),
            "neutral_overextended_min_pct": float(profile["neutral_overextended_min_pct"]),
            "allow_bull_overextension_ccs": bool(profile.get("allow_bull_overextension_ccs", False)),
        },
    }

    return EngineOutput(
        strategy_id="research_index_swing_options",
        strategy_name="Research Index Swing Options",
        variant=assumptions_mode,
        engine_type="research_index_swing_options_engine",
        assumptions_mode=assumptions_mode,
        universe="SPY,QQQ",
        strategy_parameters={
            "variant_profile": assumptions_mode,
            "universe": ["SPY", "QQQ"],
            "bull_pullback_3d_return_range": [
                float(profile["bull_pullback_return_min"]),
                float(profile["bull_pullback_return_max"]),
            ],
            "bull_pullback_rsi_max": float(profile["bull_pullback_rsi_max"]),
            "rally_fade_3d_return_range": [
                float(profile["rally_fade_return_min"]),
                float(profile["rally_fade_return_max"]),
            ],
            "rally_fade_rsi_min": float(profile["rally_fade_rsi_min"]),
            "neutral_overextended_min_pct": float(profile["neutral_overextended_min_pct"]),
            "bull_overextended_min_pct_above_ma20": float(
                profile.get("bull_overextended_min_pct_above_ma20", 0.03)
            ),
            "bull_overextended_min_pct_above_ma50": float(
                profile.get("bull_overextended_min_pct_above_ma50", 0.02)
            ),
            "iv_percentile_low_threshold": float(profile["low_iv_max"]),
            "iv_percentile_pcs_threshold": float(profile["pcs_iv_min"]),
            "iv_percentile_high_threshold": float(profile["ccs_iv_min"]),
            "iv_percentile_bull_ccs_threshold": float(profile["bull_ccs_iv_min"]),
            "debit_dte_range": [
                int(profile["debit_min_dte"]),
                int(profile["debit_max_dte"]),
            ],
            "debit_long_delta_target": 0.60,
            "debit_short_delta_target": 0.35,
            "debit_max_debit_dollars": float(profile["max_debit_dollars"]),
            "risk_pct_per_position": float(profile["risk_pct"]),
            "max_contracts_per_symbol": int(profile["max_contracts_per_symbol"]),
            "max_concurrent_positions": int(profile["max_concurrent_positions"]),
            "pcs_mode": pcs_mode,
            "ccs_mode": ccs_mode,
            "routing_thresholds": component_metrics["routing_thresholds"],
        },
        metrics=metrics,
        equity_curve=[float(v) for v in equity_curve],
        equity_points=equity_points,
        trade_pnls=trade_pnls,
        component_metrics=component_metrics,
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


def _run_research_small_account_options(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    assumptions_mode: str,
) -> EngineOutput:
    if assumptions_mode == "spy_iron_condor_proxy":
        return _run_research_spy_iron_condor_proxy(data, start_date, end_date)
    if assumptions_mode == "msft_bull_call_spread":
        return _run_research_msft_bull_call_spread(data, start_date, end_date)
    if assumptions_mode == "aapl_bull_put_45_21":
        return _run_research_aapl_bull_put_45_21(data, start_date, end_date)
    if assumptions_mode == "aapl_long_call_low_iv":
        return _run_research_aapl_long_call_low_iv(data, start_date, end_date)
    raise ValueError(
        f"Unsupported assumptions mode for research_small_account_options: {assumptions_mode}"
    )


def _run_research_spy_iron_condor_proxy(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> EngineOutput:
    frame = _prepare_option_research_frame(data, start_date, end_date, symbols=["SPY"])
    if frame.empty:
        raise ValueError("No SPY option-chain data available for research_small_account_options")

    prices = _build_underlying_close_frame(data, start_date, end_date, symbols=["SPY"])
    if prices.empty or "SPY" not in prices.columns:
        raise ValueError("No SPY price data available for research_small_account_options")

    close = prices["SPY"].astype(float).dropna()
    hv20 = close.pct_change().rolling(20).std() * (252 ** 0.5)
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    grouped = {d: g.copy() for d, g in frame.groupby("date")}

    initial_capital = 100_000.0
    cash = initial_capital
    equity_curve: List[float] = [initial_capital]
    equity_points: List[Tuple[date, float]] = []
    trades: List[Dict[str, Any]] = []
    position: Optional[Dict[str, Any]] = None
    entry_risks: List[float] = []
    entry_credits: List[float] = []

    fee_per_leg = 1.0
    target_profit_ratio = 0.50
    stop_loss_mult = 2.0
    force_close_dte = 21
    min_hold_days = 3

    for day in close.index:
        px = float(close.loc[day])
        day_slice = grouped.get(day, pd.DataFrame())

        if position is not None:
            current_close_cost = _condor_close_cost_dollars(position, day_slice, day)
            dte_left = max((position["expiry_date"] - day).days, 0)
            held_days = (day - position["entry_date"]).days
            take_profit_hit = (position["entry_credit_dollars"] - current_close_cost) >= (
                position["entry_credit_dollars"] * target_profit_ratio
            )
            stop_hit = current_close_cost >= (
                position["entry_credit_dollars"] * stop_loss_mult
            )
            breach = px <= position["short_put"]["strike"] or px >= position["short_call"]["strike"]
            time_exit = dte_left <= force_close_dte
            expiry_exit = dte_left <= 0

            should_close = False
            reason = "hold"
            if take_profit_hit and held_days >= min_hold_days:
                should_close = True
                reason = "take_profit"
            elif stop_hit:
                should_close = True
                reason = "stop_loss"
            elif breach:
                should_close = True
                reason = "short_strike_breach"
            elif time_exit:
                should_close = True
                reason = "time_exit"
            elif expiry_exit:
                should_close = True
                reason = "expiry"

            if should_close:
                exit_fees = fee_per_leg * 4.0
                cash -= current_close_cost + exit_fees
                realized = (
                    position["entry_credit_dollars"]
                    - current_close_cost
                    - position["entry_fees_dollars"]
                    - exit_fees
                )
                trades.append(
                    {
                        "underlying": "SPY",
                        "entry_date": position["entry_date"].isoformat(),
                        "close_date": day.isoformat(),
                        "entry_price": round(position["entry_credit_dollars"] / 100.0, 4),
                        "close_price": round(current_close_cost / 100.0, 4),
                        "qty": 1,
                        "realized_pnl": round(realized, 4),
                        "close_reason": reason,
                    }
                )
                position = None

        if position is None:
            hv_ok = pd.notna(hv20.loc[day]) and 0.08 <= float(hv20.loc[day]) <= 0.35
            trend_ok = pd.notna(ma20.loc[day]) and abs((px / max(float(ma20.loc[day]), 1e-6)) - 1.0) <= 0.05
            if hv_ok and trend_ok and not day_slice.empty:
                candidate = _select_spy_iron_condor_proxy(day_slice)
                if candidate is not None:
                    cash += candidate["entry_credit_dollars"] - candidate["entry_fees_dollars"]
                    position = {
                        **candidate,
                        "entry_date": day,
                    }
                    entry_risks.append(candidate["max_risk_dollars"])
                    entry_credits.append(candidate["entry_credit_dollars"])

        if position is None:
            equity = cash
        else:
            current_close_cost = _condor_close_cost_dollars(position, day_slice, day)
            equity = cash - current_close_cost

        equity_curve.append(float(equity))
        equity_points.append((day, float(equity)))

    if position is not None and equity_points:
        last_day = equity_points[-1][0]
        day_slice = grouped.get(last_day, pd.DataFrame())
        current_close_cost = _condor_close_cost_dollars(position, day_slice, last_day)
        exit_fees = fee_per_leg * 4.0
        cash -= current_close_cost + exit_fees
        realized = (
            position["entry_credit_dollars"]
            - current_close_cost
            - position["entry_fees_dollars"]
            - exit_fees
        )
        trades.append(
            {
                "underlying": "SPY",
                "entry_date": position["entry_date"].isoformat(),
                "close_date": last_day.isoformat(),
                "entry_price": round(position["entry_credit_dollars"] / 100.0, 4),
                "close_price": round(current_close_cost / 100.0, 4),
                "qty": 1,
                "realized_pnl": round(realized, 4),
                "close_reason": "period_end",
            }
        )
        equity_curve[-1] = float(cash)
        equity_points[-1] = (last_day, float(cash))

    metrics = compute_metrics(trades, equity_curve)
    metrics["rolls_executed"] = 0
    metrics["trading_days"] = len(close.index)
    metrics["avg_entry_credit"] = round(sum(entry_credits) / len(entry_credits), 4) if entry_credits else 0.0
    metrics["avg_max_risk"] = round(sum(entry_risks) / len(entry_risks), 4) if entry_risks else 0.0

    trade_pnls = _closed_trade_pnls(trades)
    component_metrics = {
        "structure": "iron_condor_proxy",
        "entries": len(entry_credits),
        "avg_entry_credit": round(sum(entry_credits) / len(entry_credits), 4) if entry_credits else 0.0,
        "avg_max_risk": round(sum(entry_risks) / len(entry_risks), 4) if entry_risks else 0.0,
    }

    return EngineOutput(
        strategy_id="research_small_account_options",
        strategy_name="Research Small Account Options",
        variant="spy_iron_condor_proxy",
        engine_type="research_small_account_options_engine",
        assumptions_mode="spy_iron_condor_proxy",
        universe="SPY",
        strategy_parameters={
            "structure": "iron_condor_proxy",
            "target_dte_range": [30, 60],
            "short_put_delta_range": [-0.25, -0.08],
            "short_call_delta_range": [0.08, 0.25],
            "max_risk_dollars": 1000.0,
            "fee_per_leg": fee_per_leg,
        },
        metrics=metrics,
        equity_curve=[float(v) for v in equity_curve],
        equity_points=equity_points,
        trade_pnls=trade_pnls,
        component_metrics=component_metrics,
    )


def _run_research_msft_bull_call_spread(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> EngineOutput:
    frame = _prepare_option_research_frame(data, start_date, end_date, symbols=["MSFT"])
    if frame.empty:
        raise ValueError("No MSFT option-chain data available for research_small_account_options")

    prices = _build_underlying_close_frame(data, start_date, end_date, symbols=["MSFT"])
    if prices.empty or "MSFT" not in prices.columns:
        raise ValueError("No MSFT price data available for research_small_account_options")

    close = prices["MSFT"].astype(float).dropna()
    hv20 = close.pct_change().rolling(20).std() * (252 ** 0.5)
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    grouped = {d: g.copy() for d, g in frame.groupby("date")}

    initial_capital = 100_000.0
    cash = initial_capital
    equity_curve: List[float] = [initial_capital]
    equity_points: List[Tuple[date, float]] = []
    trades: List[Dict[str, Any]] = []
    position: Optional[Dict[str, Any]] = None
    entry_debits: List[float] = []
    max_gains: List[float] = []

    fee_per_leg = 1.0
    force_close_dte = 14
    min_hold_days = 3

    for day in close.index:
        px = float(close.loc[day])
        day_slice = grouped.get(day, pd.DataFrame())

        if position is not None:
            current_value = _bull_call_spread_close_value_dollars(position, day_slice, day)
            dte_left = max((position["expiry_date"] - day).days, 0)
            held_days = (day - position["entry_date"]).days
            take_profit_hit = current_value >= (
                position["entry_debit_dollars"] + (position["max_gain_dollars"] * 0.60)
            )
            stop_hit = current_value <= (position["entry_debit_dollars"] * 0.55)
            bearish_break = (
                pd.notna(ma20.loc[day])
                and pd.notna(ma50.loc[day])
                and (
                    px < float(ma50.loc[day])
                    or float(ma20.loc[day]) < float(ma50.loc[day])
                )
            )
            time_exit = dte_left <= force_close_dte
            expiry_exit = dte_left <= 0

            should_close = False
            reason = "hold"
            if take_profit_hit and held_days >= min_hold_days:
                should_close = True
                reason = "take_profit"
            elif stop_hit:
                should_close = True
                reason = "stop_loss"
            elif bearish_break and held_days >= min_hold_days:
                should_close = True
                reason = "trend_break"
            elif time_exit:
                should_close = True
                reason = "time_exit"
            elif expiry_exit:
                should_close = True
                reason = "expiry"

            if should_close:
                exit_fees = fee_per_leg * 2.0
                cash += current_value - exit_fees
                realized = (
                    current_value
                    - position["entry_debit_dollars"]
                    - position["entry_fees_dollars"]
                    - exit_fees
                )
                trades.append(
                    {
                        "underlying": "MSFT",
                        "entry_date": position["entry_date"].isoformat(),
                        "close_date": day.isoformat(),
                        "entry_price": round(position["entry_debit_dollars"] / 100.0, 4),
                        "close_price": round(current_value / 100.0, 4),
                        "qty": 1,
                        "realized_pnl": round(realized, 4),
                        "close_reason": reason,
                    }
                )
                position = None

        if position is None:
            bullish_ok = (
                pd.notna(ma20.loc[day])
                and pd.notna(ma50.loc[day])
                and px > float(ma20.loc[day])
                and float(ma20.loc[day]) > float(ma50.loc[day])
            )
            hv_ok = pd.notna(hv20.loc[day]) and 0.08 <= float(hv20.loc[day]) <= 0.50
            if bullish_ok and hv_ok and not day_slice.empty:
                candidate = _select_msft_bull_call_spread(day_slice)
                if candidate is not None:
                    cash -= candidate["entry_debit_dollars"] + candidate["entry_fees_dollars"]
                    position = {
                        **candidate,
                        "entry_date": day,
                    }
                    entry_debits.append(candidate["entry_debit_dollars"])
                    max_gains.append(candidate["max_gain_dollars"])

        if position is None:
            equity = cash
        else:
            current_value = _bull_call_spread_close_value_dollars(position, day_slice, day)
            equity = cash + current_value

        equity_curve.append(float(equity))
        equity_points.append((day, float(equity)))

    if position is not None and equity_points:
        last_day = equity_points[-1][0]
        day_slice = grouped.get(last_day, pd.DataFrame())
        current_value = _bull_call_spread_close_value_dollars(position, day_slice, last_day)
        exit_fees = fee_per_leg * 2.0
        cash += current_value - exit_fees
        realized = (
            current_value
            - position["entry_debit_dollars"]
            - position["entry_fees_dollars"]
            - exit_fees
        )
        trades.append(
            {
                "underlying": "MSFT",
                "entry_date": position["entry_date"].isoformat(),
                "close_date": last_day.isoformat(),
                "entry_price": round(position["entry_debit_dollars"] / 100.0, 4),
                "close_price": round(current_value / 100.0, 4),
                "qty": 1,
                "realized_pnl": round(realized, 4),
                "close_reason": "period_end",
            }
        )
        equity_curve[-1] = float(cash)
        equity_points[-1] = (last_day, float(cash))

    metrics = compute_metrics(trades, equity_curve)
    metrics["rolls_executed"] = 0
    metrics["trading_days"] = len(close.index)
    metrics["avg_entry_debit"] = round(sum(entry_debits) / len(entry_debits), 4) if entry_debits else 0.0
    metrics["avg_max_gain"] = round(sum(max_gains) / len(max_gains), 4) if max_gains else 0.0

    trade_pnls = _closed_trade_pnls(trades)
    component_metrics = {
        "structure": "bull_call_spread",
        "entries": len(entry_debits),
        "avg_entry_debit": round(sum(entry_debits) / len(entry_debits), 4) if entry_debits else 0.0,
        "avg_max_gain": round(sum(max_gains) / len(max_gains), 4) if max_gains else 0.0,
    }

    return EngineOutput(
        strategy_id="research_small_account_options",
        strategy_name="Research Small Account Options",
        variant="msft_bull_call_spread",
        engine_type="research_small_account_options_engine",
        assumptions_mode="msft_bull_call_spread",
        universe="MSFT",
        strategy_parameters={
            "structure": "bull_call_spread",
            "target_dte_range": [30, 60],
            "long_delta_range": [0.50, 0.75],
            "short_delta_range": [0.20, 0.45],
            "max_debit_dollars": 1000.0,
            "fee_per_leg": fee_per_leg,
        },
        metrics=metrics,
        equity_curve=[float(v) for v in equity_curve],
        equity_points=equity_points,
        trade_pnls=trade_pnls,
        component_metrics=component_metrics,
    )


def _run_research_aapl_bull_put_45_21(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> EngineOutput:
    frame = _prepare_option_research_frame(data, start_date, end_date, symbols=["AAPL"])
    if frame.empty:
        raise ValueError("No AAPL option-chain data available for research_small_account_options")

    prices = _build_underlying_close_frame(data, start_date, end_date, symbols=["AAPL"])
    if prices.empty or "AAPL" not in prices.columns:
        raise ValueError("No AAPL price data available for research_small_account_options")

    close = prices["AAPL"].astype(float).dropna()
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    prior_20d_low = close.shift(1).rolling(20, min_periods=20).min()
    iv_percentile = _build_daily_iv_percentile(frame, "AAPL", min_dte=30, max_dte=60, lookback_days=252)
    grouped = {d: g.copy() for d, g in frame.groupby("date")}

    initial_capital = 100_000.0
    cash = initial_capital
    equity_curve: List[float] = [initial_capital]
    equity_points: List[Tuple[date, float]] = []
    trades: List[Dict[str, Any]] = []
    position: Optional[Dict[str, Any]] = None
    entry_credits: List[float] = []
    entry_risks: List[float] = []
    entry_ivps: List[float] = []
    entry_pops: List[float] = []

    fee_per_leg = 1.0
    stop_loss_mult = 2.0
    force_close_dte = 21
    min_hold_days = 3

    for day in close.index:
        px = float(close.loc[day])
        day_slice = grouped.get(day, pd.DataFrame())

        if position is not None:
            current_close_cost = _bull_put_spread_close_cost_dollars(position, day_slice, day)
            dte_left = max((position["expiry_date"] - day).days, 0)
            held_days = (day - position["entry_date"]).days
            trend_break = (
                held_days >= min_hold_days
                and pd.notna(ma50.loc[day])
                and px < float(ma50.loc[day])
            )
            stop_hit = current_close_cost >= (position["entry_credit_dollars"] * stop_loss_mult)
            breach = px <= position["short_put"]["strike"]
            time_exit = dte_left <= force_close_dte
            expiry_exit = dte_left <= 0

            should_close = False
            reason = "hold"
            if stop_hit:
                should_close = True
                reason = "stop_loss"
            elif breach:
                should_close = True
                reason = "short_strike_breach"
            elif trend_break:
                should_close = True
                reason = "trend_break"
            elif time_exit:
                should_close = True
                reason = "time_exit"
            elif expiry_exit:
                should_close = True
                reason = "expiry"

            if should_close:
                exit_fees = fee_per_leg * 2.0
                cash -= current_close_cost + exit_fees
                realized = (
                    position["entry_credit_dollars"]
                    - current_close_cost
                    - position["entry_fees_dollars"]
                    - exit_fees
                )
                trades.append(
                    {
                        "underlying": "AAPL",
                        "entry_date": position["entry_date"].isoformat(),
                        "close_date": day.isoformat(),
                        "entry_price": round(position["entry_credit_dollars"] / 100.0, 4),
                        "close_price": round(current_close_cost / 100.0, 4),
                        "qty": 1,
                        "realized_pnl": round(realized, 4),
                        "close_reason": reason,
                    }
                )
                position = None

        if position is None:
            day_ivp = float(iv_percentile.get(day)) if day in iv_percentile.index else float("nan")
            bullish_ok = (
                pd.notna(ma20.loc[day])
                and pd.notna(ma50.loc[day])
                and pd.notna(ma200.loc[day])
                and px > float(ma50.loc[day])
                and float(ma20.loc[day]) > float(ma50.loc[day])
                and px > float(ma200.loc[day])
            )
            support_floor = float("nan")
            if pd.notna(ma50.loc[day]) and pd.notna(prior_20d_low.loc[day]):
                support_floor = max(float(ma50.loc[day]), float(prior_20d_low.loc[day]))
            iv_ok = pd.notna(day_ivp) and day_ivp >= 65.0

            if bullish_ok and iv_ok and pd.notna(support_floor) and not day_slice.empty:
                candidate = _select_bull_put_spread(
                    day_slice,
                    underlying="AAPL",
                    support_floor=float(support_floor),
                    target_dte=45,
                    min_dte=38,
                    max_dte=52,
                    target_delta=-0.27,
                    min_delta=-0.40,
                    max_delta=-0.15,
                    min_pop_pct=65.0,
                    min_credit_dollars=45.0,
                    max_risk_dollars=1000.0,
                )
                if candidate is not None:
                    cash += candidate["entry_credit_dollars"] - candidate["entry_fees_dollars"]
                    position = {**candidate, "entry_date": day}
                    entry_credits.append(candidate["entry_credit_dollars"])
                    entry_risks.append(candidate["max_risk_dollars"])
                    entry_ivps.append(day_ivp)
                    entry_pops.append(candidate["theoretical_pop_pct"])

        if position is None:
            equity = cash
        else:
            current_close_cost = _bull_put_spread_close_cost_dollars(position, day_slice, day)
            equity = cash - current_close_cost

        equity_curve.append(float(equity))
        equity_points.append((day, float(equity)))

    if position is not None and equity_points:
        last_day = equity_points[-1][0]
        day_slice = grouped.get(last_day, pd.DataFrame())
        current_close_cost = _bull_put_spread_close_cost_dollars(position, day_slice, last_day)
        exit_fees = fee_per_leg * 2.0
        cash -= current_close_cost + exit_fees
        realized = (
            position["entry_credit_dollars"]
            - current_close_cost
            - position["entry_fees_dollars"]
            - exit_fees
        )
        trades.append(
            {
                "underlying": "AAPL",
                "entry_date": position["entry_date"].isoformat(),
                "close_date": last_day.isoformat(),
                "entry_price": round(position["entry_credit_dollars"] / 100.0, 4),
                "close_price": round(current_close_cost / 100.0, 4),
                "qty": 1,
                "realized_pnl": round(realized, 4),
                "close_reason": "period_end",
            }
        )
        equity_curve[-1] = float(cash)
        equity_points[-1] = (last_day, float(cash))

    metrics = compute_metrics(trades, equity_curve)
    metrics["rolls_executed"] = 0
    metrics["trading_days"] = len(close.index)
    metrics["avg_entry_credit"] = round(sum(entry_credits) / len(entry_credits), 4) if entry_credits else 0.0
    metrics["avg_max_risk"] = round(sum(entry_risks) / len(entry_risks), 4) if entry_risks else 0.0
    metrics["avg_entry_iv_percentile"] = round(sum(entry_ivps) / len(entry_ivps), 4) if entry_ivps else 0.0
    metrics["avg_theoretical_pop_pct"] = round(sum(entry_pops) / len(entry_pops), 4) if entry_pops else 0.0

    trade_pnls = _closed_trade_pnls(trades)
    component_metrics = {
        "structure": "bull_put_spread",
        "entries": len(entry_credits),
        "avg_entry_credit": round(sum(entry_credits) / len(entry_credits), 4) if entry_credits else 0.0,
        "avg_max_risk": round(sum(entry_risks) / len(entry_risks), 4) if entry_risks else 0.0,
        "avg_entry_iv_percentile": round(sum(entry_ivps) / len(entry_ivps), 4) if entry_ivps else 0.0,
        "avg_theoretical_pop_pct": round(sum(entry_pops) / len(entry_pops), 4) if entry_pops else 0.0,
        "entry_rule": "45DTE entry, 21DTE exit, high-IV seller, support-aware short strike",
    }

    return EngineOutput(
        strategy_id="research_small_account_options",
        strategy_name="Research Small Account Options",
        variant="aapl_bull_put_45_21",
        engine_type="research_small_account_options_engine",
        assumptions_mode="aapl_bull_put_45_21",
        universe="AAPL",
        strategy_parameters={
            "structure": "bull_put_spread",
            "target_dte_range": [38, 52],
            "exit_dte": 21,
            "short_put_delta_range": [-0.40, -0.15],
            "target_short_put_delta": -0.27,
            "iv_percentile_min": 65.0,
            "support_reference": "max(ma50, prior_20d_low)",
            "max_risk_dollars": 1000.0,
            "fee_per_leg": fee_per_leg,
        },
        metrics=metrics,
        equity_curve=[float(v) for v in equity_curve],
        equity_points=equity_points,
        trade_pnls=trade_pnls,
        component_metrics=component_metrics,
    )


def _run_research_aapl_long_call_low_iv(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> EngineOutput:
    frame = _prepare_option_research_frame(data, start_date, end_date, symbols=["AAPL"])
    if frame.empty:
        raise ValueError("No AAPL option-chain data available for research_small_account_options")

    prices = _build_underlying_close_frame(data, start_date, end_date, symbols=["AAPL"])
    if prices.empty or "AAPL" not in prices.columns:
        raise ValueError("No AAPL price data available for research_small_account_options")

    close = prices["AAPL"].astype(float).dropna()
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    iv_percentile = _build_daily_iv_percentile(frame, "AAPL", min_dte=30, max_dte=60, lookback_days=252)
    grouped = {d: g.copy() for d, g in frame.groupby("date")}

    initial_capital = 100_000.0
    cash = initial_capital
    equity_curve: List[float] = [initial_capital]
    equity_points: List[Tuple[date, float]] = []
    trades: List[Dict[str, Any]] = []
    position: Optional[Dict[str, Any]] = None
    entry_debits: List[float] = []
    entry_ivps: List[float] = []
    entry_deltas: List[float] = []

    fee_per_leg = 1.0
    stop_loss_ratio = 0.55
    force_close_dte = 21
    min_hold_days = 3

    for day in close.index:
        px = float(close.loc[day])
        day_slice = grouped.get(day, pd.DataFrame())

        if position is not None:
            current_value = _long_option_close_value_dollars(position, day_slice, day, leg_key="long_call")
            dte_left = max((position["expiry_date"] - day).days, 0)
            held_days = (day - position["entry_date"]).days
            bearish_break = (
                held_days >= min_hold_days
                and pd.notna(ma50.loc[day])
                and (
                    px < float(ma50.loc[day])
                    or (pd.notna(ma20.loc[day]) and float(ma20.loc[day]) < float(ma50.loc[day]))
                )
            )
            stop_hit = current_value <= (position["entry_debit_dollars"] * stop_loss_ratio)
            time_exit = dte_left <= force_close_dte
            expiry_exit = dte_left <= 0

            should_close = False
            reason = "hold"
            if stop_hit:
                should_close = True
                reason = "stop_loss"
            elif bearish_break:
                should_close = True
                reason = "trend_break"
            elif time_exit:
                should_close = True
                reason = "time_exit"
            elif expiry_exit:
                should_close = True
                reason = "expiry"

            if should_close:
                exit_fees = fee_per_leg
                cash += current_value - exit_fees
                realized = (
                    current_value
                    - position["entry_debit_dollars"]
                    - position["entry_fees_dollars"]
                    - exit_fees
                )
                trades.append(
                    {
                        "underlying": "AAPL",
                        "entry_date": position["entry_date"].isoformat(),
                        "close_date": day.isoformat(),
                        "entry_price": round(position["entry_debit_dollars"] / 100.0, 4),
                        "close_price": round(current_value / 100.0, 4),
                        "qty": 1,
                        "realized_pnl": round(realized, 4),
                        "close_reason": reason,
                    }
                )
                position = None

        if position is None:
            day_ivp = float(iv_percentile.get(day)) if day in iv_percentile.index else float("nan")
            bullish_ok = (
                pd.notna(ma20.loc[day])
                and pd.notna(ma50.loc[day])
                and pd.notna(ma200.loc[day])
                and px > float(ma20.loc[day])
                and float(ma20.loc[day]) > float(ma50.loc[day])
                and px > float(ma200.loc[day])
            )
            iv_ok = pd.notna(day_ivp) and day_ivp <= 35.0

            if bullish_ok and iv_ok and not day_slice.empty:
                candidate = _select_long_call(
                    day_slice,
                    underlying="AAPL",
                    target_dte=45,
                    min_dte=38,
                    max_dte=52,
                    target_delta=0.60,
                    min_delta=0.45,
                    max_delta=0.75,
                    min_debit_dollars=100.0,
                    max_debit_dollars=1000.0,
                )
                if candidate is not None:
                    cash -= candidate["entry_debit_dollars"] + candidate["entry_fees_dollars"]
                    position = {**candidate, "entry_date": day}
                    entry_debits.append(candidate["entry_debit_dollars"])
                    entry_ivps.append(day_ivp)
                    entry_delta = candidate["long_call"].get("entry_delta")
                    if entry_delta is not None:
                        entry_deltas.append(float(entry_delta))

        if position is None:
            equity = cash
        else:
            current_value = _long_option_close_value_dollars(position, day_slice, day, leg_key="long_call")
            equity = cash + current_value

        equity_curve.append(float(equity))
        equity_points.append((day, float(equity)))

    if position is not None and equity_points:
        last_day = equity_points[-1][0]
        day_slice = grouped.get(last_day, pd.DataFrame())
        current_value = _long_option_close_value_dollars(position, day_slice, last_day, leg_key="long_call")
        exit_fees = fee_per_leg
        cash += current_value - exit_fees
        realized = (
            current_value
            - position["entry_debit_dollars"]
            - position["entry_fees_dollars"]
            - exit_fees
        )
        trades.append(
            {
                "underlying": "AAPL",
                "entry_date": position["entry_date"].isoformat(),
                "close_date": last_day.isoformat(),
                "entry_price": round(position["entry_debit_dollars"] / 100.0, 4),
                "close_price": round(current_value / 100.0, 4),
                "qty": 1,
                "realized_pnl": round(realized, 4),
                "close_reason": "period_end",
            }
        )
        equity_curve[-1] = float(cash)
        equity_points[-1] = (last_day, float(cash))

    metrics = compute_metrics(trades, equity_curve)
    metrics["rolls_executed"] = 0
    metrics["trading_days"] = len(close.index)
    metrics["avg_entry_debit"] = round(sum(entry_debits) / len(entry_debits), 4) if entry_debits else 0.0
    metrics["avg_entry_iv_percentile"] = round(sum(entry_ivps) / len(entry_ivps), 4) if entry_ivps else 0.0
    metrics["avg_entry_delta"] = round(sum(entry_deltas) / len(entry_deltas), 4) if entry_deltas else 0.0

    trade_pnls = _closed_trade_pnls(trades)
    component_metrics = {
        "structure": "long_call",
        "entries": len(entry_debits),
        "avg_entry_debit": round(sum(entry_debits) / len(entry_debits), 4) if entry_debits else 0.0,
        "avg_entry_iv_percentile": round(sum(entry_ivps) / len(entry_ivps), 4) if entry_ivps else 0.0,
        "avg_entry_delta": round(sum(entry_deltas) / len(entry_deltas), 4) if entry_deltas else 0.0,
        "entry_rule": "45DTE entry, 21DTE exit, low-IV buyer",
    }

    return EngineOutput(
        strategy_id="research_small_account_options",
        strategy_name="Research Small Account Options",
        variant="aapl_long_call_low_iv",
        engine_type="research_small_account_options_engine",
        assumptions_mode="aapl_long_call_low_iv",
        universe="AAPL",
        strategy_parameters={
            "structure": "long_call",
            "target_dte_range": [38, 52],
            "exit_dte": 21,
            "target_delta": 0.60,
            "delta_range": [0.45, 0.75],
            "iv_percentile_max": 35.0,
            "max_debit_dollars": 1000.0,
            "fee_per_leg": fee_per_leg,
        },
        metrics=metrics,
        equity_curve=[float(v) for v in equity_curve],
        equity_points=equity_points,
        trade_pnls=trade_pnls,
        component_metrics=component_metrics,
    )


def _prepare_option_research_frame(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    symbols: List[str],
) -> pd.DataFrame:
    required = {
        "date",
        "underlying",
        "contract_symbol",
        "option_type",
        "strike",
        "expiration_date",
        "dte",
        "bid",
        "ask",
        "delta",
        "underlying_price",
    }
    if not required.issubset(set(data.columns)):
        return pd.DataFrame()

    cols = [
        "date",
        "underlying",
        "contract_symbol",
        "option_type",
        "strike",
        "expiration_date",
        "dte",
        "bid",
        "ask",
        "delta",
        "underlying_price",
    ]
    for optional in ("implied_volatility", "spread_pct", "open_interest"):
        if optional in data.columns:
            cols.append(optional)
    dates = pd.to_datetime(data["date"]).dt.date
    mask = data["underlying"].isin(symbols) & (dates >= start_date) & (dates <= end_date)
    if not bool(mask.any()):
        return pd.DataFrame()

    # Build the filtered frame one column at a time to avoid a large temporary
    # block allocation when pandas slices both rows and columns on the full cache.
    row_idx = np.flatnonzero(mask.to_numpy())
    frame = pd.DataFrame(
        {
            col: data[col].to_numpy(copy=False)[row_idx]
            for col in cols
        }
    )
    if frame.empty:
        return pd.DataFrame()
    frame["date"] = dates.to_numpy(copy=False)[row_idx]
    frame["expiration_date"] = pd.to_datetime(frame["expiration_date"]).dt.date

    numeric_cols = [
        "strike",
        "dte",
        "bid",
        "ask",
        "delta",
        "underlying_price",
        "implied_volatility",
        "spread_pct",
    ]
    for col in numeric_cols:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(
        subset=[
            "date",
            "underlying",
            "contract_symbol",
            "option_type",
            "strike",
            "expiration_date",
            "dte",
            "bid",
            "ask",
            "delta",
            "underlying_price",
        ]
    )
    frame = frame[(frame["ask"] > 0.0) & (frame["bid"] >= 0.0)]
    return frame.sort_values(
        ["date", "underlying", "expiration_date", "option_type", "strike"]
    )


def _pick_closest_delta_contract(
    chain: pd.DataFrame,
    target_delta: float,
    min_delta: float,
    max_delta: float,
) -> Optional[pd.Series]:
    if chain.empty:
        return None
    subset = chain[(chain["delta"] >= min_delta) & (chain["delta"] <= max_delta)].copy()
    if subset.empty:
        return None
    if "spread_pct" in subset.columns:
        subset["_spread_rank"] = subset["spread_pct"].fillna(999.0)
    else:
        subset["_spread_rank"] = 999.0
    subset["_delta_gap"] = (subset["delta"] - target_delta).abs()
    subset = subset.sort_values(["_delta_gap", "_spread_rank", "ask", "strike"])
    return subset.iloc[0]


def _build_option_leg(row: pd.Series) -> Dict[str, Any]:
    bid = float(row["bid"])
    ask = float(row["ask"])
    mid = (bid + ask) / 2.0
    spot = float(row["underlying_price"])
    strike = float(row["strike"])
    option_type = str(row["option_type"]).lower()
    if option_type == "put":
        intrinsic = max(strike - spot, 0.0)
    else:
        intrinsic = max(spot - strike, 0.0)
    time_value0 = max(mid - intrinsic, 0.0)
    return {
        "contract_symbol": str(row["contract_symbol"]),
        "underlying": str(row["underlying"]),
        "option_type": option_type,
        "strike": strike,
        "expiration_date": row["expiration_date"],
        "dte_days": int(float(row["dte"])),
        "entry_underlying": spot,
        "time_value0": time_value0,
        "entry_delta": float(row["delta"]) if pd.notna(row.get("delta")) else None,
    }


def _lookup_leg_close_price(
    day_slice: pd.DataFrame,
    leg: Dict[str, Any],
    day: date,
    side: str,
) -> float:
    if not day_slice.empty and "contract_symbol" in day_slice.columns:
        match = day_slice[day_slice["contract_symbol"] == leg["contract_symbol"]]
        if match.empty:
            required_cols = {"underlying", "option_type", "expiration_date", "strike"}
            if required_cols.issubset(set(day_slice.columns)):
                match = day_slice[
                    (day_slice["underlying"] == leg["underlying"])
                    & (day_slice["option_type"].astype(str).str.lower() == leg["option_type"])
                    & (day_slice["expiration_date"] == leg["expiration_date"])
                    & (day_slice["strike"] == leg["strike"])
                ]
        if not match.empty:
            row = match.iloc[0]
            if side == "sell":
                return max(float(row["bid"]), 0.01)
            return max(float(row["ask"]), 0.01)

    px = float(leg.get("entry_underlying", 0.0))
    if not day_slice.empty and "underlying_price" in day_slice.columns:
        try:
            px = float(day_slice["underlying_price"].iloc[0])
        except (TypeError, ValueError, IndexError):
            px = float(leg.get("entry_underlying", 0.0))
    dte_left = max((leg["expiration_date"] - day).days, 0)
    if leg["option_type"] == "put":
        mid = _option_mark_put(
            px=px,
            strike=float(leg["strike"]),
            time_value_at_entry=float(leg["time_value0"]),
            dte_left=dte_left,
            dte_total=int(leg["dte_days"]),
        )
    else:
        mid = _option_mark_call(
            px=px,
            strike=float(leg["strike"]),
            time_value_at_entry=float(leg["time_value0"]),
            dte_left=dte_left,
            dte_total=int(leg["dte_days"]),
        )
    spread = max(mid * 0.02, 0.01)
    if side == "sell":
        return max(mid - spread, 0.01)
    return max(mid + spread, 0.01)


def _condor_close_cost_dollars(
    position: Dict[str, Any],
    day_slice: pd.DataFrame,
    day: date,
) -> float:
    short_put_ask = _lookup_leg_close_price(day_slice, position["short_put"], day, side="buy")
    long_put_bid = _lookup_leg_close_price(day_slice, position["long_put"], day, side="sell")
    short_call_ask = _lookup_leg_close_price(day_slice, position["short_call"], day, side="buy")
    long_call_bid = _lookup_leg_close_price(day_slice, position["long_call"], day, side="sell")
    put_spread = max(short_put_ask - long_put_bid, 0.0)
    call_spread = max(short_call_ask - long_call_bid, 0.0)
    return round((put_spread + call_spread) * 100.0, 4)


def _bull_call_spread_close_value_dollars(
    position: Dict[str, Any],
    day_slice: pd.DataFrame,
    day: date,
) -> float:
    long_bid = _lookup_leg_close_price(day_slice, position["long_call"], day, side="sell")
    short_ask = _lookup_leg_close_price(day_slice, position["short_call"], day, side="buy")
    return round(max(long_bid - short_ask, 0.0) * 100.0, 4)


def _bull_put_spread_close_cost_dollars(
    position: Dict[str, Any],
    day_slice: pd.DataFrame,
    day: date,
) -> float:
    short_put_ask = _lookup_leg_close_price(day_slice, position["short_put"], day, side="buy")
    long_put_bid = _lookup_leg_close_price(day_slice, position["long_put"], day, side="sell")
    return round(max(short_put_ask - long_put_bid, 0.0) * 100.0, 4)


def _long_option_close_value_dollars(
    position: Dict[str, Any],
    day_slice: pd.DataFrame,
    day: date,
    leg_key: str,
) -> float:
    value = _lookup_leg_close_price(day_slice, position[leg_key], day, side="sell")
    return round(max(value, 0.0) * 100.0, 4)


def _compute_iv_percentile_series(
    series: pd.Series,
    lookback_days: int = 252,
    min_history: int = 60,
) -> pd.Series:
    if series.empty:
        return pd.Series(dtype=float)

    clean = series.astype(float).copy()
    idx = list(clean.index)
    vals = clean.tolist()
    out: List[float] = []

    for i, current in enumerate(vals):
        if pd.isna(current):
            out.append(float("nan"))
            continue
        start = max(0, i - lookback_days)
        history = [v for v in vals[start:i] if pd.notna(v)]
        if len(history) < min_history:
            out.append(float("nan"))
            continue
        lower = sum(1 for v in history if v < current)
        equal = sum(1 for v in history if v == current)
        percentile = ((lower + (0.5 * equal)) / len(history)) * 100.0
        out.append(float(percentile))

    return pd.Series(out, index=idx, dtype=float)


def _build_daily_iv_percentile(
    frame: pd.DataFrame,
    underlying: str,
    min_dte: int = 30,
    max_dte: int = 60,
    lookback_days: int = 252,
) -> pd.Series:
    if frame.empty or "implied_volatility" not in frame.columns:
        return pd.Series(dtype=float)

    subset = frame[
        (frame["underlying"] == underlying)
        & (frame["dte"] >= min_dte)
        & (frame["dte"] <= max_dte)
        & frame["implied_volatility"].notna()
        & (frame["implied_volatility"] > 0.0)
    ].copy()
    if subset.empty:
        return pd.Series(dtype=float)

    subset["_atm_gap"] = (subset["strike"] / subset["underlying_price"] - 1.0).abs()
    subset = subset.sort_values(["date", "_atm_gap", "dte"])
    subset["_atm_rank"] = subset.groupby("date")["_atm_gap"].rank(method="first")
    daily_iv = (
        subset[subset["_atm_rank"] <= 8]
        .groupby("date")["implied_volatility"]
        .median()
        .sort_index()
    )
    return _compute_iv_percentile_series(daily_iv, lookback_days=lookback_days)


def _select_spy_iron_condor_proxy(day_slice: pd.DataFrame) -> Optional[Dict[str, Any]]:
    chain = day_slice[(day_slice["underlying"] == "SPY") & (day_slice["dte"] >= 30) & (day_slice["dte"] <= 60)]
    if chain.empty:
        return None

    expiries = sorted(
        chain["expiration_date"].dropna().unique().tolist(),
        key=lambda exp: abs(
            float(chain[chain["expiration_date"] == exp]["dte"].median()) - 45.0
        ),
    )
    best_candidate: Optional[Dict[str, Any]] = None
    best_score = float("-inf")

    for exp in expiries:
        exp_rows = chain[chain["expiration_date"] == exp]
        puts = exp_rows[exp_rows["option_type"].astype(str).str.lower() == "put"]
        calls = exp_rows[exp_rows["option_type"].astype(str).str.lower() == "call"]
        short_put = _pick_closest_delta_contract(puts, -0.12, -0.25, -0.08)
        short_call = _pick_closest_delta_contract(calls, 0.12, 0.08, 0.25)
        if short_put is None or short_call is None:
            continue

        long_puts = puts[puts["strike"] < float(short_put["strike"])].sort_values(
            "strike", ascending=False
        )
        long_calls = calls[calls["strike"] > float(short_call["strike"])].sort_values(
            "strike"
        )
        if long_puts.empty or long_calls.empty:
            continue

        for _, long_put in long_puts.head(3).iterrows():
            for _, long_call in long_calls.head(3).iterrows():
                put_width_dollars = (float(short_put["strike"]) - float(long_put["strike"])) * 100.0
                call_width_dollars = (float(long_call["strike"]) - float(short_call["strike"])) * 100.0
                entry_credit_dollars = (
                    (float(short_put["bid"]) - float(long_put["ask"]))
                    + (float(short_call["bid"]) - float(long_call["ask"]))
                ) * 100.0
                max_risk_dollars = max(put_width_dollars, call_width_dollars) - entry_credit_dollars
                if (
                    entry_credit_dollars <= 0.0
                    or max_risk_dollars < 100.0
                    or max_risk_dollars > 1000.0
                ):
                    continue
                score = (
                    (entry_credit_dollars / max(max_risk_dollars, 1.0))
                    - (abs(put_width_dollars - call_width_dollars) / 1000.0)
                )
                if score <= best_score:
                    continue
                best_score = score
                best_candidate = {
                    "expiry_date": exp,
                    "short_put": _build_option_leg(short_put),
                    "long_put": _build_option_leg(long_put),
                    "short_call": _build_option_leg(short_call),
                    "long_call": _build_option_leg(long_call),
                    "entry_credit_dollars": round(entry_credit_dollars, 4),
                    "max_risk_dollars": round(max_risk_dollars, 4),
                    "entry_fees_dollars": 4.0,
                }

    return best_candidate


def _select_bull_call_spread(
    day_slice: pd.DataFrame,
    underlying: str,
    target_dte: int = 45,
    min_dte: int = 30,
    max_dte: int = 60,
    target_long_delta: float = 0.60,
    min_long_delta: float = 0.45,
    max_long_delta: float = 0.75,
    target_short_delta: float = 0.35,
    min_short_delta: float = 0.20,
    max_short_delta: float = 0.50,
    min_debit_dollars: float = 150.0,
    max_debit_dollars: float = 1200.0,
    max_spread_pct: float = 0.12,
    min_open_interest: int = 200,
) -> Optional[Dict[str, Any]]:
    chain = day_slice[
        (day_slice["underlying"] == underlying)
        & (day_slice["option_type"].astype(str).str.lower() == "call")
        & (day_slice["dte"] >= min_dte)
        & (day_slice["dte"] <= max_dte)
    ].copy()
    if chain.empty:
        return None

    if "spread_pct" not in chain.columns:
        chain["spread_pct"] = (chain["ask"] - chain["bid"]) / chain["ask"].clip(lower=0.01)

    expiries = sorted(
        chain["expiration_date"].dropna().unique().tolist(),
        key=lambda exp: abs(
            float(chain[chain["expiration_date"] == exp]["dte"].median()) - float(target_dte)
        ),
    )
    best_candidate: Optional[Dict[str, Any]] = None
    best_score = float("-inf")

    for exp in expiries:
        exp_rows = chain[chain["expiration_date"] == exp].copy()
        if exp_rows.empty:
            continue
        longs = exp_rows[
            (exp_rows["delta"] >= min_long_delta)
            & (exp_rows["delta"] <= max_long_delta)
        ].copy()
        if longs.empty:
            continue
        if "open_interest" in longs.columns:
            longs = longs[
                longs["open_interest"].isna() | (longs["open_interest"] >= min_open_interest)
            ]
        longs = longs[longs["spread_pct"] <= max_spread_pct]
        if longs.empty:
            continue
        longs["_delta_gap"] = (longs["delta"] - target_long_delta).abs()
        longs = longs.sort_values(["_delta_gap", "spread_pct", "ask", "strike"])

        for _, long_call in longs.head(8).iterrows():
            shorts = exp_rows[
                (exp_rows["strike"] > float(long_call["strike"]))
                & (exp_rows["delta"] >= min_short_delta)
                & (exp_rows["delta"] <= max_short_delta)
            ].copy()
            if shorts.empty:
                continue
            if "open_interest" in shorts.columns:
                shorts = shorts[
                    shorts["open_interest"].isna() | (shorts["open_interest"] >= min_open_interest)
                ]
            shorts = shorts[shorts["spread_pct"] <= max_spread_pct]
            if shorts.empty:
                continue
            shorts["_delta_gap"] = (shorts["delta"] - target_short_delta).abs()
            shorts = shorts.sort_values(["_delta_gap", "spread_pct", "strike", "ask"])

            for _, short_call in shorts.head(8).iterrows():
                width_dollars = (float(short_call["strike"]) - float(long_call["strike"])) * 100.0
                entry_debit_dollars = (
                    float(long_call["ask"]) - float(short_call["bid"])
                ) * 100.0
                max_gain_dollars = width_dollars - entry_debit_dollars
                combined_spread_pct = (
                    ((float(long_call["ask"]) - float(long_call["bid"])) +
                     (float(short_call["ask"]) - float(short_call["bid"])))
                    / max((float(long_call["ask"]) - float(short_call["bid"])), 0.01)
                )
                if (
                    width_dollars <= 0.0
                    or entry_debit_dollars < min_debit_dollars
                    or entry_debit_dollars > max_debit_dollars
                    or max_gain_dollars <= 0.0
                    or combined_spread_pct > max_spread_pct
                ):
                    continue
                liquidity_bonus = 0.0
                if "open_interest" in long_call.index and pd.notna(long_call.get("open_interest")):
                    liquidity_bonus += min(float(long_call["open_interest"]) / 5000.0, 0.25)
                if "open_interest" in short_call.index and pd.notna(short_call.get("open_interest")):
                    liquidity_bonus += min(float(short_call["open_interest"]) / 5000.0, 0.25)
                score = (
                    (max_gain_dollars / max(entry_debit_dollars, 1.0))
                    - (abs(float(long_call["delta"]) - target_long_delta) * 0.30)
                    - (abs(float(short_call["delta"]) - target_short_delta) * 0.25)
                    - combined_spread_pct
                    + liquidity_bonus
                )
                if score <= best_score:
                    continue
                best_score = score
                best_candidate = {
                    "expiry_date": exp,
                    "long_call": _build_option_leg(long_call),
                    "short_call": _build_option_leg(short_call),
                    "entry_debit_dollars": round(entry_debit_dollars, 4),
                    "max_gain_dollars": round(max_gain_dollars, 4),
                    "entry_fees_dollars": 2.0,
                    "combined_spread_pct": round(combined_spread_pct, 4),
                }

    return best_candidate


def _select_msft_bull_call_spread(day_slice: pd.DataFrame) -> Optional[Dict[str, Any]]:
    return _select_bull_call_spread(
        day_slice=day_slice,
        underlying="MSFT",
        target_dte=45,
        min_dte=30,
        max_dte=60,
        target_long_delta=0.60,
        min_long_delta=0.50,
        max_long_delta=0.75,
        target_short_delta=0.30,
        min_short_delta=0.20,
        max_short_delta=0.45,
        min_debit_dollars=100.0,
        max_debit_dollars=1000.0,
        max_spread_pct=0.20,
        min_open_interest=200,
    )


def _select_bull_put_spread(
    day_slice: pd.DataFrame,
    underlying: str,
    support_floor: float,
    target_dte: int = 45,
    min_dte: int = 38,
    max_dte: int = 52,
    target_delta: float = -0.27,
    min_delta: float = -0.40,
    max_delta: float = -0.15,
    min_pop_pct: float = 65.0,
    min_credit_dollars: float = 40.0,
    max_risk_dollars: float = 1000.0,
) -> Optional[Dict[str, Any]]:
    chain = day_slice[
        (day_slice["underlying"] == underlying)
        & (day_slice["option_type"].astype(str).str.lower() == "put")
        & (day_slice["dte"] >= min_dte)
        & (day_slice["dte"] <= max_dte)
    ]
    if chain.empty:
        return None

    expiries = sorted(
        chain["expiration_date"].dropna().unique().tolist(),
        key=lambda exp: abs(
            float(chain[chain["expiration_date"] == exp]["dte"].median()) - float(target_dte)
        ),
    )
    best_candidate: Optional[Dict[str, Any]] = None
    best_score = float("-inf")

    for exp in expiries:
        exp_rows = chain[chain["expiration_date"] == exp].copy()
        if exp_rows.empty:
            continue
        shorts = exp_rows[
            (exp_rows["delta"] >= min_delta)
            & (exp_rows["delta"] <= max_delta)
            & (exp_rows["strike"] <= support_floor)
        ].copy()
        if shorts.empty:
            continue
        shorts["_delta_gap"] = (shorts["delta"] - target_delta).abs()
        shorts = shorts.sort_values(["_delta_gap", "spread_pct", "strike"], ascending=[True, True, False])

        for _, short_put in shorts.head(8).iterrows():
            longs = exp_rows[exp_rows["strike"] < float(short_put["strike"])].copy()
            if longs.empty:
                continue
            longs["_width_dollars"] = (
                (float(short_put["strike"]) - longs["strike"]) * 100.0
            )
            longs = longs[(longs["_width_dollars"] >= 100.0) & (longs["_width_dollars"] <= 1000.0)]
            if longs.empty:
                continue
            longs = longs.sort_values(["_width_dollars", "ask", "strike"])

            for _, long_put in longs.head(8).iterrows():
                width_dollars = (float(short_put["strike"]) - float(long_put["strike"])) * 100.0
                entry_credit_dollars = (
                    float(short_put["bid"]) - float(long_put["ask"])
                ) * 100.0
                max_loss_dollars = width_dollars - entry_credit_dollars
                break_even = float(short_put["strike"]) - (entry_credit_dollars / 100.0)
                theoretical_pop_pct = max(0.0, min(1.0, 1.0 - abs(float(short_put["delta"])))) * 100.0

                if (
                    entry_credit_dollars < min_credit_dollars
                    or max_loss_dollars <= 0.0
                    or max_loss_dollars > max_risk_dollars
                    or break_even > support_floor
                    or theoretical_pop_pct < min_pop_pct
                ):
                    continue

                support_buffer_pct = (
                    (support_floor - break_even) / max(float(short_put["underlying_price"]), 1.0)
                )
                score = (
                    (entry_credit_dollars / max(max_loss_dollars, 1.0))
                    + (theoretical_pop_pct / 100.0)
                    + support_buffer_pct
                    - max(float(short_put.get("spread_pct", 0.0) or 0.0), 0.0)
                )
                if score <= best_score:
                    continue
                best_score = score
                best_candidate = {
                    "expiry_date": exp,
                    "short_put": _build_option_leg(short_put),
                    "long_put": _build_option_leg(long_put),
                    "entry_credit_dollars": round(entry_credit_dollars, 4),
                    "max_risk_dollars": round(max_loss_dollars, 4),
                    "break_even": round(break_even, 4),
                    "support_floor": round(float(support_floor), 4),
                    "theoretical_pop_pct": round(theoretical_pop_pct, 4),
                    "entry_fees_dollars": 2.0,
                }

    return best_candidate


def _select_long_call(
    day_slice: pd.DataFrame,
    underlying: str,
    target_dte: int = 45,
    min_dte: int = 38,
    max_dte: int = 52,
    target_delta: float = 0.60,
    min_delta: float = 0.45,
    max_delta: float = 0.75,
    min_debit_dollars: float = 100.0,
    max_debit_dollars: float = 1000.0,
) -> Optional[Dict[str, Any]]:
    chain = day_slice[
        (day_slice["underlying"] == underlying)
        & (day_slice["option_type"].astype(str).str.lower() == "call")
        & (day_slice["dte"] >= min_dte)
        & (day_slice["dte"] <= max_dte)
    ]
    if chain.empty:
        return None

    expiries = sorted(
        chain["expiration_date"].dropna().unique().tolist(),
        key=lambda exp: abs(
            float(chain[chain["expiration_date"] == exp]["dte"].median()) - float(target_dte)
        ),
    )
    best_candidate: Optional[Dict[str, Any]] = None
    best_score = float("-inf")

    for exp in expiries:
        exp_rows = chain[chain["expiration_date"] == exp].copy()
        call_row = _pick_closest_delta_contract(exp_rows, target_delta, min_delta, max_delta)
        if call_row is None:
            continue
        entry_debit_dollars = float(call_row["ask"]) * 100.0
        if entry_debit_dollars < min_debit_dollars or entry_debit_dollars > max_debit_dollars:
            continue

        spread_penalty = max(float(call_row.get("spread_pct", 0.0) or 0.0), 0.0)
        delta_gap = abs(float(call_row["delta"]) - target_delta)
        score = 1.0 - delta_gap - spread_penalty - (entry_debit_dollars / max(max_debit_dollars, 1.0))
        if score <= best_score:
            continue
        best_score = score
        best_candidate = {
            "expiry_date": exp,
            "long_call": _build_option_leg(call_row),
            "entry_debit_dollars": round(entry_debit_dollars, 4),
            "entry_fees_dollars": 1.0,
        }

    return best_candidate


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
    if "date" not in data.columns or "underlying" not in data.columns or "underlying_price" not in data.columns:
        return pd.DataFrame()
    frame = data.loc[:, ["date", "underlying", "underlying_price"]].copy()

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
    if "date" not in data.columns or "underlying" not in data.columns or "underlying_price" not in data.columns:
        return pd.DataFrame()
    dates = pd.to_datetime(data["date"]).dt.date
    mask = data["underlying"].isin(symbols) & (dates >= start_date) & (dates <= end_date)
    frame = data.loc[mask, ["date", "underlying", "underlying_price"]].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame.dropna()
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


def _wilder_rsi_frame(prices: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    delta = prices.diff()
    gains = delta.clip(lower=0).ewm(alpha=1.0 / max(period, 1), adjust=False).mean()
    losses = (-delta.clip(upper=0)).ewm(alpha=1.0 / max(period, 1), adjust=False).mean()
    rs = gains / (losses + 1e-9)
    return 100.0 - (100.0 / (1.0 + rs))


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
