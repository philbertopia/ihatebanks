import math
from datetime import date

import pandas as pd
import pytest

from ovtlyr.backtester.openclaw_engines import (
    _compute_regime_effective_risk_pct,
    _apply_regime_credit_overrides,
    _build_option_leg,
    _credit_timing_signals,
    _lookup_leg_close_price,
    _put_credit_params,
    _regime_credit_params,
    _resolve_regime_score_risk_scale,
    _resolve_regime_side_risk_pct,
    _research_index_swing_params,
    _route_index_swing_structure,
    _select_bull_call_spread,
    run_openclaw_variant,
)


def _sample_credit_spread_data() -> pd.DataFrame:
    rows = []
    days = pd.bdate_range("2024-01-02", periods=360)
    for i, day in enumerate(days):
        if i < 220:
            spy = 100.0 + (0.20 * i) + (8.0 * math.sin(i / 3.0))
            qqq = 200.0 + (0.34 * i) + (16.0 * math.sin(i / 4.0))
        else:
            j = i - 220
            spy = 144.0 - (0.30 * j) + (8.0 * math.sin(i / 3.0))
            qqq = 274.8 - (0.48 * j) + (16.0 * math.sin(i / 4.0))

        for symbol, px in (("SPY", spy), ("QQQ", qqq)):
            rows.append(
                {
                    "date": day.date().isoformat(),
                    "underlying": symbol,
                    "underlying_price": round(px, 4),
                }
            )
    return pd.DataFrame(rows)


def _sample_credit_spread_data_with_pairs() -> pd.DataFrame:
    rows = []
    days = pd.bdate_range("2024-01-02", periods=360)
    symbol_specs = {
        "SPY": (100.0, 0.20, 8.0, 3.0),
        "QQQ": (200.0, 0.34, 16.0, 4.0),
        "IWM": (150.0, 0.26, 10.0, 3.5),
        "GLD": (175.0, 0.12, 4.0, 5.5),
        "TLT": (110.0, 0.08, 3.0, 6.5),
    }
    bear_turn = 220
    for i, day in enumerate(days):
        for symbol, (start_px, up_slope, amplitude, cycle) in symbol_specs.items():
            if i < bear_turn:
                px = start_px + (up_slope * i) + (amplitude * math.sin(i / cycle))
            else:
                j = i - bear_turn
                down_slope = up_slope * 1.55
                px = (
                    start_px
                    + (up_slope * bear_turn)
                    - (down_slope * j)
                    + (amplitude * math.sin(i / cycle))
                )
            rows.append(
                {
                    "date": day.date().isoformat(),
                    "underlying": symbol,
                    "underlying_price": round(px, 4),
                }
            )
    return pd.DataFrame(rows)


def _sample_falling_knife_data() -> pd.DataFrame:
    rows = []
    days = pd.bdate_range("2023-01-03", periods=360)
    for i, day in enumerate(days):
        spy = 400.0 + (0.14 * i) + (2.0 * math.sin(i / 10.0))
        qqq = 260.0 + (0.32 * i) + (8.0 * math.sin(i / 9.0))

        if 220 <= i < 224:
            qqq -= 14.0 * (i - 219)
        elif 224 <= i < 232:
            qqq -= 56.0 - (2.0 * (i - 223))

        for symbol, px in (("SPY", spy), ("QQQ", qqq)):
            rows.append(
                {
                    "date": day.date().isoformat(),
                    "underlying": symbol,
                    "underlying_price": round(px, 4),
                }
            )
    return pd.DataFrame(rows)


