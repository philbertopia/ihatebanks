import pytest
from ovtlyr.utils.math_utils import (
    compute_intrinsic_value,
    compute_extrinsic_value,
    compute_extrinsic_pct,
    compute_spread_pct,
    compute_unrealized_pnl,
    compute_realized_pnl,
)


def test_intrinsic_call_itm():
    assert compute_intrinsic_value("call", 155.0, 150.0) == pytest.approx(5.0)


def test_intrinsic_call_otm():
    assert compute_intrinsic_value("call", 145.0, 150.0) == 0.0


def test_intrinsic_put_itm():
    assert compute_intrinsic_value("put", 145.0, 150.0) == pytest.approx(5.0)


def test_extrinsic_value():
    assert compute_extrinsic_value(7.0, 5.0) == pytest.approx(2.0)


def test_extrinsic_value_never_negative():
    assert compute_extrinsic_value(4.0, 5.0) == 0.0


def test_extrinsic_pct():
    assert compute_extrinsic_pct(2.0, 10.0) == pytest.approx(0.20)


def test_spread_pct():
    assert compute_spread_pct(9.5, 10.0) == pytest.approx(0.05)


def test_spread_pct_zero_ask():
    assert compute_spread_pct(0, 0) == 1.0


def test_unrealized_pnl():
    # 1 contract: price moved from $10 to $12 → +$200
    assert compute_unrealized_pnl(10.0, 12.0, 1) == pytest.approx(200.0)


def test_realized_pnl_loss():
    assert compute_realized_pnl(10.0, 8.0, 2) == pytest.approx(-400.0)
