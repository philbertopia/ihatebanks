from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


_ALIASES = {
    "uhl_directives": "uhl_directives_full",
}


_VARIANT_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "base": {
        "target_delta": 0.80,
        "min_delta": 0.65,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 0.30,
        "ideal_extrinsic_pct": 0.20,
        "min_open_interest": 500,
        "require_open_interest": False,
        "max_spread_pct": 0.10,
        "min_dte": 8,
        "max_dte": 60,
        "option_type": "call",
        "prefer_monthly": True,
        "monthly_only": False,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
    },
    "conservative_85d": {
        "target_delta": 0.85,
        "delta_tolerance": 0.08,
        "min_delta": 0.70,
    },
    "aggressive_70d": {
        "target_delta": 0.70,
        "delta_tolerance": 0.10,
        "min_delta": 0.55,
    },
    "strict_extrinsic_20": {
        "max_extrinsic_pct": 0.20,
        "ideal_extrinsic_pct": 0.15,
    },
    "monthly_only": {
        "prefer_monthly": True,
        "monthly_only": True,
        "min_dte": 30,
        "max_dte": 60,
    },
    # ── New signal-gate variants (2026-03) ────────────────────────────────────
    # VIX proxy gate: block entries when SPY HV30 > 25% (panic regime)
    "vix_gated": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.25,
    },
    # Market breadth gate (strict): block when < 60% of universe above MA200
    "breadth_60": {
        "breadth_gate_enabled": True,
        "breadth_min_pct": 60.0,
    },
    # Market breadth gate (permissive): block when < 40% of universe above MA200
    "breadth_40": {
        "breadth_gate_enabled": True,
        "breadth_min_pct": 40.0,
    },
    # Order block resistance: skip entries when price within 3% below 30-day high
    "order_block_filtered": {
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
    },
    # Sector ETF trend gate: require XLK/XLC/XLY to be in bullish trend
    "sector_trend": {
        "require_sector_trend": True,
    },
    # VIX + breadth combined (no order block / sector)
    "vix_breadth_combo": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
    },
    # Full filter stack: all 4 gates — most selective
    "full_filter_stack": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
    },
    # Strategy profile based on Chris Uhl / OVTLYR transcript directives.
    # BUG FIX (2026-03): max_dte raised from 60 → 90.
    # monthly_only + 30-60 DTE created an ~10-day valid window per month, causing
    # nearly all roll attempts to fail (no valid replacement found). With 30-90 DTE
    # the next monthly expiration is always inside the window.
    "uhl_directives_full": {
        "target_delta": 0.80,
        "min_delta": 0.65,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 0.30,
        "ideal_extrinsic_pct": 0.20,
        "min_open_interest": 200,
        "max_spread_pct": 0.10,
        "min_dte": 30,
        "max_dte": 90,  # was 60 — too narrow with monthly_only=True
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": True,
        "sit_in_cash_when_bearish": True,
        "market_trend_symbol": "SPY",
        "trend_ema_fast": 10,
        "trend_ema_medium": 20,
        "trend_ema_slow": 50,
        "trend_lookback_days": 180,
    },
    # Complete faithful implementation of Chris Uhl's OVTLYR strategy.
    # Adds the three "Plan M" exits that the base engine was missing:
    #   - Exit when underlying's 10 EMA crosses below 20 EMA (trend reversal)
    #   - Take profit at +30% gain on the option contract
    #   - Stop loss at -20% loss on the option contract
    "uhl_authentic": {
        "target_delta": 0.80,
        "min_delta": 0.65,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 0.30,
        "ideal_extrinsic_pct": 0.20,
        "min_open_interest": 200,
        "max_spread_pct": 0.10,
        "min_dte": 30,
        "max_dte": 90,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": True,
        "sit_in_cash_when_bearish": True,
        "market_trend_symbol": "SPY",
        "trend_ema_fast": 10,
        "trend_ema_medium": 20,
        "trend_ema_slow": 50,
        # Plan M exits
        "exit_on_bearish_cross": True,
        "profit_target_pct": 30.0,
        "stop_loss_pct": 20.0,
    },
    # Full Uhl rules + all 4 signal gates (the ultimate combined filter).
    # uhl_authentic (entry/exit discipline) + full_filter_stack (regime quality gates).
    "uhl_authentic_filtered": {
        "target_delta": 0.80,
        "min_delta": 0.65,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 0.30,
        "ideal_extrinsic_pct": 0.20,
        "min_open_interest": 200,
        "max_spread_pct": 0.10,
        "min_dte": 30,
        "max_dte": 90,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": True,
        "sit_in_cash_when_bearish": True,
        "market_trend_symbol": "SPY",
        "trend_ema_fast": 10,
        "trend_ema_medium": 20,
        "trend_ema_slow": 50,
        # Plan M exits
        "exit_on_bearish_cross": True,
        "profit_target_pct": 30.0,
        "stop_loss_pct": 20.0,
        # All 4 signal gates
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
    },
    # ── Improvement experiments (2026-03) ─────────────────────────────────────
    # uhl_authentic but with ONLY the bearish EMA cross exit — no profit target
    # or stop loss. Tests the hypothesis that the -20% SL is the main culprit
    # in uhl_authentic's -37% return (avg hold 7.3 days, lots of SL hits).
    "uhl_bearish_cross_only": {
        "target_delta": 0.80,
        "min_delta": 0.65,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 0.30,
        "ideal_extrinsic_pct": 0.20,
        "min_open_interest": 200,
        "max_spread_pct": 0.10,
        "min_dte": 30,
        "max_dte": 90,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": True,
        "sit_in_cash_when_bearish": True,
        "market_trend_symbol": "SPY",
        "trend_ema_fast": 10,
        "trend_ema_medium": 20,
        "trend_ema_slow": 50,
        "exit_on_bearish_cross": True,
        # No profit_target_pct or stop_loss_pct — hold until EMA cross or roll
    },
    # uhl_authentic with a wider stop loss (-40% instead of -20%).
    # Tech stocks have high daily volatility; the -20% SL fires before the
    # position has a chance to recover. -40% gives more breathing room.
    "uhl_loose_stop_40": {
        "target_delta": 0.80,
        "min_delta": 0.65,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 0.30,
        "ideal_extrinsic_pct": 0.20,
        "min_open_interest": 200,
        "max_spread_pct": 0.10,
        "min_dte": 30,
        "max_dte": 90,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": True,
        "sit_in_cash_when_bearish": True,
        "market_trend_symbol": "SPY",
        "trend_ema_fast": 10,
        "trend_ema_medium": 20,
        "trend_ema_slow": 50,
        "exit_on_bearish_cross": True,
        "profit_target_pct": 30.0,
        "stop_loss_pct": 40.0,  # was 20.0 — wider stop for volatile tech stocks
    },
    # full_filter_stack with max_positions raised to 20 (top_50 universe).
    # The base full_filter_stack caps at 10 positions; with 50 stocks to
    # choose from, increasing the cap lets the strategy diversify into more
    # qualifying setups simultaneously.
    "full_filter_20pos": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
        "max_positions": 20,  # up from default 10 — use with --universe top_50
    },
    # ── IV rank + relative strength experiments (2026-03) ────────────────────
    # full_filter_20pos + IV rank gate: only enter when symbol options are cheap
    # vs. that symbol's own 252-day IV history (rank < 40% = bottom 40%).
    # Low IV rank = call premiums are cheap relative to history — best time to buy.
    "full_filter_iv_rank": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
        "iv_rank_gate_enabled": True,
        "iv_rank_max_pct": 40.0,  # only enter when IV rank < 40th percentile
        "iv_rank_lookback_days": 252,
        "max_positions": 20,
    },
    # full_filter_20pos + relative strength gate: only enter when stock has
    # outperformed SPY over the past 90 trading days (RS >= SPY return).
    # Unlike absolute momentum, RS >= SPY remains valid even after a crash when
    # a stock recovers faster than the index.
    "full_filter_rs": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
        "rs_gate_enabled": True,
        "rs_lookback_days": 90,
        "rs_benchmark_symbol": "SPY",
        "max_positions": 20,
    },
    # full_filter_20pos + both IV rank AND relative strength gates combined.
    "full_filter_iv_rs": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
        "iv_rank_gate_enabled": True,
        "iv_rank_max_pct": 40.0,
        "iv_rank_lookback_days": 252,
        "rs_gate_enabled": True,
        "rs_lookback_days": 90,
        "rs_benchmark_symbol": "SPY",
        "max_positions": 20,
    },
    # ── Momentum rank improvements (2026-03) ──────────────────────────────────
    # full_filter_stack + momentum rank top-50% filter.
    # Only enters stocks whose 90-day price return ranks in the top half of the
    # universe. Adds stock-level quality selection on top of the existing
    # market-wide (VIX + breadth) and per-symbol (order block + sector) gates.
    "full_filter_momentum": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
        "momentum_rank_enabled": True,
        "momentum_lookback_days": 90,
        "momentum_min_rank_pct": 50.0,  # top half by 90-day return
        "max_positions": 20,
    },
    # Stricter momentum: only top quartile (top 25%) by 90-day return.
    "full_filter_momentum_strict": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
        "momentum_rank_enabled": True,
        "momentum_lookback_days": 90,
        "momentum_min_rank_pct": 75.0,  # top quartile only
        "max_positions": 20,
    },
    # ── Cash-Secured Put (CSP) Strategy Variants (2026-03) ─────────────────────
    # CSP: Sell OTM puts, hold until expiration or roll. Compare delta targets,
    # exit strategies (profit target vs ride to expiry), and roll triggers.
    # CSP-01: Delta -0.30, 50% profit exit, roll on delta < -0.10
    "csp_d30_pt50_roll_delta": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.30,
        "min_delta": -0.40,
        "max_delta": -0.20,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "ideal_extrinsic_pct": 0.30,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 90,  # was 45 — too narrow with monthly_only=True, creates entry desert
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "profit_target",
        "profit_target_ratio": 0.50,
        "roll_trigger": "delta",
        "roll_delta_threshold": -0.10,
    },
    # CSP-02: Delta -0.30, 50% profit exit, roll on 7 DTE
    "csp_d30_pt50_roll_dte": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.30,
        "min_delta": -0.40,
        "max_delta": -0.20,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "ideal_extrinsic_pct": 0.30,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 90,  # was 45 — too narrow with monthly_only=True
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "profit_target",
        "profit_target_ratio": 0.50,
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
    },
    # CSP-03: Delta -0.30, ride to expiry, roll on delta < -0.10
    "csp_d30_ride_roll_delta": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.30,
        "min_delta": -0.40,
        "max_delta": -0.20,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "ideal_extrinsic_pct": 0.30,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 90,  # was 45 — too narrow with monthly_only=True
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "delta",
        "roll_delta_threshold": -0.10,
    },
    # CSP-04: Delta -0.30, ride to expiry, roll on 7 DTE
    "csp_d30_ride_roll_dte": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.30,
        "min_delta": -0.40,
        "max_delta": -0.20,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "ideal_extrinsic_pct": 0.30,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 90,  # was 45 — too narrow with monthly_only=True
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
    },
    # CSP-05: Delta -0.20, 50% profit exit, roll on delta < -0.10
    "csp_d20_pt50_roll_delta": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.20,
        "min_delta": -0.30,
        "max_delta": -0.10,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "ideal_extrinsic_pct": 0.40,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 90,  # was 45 — too narrow with monthly_only=True
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "profit_target",
        "profit_target_ratio": 0.50,
        "roll_trigger": "delta",
        "roll_delta_threshold": -0.10,
    },
    # CSP-06: Delta -0.20, 50% profit exit, roll on 7 DTE
    "csp_d20_pt50_roll_dte": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.20,
        "min_delta": -0.30,
        "max_delta": -0.10,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "ideal_extrinsic_pct": 0.40,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 90,  # was 45 — too narrow with monthly_only=True
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "profit_target",
        "profit_target_ratio": 0.50,
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
    },
    # CSP-07: Delta -0.20, ride to expiry, roll on delta < -0.10
    "csp_d20_ride_roll_delta": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.20,
        "min_delta": -0.30,
        "max_delta": -0.10,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "ideal_extrinsic_pct": 0.40,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 90,  # was 45 — too narrow with monthly_only=True
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "delta",
        "roll_delta_threshold": -0.10,
    },
    # ── Next-wave experiments (2026-03) ───────────────────────────────────────
    # full_filter_iv_rs + SPY trend block: block all new entries when SPY is in a
    # confirmed downtrend (10 EMA < 20 EMA). The 2022 bear market is the main source
    # of the 40.8% max drawdown in full_filter_iv_rs. With the SPY regime block on
    # top of 4 gates + IV rank + RS, entries are very selective — should target DD < 30%.
    "full_filter_iv_rs_gated": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
        "iv_rank_gate_enabled": True,
        "iv_rank_max_pct": 40.0,
        "iv_rank_lookback_days": 252,
        "rs_gate_enabled": True,
        "rs_lookback_days": 90,
        "rs_benchmark_symbol": "SPY",
        "max_positions": 20,
        # SPY regime block — block new entries when SPY is bearish
        "require_symbol_bullish_trend": True,
        "sit_in_cash_when_bearish": True,
        "market_trend_symbol": "SPY",
        "trend_ema_fast": 10,
        "trend_ema_medium": 20,
        "trend_ema_slow": 50,
    },
    # full_filter_20pos + 30% profit target. The champion strategy has no profit
    # exit — it holds until delta degrades or DTE <= 7. A 30% profit target
    # recycles capital faster into fresh setups and locks in gains before reversals.
    "full_filter_20pos_tp30": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
        "max_positions": 20,
        "profit_target_pct": 30.0,  # lock in gains, recycle into next cheap entry
    },
    # full_filter_iv_rank with stricter 30th percentile cutoff (was 40th).
    # Only the very cheapest options historically. Fewer trades, higher quality.
    # Risk: might fall below 150 trades — watch trade count carefully.
    "full_filter_iv_rank_30": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
        "iv_rank_gate_enabled": True,
        "iv_rank_max_pct": 30.0,  # stricter: was 40.0
        "iv_rank_lookback_days": 252,
        "max_positions": 20,
    },
    # full_filter_iv_rank + monthly-only expirations (30-90 DTE, 3rd Friday).
    # Monthly options have tighter spreads and more institutional liquidity.
    # Max DTE raised to 90 to avoid the entry desert problem (uhl bug fix pattern).
    "full_filter_monthly": {
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
        "iv_rank_gate_enabled": True,
        "iv_rank_max_pct": 40.0,
        "iv_rank_lookback_days": 252,
        "max_positions": 20,
        "prefer_monthly": True,
        "monthly_only": True,
        "min_dte": 30,
        "max_dte": 90,  # wide enough to always find next monthly expiration
    },
    # CSP-08: Delta -0.20, ride to expiry, roll on 7 DTE
    "csp_d20_ride_roll_dte": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.20,
        "min_delta": -0.30,
        "max_delta": -0.10,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "ideal_extrinsic_pct": 0.40,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 90,  # was 45 — too narrow with monthly_only=True
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
    },
    # ── Wheel Strategy Variants (2026-03) ─────────────────────────────
    # Wheel: CSP → If assigned, sell covered calls → If called, repeat
    # Using more aggressive delta puts for higher assignment probability
    # Wheel: -0.40 delta puts (more likely ITM/assigned), 0.30 delta calls
    "wheel_d40_c30": {
        "strategy_type": "wheel",
        "option_type": "put",
        "target_delta": -0.40,
        "min_delta": -0.50,
        "max_delta": -0.30,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 60,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
        # Wheel-specific
        "wheel_call_delta": 0.30,
        "wheel_call_min_dte": 20,
        "wheel_call_max_dte": 45,
    },
    # Wheel: -0.40 delta puts, 0.20 delta calls
    "wheel_d40_c20": {
        "strategy_type": "wheel",
        "option_type": "put",
        "target_delta": -0.40,
        "min_delta": -0.50,
        "max_delta": -0.30,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 60,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
        # Wheel-specific
        "wheel_call_delta": 0.20,
        "wheel_call_min_dte": 20,
        "wheel_call_max_dte": 45,
    },
    # Wheel: -0.50 delta puts (very likely ITM), 0.30 delta calls
    "wheel_d50_c30": {
        "strategy_type": "wheel",
        "option_type": "put",
        "target_delta": -0.50,
        "min_delta": -0.60,
        "max_delta": -0.40,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 60,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
        # Wheel-specific
        "wheel_call_delta": 0.30,
        "wheel_call_min_dte": 20,
        "wheel_call_max_dte": 45,
    },
    # ── Aggressive CSP Variants (more contracts) ─────────────────────
    # CSP 2x contracts
    "csp_d30_2x": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.30,
        "min_delta": -0.40,
        "max_delta": -0.20,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 60,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
        # Aggressive sizing
        "position_size_multiplier": 2,
        "max_contracts_per_trade": 5,
    },
    # CSP 3x contracts
    "csp_d30_3x": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.30,
        "min_delta": -0.40,
        "max_delta": -0.20,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 60,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
        # Aggressive sizing
        "position_size_multiplier": 3,
        "max_contracts_per_trade": 10,
    },
    # CSP 5x contracts
    "csp_d30_5x": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.30,
        "min_delta": -0.40,
        "max_delta": -0.20,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 60,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
        # Aggressive sizing
        "position_size_multiplier": 5,
        "max_contracts_per_trade": 15,
    },
    # CSP 3x with -0.20 delta (more ITM, higher premium)
    "csp_d20_3x": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.20,
        "min_delta": -0.30,
        "max_delta": -0.10,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 60,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
        # Aggressive sizing
        "position_size_multiplier": 3,
        "max_contracts_per_trade": 10,
    },
    # CSP 3x with -0.40 delta (more OTM, lower premium)
    "csp_d40_3x": {
        "strategy_type": "csp",
        "option_type": "put",
        "target_delta": -0.40,
        "min_delta": -0.50,
        "max_delta": -0.30,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 60,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
        # Aggressive sizing
        "position_size_multiplier": 3,
        "max_contracts_per_trade": 10,
    },
    # Wheel: -0.20 delta puts, 0.30 delta calls (original)
    "wheel_d20_c30": {
        "strategy_type": "wheel",
        "option_type": "put",
        "target_delta": -0.20,
        "min_delta": -0.30,
        "max_delta": -0.10,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 60,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
        # Wheel-specific
        "wheel_call_delta": 0.30,
        "wheel_call_min_dte": 20,
        "wheel_call_max_dte": 45,
    },
    # Wheel: -0.20 delta puts, 0.20 delta calls
    "wheel_d20_c20": {
        "strategy_type": "wheel",
        "option_type": "put",
        "target_delta": -0.20,
        "min_delta": -0.30,
        "max_delta": -0.10,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 60,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
        # Wheel-specific
        "wheel_call_delta": 0.20,
        "wheel_call_min_dte": 20,
        "wheel_call_max_dte": 45,
    },
    # Wheel: -0.30 delta puts, 0.30 delta calls
    "wheel_d30_c30": {
        "strategy_type": "wheel",
        "option_type": "put",
        "target_delta": -0.30,
        "min_delta": -0.40,
        "max_delta": -0.20,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 1.00,
        "min_open_interest": 200,
        "max_spread_pct": 0.15,
        "min_dte": 30,
        "max_dte": 60,
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "exit_strategy": "ride_to_expiry",
        "roll_trigger": "dte",
        "roll_dte_threshold": 7,
        # Wheel-specific
        "wheel_call_delta": 0.30,
        "wheel_call_min_dte": 20,
        "wheel_call_max_dte": 45,
    },
    # ── LEAPS-Style Long-Duration Variants (2026-03) ─────────────────────────
    # LEAPS = Long-term Equity Anticipation Securities (DTE > 365).
    # Economics: deep ITM call tracks stock ~dollar-for-dollar (high delta),
    # minimal theta decay relative to intrinsic value, less extrinsic cost.
    # Strategy: buy once, hold for a year or until profit target / stop loss.
    # Roll forward when DTE drops below roll_trigger threshold (30 DTE).
    #
    # Note: requires Parquet data with 180-365 DTE options. If the cache only
    # has shorter-dated chains, trade count will be low — watch carefully.
    # ─────────────────────────────────────────────────────────────────────────
    # LEAPS-01: 0.80 delta, 180-365 DTE — base LEAPS profile.
    # Mimics the video's "buy deep ITM call with 70-90 delta, 1 year expiry".
    # Low extrinsic threshold (0.20) ensures we're buying near-pure intrinsic.
    # 50% profit target: stock up 50%+ means the LEAPS option is up ~40-50%.
    "leaps_80d": {
        "target_delta": 0.80,
        "min_delta": 0.70,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 0.25,    # LEAPS should be near-pure intrinsic
        "ideal_extrinsic_pct": 0.15,
        "min_open_interest": 100,      # LEAPS have lower OI than monthlies
        "require_open_interest": False,
        "max_spread_pct": 0.12,
        "min_dte": 180,
        "max_dte": 400,               # 180-400 DTE: true LEAPS window
        "option_type": "call",
        "prefer_monthly": True,
        "monthly_only": True,          # annual expirations (Jan LEAPS)
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "max_positions": 10,
        "profit_target_pct": 50.0,    # take 50% gain — stock move of ~50%
        "stop_loss_pct": 25.0,        # wider stop: LEAPS are volatile day-to-day
    },
    # LEAPS-02: 0.85 delta, 180-365 DTE — deeper ITM for even more intrinsic.
    # Higher delta = more intrinsic value, less extrinsic risk. More expensive
    # per contract but closer 1:1 tracking with underlying stock price.
    "leaps_85d": {
        "target_delta": 0.85,
        "min_delta": 0.75,
        "delta_tolerance": 0.08,
        "max_extrinsic_pct": 0.18,    # deeper ITM = even less extrinsic
        "ideal_extrinsic_pct": 0.10,
        "min_open_interest": 100,
        "require_open_interest": False,
        "max_spread_pct": 0.12,
        "min_dte": 180,
        "max_dte": 400,
        "option_type": "call",
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "max_positions": 10,
        "profit_target_pct": 40.0,    # tighter target — stock move of ~40%
        "stop_loss_pct": 20.0,
    },
    # LEAPS-03: Full filter gates on leaps_80d — quality entries only.
    # Add VIX + breadth + order block + sector + IV rank gate to LEAPS.
    # The IV rank gate is especially important for LEAPS: buying when options
    # are cheap (low IV rank) means less extrinsic to decay over the year.
    "leaps_gated": {
        "target_delta": 0.80,
        "min_delta": 0.70,
        "delta_tolerance": 0.10,
        "max_extrinsic_pct": 0.25,
        "ideal_extrinsic_pct": 0.15,
        "min_open_interest": 100,
        "require_open_interest": False,
        "max_spread_pct": 0.12,
        "min_dte": 180,
        "max_dte": 400,
        "option_type": "call",
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "max_positions": 15,          # allow more concurrent LEAPS (slow turnover)
        "profit_target_pct": 50.0,
        "stop_loss_pct": 25.0,
        # All 4 regime gates
        "vix_gate_enabled": True,
        "vix_max_threshold": 0.28,
        "breadth_gate_enabled": True,
        "breadth_min_pct": 50.0,
        "order_block_gate_enabled": True,
        "order_block_lookback": 30,
        "order_block_buffer_pct": 0.03,
        "require_sector_trend": True,
        # IV rank: only enter when options are historically cheap
        "iv_rank_gate_enabled": True,
        "iv_rank_max_pct": 40.0,
        "iv_rank_lookback_days": 252,
        # Relative strength: only buy LEAPS on stocks outperforming SPY
        "rs_gate_enabled": True,
        "rs_lookback_days": 90,
        "rs_benchmark_symbol": "SPY",
    },
    # LEAPS-04: Defensive LEAPS — sits in cash during SPY downtrends.
    # Most LEAPS losses come from bear markets where the stock trends down
    # for the full year. Adding SPY trend block should dramatically reduce DD.
    "leaps_defensive": {
        "target_delta": 0.85,
        "min_delta": 0.75,
        "delta_tolerance": 0.08,
        "max_extrinsic_pct": 0.18,
        "ideal_extrinsic_pct": 0.10,
        "min_open_interest": 100,
        "require_open_interest": False,
        "max_spread_pct": 0.12,
        "min_dte": 180,
        "max_dte": 400,
        "option_type": "call",
        "prefer_monthly": True,
        "monthly_only": True,
        "avoid_final_week": True,
        "max_positions": 10,
        "profit_target_pct": 40.0,
        "stop_loss_pct": 20.0,
        # SPY regime block: sit in cash during bear markets
        "require_symbol_bullish_trend": True,
        "sit_in_cash_when_bearish": True,
        "market_trend_symbol": "SPY",
        "trend_ema_fast": 10,
        "trend_ema_medium": 20,
        "trend_ema_slow": 50,
        "trend_lookback_days": 180,
        # IV rank gate
        "iv_rank_gate_enabled": True,
        "iv_rank_max_pct": 40.0,
        "iv_rank_lookback_days": 252,
    },
}