def _sample_small_account_option_data() -> pd.DataFrame:
    rows = []
    days = pd.bdate_range("2024-01-02", periods=90)
    expiries = [pd.Timestamp("2024-02-16").date(), pd.Timestamp("2024-04-19").date()]

    for i, day in enumerate(days):
        d = day.date()
        spy = 100.0 + (0.12 * math.sin(i / 5.0))
        msft = 200.0 + (0.55 * i)

        for expiry in expiries:
            dte = (expiry - d).days
            if dte <= 0:
                continue
            t_ratio = max(min(dte / 60.0, 1.0), 0.0)

            spy_specs = [
                ("put", 96.0, -0.12, 0.55 * t_ratio),
                ("put", 94.0, -0.05, 0.20 * t_ratio),
                ("call", 104.0, 0.12, 0.55 * t_ratio),
                ("call", 106.0, 0.05, 0.20 * t_ratio),
            ]
            for opt_type, strike, delta, extrinsic in spy_specs:
                intrinsic = max(strike - spy, 0.0) if opt_type == "put" else max(spy - strike, 0.0)
                mid = intrinsic + extrinsic
                bid = max(mid - 0.03, 0.01)
                ask = bid + 0.06
                rows.append(
                    {
                        "date": d.isoformat(),
                        "underlying": "SPY",
                        "contract_symbol": f"SPY_{expiry.isoformat()}_{opt_type}_{strike:.2f}",
                        "option_type": opt_type,
                        "strike": strike,
                        "expiration_date": expiry.isoformat(),
                        "dte": dte,
                        "bid": round(bid, 4),
                        "ask": round(ask, 4),
                        "delta": delta,
                        "implied_volatility": 0.18,
                        "open_interest": 1000,
                        "underlying_price": round(spy, 4),
                        "spread_pct": round((ask - bid) / max(ask, 0.01), 4),
                    }
                )

            msft_specs = [
                ("call", 200.0, 0.72, max(msft - 200.0, 0.0) + (5.2 * t_ratio)),
                ("call", 205.0, 0.60, max(msft - 205.0, 0.0) + (4.0 * t_ratio)),
                ("call", 210.0, 0.44, max(msft - 210.0, 0.0) + (2.8 * t_ratio)),
                ("call", 215.0, 0.30, max(msft - 215.0, 0.0) + (1.9 * t_ratio)),
            ]
            for opt_type, strike, delta, mid in msft_specs:
                bid = max(mid - 0.10, 0.01)
                ask = bid + 0.20
                rows.append(
                    {
                        "date": d.isoformat(),
                        "underlying": "MSFT",
                        "contract_symbol": f"MSFT_{expiry.isoformat()}_{opt_type}_{strike:.2f}",
                        "option_type": opt_type,
                        "strike": strike,
                        "expiration_date": expiry.isoformat(),
                        "dte": dte,
                        "bid": round(bid, 4),
                        "ask": round(ask, 4),
                        "delta": delta,
                        "implied_volatility": 0.22,
                        "open_interest": 1000,
                        "underlying_price": round(msft, 4),
                        "spread_pct": round((ask - bid) / max(ask, 0.01), 4),
                    }
                )

    return pd.DataFrame(rows)


def _sample_aapl_video_option_data() -> pd.DataFrame:
    rows = []
    days = pd.bdate_range("2023-01-03", periods=420)
    expiries = [
        (pd.Timestamp("2023-03-17") + pd.Timedelta(days=(28 * k))).date()
        for k in range(24)
    ]
    strikes = [150.0, 155.0, 160.0, 165.0, 170.0, 175.0, 180.0, 185.0, 190.0, 195.0]

    for i, day in enumerate(days):
        d = day.date()
        spot = 165.0 + (0.08 * i) + (2.0 * math.sin(i / 8.0))
        if i < 220:
            iv = 0.21
        elif i < 310:
            iv = 0.34
        else:
            iv = 0.14

        for expiry in expiries:
            dte = (expiry - d).days
            if dte <= 7 or dte > 70:
                continue
            t_scale = max((dte / 45.0) ** 0.5, 0.35)

            for strike in strikes:
                gap = (strike - spot) / 6.0
                call_delta = 1.0 / (1.0 + math.exp(gap))
                put_delta = call_delta - 1.0

                for option_type, delta in (("call", call_delta), ("put", put_delta)):
                    intrinsic = (
                        max(spot - strike, 0.0)
                        if option_type == "call"
                        else max(strike - spot, 0.0)
                    )
                    moneyness_gap = abs((strike / spot) - 1.0)
                    time_value = max(
                        0.18,
                        iv * spot * 0.06 * t_scale * math.exp(-moneyness_gap * 12.0),
                    )
                    mid = intrinsic + time_value
                    bid = max(mid - 0.12, 0.05)
                    ask = bid + 0.24
                    rows.append(
                        {
                            "date": d.isoformat(),
                            "underlying": "AAPL",
                            "contract_symbol": f"AAPL_{expiry.isoformat()}_{option_type}_{strike:.2f}",
                            "option_type": option_type,
                            "strike": strike,
                            "expiration_date": expiry.isoformat(),
                            "dte": dte,
                            "bid": round(bid, 4),
                            "ask": round(ask, 4),
                            "delta": round(delta, 4),
                            "implied_volatility": round(iv, 4),
                            "open_interest": 1500,
                            "underlying_price": round(spot, 4),
                            "spread_pct": round((ask - bid) / max(ask, 0.01), 4),
                        }
                    )

    return pd.DataFrame(rows)


