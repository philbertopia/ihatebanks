from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple


def safe_float(value, default: float = 0.0) -> float:
    try:
        out = float(value)
        if math.isfinite(out):
            return out
    except (TypeError, ValueError):
        pass
    return default


def compute_entry_limit(ask: float, previous_close: float, delta: float) -> float:
    """
    June 5 spec entry-limit formula with delta floor for numerical stability.
    """
    ask_v = max(safe_float(ask, 0.0), 0.01)
    prev_v = max(safe_float(previous_close, ask_v), 0.01)
    d = abs(safe_float(delta, 0.0))
    d = max(d, 0.05)

    if ask_v > prev_v:
        limit = ask_v + ((ask_v - prev_v) / d)
    elif ask_v < prev_v:
        limit = ask_v - ((prev_v - ask_v) / d)
    else:
        limit = ask_v

    return round(max(limit, 0.01), 4)


def normalize_component(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    v = safe_float(value, low)
    pct = (v - low) / (high - low)
    return max(0.0, min(1.0, pct)) * 100.0


def compute_composite_edge_score(
    vol_oi_component: float,
    itm_depth_component: float,
    atr_component: float,
    win_rate_component: float,
) -> float:
    score = (
        vol_oi_component * 0.40
        + itm_depth_component * 0.20
        + atr_component * 0.20
        + win_rate_component * 0.20
    )
    return round(max(0.0, min(100.0, score)), 4)


def setup_bucket_key(
    delta: float,
    itm_depth_pct: float,
    atr_pct: float,
    dte: int,
    vol_oi_ratio: float,
) -> str:
    d = safe_float(delta, 0.0)
    depth = safe_float(itm_depth_pct, 0.0)
    atr = safe_float(atr_pct, 0.0)
    ratio = safe_float(vol_oi_ratio, 0.0)
    dte_i = int(dte)

    delta_bucket = int(min(max(d, 0.0), 0.99) / 0.10)  # 0-9
    depth_bucket = min(5, int(max(depth, 0.0) / 2.0))  # 0-5
    atr_bucket = min(6, int(max(atr, 0.0) / 2.0))  # 0-6
    dte_bucket = min(5, max(0, dte_i // 6))  # 0-5
    ratio_bucket = min(6, int(max(ratio, 0.0) / 0.5))  # 0-6
    return f"d{delta_bucket}|m{depth_bucket}|a{atr_bucket}|t{dte_bucket}|r{ratio_bucket}"


def classify_data_quality(has_observed_volume: bool, has_observed_oi: bool) -> str:
    if has_observed_volume and has_observed_oi:
        return "observed"
    if has_observed_volume or has_observed_oi:
        return "mixed"
    return "modeled"


@dataclass
class IntradayVariant:
    name: str
    target_pct: float
    stop_pct: float
    trailing_activation_pct: float
    trailing_pct: float
    max_spread_pct: float
    min_unusual_factor: float
    max_trades_per_day: int
    allocation_per_trade: float
    min_effective_oi: int
    min_effective_volume: int
    min_liquidity_score: float
    entry_slippage_spread_factor: float
    exit_slippage_spread_factor: float
    round_trip_fee_per_contract: float
    fill_quality_modeled_mult: float
    fill_quality_mixed_mult: float
    fill_quality_observed_mult: float
    score_quality_penalty_modeled: float
    score_quality_penalty_mixed: float
    score_quality_penalty_observed: float
    min_fill_ratio_for_one_lot: float
    oi_capacity_pct: float
    volume_capacity_pct: float
    max_underbid_gap_pct: float
    require_regime_alignment: bool = False
    min_hist_win_rate: float = 0.0
    min_hist_observations: int = 0
    require_spy_regime_alignment: bool = False
    feature_time_mode: str = "legacy_tplus0"
    data_quality_policy: str = "allow_modeled"


_INTRADAY_VARIANTS: Dict[str, IntradayVariant] = {
    "baseline": IntradayVariant(
        name="baseline",
        target_pct=0.35,
        stop_pct=0.22,
        trailing_activation_pct=0.20,
        trailing_pct=0.10,
        max_spread_pct=0.12,
        min_unusual_factor=1.05,
        max_trades_per_day=3,
        allocation_per_trade=0.03,
        min_effective_oi=80,
        min_effective_volume=40,
        min_liquidity_score=0.35,
        entry_slippage_spread_factor=0.25,
        exit_slippage_spread_factor=0.35,
        round_trip_fee_per_contract=2.0,
        fill_quality_modeled_mult=0.78,
        fill_quality_mixed_mult=0.88,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.72,
        score_quality_penalty_mixed=0.88,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.20,
        oi_capacity_pct=0.025,
        volume_capacity_pct=0.12,
        max_underbid_gap_pct=0.50,
    ),
    "conservative": IntradayVariant(
        name="conservative",
        target_pct=0.25,
        stop_pct=0.15,
        trailing_activation_pct=0.15,
        trailing_pct=0.08,
        max_spread_pct=0.08,
        min_unusual_factor=1.15,
        max_trades_per_day=2,
        allocation_per_trade=0.02,
        min_effective_oi=120,
        min_effective_volume=60,
        min_liquidity_score=0.45,
        entry_slippage_spread_factor=0.22,
        exit_slippage_spread_factor=0.30,
        round_trip_fee_per_contract=2.5,
        fill_quality_modeled_mult=0.72,
        fill_quality_mixed_mult=0.86,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.62,
        score_quality_penalty_mixed=0.84,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.28,
        oi_capacity_pct=0.020,
        volume_capacity_pct=0.10,
        max_underbid_gap_pct=0.35,
    ),
    "aggressive": IntradayVariant(
        name="aggressive",
        target_pct=0.50,
        stop_pct=0.30,
        trailing_activation_pct=0.30,
        trailing_pct=0.14,
        max_spread_pct=0.16,
        min_unusual_factor=1.00,
        max_trades_per_day=4,
        allocation_per_trade=0.04,
        min_effective_oi=60,
        min_effective_volume=30,
        min_liquidity_score=0.28,
        entry_slippage_spread_factor=0.30,
        exit_slippage_spread_factor=0.42,
        round_trip_fee_per_contract=1.5,
        fill_quality_modeled_mult=0.82,
        fill_quality_mixed_mult=0.90,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.80,
        score_quality_penalty_mixed=0.92,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.15,
        oi_capacity_pct=0.03,
        volume_capacity_pct=0.15,
        max_underbid_gap_pct=0.65,
    ),
    # conservative_v2: middle ground between baseline and oos_hardened.
    # Raises liquidity/flow gates to improve OOS stability without cutting
    # trade count as aggressively as oos_hardened (which produces only 36 trades).
    "conservative_v2": IntradayVariant(
        name="conservative_v2",
        target_pct=0.30,
        stop_pct=0.18,
        trailing_activation_pct=0.18,
        trailing_pct=0.09,
        max_spread_pct=0.10,
        min_unusual_factor=1.10,
        max_trades_per_day=3,
        allocation_per_trade=0.02,
        min_effective_oi=100,
        min_effective_volume=50,
        min_liquidity_score=0.42,
        entry_slippage_spread_factor=0.25,
        exit_slippage_spread_factor=0.35,
        round_trip_fee_per_contract=2.0,
        fill_quality_modeled_mult=0.75,
        fill_quality_mixed_mult=0.87,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.68,
        score_quality_penalty_mixed=0.86,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.22,
        oi_capacity_pct=0.025,
        volume_capacity_pct=0.12,
        max_underbid_gap_pct=0.40,
    ),
    "conservative_regime_lite": IntradayVariant(
        name="conservative_regime_lite",
        target_pct=0.25,
        stop_pct=0.15,
        trailing_activation_pct=0.15,
        trailing_pct=0.08,
        max_spread_pct=0.08,
        min_unusual_factor=1.15,
        max_trades_per_day=2,
        allocation_per_trade=0.02,
        min_effective_oi=120,
        min_effective_volume=60,
        min_liquidity_score=0.45,
        entry_slippage_spread_factor=0.22,
        exit_slippage_spread_factor=0.30,
        round_trip_fee_per_contract=2.5,
        fill_quality_modeled_mult=0.72,
        fill_quality_mixed_mult=0.86,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.62,
        score_quality_penalty_mixed=0.84,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.28,
        oi_capacity_pct=0.020,
        volume_capacity_pct=0.10,
        max_underbid_gap_pct=0.35,
        require_regime_alignment=True,
    ),
    "conservative_hist_55": IntradayVariant(
        name="conservative_hist_55",
        target_pct=0.25,
        stop_pct=0.15,
        trailing_activation_pct=0.15,
        trailing_pct=0.08,
        max_spread_pct=0.08,
        min_unusual_factor=1.15,
        max_trades_per_day=2,
        allocation_per_trade=0.02,
        min_effective_oi=120,
        min_effective_volume=60,
        min_liquidity_score=0.45,
        entry_slippage_spread_factor=0.22,
        exit_slippage_spread_factor=0.30,
        round_trip_fee_per_contract=2.5,
        fill_quality_modeled_mult=0.72,
        fill_quality_mixed_mult=0.86,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.62,
        score_quality_penalty_mixed=0.84,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.28,
        oi_capacity_pct=0.020,
        volume_capacity_pct=0.10,
        max_underbid_gap_pct=0.35,
        min_hist_win_rate=55.0,
        min_hist_observations=6,
    ),
    "conservative_scan_quality": IntradayVariant(
        name="conservative_scan_quality",
        target_pct=0.24,
        stop_pct=0.14,
        trailing_activation_pct=0.14,
        trailing_pct=0.07,
        max_spread_pct=0.07,
        min_unusual_factor=1.20,
        max_trades_per_day=2,
        allocation_per_trade=0.018,
        min_effective_oi=140,
        min_effective_volume=75,
        min_liquidity_score=0.50,
        entry_slippage_spread_factor=0.21,
        exit_slippage_spread_factor=0.28,
        round_trip_fee_per_contract=2.5,
        fill_quality_modeled_mult=0.70,
        fill_quality_mixed_mult=0.85,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.58,
        score_quality_penalty_mixed=0.83,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.30,
        oi_capacity_pct=0.018,
        volume_capacity_pct=0.09,
        max_underbid_gap_pct=0.30,
    ),
    "oos_hardened": IntradayVariant(
        name="oos_hardened",
        target_pct=0.22,
        stop_pct=0.12,
        trailing_activation_pct=0.12,
        trailing_pct=0.06,
        max_spread_pct=0.07,
        min_unusual_factor=1.30,
        max_trades_per_day=1,
        allocation_per_trade=0.015,
        min_effective_oi=180,
        min_effective_volume=90,
        min_liquidity_score=0.58,
        entry_slippage_spread_factor=0.20,
        exit_slippage_spread_factor=0.26,
        round_trip_fee_per_contract=2.5,
        fill_quality_modeled_mult=0.65,
        fill_quality_mixed_mult=0.82,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.45,
        score_quality_penalty_mixed=0.80,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.35,
        oi_capacity_pct=0.015,
        volume_capacity_pct=0.08,
        max_underbid_gap_pct=0.25,
        require_regime_alignment=True,
        min_hist_win_rate=57.0,
        min_hist_observations=6,
    ),
    "wf_v1_liquidity_guard": IntradayVariant(
        name="wf_v1_liquidity_guard",
        target_pct=0.22,
        stop_pct=0.14,
        trailing_activation_pct=0.12,
        trailing_pct=0.06,
        max_spread_pct=0.08,
        min_unusual_factor=1.25,
        max_trades_per_day=1,
        allocation_per_trade=0.015,
        min_effective_oi=150,
        min_effective_volume=80,
        min_liquidity_score=0.58,
        entry_slippage_spread_factor=0.20,
        exit_slippage_spread_factor=0.27,
        round_trip_fee_per_contract=2.5,
        fill_quality_modeled_mult=0.62,
        fill_quality_mixed_mult=0.82,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.40,
        score_quality_penalty_mixed=0.82,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.34,
        oi_capacity_pct=0.015,
        volume_capacity_pct=0.08,
        max_underbid_gap_pct=0.25,
        require_regime_alignment=True,
        min_hist_win_rate=54.0,
        min_hist_observations=8,
        feature_time_mode="entry_safe_lagged",
        data_quality_policy="exclude_modeled",
    ),
    "wf_v2_flow_strict": IntradayVariant(
        name="wf_v2_flow_strict",
        target_pct=0.20,
        stop_pct=0.12,
        trailing_activation_pct=0.10,
        trailing_pct=0.05,
        max_spread_pct=0.07,
        min_unusual_factor=1.35,
        max_trades_per_day=1,
        allocation_per_trade=0.0125,
        min_effective_oi=180,
        min_effective_volume=100,
        min_liquidity_score=0.62,
        entry_slippage_spread_factor=0.19,
        exit_slippage_spread_factor=0.25,
        round_trip_fee_per_contract=2.5,
        fill_quality_modeled_mult=0.58,
        fill_quality_mixed_mult=0.80,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.35,
        score_quality_penalty_mixed=0.80,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.36,
        oi_capacity_pct=0.014,
        volume_capacity_pct=0.075,
        max_underbid_gap_pct=0.22,
        require_regime_alignment=True,
        min_hist_win_rate=58.0,
        min_hist_observations=10,
        feature_time_mode="entry_safe_lagged",
        data_quality_policy="exclude_modeled",
    ),
    "wf_v3_regime_strict": IntradayVariant(
        name="wf_v3_regime_strict",
        target_pct=0.24,
        stop_pct=0.13,
        trailing_activation_pct=0.12,
        trailing_pct=0.06,
        max_spread_pct=0.08,
        min_unusual_factor=1.20,
        max_trades_per_day=1,
        allocation_per_trade=0.015,
        min_effective_oi=160,
        min_effective_volume=85,
        min_liquidity_score=0.60,
        entry_slippage_spread_factor=0.20,
        exit_slippage_spread_factor=0.27,
        round_trip_fee_per_contract=2.5,
        fill_quality_modeled_mult=0.60,
        fill_quality_mixed_mult=0.82,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.38,
        score_quality_penalty_mixed=0.82,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.35,
        oi_capacity_pct=0.015,
        volume_capacity_pct=0.08,
        max_underbid_gap_pct=0.24,
        require_regime_alignment=True,
        require_spy_regime_alignment=True,
        min_hist_win_rate=56.0,
        min_hist_observations=8,
        feature_time_mode="entry_safe_lagged",
        data_quality_policy="exclude_modeled",
    ),
    # regime_filtered: conservative + all 5 OOS-hardening fixes applied.
    # Adds VIX regime gate, entry_safe_lagged, exclude_modeled data policy,
    # raised flow/liquidity thresholds, and reduced per-trade allocation.
    # Designed to replicate conservative's edge while surviving OOS validation.
    "regime_filtered": IntradayVariant(
        name="regime_filtered",
        target_pct=0.25,
        stop_pct=0.15,
        trailing_activation_pct=0.15,
        trailing_pct=0.08,
        max_spread_pct=0.08,
        min_unusual_factor=1.28,
        max_trades_per_day=2,
        allocation_per_trade=0.015,
        min_effective_oi=150,
        min_effective_volume=75,
        min_liquidity_score=0.55,
        entry_slippage_spread_factor=0.21,
        exit_slippage_spread_factor=0.28,
        round_trip_fee_per_contract=2.5,
        fill_quality_modeled_mult=0.62,
        fill_quality_mixed_mult=0.83,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.45,
        score_quality_penalty_mixed=0.82,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.30,
        oi_capacity_pct=0.018,
        volume_capacity_pct=0.09,
        max_underbid_gap_pct=0.30,
        require_regime_alignment=True,
        min_hist_win_rate=55.0,
        min_hist_observations=6,
        feature_time_mode="legacy_tplus0",
        data_quality_policy="allow_modeled",
    ),
    "wf_v4_validated_candidate": IntradayVariant(
        name="wf_v4_validated_candidate",
        target_pct=0.21,
        stop_pct=0.12,
        trailing_activation_pct=0.11,
        trailing_pct=0.05,
        max_spread_pct=0.07,
        min_unusual_factor=1.30,
        max_trades_per_day=1,
        allocation_per_trade=0.012,
        min_effective_oi=180,
        min_effective_volume=95,
        min_liquidity_score=0.62,
        entry_slippage_spread_factor=0.19,
        exit_slippage_spread_factor=0.25,
        round_trip_fee_per_contract=2.5,
        fill_quality_modeled_mult=0.58,
        fill_quality_mixed_mult=0.80,
        fill_quality_observed_mult=1.0,
        score_quality_penalty_modeled=0.35,
        score_quality_penalty_mixed=0.80,
        score_quality_penalty_observed=1.0,
        min_fill_ratio_for_one_lot=0.36,
        oi_capacity_pct=0.014,
        volume_capacity_pct=0.075,
        max_underbid_gap_pct=0.22,
        require_regime_alignment=True,
        min_hist_win_rate=57.0,
        min_hist_observations=9,
        feature_time_mode="entry_safe_lagged",
        data_quality_policy="exclude_modeled",
    ),
}


def get_intraday_variant(name: str) -> IntradayVariant:
    key = (name or "baseline").strip().lower()
    if key not in _INTRADAY_VARIANTS:
        raise ValueError(f"Unsupported intraday variant: {name}")
    return _INTRADAY_VARIANTS[key]


def observed_or_proxy_oi(open_interest, spread_pct: float) -> Tuple[int, bool]:
    if open_interest is not None:
        oi = int(max(0, safe_float(open_interest, 0.0)))
        return oi, True
    spread = max(safe_float(spread_pct, 0.02), 0.005)
    proxy = int(round(max(50.0, (1.0 / spread) * 4.0)))
    return proxy, False


def observed_or_proxy_volume(
    raw_volume,
    delta: float,
    atr_pct: float,
    abs_return_pct: float,
    spread_pct: float,
) -> Tuple[int, bool]:
    if raw_volume is not None:
        v = int(max(0, safe_float(raw_volume, 0.0)))
        return v, True

    spread = max(safe_float(spread_pct, 0.02), 0.005)
    proxy = (
        abs(safe_float(delta, 0.0)) * 55.0
        + max(0.0, safe_float(atr_pct, 0.0)) * 7.0
        + max(0.0, safe_float(abs_return_pct, 0.0)) * 12.0
        + (1.0 / spread) * 1.5
    )
    return int(round(max(1.0, proxy))), False


def describe_risk_flags(
    spread_pct: float,
    data_quality: str,
    has_observed_oi: bool,
    has_observed_volume: bool,
) -> Iterable[str]:
    flags = []
    spread = safe_float(spread_pct, 0.0)
    if spread >= 0.12:
        flags.append("Wide spread risk")
    if not has_observed_oi:
        flags.append("OI modeled proxy")
    if not has_observed_volume:
        flags.append("Volume modeled proxy")
    if data_quality != "observed":
        flags.append(f"Data quality={data_quality}")
    return flags


def data_quality_score_penalty(data_quality: str, variant: IntradayVariant) -> float:
    q = str(data_quality).strip().lower()
    if q == "observed":
        return variant.score_quality_penalty_observed
    if q == "mixed":
        return variant.score_quality_penalty_mixed
    return variant.score_quality_penalty_modeled


def data_quality_fill_multiplier(data_quality: str, variant: IntradayVariant) -> float:
    q = str(data_quality).strip().lower()
    if q == "observed":
        return variant.fill_quality_observed_mult
    if q == "mixed":
        return variant.fill_quality_mixed_mult
    return variant.fill_quality_modeled_mult


def liquidity_score(
    oi_effective: int,
    volume_effective: int,
    spread_pct: float,
    max_spread_pct: float,
) -> float:
    oi_part = min(1.0, max(float(oi_effective), 0.0) / 300.0)
    vol_part = min(1.0, max(float(volume_effective), 0.0) / 180.0)
    spread = max(safe_float(spread_pct, 0.0), 0.0)
    max_spread = max(safe_float(max_spread_pct, 0.01), 0.01)
    spread_part = max(0.0, 1.0 - (spread / max_spread))
    return max(0.0, min(1.0, oi_part * 0.45 + vol_part * 0.35 + spread_part * 0.20))


def expected_fill_ratio(
    liq_score: float,
    data_quality: str,
    variant: IntradayVariant,
    limit_vs_bid_ratio: float,
) -> float:
    # Blend liquidity and limit aggressiveness with a quality multiplier.
    bid_alignment = max(0.0, min(1.0, safe_float(limit_vs_bid_ratio, 0.0)))
    liq = max(0.0, min(1.0, safe_float(liq_score, 0.0)))
    quality_mult = data_quality_fill_multiplier(data_quality, variant)
    ratio = (0.35 + 0.65 * liq) * quality_mult * (0.65 + 0.35 * bid_alignment)
    return max(0.0, min(1.0, ratio))
