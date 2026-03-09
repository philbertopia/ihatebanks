from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from ovtlyr.backtester.execution_model import (
    adjust_fill_price,
    expected_slippage_bps,
    get_execution_settings,
    partial_fill_ratio,
    summarize_execution_realism,
)
from ovtlyr.backtester.metrics import compute_metrics
from ovtlyr.backtester.position_sizing import (
    cap_symbol_notional,
    risk_budget_contracts,
    vol_target_contracts,
)
from ovtlyr.backtester.series import (
    compute_drawdown_curve,
    compute_monthly_returns,
    compute_rolling_win_rate,
)
from ovtlyr.backtester.intraday_features import (
    IntradayVariant,
    classify_data_quality,
    compute_composite_edge_score,
    compute_entry_limit,
    data_quality_score_penalty,
    describe_risk_flags,
    expected_fill_ratio,
    get_intraday_variant,
    liquidity_score,
    normalize_component,
    observed_or_proxy_oi,
    observed_or_proxy_volume,
    safe_float,
    setup_bucket_key,
)


INITIAL_EQUITY = 100_000.0


@dataclass
class IntradayReport:
    strategy_id: str
    strategy_name: str
    variant: str
    report_date: str
    total_contracts: int
    qualified_contracts: int
    min_qualifiers: int
    warning: Optional[str]
    top_picks: List[Dict[str, Any]]
    data_quality_breakdown: Dict[str, int]
    rejection_counts: Dict[str, int]
    execution_window: Dict[str, str]


def _to_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _third_friday(dt: date) -> bool:
    return dt.weekday() == 4 and 15 <= dt.day <= 21


def _prepare_daily_underlying(data: pd.DataFrame) -> pd.DataFrame:
    df = (
        data[["date", "underlying", "underlying_price"]]
        .drop_duplicates(subset=["date", "underlying"])
        .copy()
    )
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.sort_values(["underlying", "date"])
    df["underlying_price"] = df["underlying_price"].astype(float)
    df["prev_close"] = df.groupby("underlying")["underlying_price"].shift(1)
    df["ma20"] = df.groupby("underlying")["underlying_price"].transform(
        lambda s: s.rolling(20, min_periods=1).mean()
    )
    df["ma50"] = df.groupby("underlying")["underlying_price"].transform(
        lambda s: s.rolling(50, min_periods=1).mean()
    )
    df["abs_change"] = (df["underlying_price"] - df["prev_close"]).abs()
    df["atr14"] = df.groupby("underlying")["abs_change"].transform(
        lambda s: s.rolling(14, min_periods=1).mean()
    )
    df["atr_pct"] = (df["atr14"] / df["underlying_price"]) * 100.0
    df["abs_return_pct"] = (
        (df["underlying_price"] - df["prev_close"]) / df["prev_close"]
    ).abs() * 100.0
    # Entry-time-safe features (known at D open): use D-1 values.
    df["ma20_lag1"] = df.groupby("underlying")["ma20"].shift(1)
    df["ma50_lag1"] = df.groupby("underlying")["ma50"].shift(1)
    df["atr14_lag1"] = df.groupby("underlying")["atr14"].shift(1)
    df["atr_pct_lag1"] = df.groupby("underlying")["atr_pct"].shift(1)
    df["abs_return_pct_lag1"] = df.groupby("underlying")["abs_return_pct"].shift(1)
    return df


def _build_underlying_lookup(underlying_df: pd.DataFrame) -> Dict[Tuple[str, date], Dict[str, float]]:
    out: Dict[Tuple[str, date], Dict[str, float]] = {}
    for _, row in underlying_df.iterrows():
        out[(str(row["underlying"]), row["date"])] = {
            "close": safe_float(row["underlying_price"]),
            "prev_close": safe_float(row["prev_close"]),
            "ma20": safe_float(row.get("ma20")),
            "ma50": safe_float(row.get("ma50")),
            "ma20_lag1": safe_float(row.get("ma20_lag1")),
            "ma50_lag1": safe_float(row.get("ma50_lag1")),
            "atr14": safe_float(row["atr14"]),
            "atr_pct": safe_float(row["atr_pct"]),
            "abs_return_pct": safe_float(row["abs_return_pct"]),
            "atr14_lag1": safe_float(row.get("atr14_lag1")),
            "atr_pct_lag1": safe_float(row.get("atr_pct_lag1")),
            "abs_return_pct_lag1": safe_float(row.get("abs_return_pct_lag1")),
        }
    return out


def _build_prev_day_contract_map(data: pd.DataFrame) -> Dict[Tuple[date, str], Dict[str, float]]:
    out: Dict[Tuple[date, str], Dict[str, float]] = {}
    slim = data[
        ["date", "contract_symbol", "bid", "ask", "underlying_price", "intrinsic_value", "extrinsic_value"]
    ].copy()
    slim["date"] = pd.to_datetime(slim["date"]).dt.date
    for _, row in slim.iterrows():
        out[(row["date"], str(row["contract_symbol"]))] = {
            "bid": safe_float(row["bid"]),
            "ask": safe_float(row["ask"]),
            "underlying_price": safe_float(row["underlying_price"]),
            "intrinsic_value": safe_float(row.get("intrinsic_value")),
            "extrinsic_value": safe_float(row.get("extrinsic_value")),
        }
    return out