def _sample_index_swing_option_data() -> pd.DataFrame:
    rows = []
    days = pd.bdate_range("2023-01-03", periods=380)
    expiries = [
        (days[0] + pd.Timedelta(days=14 * k)).date()
        for k in range(4, 60)
    ]
    spy_strikes = [float(v) for v in range(340, 521, 10)]
    qqq_strikes = [float(v) for v in range(260, 531, 10)]

    def _spot(symbol: str, i: int) -> float:
        if symbol == "SPY":
            base = 400.0 + (0.24 * i) + (3.0 * math.sin(i / 12.0))
            if 288 <= i <= 292:
                base -= 3.5 * (i - 287)
            elif 293 <= i <= 299:
                base -= max(0.0, 17.5 - (2.5 * (i - 292)))
            elif 320 <= i <= 324:
                base -= 3.8 * (i - 319)
            elif 325 <= i <= 332:
                base -= max(0.0, 19.0 - (2.2 * (i - 324)))
            return base
        base = 300.0 + (0.34 * i) + (5.0 * math.sin(i / 11.0))
        if 288 <= i <= 292:
            base -= 5.5 * (i - 287)
        elif 293 <= i <= 299:
            base -= max(0.0, 27.5 - (3.5 * (i - 292)))
        elif 320 <= i <= 324:
            base -= 6.2 * (i - 319)
        elif 325 <= i <= 332:
            base -= max(0.0, 31.0 - (3.5 * (i - 324)))
        return base

    for i, day in enumerate(days):
        d = day.date()
        for symbol, strikes in (("SPY", spy_strikes), ("QQQ", qqq_strikes)):
            spot = _spot(symbol, i)
            iv = 0.16
            if i >= 310:
                iv = 0.33
            elif i >= 250:
                iv = 0.19

            for expiry in expiries:
                dte = (expiry - d).days
                if dte < 20 or dte > 70:
                    continue
                t_scale = max((dte / 45.0) ** 0.5, 0.35)

                for strike in strikes:
                    gap = ((strike / max(spot, 1.0)) - 1.0) * 22.0
                    call_delta = 1.0 / (1.0 + math.exp(gap))
                    put_delta = call_delta - 1.0

                    for option_type, delta in (("call", call_delta), ("put", put_delta)):
                        intrinsic = (
                            max(spot - strike, 0.0)
                            if option_type == "call"
                            else max(strike - spot, 0.0)
                        )
                        moneyness = abs((strike / max(spot, 1.0)) - 1.0)
                        time_value = max(
                            0.10,
                            iv
                            * spot
                            * 0.035
                            * t_scale
                            * math.exp(-moneyness * 9.0),
                        )
                        mid = intrinsic + time_value
                        bid = max(mid - max(0.05, mid * 0.04), 0.05)
                        ask = bid + max(0.10, mid * 0.06)
                        open_interest = max(
                            75,
                            int(1200 * math.exp(-moneyness * 7.0)),
                        )
                        rows.append(
                            {
                                "date": d.isoformat(),
                                "underlying": symbol,
                                "contract_symbol": f"{symbol}_{expiry.isoformat()}_{option_type}_{strike:.2f}",
                                "option_type": option_type,
                                "strike": strike,
                                "expiration_date": expiry.isoformat(),
                                "dte": dte,
                                "bid": round(bid, 4),
                                "ask": round(ask, 4),
                                "delta": round(delta, 4),
                                "implied_volatility": round(iv, 4),
                                "open_interest": open_interest,
                                "underlying_price": round(spot, 4),
                                "spread_pct": round((ask - bid) / max(ask, 0.01), 4),
                            }
                        )

    return pd.DataFrame(rows)


def test_run_openclaw_regime_credit_spread_switches_between_put_and_call_legs():
    data = _sample_credit_spread_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2024, 1, 2),
        end_date=date(2025, 5, 19),
        strategy_id="openclaw_regime_credit_spread",
        assumptions_mode="regime_balanced",
    )

    assert out.strategy_id == "openclaw_regime_credit_spread"
    assert out.strategy_name == "OpenClaw Regime Credit Spread"
    assert out.engine_type == "openclaw_regime_credit_spread_engine"
    assert out.strategy_parameters["bull_profile_mode"] == "legacy_replica"
    assert out.strategy_parameters["bear_profile_mode"] == "ccs_baseline"
    assert out.component_metrics["entry_counts"]["put"] > 0
    assert out.component_metrics["entry_counts"]["call"] > 0
    assert out.metrics["put_entries"] == out.component_metrics["entry_counts"]["put"]
    assert out.metrics["call_entries"] == out.component_metrics["entry_counts"]["call"]
    assert out.metrics["trading_days"] > 200
    assert len(out.equity_curve) == out.metrics["trading_days"] + 1


