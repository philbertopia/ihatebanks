from datetime import date

import pandas as pd

from ovtlyr.backtester.intraday_features import get_intraday_variant
from ovtlyr.backtester.intraday_features import observed_or_proxy_oi, observed_or_proxy_volume
from ovtlyr.backtester.intraday_options_engine import (
    build_intraday_candidates_for_date,
    run_intraday_open_close_options,
    _build_daily_ratio_history,
    _build_prev_day_contract_map,
    _build_underlying_lookup,
    _prepare_daily_underlying,
)


def _sample_data() -> pd.DataFrame:
    rows = []
    days = ["2025-06-03", "2025-06-04", "2025-06-05", "2025-06-06"]
    prices = [100.0, 104.0, 110.0, 108.0]
    for d, px in zip(days, prices):
        rows.append(
            {
                "date": d,
                "underlying": "AAA",
                "contract_symbol": "AAA250620C00095000",
                "option_type": "call",
                "strike": 95.0,
                "expiration_date": "2025-06-20",
                "dte": 15,
                "bid": 6.8 + (px - 100) * 0.1,
                "ask": 7.1 + (px - 100) * 0.1,
                "delta": 0.82,
                "gamma": 0.02,
                "theta": -0.04,
                "vega": 0.08,
                "implied_volatility": 0.32,
                "open_interest": None,
                "underlying_price": px,
                "intrinsic_value": max(px - 95.0, 0.0),
                "extrinsic_value": 1.0,
                "extrinsic_pct": 0.14,
                "spread_pct": 0.04,
            }
        )
    return pd.DataFrame(rows)


def test_build_intraday_candidates_for_date_returns_ranked_candidates():
    data = _sample_data()
    data["date"] = pd.to_datetime(data["date"]).dt.date
    variant = get_intraday_variant("baseline")
    underlying_df = _prepare_daily_underlying(data)
    underlying_lookup = _build_underlying_lookup(underlying_df)
    prev_day_contract_map = _build_prev_day_contract_map(data)
    ratio_history = _build_daily_ratio_history(data, underlying_lookup)

    total, candidates, dq, rejections = build_intraday_candidates_for_date(
        data=data,
        target_day=date(2025, 6, 5),
        variant=variant,
        bucket_stats={},
        ratio_history=ratio_history,
        underlying_lookup=underlying_lookup,
        prev_day_contract_map=prev_day_contract_map,
        universe_symbols=["AAA"],
    )

    assert total >= 1
    assert len(candidates) >= 1
    assert candidates[0]["rank"] == 1
    assert "composite_edge_score" in candidates[0]
    assert set(dq.keys()) == {"observed", "mixed", "modeled"}
    assert {
        "reject_modeled_only",
        "reject_regime",
        "reject_hist_winrate",
        "reject_liquidity",
        "reject_spread",
        "reject_unusual_flow",
        "reject_dte",
        "reject_not_itm",
        "reject_atr",
    }.issubset(set(rejections.keys()))


def test_run_intraday_open_close_options_returns_backtest_payload():
    data = _sample_data()
    out = run_intraday_open_close_options(
        data=data,
        start_date=date(2025, 6, 3),
        end_date=date(2025, 6, 6),
        assumptions_mode="baseline",
        universe_symbols=["AAA"],
    )

    assert "metrics" in out
    assert "equity_curve" in out
    assert "intraday_report" in out
    assert "candidate_count_total" in out
    assert out["metrics"]["trading_days"] >= 1


def test_build_daily_ratio_history_matches_manual_proxy_logic():
    data = pd.DataFrame(
        [
            {
                "date": "2025-06-03",
                "underlying": "AAA",
                "contract_symbol": "AAA1",
                "open_interest": None,
                "volume": None,
                "delta": 0.80,
                "spread_pct": 0.04,
                "underlying_price": 100.0,
            },
            {
                "date": "2025-06-03",
                "underlying": "AAA",
                "contract_symbol": "AAA2",
                "open_interest": 120,
                "volume": 18,
                "delta": 0.70,
                "spread_pct": 0.05,
                "underlying_price": 100.0,
            },
            {
                "date": "2025-06-04",
                "underlying": "AAA",
                "contract_symbol": "AAA3",
                "open_interest": None,
                "volume": 30,
                "delta": 0.82,
                "spread_pct": 0.03,
                "underlying_price": 104.0,
            },
            {
                "date": "2025-06-03",
                "underlying": "BBB",
                "contract_symbol": "BBB1",
                "open_interest": 80,
                "volume": None,
                "delta": -0.65,
                "spread_pct": 0.06,
                "underlying_price": 55.0,
            },
        ]
    )
    data["date"] = pd.to_datetime(data["date"]).dt.date

    underlying_df = _prepare_daily_underlying(data)
    underlying_lookup = _build_underlying_lookup(underlying_df)

    expected = {}
    for (day, sym), frame in data.groupby(["date", "underlying"], sort=True):
        u = underlying_lookup[(sym, day)]
        ratios = []
        for _, row in frame.iterrows():
            oi_effective, _ = observed_or_proxy_oi(row.get("open_interest"), row.get("spread_pct"))
            vol_effective, _ = observed_or_proxy_volume(
                row.get("volume"),
                row.get("delta"),
                u.get("atr_pct"),
                u.get("abs_return_pct"),
                row.get("spread_pct"),
            )
            ratios.append(float(vol_effective) / max(float(oi_effective), 1.0))
        ratios_sorted = sorted(ratios)
        expected.setdefault(sym, []).append((day, ratios_sorted[len(ratios_sorted) // 2]))

    actual = _build_daily_ratio_history(data, underlying_lookup)

    assert actual.keys() == expected.keys()
    for sym in expected:
        assert actual[sym] == expected[sym]