def _build_daily_ratio_history(
    data: pd.DataFrame,
    underlying_lookup: Dict[Tuple[str, date], Dict[str, float]],
) -> Dict[str, List[Tuple[date, float]]]:
    """
    Build per-underlying day-level median vol/oi ratio history for unusual-flow baselines.
    """
    by_key: Dict[Tuple[str, date], List[float]] = defaultdict(list)
    cols = ["date", "underlying", "open_interest", "volume", "delta", "spread_pct"]
    available_cols = [col for col in cols if col in data.columns]
    slim = data[available_cols]

    for (day, sym), frame in slim.groupby(["date", "underlying"], sort=True, observed=True):
        day_key = _to_date(day)
        sym_key = str(sym)
        u = underlying_lookup.get((sym_key, day_key))
        if not u:
            continue

        if "spread_pct" in frame.columns:
            spread = pd.to_numeric(frame["spread_pct"], errors="coerce")
        else:
            spread = pd.Series(index=frame.index, dtype=float)
        spread = spread.fillna(0.02).clip(lower=0.005)

        oi_proxy = ((1.0 / spread) * 4.0).clip(lower=50.0).round()
        if "open_interest" in frame.columns:
            oi_source = frame["open_interest"]
            oi_raw = pd.to_numeric(oi_source, errors="coerce").fillna(0.0).clip(lower=0.0)
            oi_missing = oi_source.map(lambda value: value is None)
            oi_effective = oi_raw.where(~oi_missing, oi_proxy)
        else:
            oi_effective = oi_proxy

        if "delta" in frame.columns:
            delta = pd.to_numeric(frame["delta"], errors="coerce")
        else:
            delta = pd.Series(index=frame.index, dtype=float)
        delta = delta.fillna(0.0).abs()

        atr_pct = max(0.0, safe_float(u.get("atr_pct"), 0.0))
        abs_return_pct = max(0.0, safe_float(u.get("abs_return_pct"), 0.0))
        vol_proxy = (
            (delta * 55.0)
            + (atr_pct * 7.0)
            + (abs_return_pct * 12.0)
            + ((1.0 / spread) * 1.5)
        ).clip(lower=1.0).round()
        if "volume" in frame.columns:
            vol_source = frame["volume"]
            vol_raw = pd.to_numeric(vol_source, errors="coerce").fillna(0.0).clip(lower=0.0)
            vol_missing = vol_source.map(lambda value: value is None)
            vol_effective = vol_raw.where(~vol_missing, vol_proxy)
        else:
            vol_effective = vol_proxy

        ratios = (vol_effective / oi_effective.clip(lower=1.0)).astype(float)
        if ratios.empty:
            continue
        ratios_sorted = ratios.sort_values(ignore_index=True)
        by_key[(sym_key, day_key)].append(float(ratios_sorted.iloc[len(ratios_sorted) // 2]))

    history: Dict[str, List[Tuple[date, float]]] = defaultdict(list)
    for (sym, day), ratios in by_key.items():
        history[sym].append((day, ratios[0]))

    for sym in list(history.keys()):
        history[sym] = sorted(history[sym], key=lambda t: t[0])
    return history


def _median_prior_30_days(history: List[Tuple[date, float]], day: date) -> float:
    vals = [v for d, v in history if d < day][-30:]
    if not vals:
        return 1.0
    vals = sorted(vals)
    return float(vals[len(vals) // 2])


def _is_itm(option_type: str, strike: float, prev_close: float) -> Tuple[bool, float]:
    if prev_close <= 0:
        return False, 0.0
    if option_type == "put":
        depth = ((strike - prev_close) / prev_close) * 100.0
        return strike > prev_close, max(depth, 0.0)
    depth = ((prev_close - strike) / prev_close) * 100.0
    return prev_close > strike, max(depth, 0.0)


def _estimate_previous_option_close(
    contract_symbol: str,
    option_type: str,
    strike: float,
    today_bid: float,
    today_ask: float,
    prev_underlying_close: float,
    today_extrinsic: float,
    theta: float,
    prev_day_contract_map: Dict[Tuple[date, str], Dict[str, float]],
    prev_day: date,
) -> float:
    mid_today = max(0.01, (safe_float(today_bid, 0.01) + safe_float(today_ask, 0.01)) / 2.0)
    prev_row = prev_day_contract_map.get((prev_day, contract_symbol))
    if prev_row:
        mid = (safe_float(prev_row["bid"]) + safe_float(prev_row["ask"])) / 2.0
        if mid > 0:
            return round(mid, 4)

    if option_type == "put":
        prev_intrinsic = max(strike - prev_underlying_close, 0.0)
    else:
        prev_intrinsic = max(prev_underlying_close - strike, 0.0)

    # Theta is typically negative; backing one session out adds abs(theta).
    prev_extrinsic = max(0.01, safe_float(today_extrinsic) + abs(safe_float(theta)))
    modeled = max(0.01, prev_intrinsic + prev_extrinsic)
    # Synthetic chains do not always contain exact contract continuity day-to-day.
    # Anchor modeled close near today's midpoint to avoid pathological entry limits.
    lower_bound = max(0.01, mid_today * 0.75)
    upper_bound = max(lower_bound + 0.01, mid_today * 1.25)
    if modeled < lower_bound or modeled > upper_bound:
        return round(mid_today, 4)
    return round(modeled, 4)


def _simulate_intraday_exit(
    entry_price: float,
    close_proxy: float,
    d_underlying: float,
    atr_abs: float,
    delta: float,
    variant: IntradayVariant,
) -> Tuple[float, str]:
    entry = max(safe_float(entry_price, 0.01), 0.01)
    close_px = max(safe_float(close_proxy, entry), 0.01)
    target_px = entry * (1.0 + variant.target_pct)
    stop_px = entry * (1.0 - variant.stop_pct)

    # Deterministic intraday envelope.
    swing = max(safe_float(atr_abs, 0.0), abs(safe_float(d_underlying, 0.0)))
    delta_mag = max(abs(safe_float(delta, 0.0)), 0.05)
    est_high = max(close_px, entry + delta_mag * max(0.0, d_underlying + 0.45 * swing))
    est_low = min(close_px, entry - delta_mag * max(0.0, -d_underlying + 0.45 * swing))

    if est_low <= stop_px and est_high >= target_px:
        # Conflict resolution: use direction-of-day heuristic.
        return (round(target_px, 4), "target_hit") if d_underlying >= 0 else (round(stop_px, 4), "stop_hit")
    if est_low <= stop_px:
        return round(stop_px, 4), "stop_hit"
    if est_high >= target_px:
        return round(target_px, 4), "target_hit"

    activation_px = entry * (1.0 + variant.trailing_activation_pct)
    if est_high >= activation_px:
        trail_stop = est_high * (1.0 - variant.trailing_pct)
        if close_px <= trail_stop:
            return round(max(trail_stop, stop_px), 4), "trailing_stop"

    return round(close_px, 4), "eod_close"


def _candidate_rationale(option_type: str, unusual_factor: float, itm_depth_pct: float, atr_pct: float) -> List[str]:
    direction = "call" if option_type == "call" else "put"
    return [
        f"Unusual {direction} flow proxy elevated ({unusual_factor:.2f}x of 30-day median).",
        f"ITM depth {itm_depth_pct:.2f}% with ATR regime {atr_pct:.2f}% supports intraday movement.",
    ]


def build_intraday_candidates_for_date(
    data: pd.DataFrame,
    target_day: date,
    variant: IntradayVariant,
    bucket_stats: Dict[str, Dict[str, int]],
    ratio_history: Dict[str, List[Tuple[date, float]]],
    underlying_lookup: Dict[Tuple[str, date], Dict[str, float]],
    prev_day_contract_map: Dict[Tuple[date, str], Dict[str, float]],
    universe_symbols: Optional[Sequence[str]] = None,
    min_dte: int = 3,
    max_dte: int = 30,
    day_groups: Optional[Dict[date, pd.DataFrame]] = None,
) -> Tuple[int, List[Dict[str, Any]], Dict[str, int], Dict[str, int]]:
    if day_groups is not None:
        day_rows = day_groups.get(target_day, pd.DataFrame(columns=data.columns))
    else:
        day_rows = data[data["date"] == target_day]
    if universe_symbols:
        allowed = {s.upper() for s in universe_symbols}
        day_rows = day_rows[day_rows["underlying"].astype(str).str.upper().isin(allowed)]

    total_count = int(len(day_rows))
    rejection_counts = {
        "reject_modeled_only": 0,
        "reject_regime": 0,
        "reject_hist_winrate": 0,
        "reject_liquidity": 0,
        "reject_spread": 0,
        "reject_unusual_flow": 0,
        "reject_dte": 0,
        "reject_not_itm": 0,
        "reject_atr": 0,
    }
    if total_count == 0:
        return 0, [], {"observed": 0, "mixed": 0, "modeled": 0}, rejection_counts

    prev_day = target_day - pd.tseries.offsets.BDay(1)
    prev_day = _to_date(prev_day.date())
    candidates: List[Dict[str, Any]] = []
    quality_counts = {"observed": 0, "mixed": 0, "modeled": 0}

    for _, row in day_rows.iterrows():
        sym = str(row["underlying"])
        u = underlying_lookup.get((sym, target_day))
        if not u:
            continue
        entry_safe = str(variant.feature_time_mode).strip().lower() == "entry_safe_lagged"
        atr_abs = safe_float(u.get("atr14_lag1" if entry_safe else "atr14"))
        atr_pct = safe_float(u.get("atr_pct_lag1" if entry_safe else "atr_pct"))
        prev_close_underlying = safe_float(u.get("prev_close"))
        close_underlying = safe_float(u.get("close"))
        abs_ret_pct = safe_float(u.get("abs_return_pct_lag1" if entry_safe else "abs_return_pct"))
        if atr_abs < 3.0:
            rejection_counts["reject_atr"] += 1
            continue

        dte = int(safe_float(row.get("dte"), 0.0))
        if dte < min_dte or dte > max_dte:
            rejection_counts["reject_dte"] += 1
            continue

        option_type = str(row.get("option_type", "call")).lower()
        trend_close = prev_close_underlying if entry_safe else close_underlying
        ma20 = safe_float(u.get("ma20_lag1" if entry_safe else "ma20"), trend_close)
        ma50 = safe_float(u.get("ma50_lag1" if entry_safe else "ma50"), trend_close)

        if variant.require_spy_regime_alignment:
            spy = underlying_lookup.get(("SPY", target_day))
            if not spy:
                rejection_counts["reject_regime"] += 1
                continue
            spy_close = safe_float(spy.get("prev_close" if entry_safe else "close"))
            spy_ma20 = safe_float(spy.get("ma20_lag1" if entry_safe else "ma20"), spy_close)
            spy_ma50 = safe_float(spy.get("ma50_lag1" if entry_safe else "ma50"), spy_close)
            spy_risk_on = spy_close > spy_ma20 and spy_ma20 > spy_ma50
            spy_risk_off = spy_close < spy_ma20 and spy_ma20 < spy_ma50
            if option_type == "call" and not spy_risk_on:
                rejection_counts["reject_regime"] += 1
                continue
            if option_type == "put" and not spy_risk_off:
                rejection_counts["reject_regime"] += 1
                continue

        if variant.require_regime_alignment:
            if option_type == "call":
                if not (trend_close > ma20 and ma20 > ma50):
                    rejection_counts["reject_regime"] += 1
                    continue
            elif option_type == "put":
                if not (trend_close < ma20 and ma20 < ma50):
                    rejection_counts["reject_regime"] += 1
                    continue

        strike = safe_float(row.get("strike"))
        is_itm, itm_depth_pct = _is_itm(option_type, strike, prev_close_underlying)
        if not is_itm:
            rejection_counts["reject_not_itm"] += 1
            continue

        spread_pct = safe_float(row.get("spread_pct"))
        if spread_pct > variant.max_spread_pct:
            rejection_counts["reject_spread"] += 1
            continue

        oi_effective, has_obs_oi = observed_or_proxy_oi(row.get("open_interest"), spread_pct)
        if oi_effective < max(50, int(variant.min_effective_oi)):
            rejection_counts["reject_liquidity"] += 1
            continue

        vol_effective, has_obs_vol = observed_or_proxy_volume(
            row.get("volume"),
            safe_float(row.get("delta")),
            atr_pct,
            abs_ret_pct,
            spread_pct,
        )
        if vol_effective < int(variant.min_effective_volume):
            rejection_counts["reject_liquidity"] += 1
            continue
        vol_oi_ratio = float(vol_effective) / max(float(oi_effective), 1.0)
        baseline = _median_prior_30_days(ratio_history.get(sym, []), target_day)
        unusual_factor = vol_oi_ratio / max(baseline, 1e-6)
        if unusual_factor < variant.min_unusual_factor:
            rejection_counts["reject_unusual_flow"] += 1
            continue

        data_quality = classify_data_quality(has_obs_vol, has_obs_oi)
        if str(variant.data_quality_policy).strip().lower() == "exclude_modeled" and data_quality == "modeled":
            rejection_counts["reject_modeled_only"] += 1
            continue
        liq_score = liquidity_score(
            oi_effective=oi_effective,
            volume_effective=vol_effective,
            spread_pct=spread_pct,
            max_spread_pct=variant.max_spread_pct,
        )
        if liq_score < variant.min_liquidity_score:
            rejection_counts["reject_liquidity"] += 1
            continue
        quality_counts[data_quality] += 1

        bucket = setup_bucket_key(
            delta=safe_float(row.get("delta")),
            itm_depth_pct=itm_depth_pct,
            atr_pct=atr_pct,
            dte=dte,
            vol_oi_ratio=vol_oi_ratio,
        )
        hist = bucket_stats.get(bucket, {"wins": 0, "total": 0})
        hist_total = int(safe_float(hist.get("total"), 0.0))
        hist_win_rate = (
            (safe_float(hist.get("wins")) / max(safe_float(hist.get("total")), 1.0)) * 100.0
            if safe_float(hist.get("total")) > 0
            else 50.0
        )
        if (
            hist_total >= int(variant.min_hist_observations)
            and hist_win_rate < float(variant.min_hist_win_rate)
        ):
            rejection_counts["reject_hist_winrate"] += 1
            continue

        vol_component = normalize_component(unusual_factor, 1.0, 3.0)
        depth_component = normalize_component(itm_depth_pct, 0.0, 10.0)
        atr_component = normalize_component(atr_pct, 2.0, 12.0)
        win_component = max(0.0, min(100.0, hist_win_rate))
        edge_raw = compute_composite_edge_score(
            vol_component,
            depth_component,
            atr_component,
            win_component,
        )

        ask = max(safe_float(row.get("ask"), 0.01), 0.01)
        bid = max(safe_float(row.get("bid"), 0.01), 0.01)
        delta = safe_float(row.get("delta"), 0.0)
        gamma = safe_float(row.get("gamma"), 0.0)
        theta = safe_float(row.get("theta"), 0.0)
        vega = safe_float(row.get("vega"), 0.0)
        iv = safe_float(row.get("implied_volatility"), 0.0)

        prev_opt_close = _estimate_previous_option_close(
            contract_symbol=str(row["contract_symbol"]),
            option_type=option_type,
            strike=strike,
            today_bid=bid,
            today_ask=ask,
            prev_underlying_close=prev_close_underlying,
            today_extrinsic=safe_float(row.get("extrinsic_value"), ask * 0.15),
            theta=theta,
            prev_day_contract_map=prev_day_contract_map,
            prev_day=prev_day,
        )

        entry_limit = compute_entry_limit(ask=ask, previous_close=prev_opt_close, delta=delta)
        d_underlying = close_underlying - prev_close_underlying
        close_proxy = max(0.01, entry_limit + delta * d_underlying + 0.5 * gamma * (d_underlying**2) + theta * 0.9)
        exit_px, exit_reason = _simulate_intraday_exit(
            entry_price=entry_limit,
            close_proxy=close_proxy,
            d_underlying=d_underlying,
            atr_abs=atr_abs,
            delta=delta,
            variant=variant,
        )
        pnl_per_contract = (exit_px - entry_limit) * 100.0
        return_pct = ((exit_px - entry_limit) / entry_limit) * 100.0 if entry_limit > 0 else 0.0

        expiry_date = _to_date(row.get("expiration_date"))
        expiry_kind = "monthly" if _third_friday(expiry_date) else "weekly"
        expiry_bias = 2.0 if expiry_kind == "weekly" else 0.0
        quality_penalty = data_quality_score_penalty(data_quality, variant)
        edge = min(100.0, max(0.0, (edge_raw + expiry_bias) * quality_penalty))

        risk_flags = list(
            describe_risk_flags(
                spread_pct=spread_pct,
                data_quality=data_quality,
                has_observed_oi=has_obs_oi,
                has_observed_volume=has_obs_vol,
            )
        )
        if liq_score < 0.45:
            risk_flags.append("Low liquidity score")

        candidates.append(
            {
                "ticker": sym,
                "name": sym,
                "contract_symbol": str(row.get("contract_symbol")),
                "option_type": option_type,
                "expiry": expiry_date.isoformat(),
                "expiry_kind": expiry_kind,
                "strike": strike,
                "dte": dte,
                "buy_volume": int(vol_effective),
                "open_interest": int(oi_effective),
                "vol_oi_ratio": round(vol_oi_ratio, 4),
                "unusual_factor": round(unusual_factor, 4),
                "itm_depth_pct": round(itm_depth_pct, 4),
                "atr14": round(atr_abs, 4),
                "atr_pct": round(atr_pct, 4),
                "delta": round(delta, 6),
                "gamma": round(gamma, 6),
                "theta": round(theta, 6),
                "vega": round(vega, 6),
                "implied_volatility": round(iv, 6),
                "bid": round(bid, 4),
                "ask": round(ask, 4),
                "previous_close": round(prev_opt_close, 4),
                "entry_limit": round(entry_limit, 4),
                "exit_plan": {
                    "target_pct": round(variant.target_pct * 100.0, 2),
                    "stop_pct": round(variant.stop_pct * 100.0, 2),
                    "trailing_activation_pct": round(variant.trailing_activation_pct * 100.0, 2),
                    "trailing_pct": round(variant.trailing_pct * 100.0, 2),
                },
                "rationale": _candidate_rationale(option_type, unusual_factor, itm_depth_pct, atr_pct),
                "risk_flags": risk_flags,
                "data_quality": data_quality,
                "scoring_components": {
                    "vol_oi": round(vol_component, 4),
                    "itm_depth": round(depth_component, 4),
                    "atr_pct": round(atr_component, 4),
                    "historical_win_rate": round(win_component, 4),
                    "quality_penalty": round(quality_penalty, 4),
                    "edge_before_quality_penalty": round(edge_raw + expiry_bias, 4),
                },
                "historical_win_rate": round(hist_win_rate, 4),
                "composite_edge_score": round(edge, 4),
                "liquidity_score": round(liq_score, 4),
                "bucket_key": bucket,
                "simulated_exit_price": round(exit_px, 4),
                "simulated_exit_reason": exit_reason,
                "simulated_return_pct": round(return_pct, 4),
                "simulated_pnl_per_contract": round(pnl_per_contract, 4),
                "execution_window": {"entry_time": "09:35", "exit_time": "15:55"},
            }
        )

    candidates = sorted(candidates, key=lambda x: x["composite_edge_score"], reverse=True)
    for i, row in enumerate(candidates, start=1):
        row["rank"] = i
    return total_count, candidates, quality_counts, rejection_counts


def _sorted_days(data: pd.DataFrame, start_date: date, end_date: date) -> List[date]:
    days = sorted(data["date"].unique())
    return [d for d in days if start_date <= d <= end_date]


def _bootstrap_bucket_stats(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    variant: IntradayVariant,
    universe_symbols: Optional[Sequence[str]],
    underlying_lookup: Dict[Tuple[str, date], Dict[str, float]],
    prev_day_contract_map: Dict[Tuple[date, str], Dict[str, float]],
    ratio_history: Dict[str, List[Tuple[date, float]]],
    day_groups: Dict[date, pd.DataFrame],
    max_days: int = 252,
) -> Dict[str, Dict[str, int]]:
    days = _sorted_days(data, start_date, end_date)
    if not days:
        return {}
    days = days[-max_days:]
    bucket_stats: Dict[str, Dict[str, int]] = {}
    for d in days:
        _, candidates, _, _ = build_intraday_candidates_for_date(
            data=data,
            target_day=d,
            variant=variant,
            bucket_stats=bucket_stats,
            ratio_history=ratio_history,
            underlying_lookup=underlying_lookup,
            prev_day_contract_map=prev_day_contract_map,
            universe_symbols=universe_symbols,
            day_groups=day_groups,
        )
        for c in candidates[: variant.max_trades_per_day]:
            b = c["bucket_key"]
            item = bucket_stats.setdefault(b, {"wins": 0, "total": 0})
            item["total"] += 1
            if c["simulated_return_pct"] > 0:
                item["wins"] += 1
    return bucket_stats


def generate_intraday_candidate_report(
    data: pd.DataFrame,
    report_date: date,
    variant_name: str = "baseline",
    universe_symbols: Optional[Sequence[str]] = None,
    top_n: int = 15,
    min_qualifiers: int = 30,
) -> IntradayReport:
    variant = get_intraday_variant(variant_name)
    df = data.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    underlying_df = _prepare_daily_underlying(df)
    underlying_lookup = _build_underlying_lookup(underlying_df)
    prev_day_contract_map = _build_prev_day_contract_map(df)
    ratio_history = _build_daily_ratio_history(df, underlying_lookup)
    day_groups = {d: g for d, g in df.groupby("date", sort=False)}

    warm_end = report_date - pd.tseries.offsets.BDay(1)
    warm_end_date = _to_date(warm_end.date())
    warm_start_date = warm_end_date - pd.tseries.offsets.BDay(300)
    warm_start_date = _to_date(warm_start_date.date())
    bucket_stats = _bootstrap_bucket_stats(
        data=df,
        start_date=warm_start_date,
        end_date=warm_end_date,
        variant=variant,
        universe_symbols=universe_symbols,
        underlying_lookup=underlying_lookup,
        prev_day_contract_map=prev_day_contract_map,
        ratio_history=ratio_history,
        day_groups=day_groups,
        max_days=252,
    )

    total_count, candidates, quality_counts, rejection_counts = build_intraday_candidates_for_date(
        data=df,
        target_day=report_date,
        variant=variant,
        bucket_stats=bucket_stats,
        ratio_history=ratio_history,
        underlying_lookup=underlying_lookup,
        prev_day_contract_map=prev_day_contract_map,
        universe_symbols=universe_symbols,
        day_groups=day_groups,
    )
    qualified_count = len(candidates)
    warning = None
    if qualified_count < min_qualifiers:
        warning = (
            f"Qualified contracts below target minimum: {qualified_count} < {min_qualifiers}. "
            "Ranking produced with available candidates."
        )

    top_rows = candidates[: max(1, int(top_n))]
    return IntradayReport(
        strategy_id="intraday_open_close_options",
        strategy_name="Intraday Open-Close Options",
        variant=variant.name,
        report_date=report_date.isoformat(),
        total_contracts=total_count,
        qualified_contracts=qualified_count,
        min_qualifiers=int(min_qualifiers),
        warning=warning,
        top_picks=top_rows,
        data_quality_breakdown=quality_counts,
        rejection_counts=rejection_counts,
        execution_window={"entry_time": "09:35", "exit_time": "15:55"},
    )


def run_intraday_open_close_options(
    data: pd.DataFrame,
    start_date: date,
    end_date: date,
    assumptions_mode: str,
    universe_symbols: Optional[Sequence[str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    variant = get_intraday_variant(assumptions_mode)
    exec_settings = get_execution_settings(config or {})
    risk_cfg = (config or {}).get("risk", {}) if isinstance(config, dict) else {}
    target_annual_vol = float((config or {}).get("execution", {}).get("target_annual_vol", 0.18))
    if variant.name == "conservative":
        target_annual_vol = min(target_annual_vol, 0.14)
    elif variant.name == "aggressive":
        target_annual_vol = max(target_annual_vol, 0.22)
    max_symbol_notional_pct = float(risk_cfg.get("max_symbol_notional_pct", 0.20))
    _dates_raw = pd.to_datetime(data["date"]).dt.date
    _lookback_start = start_date - pd.tseries.offsets.BDay(30)
    _lookback_start_date = _lookback_start.date() if hasattr(_lookback_start, "date") else _lookback_start
    df = data.loc[(_dates_raw >= _lookback_start_date) & (_dates_raw <= end_date)].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date

    underlying_df = _prepare_daily_underlying(df)
    underlying_lookup = _build_underlying_lookup(underlying_df)
    prev_day_contract_map = _build_prev_day_contract_map(df)
    ratio_history = _build_daily_ratio_history(df, underlying_lookup)
    day_groups = {d: g for d, g in df.groupby("date", sort=False)}

    days = _sorted_days(df, start_date, end_date)
    if not days:
        raise ValueError("No trading days available in selected period for intraday strategy")

    equity = INITIAL_EQUITY
    equity_curve: List[float] = [equity]
    equity_points: List[Tuple[date, float]] = []
    trade_pnls: List[float] = []
    closed_trades: List[Dict[str, Any]] = []
    bucket_stats: Dict[str, Dict[str, int]] = {}
    quality_totals = {"observed": 0, "mixed": 0, "modeled": 0}
    rejection_totals = {
        "reject_modeled_only": 0,
        "reject_regime": 0,
        "reject_hist_winrate": 0,
        "reject_liquidity": 0,
        "reject_spread": 0,
        "reject_unusual_flow": 0,
        "reject_dte": 0,
        "reject_not_itm": 0,
        "reject_atr": 0,
    }
    candidate_total = 0
    candidate_qualified = 0
    top_snapshot: List[Dict[str, Any]] = []
    last_candidate_day: Optional[date] = None
    fill_rejections = 0
    partial_fill_trades = 0
    total_fees_paid = 0.0
    fill_ratios: List[float] = []
    slippage_bps: List[float] = []
    spread_cost_total = 0.0
    slippage_cost_total = 0.0
    fills_attempted = 0
    fills_completed = 0

    for day in days:
        total_count, candidates, quality_counts, rejection_counts = build_intraday_candidates_for_date(
            data=df,
            target_day=day,
            variant=variant,
            bucket_stats=bucket_stats,
            ratio_history=ratio_history,
            underlying_lookup=underlying_lookup,
            prev_day_contract_map=prev_day_contract_map,
            universe_symbols=universe_symbols,
            day_groups=day_groups,
        )
        candidate_total += total_count
        candidate_qualified += len(candidates)
        for k in quality_totals.keys():
            quality_totals[k] += int(quality_counts.get(k, 0))
        for k in rejection_totals.keys():
            rejection_totals[k] += int(rejection_counts.get(k, 0))

        if candidates:
            top_snapshot = candidates[:15]
            last_candidate_day = day

        selected = candidates[: variant.max_trades_per_day]
        day_pnl = 0.0
        for c in selected:
            fills_attempted += 1
            bid = max(safe_float(c.get("bid"), 0.01), 0.01)
            ask = max(safe_float(c.get("ask"), bid + 0.01), bid + 0.01)
            spread_abs = max(ask - bid, 0.01)
            raw_entry_limit = max(safe_float(c["entry_limit"]), 0.01)
            if raw_entry_limit < bid:
                underbid_gap_pct = (bid - raw_entry_limit) / max(bid, 1e-6)
                if underbid_gap_pct > variant.max_underbid_gap_pct:
                    fill_rejections += 1
                    continue
                entry_limit = bid
            else:
                entry_limit = raw_entry_limit

            limit_vs_bid_ratio = entry_limit / max(ask, 1e-6)
            liq_score = safe_float(c.get("liquidity_score"), 0.0)
            data_quality = str(c.get("data_quality", "modeled"))
            fill_ratio = expected_fill_ratio(
                liq_score=liq_score,
                data_quality=data_quality,
                variant=variant,
                limit_vs_bid_ratio=limit_vs_bid_ratio,
            )
            fill_ratio = min(
                1.0,
                (
                    fill_ratio
                    + partial_fill_ratio(liq_score, "open", exec_settings)
                )
                / 2.0,
            )
            fill_ratios.append(fill_ratio)

            alloc = equity * variant.allocation_per_trade
            target_qty_risk = risk_budget_contracts(
                allocation_dollars=alloc,
                option_price=entry_limit,
                min_contracts=1,
                max_contracts=max(1, variant.max_trades_per_day * 2),
            )
            atr_pct = safe_float(c.get("atr_pct"), 2.0)
            underlying_annual_vol = max((atr_pct / 100.0) * (252.0 ** 0.5), 0.08)
            target_qty_vol = vol_target_contracts(
                equity=equity,
                option_price=entry_limit,
                underlying_annual_vol=underlying_annual_vol,
                target_annual_vol=target_annual_vol,
                min_contracts=1,
                max_contracts=max(1, variant.max_trades_per_day * 2),
            )
            target_qty = max(1, min(target_qty_risk, target_qty_vol))
            target_qty = cap_symbol_notional(
                contracts=target_qty,
                option_price=max(entry_limit, safe_float(c.get("strike"), entry_limit)),
                equity=equity,
                max_symbol_notional_pct=max_symbol_notional_pct,
            )
            target_qty = max(1, target_qty)
            raw_fill_qty = int(round(target_qty * fill_ratio))
            if raw_fill_qty == 0 and target_qty > 0 and fill_ratio >= variant.min_fill_ratio_for_one_lot:
                raw_fill_qty = 1

            cap_by_oi = max(1, int(max(0.0, safe_float(c.get("open_interest"), 0.0) * variant.oi_capacity_pct)))
            cap_by_vol = max(1, int(max(0.0, safe_float(c.get("buy_volume"), 0.0) * variant.volume_capacity_pct)))
            capacity_qty = min(cap_by_oi, cap_by_vol)

            qty = min(target_qty, raw_fill_qty, capacity_qty)
            if qty < 1:
                fill_rejections += 1
                continue
            fills_completed += 1
            if qty < target_qty:
                partial_fill_trades += 1

            slippage_quality_mult = 1.0 if data_quality == "observed" else (1.10 if data_quality == "mixed" else 1.20)
            if entry_limit >= ask:
                entry_base = min(
                    entry_limit,
                    ask + (spread_abs * variant.entry_slippage_spread_factor * slippage_quality_mult),
                )
            else:
                # Passive fill in/near the spread if the limit is below ask.
                entry_base = max(
                    bid,
                    min(ask, entry_limit),
                )
            entry_exec = adjust_fill_price(
                price=entry_base,
                spread_abs=spread_abs,
                side="buy",
                tod_bucket="open",
                settings=exec_settings,
                data_quality=data_quality,
            )

            exit_px_model = max(0.01, safe_float(c["simulated_exit_price"]))
            exit_slip_mult = variant.exit_slippage_spread_factor * slippage_quality_mult
            reason = str(c.get("simulated_exit_reason", "eod_close"))
            if reason == "stop_hit":
                exit_slip_mult *= 1.30
            elif reason == "target_hit":
                exit_slip_mult *= 0.90
            exit_base = max(0.01, exit_px_model - (spread_abs * exit_slip_mult))
            exit_exec = adjust_fill_price(
                price=exit_base,
                spread_abs=spread_abs,
                side="sell",
                tod_bucket="close",
                settings=exec_settings,
                data_quality=data_quality,
            )

            entry_slip_bps = expected_slippage_bps(
                spread_pct=spread_abs / max(entry_exec, 1e-6),
                tod_bucket="open",
                settings=exec_settings,
                data_quality=data_quality,
            )
            exit_slip_bps = expected_slippage_bps(
                spread_pct=spread_abs / max(exit_exec, 1e-6),
                tod_bucket="close",
                settings=exec_settings,
                data_quality=data_quality,
            )
            slippage_bps.append((entry_slip_bps + exit_slip_bps) / 2.0)
            spread_cost_total += spread_abs * qty * 100.0
            slippage_cost_total += (
                ((entry_exec - entry_base) + (exit_base - exit_exec)) * qty * 100.0
            )

            fee = variant.round_trip_fee_per_contract * qty
            total_fees_paid += fee
            realized = ((exit_exec - entry_exec) * 100.0 * qty) - fee
            day_pnl += realized
            trade_pnls.append(realized)

            closed_trades.append(
                {
                    "symbol": c["ticker"],
                    "contract_symbol": c["contract_symbol"],
                    "entry_date": f"{day.isoformat()}T09:35:00",
                    "close_date": f"{day.isoformat()}T15:55:00",
                    "entry_price": entry_exec,
                    "close_price": exit_exec,
                    "qty": qty,
                    "exit_reason": reason,
                    "fill_ratio": fill_ratio,
                    "fee_paid": fee,
                    "realized_pnl": realized,
                }
            )

            bucket = c["bucket_key"]
            item = bucket_stats.setdefault(bucket, {"wins": 0, "total": 0})
            item["total"] += 1
            if safe_float(c["simulated_return_pct"]) > 0:
                item["wins"] += 1

        equity += day_pnl
        equity_curve.append(equity)
        equity_points.append((day, equity))

    metrics = compute_metrics(closed_trades, equity_curve)
    metrics["trading_days"] = len(days)
    metrics["candidate_count_total"] = candidate_total
    metrics["candidate_count_qualified"] = candidate_qualified
    for k, v in rejection_totals.items():
        metrics[k] = int(v)
    metrics["fill_rejections"] = int(fill_rejections)
    metrics["partial_fill_trades"] = int(partial_fill_trades)
    metrics["total_fees_paid"] = round(float(total_fees_paid), 4)
    metrics["avg_fill_ratio"] = round(
        sum(fill_ratios) / len(fill_ratios), 4
    ) if fill_ratios else 0.0
    execution_realism = summarize_execution_realism(
        slippage_bps=slippage_bps,
        spread_cost_total=spread_cost_total,
        slippage_cost_total=slippage_cost_total,
        filled=fills_completed,
        partial=partial_fill_trades,
        attempted=fills_attempted,
    )
    metrics.update(execution_realism)

    return {
        "strategy_parameters": {
            "target_pct": variant.target_pct,
            "stop_pct": variant.stop_pct,
            "trailing_activation_pct": variant.trailing_activation_pct,
            "trailing_pct": variant.trailing_pct,
            "max_spread_pct": variant.max_spread_pct,
            "min_unusual_factor": variant.min_unusual_factor,
            "max_trades_per_day": variant.max_trades_per_day,
            "allocation_per_trade": variant.allocation_per_trade,
            "min_effective_oi": variant.min_effective_oi,
            "min_effective_volume": variant.min_effective_volume,
            "min_liquidity_score": variant.min_liquidity_score,
            "entry_slippage_spread_factor": variant.entry_slippage_spread_factor,
            "exit_slippage_spread_factor": variant.exit_slippage_spread_factor,
            "round_trip_fee_per_contract": variant.round_trip_fee_per_contract,
            "min_fill_ratio_for_one_lot": variant.min_fill_ratio_for_one_lot,
            "oi_capacity_pct": variant.oi_capacity_pct,
            "volume_capacity_pct": variant.volume_capacity_pct,
            "max_underbid_gap_pct": variant.max_underbid_gap_pct,
            "target_annual_vol": target_annual_vol,
            "max_symbol_notional_pct": max_symbol_notional_pct,
            "feature_time_mode": variant.feature_time_mode,
            "data_quality_policy": variant.data_quality_policy,
            "execution_model": {
                "block_first_minutes": exec_settings.block_first_minutes,
                "open_slippage_mult": exec_settings.open_slippage_mult,
                "midday_slippage_mult": exec_settings.midday_slippage_mult,
                "close_slippage_mult": exec_settings.close_slippage_mult,
            },
            "entry_time": "09:35",
            "exit_time": "15:55",
        },
        "metrics": metrics,
        "equity_curve": [float(v) for v in equity_curve],
        "equity_points": equity_points,
        "trade_pnls": [float(v) for v in trade_pnls],
        "series": {
            "equity_curve": [float(v) for v in equity_curve],
            "drawdown_curve": compute_drawdown_curve(equity_curve),
            "rolling_win_rate": compute_rolling_win_rate(trade_pnls, window=20),
            "monthly_returns": compute_monthly_returns(equity_points),
        },
        "intraday_report": top_snapshot,
        "candidate_count_total": candidate_total,
        "candidate_count_qualified": candidate_qualified,
        "data_quality_breakdown": quality_totals,
        "rejection_counts": rejection_totals,
        "execution_realism": execution_realism,
        "execution_window": {"entry_time": "09:35", "exit_time": "15:55"},
        "last_candidate_day": last_candidate_day.isoformat() if last_candidate_day else "",
    }