def test_run_openclaw_regime_credit_spread_supports_new_hybrid_mode():
    data = _sample_credit_spread_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2024, 1, 2),
        end_date=date(2025, 5, 19),
        strategy_id="openclaw_regime_credit_spread",
        assumptions_mode="regime_legacy_defensive",
    )

    assert out.strategy_parameters["bull_profile_mode"] == "legacy_replica"
    assert out.strategy_parameters["bear_profile_mode"] == "ccs_defensive"
    assert out.strategy_parameters["neutral_profile_mode"] == "ccs_defensive"
    assert out.strategy_parameters["allow_neutral_call_entries"] is True
    assert out.component_metrics["entry_counts"]["put"] > 0
    assert out.component_metrics["entry_counts"]["call"] > 0


def test_run_openclaw_regime_credit_spread_defaults_to_spy_qqq_allowed_symbols():
    data = _sample_credit_spread_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2024, 1, 2),
        end_date=date(2025, 5, 19),
        strategy_id="openclaw_regime_credit_spread",
        assumptions_mode="regime_legacy_defensive",
    )

    assert out.universe == "SPY,QQQ"
    assert out.strategy_parameters["allowed_symbols"] == ["SPY", "QQQ"]
    assert out.component_metrics["allowed_symbols"] == ["SPY", "QQQ"]
    assert set(out.component_metrics["entry_counts_by_symbol"]) == {"SPY", "QQQ"}


def test_run_openclaw_regime_credit_spread_respects_custom_allowed_symbols():
    data = _sample_credit_spread_data_with_pairs()

    out = run_openclaw_variant(
        data=data,
        config={"allowed_symbols": ["SPY", "GLD"]},
        start_date=date(2024, 1, 2),
        end_date=date(2025, 5, 19),
        strategy_id="openclaw_regime_credit_spread",
        assumptions_mode="regime_legacy_defensive",
    )

    assert out.universe == "SPY,GLD"
    assert out.strategy_parameters["allowed_symbols"] == ["SPY", "GLD"]
    assert out.component_metrics["allowed_symbols"] == ["SPY", "GLD"]
    assert set(out.component_metrics["entry_counts_by_symbol"]) == {"SPY", "GLD"}
    assert (
        out.component_metrics["entry_counts_by_symbol"]["SPY"]
        + out.component_metrics["entry_counts_by_symbol"]["GLD"]
    ) == (
        out.component_metrics["entry_counts"]["put"]
        + out.component_metrics["entry_counts"]["call"]
    )


def test_run_openclaw_regime_credit_spread_supports_spy_context_for_non_spy_pair():
    data = _sample_credit_spread_data_with_pairs()

    out = run_openclaw_variant(
        data=data,
        config={
            "allowed_symbols": ["QQQ", "IWM"],
            "context_symbols": ["SPY"],
        },
        start_date=date(2024, 1, 2),
        end_date=date(2025, 5, 19),
        strategy_id="openclaw_regime_credit_spread",
        assumptions_mode="regime_legacy_defensive",
    )

    assert out.universe == "QQQ,IWM"
    assert out.strategy_parameters["allowed_symbols"] == ["QQQ", "IWM"]
    assert out.strategy_parameters["context_symbols"] == ["SPY"]
    assert out.component_metrics["context_symbols"] == ["SPY"]
    assert set(out.component_metrics["entry_counts_by_symbol"]) == {"QQQ", "IWM"}
    assert out.metrics["total_trades"] > 0


def test_run_openclaw_regime_credit_spread_bear_only_mode_disables_neutral_entries():
    data = _sample_credit_spread_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2024, 1, 2),
        end_date=date(2025, 5, 19),
        strategy_id="openclaw_regime_credit_spread",
        assumptions_mode="regime_legacy_defensive_bear_only",
    )

    assert out.strategy_parameters["bull_profile_mode"] == "legacy_replica"
    assert out.strategy_parameters["bear_profile_mode"] == "ccs_defensive"
    assert out.strategy_parameters["allow_neutral_call_entries"] is False
    assert out.metrics["put_entries"] > 0
    assert out.metrics["call_entries"] > 0


def test_credit_timing_signals_allow_bull_pullback_only_when_conditions_match():
    profile = _regime_credit_params("timed_legacy_defensive_50_10_r100")

    good = _credit_timing_signals(
        profile=profile,
        regime="bull",
        ret3=-0.02,
        rsi_val=44.0,
        px=102.0,
        ma20_val=101.0,
        ma50_val=100.0,
    )
    blocked = _credit_timing_signals(
        profile=profile,
        regime="bull",
        ret3=0.01,
        rsi_val=44.0,
        px=102.0,
        ma20_val=101.0,
        ma50_val=100.0,
    )

    assert good["bull_pullback"] is True
    assert blocked["bull_pullback"] is False


