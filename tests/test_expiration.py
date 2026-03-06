import pytest
from datetime import date
from ovtlyr.utils.time_utils import (
    get_third_friday,
    get_monthly_expirations,
    is_final_week,
    days_to_expiration,
)


def test_third_friday_known():
    # January 2024: Fridays are 5, 12, 19, 26 → 3rd Friday = Jan 19
    assert get_third_friday(2024, 1) == date(2024, 1, 19)


def test_third_friday_another():
    # March 2024: Fridays are 1, 8, 15, 22, 29 → 3rd Friday = Mar 15
    assert get_third_friday(2024, 3) == date(2024, 3, 15)


def test_is_final_week_true():
    today = date(2024, 1, 13)
    expiry = date(2024, 1, 19)
    assert is_final_week(expiry, today) is True


def test_is_final_week_false():
    today = date(2024, 1, 1)
    expiry = date(2024, 1, 19)
    assert is_final_week(expiry, today) is False


def test_days_to_expiration():
    today = date(2024, 1, 1)
    expiry = date(2024, 1, 21)
    assert days_to_expiration(expiry, today) == 20


def test_monthly_expirations_returns_dates():
    today = date(2024, 1, 2)
    exps = get_monthly_expirations(min_dte=8, max_dte=60, today=today)
    assert len(exps) > 0
    for exp in exps:
        dte = days_to_expiration(exp, today)
        assert 8 <= dte <= 60
        assert not is_final_week(exp, today)