def available_stock_replacement_variants() -> List[str]:
    return sorted(_VARIANT_OVERRIDES.keys())


def normalize_variant(variant: str | None) -> str:
    v = (variant or "base").strip().lower()
    return _ALIASES.get(v, v)


def variant_exists(variant: str | None) -> bool:
    return normalize_variant(variant) in _VARIANT_OVERRIDES


def resolve_stock_replacement_strategy(
    config: Dict[str, Any], variant: str | None
) -> Dict[str, Any]:
    variant_name = normalize_variant(variant)
    overrides = _VARIANT_OVERRIDES.get(variant_name)
    if overrides is None:
        raise ValueError(
            f"Unknown stock replacement variant '{variant}'. "
            f"Available: {', '.join(available_stock_replacement_variants())}"
        )
    # Start from an explicit baseline so each variant is deterministic and
    # independent of whatever defaults are currently in settings.yaml.
    base = deepcopy(_VARIANT_OVERRIDES["base"])
    # Carry forward any unknown strategy keys from config as long as they don't
    # override explicitly managed baseline keys.
    for k, v in deepcopy(config.get("strategy", {})).items():
        if k not in base:
            base[k] = v
    base.update(deepcopy(overrides))
    return base


def apply_stock_replacement_variant(
    config: Dict[str, Any], variant: str | None
) -> Dict[str, Any]:
    cfg = deepcopy(config)
    cfg["strategy"] = resolve_stock_replacement_strategy(cfg, variant)
    return cfg