def test_credit_timing_signals_allow_bear_rally_fade_only_when_conditions_match():
    profile = _regime_credit_params("timed_legacy_defensive_50_10_r100")

    good = _credit_timing_signals(
        profile=profile,
        regime="bear",
        ret3=0.02,
        rsi_val=61.0,
        px=98.0,
        ma20_val=99.0,
        ma50_val=101.0,
    )
    blocked = _credit_timing_signals(
        profile=profile,
        regime="bear",
        ret3=-0.01,
        rsi_val=61.0,
        px=98.0,
        ma20_val=99.0,
        ma50_val=101.0,
    )

    assert good["bear_rally_fade"] is True
    assert blocked["bear_rally_fade"] is False


def test_credit_timing_signals_block_neutral_gate_without_overextension():
    profile = _regime_credit_params("timed_legacy_defensive_50_10_r100")

    blocked = _credit_timing_signals(
        profile=profile,
        regime="neutral",
        ret3=0.02,
        rsi_val=62.0,
        px=100.5,
        ma20_val=100.0,
        ma50_val=100.0,
    )
    allowed = _credit_timing_signals(
        profile=profile,
        regime="neutral",
        ret3=0.02,
        rsi_val=62.0,
        px=101.5,
        ma20_val=100.0,
        ma50_val=100.0,
    )

    assert blocked["neutral_rally_fade"] is False
    assert allowed["neutral_rally_fade"] is True


def test_regime_credit_overrides_apply_profit_dte_and_risk_scaling():
    profile = _regime_credit_params("timed_legacy_defensive_40_7_r075")
    params = _apply_regime_credit_overrides(_put_credit_params("legacy_replica"), profile)

    assert params["take_profit_ratio"] == pytest.approx(0.40)
    assert params["force_close_dte"] == pytest.approx(7.0)
    assert params["risk_pct"] == pytest.approx(0.015 * 0.75)


def test_timed_bear_only_variant_disables_neutral_calls():
    profile = _regime_credit_params("timed_legacy_defensive_bear_only_50_10_r100")

    assert profile["timing_enabled"] is True
    assert profile["timed_bear_only"] is True
    assert profile["allow_neutral_call_entries"] is False


@pytest.mark.parametrize(
    ("variant", "expected_threshold"),
    [
        ("scored_legacy_defensive_s65", 65.0),
        ("scored_legacy_defensive_s75", 75.0),
    ],
)
def test_scored_regime_variant_enables_setup_scores(variant, expected_threshold):
    profile = _regime_credit_params(variant)

    assert profile["setup_score_enabled"] is True
    assert profile["setup_score_threshold"] == pytest.approx(expected_threshold)
    assert profile["vol_target_sizing"] is False


def test_scored_vol_regime_variant_applies_base_risk_override():
    profile = _regime_credit_params("scored_legacy_defensive_s75_vol")
    params = _apply_regime_credit_overrides(_put_credit_params("legacy_replica"), profile)

    assert profile["vol_target_sizing"] is True
    assert params["risk_pct"] == pytest.approx(0.01)


def test_run_timed_regime_credit_spread_produces_put_and_call_entries():
    data = _sample_credit_spread_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2024, 1, 2),
        end_date=date(2025, 5, 19),
        strategy_id="openclaw_regime_credit_spread",
        assumptions_mode="timed_legacy_defensive_50_10_r100",
    )

    assert out.component_metrics["timing_enabled"] is True
    assert out.component_metrics["timed_entry_counts"]["put"] > 0
    assert out.component_metrics["timed_entry_counts"]["call"] > 0
    assert out.component_metrics["entry_counts"]["put"] > 0
    assert out.component_metrics["entry_counts"]["call"] > 0
    assert out.strategy_parameters["management_overrides"]["take_profit_ratio_override"] == pytest.approx(0.50)
    assert out.strategy_parameters["management_overrides"]["force_close_dte_override"] == 10


def test_run_scored_regime_credit_spread_records_setup_scores():
    data = _sample_credit_spread_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2024, 1, 2),
        end_date=date(2025, 5, 19),
        strategy_id="openclaw_regime_credit_spread",
        assumptions_mode="scored_legacy_defensive_s70",
    )

    assert out.component_metrics["setup_score_threshold"] == pytest.approx(70.0)
    assert out.strategy_parameters["setup_score_enabled"] is True
    assert out.metrics["avg_entry_setup_score"] >= 0.0
    assert (
        out.component_metrics["setup_score_signal_counts"]["put"]
        + out.component_metrics["setup_score_signal_counts"]["call"]
    ) > 0


