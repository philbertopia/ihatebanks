import pytest

from ovtlyr.backtester.intraday_features import (
    compute_composite_edge_score,
    compute_entry_limit,
    data_quality_score_penalty,
    expected_fill_ratio,
    get_intraday_variant,
    liquidity_score,
    normalize_component,
    setup_bucket_key,
)


def test_compute_entry_limit_ask_greater_than_prev_close():
    limit_price = compute_entry_limit(ask=4.0, previous_close=3.5, delta=0.5)
    assert limit_price == pytest.approx(5.0, rel=1e-6)


def test_compute_entry_limit_ask_less_than_prev_close():
    limit_price = compute_entry_limit(ask=3.0, previous_close=3.5, delta=0.5)
    assert limit_price == pytest.approx(2.0, rel=1e-6)


def test_compute_entry_limit_delta_floor_prevents_explosion():
    limit_price = compute_entry_limit(ask=4.0, previous_close=3.5, delta=0.0)
    assert limit_price > 0.0
    assert limit_price < 20.0


def test_normalize_component_bounds():
    assert normalize_component(0, 1, 3) == 0.0
    assert normalize_component(10, 1, 3) == 100.0
    mid = normalize_component(2, 1, 3)
    assert mid == pytest.approx(50.0)


def test_composite_score_weighting():
    score = compute_composite_edge_score(
        vol_oi_component=100,
        itm_depth_component=50,
        atr_component=50,
        win_rate_component=50,
    )
    # 40 + 10 + 10 + 10
    assert score == pytest.approx(70.0)


def test_setup_bucket_key_stable_shape():
    key = setup_bucket_key(delta=0.82, itm_depth_pct=4.3, atr_pct=5.0, dte=12, vol_oi_ratio=1.7)
    assert key.startswith("d")
    assert key.count("|") == 4


def test_get_intraday_variant_known_and_unknown():
    baseline = get_intraday_variant("baseline")
    assert baseline.name == "baseline"
    with pytest.raises(ValueError):
        get_intraday_variant("not_a_variant")


def test_new_conservative_family_variants_are_registered():
    regime = get_intraday_variant("conservative_regime_lite")
    hist = get_intraday_variant("conservative_hist_55")
    scan = get_intraday_variant("conservative_scan_quality")

    assert regime.require_regime_alignment is True
    assert hist.min_hist_win_rate == pytest.approx(55.0)
    assert hist.min_hist_observations == 6
    assert scan.min_liquidity_score > get_intraday_variant("conservative").min_liquidity_score
    assert scan.max_spread_pct < get_intraday_variant("conservative").max_spread_pct


def test_data_quality_score_penalty_ordering():
    v = get_intraday_variant("baseline")
    observed = data_quality_score_penalty("observed", v)
    mixed = data_quality_score_penalty("mixed", v)
    modeled = data_quality_score_penalty("modeled", v)
    assert observed >= mixed >= modeled


def test_liquidity_score_bounds():
    hi = liquidity_score(oi_effective=800, volume_effective=500, spread_pct=0.02, max_spread_pct=0.12)
    lo = liquidity_score(oi_effective=60, volume_effective=20, spread_pct=0.12, max_spread_pct=0.12)
    assert 0.0 <= hi <= 1.0
    assert 0.0 <= lo <= 1.0
    assert hi > lo


def test_expected_fill_ratio_penalizes_modeled_data():
    v = get_intraday_variant("baseline")
    observed = expected_fill_ratio(0.7, "observed", v, 0.95)
    modeled = expected_fill_ratio(0.7, "modeled", v, 0.95)
    assert 0.0 <= observed <= 1.0
    assert 0.0 <= modeled <= 1.0
    assert observed > modeled