def test_regime_credit_research_empty_overrides_preserve_baseline_behavior():
    data = _sample_credit_spread_data()

    base = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2024, 1, 2),
        end_date=date(2025, 5, 19),
        strategy_id="openclaw_regime_credit_spread",
        assumptions_mode="regime_legacy_defensive",
    )
    overridden = run_openclaw_variant(
        data=data,
        config={"regime_research_overrides": {}},
        start_date=date(2024, 1, 2),
        end_date=date(2025, 5, 19),
        strategy_id="openclaw_regime_credit_spread",
        assumptions_mode="regime_legacy_defensive",
    )

    assert overridden.metrics["total_return_pct"] == pytest.approx(base.metrics["total_return_pct"])
    assert overridden.metrics["sharpe_ratio"] == pytest.approx(base.metrics["sharpe_ratio"])
    assert overridden.metrics["max_drawdown_pct"] == pytest.approx(base.metrics["max_drawdown_pct"])
    assert overridden.component_metrics["entry_counts"] == base.component_metrics["entry_counts"]


def test_resolve_regime_score_risk_scale_uses_bucket_boundaries():
    overrides = {
        "score_weighted_sizing_enabled": True,
        "score_sizing_buckets": [
            {"min_score": 0.0, "risk_mult": 0.75, "label": "score>=0:x0.75"},
            {"min_score": 65.0, "risk_mult": 1.00, "label": "score>=65:x1"},
            {"min_score": 75.0, "risk_mult": 1.15, "label": "score>=75:x1.15"},
            {"min_score": 85.0, "risk_mult": 1.25, "label": "score>=85:x1.25"},
        ],
    }

    assert _resolve_regime_score_risk_scale(64.99, overrides) == (pytest.approx(0.75), "score>=0:x0.75")
    assert _resolve_regime_score_risk_scale(65.0, overrides) == (pytest.approx(1.00), "score>=65:x1")
    assert _resolve_regime_score_risk_scale(75.0, overrides) == (pytest.approx(1.15), "score>=75:x1.15")
    assert _resolve_regime_score_risk_scale(85.0, overrides) == (pytest.approx(1.25), "score>=85:x1.25")


def test_resolve_regime_side_risk_pct_applies_side_specific_overrides():
    params = {"risk_pct": 0.009}
    overrides = {
        "bull_risk_pct_override": 0.0165,
        "bear_risk_pct_override": 0.0075,
        "neutral_risk_pct_override": None,
    }

    assert _resolve_regime_side_risk_pct("bull", "put", params, overrides) == pytest.approx(0.0165)
    assert _resolve_regime_side_risk_pct("bear", "call", params, overrides) == pytest.approx(0.0075)
    assert _resolve_regime_side_risk_pct("neutral", "call", params, overrides) == pytest.approx(0.0075)
    assert _resolve_regime_side_risk_pct("bull", "call", params, overrides) == pytest.approx(0.009)


def test_compute_regime_effective_risk_pct_multiplies_in_expected_order():
    risk_pct = _compute_regime_effective_risk_pct(
        side_risk_pct=0.0165,
        score_risk_scale=1.15,
        dynamic_risk_scale=0.75,
        overlay_risk_scale=0.50,
    )

    assert risk_pct == pytest.approx(0.0165 * 1.15 * 0.75 * 0.50)


def test_run_regime_credit_research_score_weighted_sizing_records_bucket_metrics():
    data = _sample_credit_spread_data()

    out = run_openclaw_variant(
        data=data,
        config={
            "regime_research_overrides": {
                "score_weighted_sizing_enabled": True,
                "score_sizing_buckets": [
                    {"min_score": 0.0, "risk_mult": 0.75},
                    {"min_score": 65.0, "risk_mult": 1.00},
                    {"min_score": 75.0, "risk_mult": 1.15},
                ],
            }
        },
        start_date=date(2024, 1, 2),
        end_date=date(2025, 5, 19),
        strategy_id="openclaw_regime_credit_spread",
        assumptions_mode="regime_legacy_defensive",
    )

    bucket_counts = out.component_metrics["score_risk_bucket_counts"]
    total_bucketed = sum(bucket_counts["put"].values()) + sum(bucket_counts["call"].values())
    total_entries = out.component_metrics["entry_counts"]["put"] + out.component_metrics["entry_counts"]["call"]

    assert out.strategy_parameters["score_weighted_sizing_enabled"] is True
    assert out.metrics["avg_entry_setup_score"] >= 0.0
    assert out.metrics["avg_entry_score_risk_scale"] > 0.0
    assert total_bucketed == total_entries
    assert len(out.trade_records or []) == out.metrics["total_trades"]


def test_run_openclaw_regime_credit_spread_rejects_unknown_mode():
    data = _sample_credit_spread_data()

    with pytest.raises(ValueError, match="Unsupported assumptions mode"):
        run_openclaw_variant(
            data=data,
            config={},
            start_date=date(2024, 1, 2),
            end_date=date(2025, 5, 19),
            strategy_id="openclaw_regime_credit_spread",
            assumptions_mode="not_a_mode",
        )


def test_run_openclaw_put_credit_spread_qqq_falling_knife_is_qqq_only():
    data = _sample_falling_knife_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2023, 1, 3),
        end_date=date(2024, 4, 22),
        strategy_id="openclaw_put_credit_spread",
        assumptions_mode="qqq_falling_knife",
    )

    assert out.strategy_id == "openclaw_put_credit_spread"
    assert out.variant == "qqq_falling_knife"
    assert out.universe == "QQQ"
    assert out.strategy_parameters["allowed_symbols"] == ["QQQ"]
    assert out.component_metrics["allowed_symbols"] == ["QQQ"]
    assert out.component_metrics["entry_counts_by_symbol"]["QQQ"] > 0
    assert (
        out.component_metrics["signal_counts_by_symbol"]["QQQ"]
        >= out.component_metrics["entry_counts_by_symbol"]["QQQ"]
    )
    assert out.metrics["total_trades"] > 0


def test_run_research_small_account_spy_iron_condor_proxy_returns_payload():
    data = _sample_small_account_option_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2024, 1, 2),
        end_date=date(2024, 5, 6),
        strategy_id="research_small_account_options",
        assumptions_mode="spy_iron_condor_proxy",
    )

    assert out.strategy_id == "research_small_account_options"
    assert out.variant == "spy_iron_condor_proxy"
    assert out.universe == "SPY"
    assert out.component_metrics["structure"] == "iron_condor_proxy"
    assert out.metrics["trading_days"] > 50
    assert len(out.equity_curve) == out.metrics["trading_days"] + 1


def test_run_research_small_account_msft_bull_call_spread_returns_payload():
    data = _sample_small_account_option_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2024, 1, 2),
        end_date=date(2024, 5, 6),
        strategy_id="research_small_account_options",
        assumptions_mode="msft_bull_call_spread",
    )

    assert out.strategy_id == "research_small_account_options"
    assert out.variant == "msft_bull_call_spread"
    assert out.universe == "MSFT"
    assert out.component_metrics["structure"] == "bull_call_spread"
    assert out.metrics["trading_days"] > 50
    assert len(out.equity_curve) == out.metrics["trading_days"] + 1


def test_run_research_small_account_aapl_bull_put_45_21_returns_payload():
    data = _sample_aapl_video_option_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2023, 1, 3),
        end_date=date(2024, 8, 12),
        strategy_id="research_small_account_options",
        assumptions_mode="aapl_bull_put_45_21",
    )

    assert out.strategy_id == "research_small_account_options"
    assert out.variant == "aapl_bull_put_45_21"
    assert out.universe == "AAPL"
    assert out.component_metrics["structure"] == "bull_put_spread"
    assert out.component_metrics["entries"] > 0
    assert out.metrics["trading_days"] > 100
    assert len(out.equity_curve) == out.metrics["trading_days"] + 1


def test_run_research_small_account_aapl_long_call_low_iv_returns_payload():
    data = _sample_aapl_video_option_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2023, 1, 3),
        end_date=date(2024, 8, 12),
        strategy_id="research_small_account_options",
        assumptions_mode="aapl_long_call_low_iv",
    )

    assert out.strategy_id == "research_small_account_options"
    assert out.variant == "aapl_long_call_low_iv"
    assert out.universe == "AAPL"
    assert out.component_metrics["structure"] == "long_call"
    assert out.component_metrics["entries"] > 0
    assert out.metrics["trading_days"] > 100
    assert len(out.equity_curve) == out.metrics["trading_days"] + 1


def test_route_index_swing_structure_switches_between_buying_and_selling():
    profile = _research_index_swing_params("pullback_baseline_30_45")
    assert (
        _route_index_swing_structure(
            profile=profile,
            regime="bull",
            bull_pullback_trigger=True,
            rally_fade_trigger=False,
            iv_percentile=25.0,
        )
        == "bull_call_spread"
    )
    assert (
        _route_index_swing_structure(
            profile=profile,
            regime="bull",
            bull_pullback_trigger=True,
            rally_fade_trigger=False,
            iv_percentile=62.0,
        )
        == "put_credit_spread"
    )
    assert (
        _route_index_swing_structure(
            profile=profile,
            regime="bear",
            bull_pullback_trigger=False,
            rally_fade_trigger=True,
            iv_percentile=68.0,
        )
        == "call_credit_spread"
    )
    assert (
        _route_index_swing_structure(
            profile=profile,
            regime="neutral",
            bull_pullback_trigger=False,
            rally_fade_trigger=True,
            iv_percentile=68.0,
            neutral_overextended=False,
        )
        == "cash"
    )


def test_route_index_swing_structure_allows_bull_overextension_ccs_in_v2():
    profile = _research_index_swing_params("pullback_baseline_30_45_v2")

    assert (
        _route_index_swing_structure(
            profile=profile,
            regime="bull",
            bull_pullback_trigger=False,
            rally_fade_trigger=True,
            iv_percentile=62.0,
            neutral_overextended=False,
            bull_overextended=True,
        )
        == "call_credit_spread"
    )


def test_select_bull_call_spread_prefers_liquid_target_delta_contracts():
    data = _sample_index_swing_option_data()
    day = sorted(pd.to_datetime(data["date"]).dt.date.unique())[300]
    day_slice = data[pd.to_datetime(data["date"]).dt.date == day].copy()

    candidate = _select_bull_call_spread(
        day_slice=day_slice,
        underlying="SPY",
        target_dte=37,
        min_dte=30,
        max_dte=45,
        target_long_delta=0.60,
        target_short_delta=0.35,
        min_debit_dollars=150.0,
        max_debit_dollars=1200.0,
        max_spread_pct=0.12,
        min_open_interest=200,
    )

    assert candidate is not None
    assert candidate["entry_debit_dollars"] >= 150.0
    assert candidate["entry_debit_dollars"] <= 1200.0
    assert candidate["max_gain_dollars"] > 0.0
    assert candidate["combined_spread_pct"] <= 0.12
    assert abs(candidate["long_call"]["entry_delta"] - 0.60) <= 0.15
    assert abs(candidate["short_call"]["entry_delta"] - 0.35) <= 0.20


def test_lookup_leg_close_price_falls_back_to_synthetic_when_leg_missing():
    row = pd.Series(
        {
            "contract_symbol": "SPY_2024-03-15_call_450.00",
            "underlying": "SPY",
            "option_type": "call",
            "strike": 450.0,
            "expiration_date": date(2024, 3, 15),
            "dte": 42,
            "bid": 3.8,
            "ask": 4.2,
            "delta": 0.58,
            "underlying_price": 452.0,
        }
    )
    leg = _build_option_leg(row)
    fallback_slice = pd.DataFrame(
        [{"underlying": "SPY", "underlying_price": 456.0}]
    )

    price = _lookup_leg_close_price(
        day_slice=fallback_slice,
        leg=leg,
        day=date(2024, 2, 20),
        side="sell",
    )

    assert price > 0.01
    assert price != pytest.approx(3.8)


def test_run_research_index_swing_options_returns_payload():
    data = _sample_index_swing_option_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2023, 1, 3),
        end_date=date(2024, 6, 14),
        strategy_id="research_index_swing_options",
        assumptions_mode="pullback_baseline_30_45",
    )

    assert out.strategy_id == "research_index_swing_options"
    assert out.variant == "pullback_baseline_30_45"
    assert out.universe == "SPY,QQQ"
    assert out.engine_type == "research_index_swing_options_engine"
    assert out.metrics["trading_days"] > 250
    assert len(out.equity_curve) == out.metrics["trading_days"] + 1
    assert out.component_metrics["signal_counts"]["bull_pullback"] > 0


def test_run_research_index_convex_swing_returns_payload():
    data = _sample_index_swing_option_data()

    out = run_openclaw_variant(
        data=data,
        config={},
        start_date=date(2023, 1, 3),
        end_date=date(2024, 6, 14),
        strategy_id="research_index_convex_swing",
        assumptions_mode="qqq_pullback_low_iv_30_45",
    )

    assert out.strategy_id == "research_index_convex_swing"
    assert out.variant == "qqq_pullback_low_iv_30_45"
    assert out.engine_type == "research_index_convex_swing_engine"
    assert out.metrics["trading_days"] > 250
    assert len(out.equity_curve) == out.metrics["trading_days"] + 1
