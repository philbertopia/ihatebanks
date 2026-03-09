from datetime import date

import pandas as pd

from scripts.run_regime_universe_sweep import (
    build_shared_price_frame,
    cohort_symbols,
    first_shared_valid_day,
)


def test_cohort_symbols_collects_unique_symbols_in_order():
    cohort = {
        "pairs": [
            {"symbols": ["SPY", "QQQ"]},
            {"symbols": ["QQQ", "IBIT"]},
            {"symbols": ["GLD", "IBIT"]},
        ]
    }

    assert cohort_symbols(cohort) == ["SPY", "QQQ", "IBIT", "GLD"]


def test_first_shared_valid_day_uses_actual_first_common_history():
    idx = [
        date(2024, 1, 10),
        date(2024, 1, 11),
        date(2024, 1, 12),
        date(2024, 1, 16),
    ]
    prices = pd.DataFrame(
        {
            "SPY": [470.0, 471.0, 472.0, 473.0],
            "QQQ": [400.0, 401.0, 402.0, 403.0],
            "IBIT": [None, 24.0, 24.2, 24.1],
        },
        index=idx,
    )

    shared_start = first_shared_valid_day(
        prices=prices,
        symbols=["SPY", "QQQ", "IBIT"],
        requested_start=date(2020, 1, 2),
        end_day=date(2025, 12, 31),
    )

    assert shared_start == date(2024, 1, 11)


def test_build_shared_price_frame_filters_to_common_complete_rows():
    idx = [
        date(2024, 1, 10),
        date(2024, 1, 11),
        date(2024, 1, 12),
        date(2024, 1, 16),
    ]
    prices = pd.DataFrame(
        {
            "SPY": [470.0, 471.0, 472.0, 473.0],
            "IBIT": [None, 24.0, None, 24.1],
        },
        index=idx,
    )

    out = build_shared_price_frame(
        prices=prices,
        symbols=["SPY", "IBIT"],
        start_day=date(2024, 1, 11),
        end_day=date(2024, 1, 16),
    )

    assert list(out.index) == [date(2024, 1, 11), date(2024, 1, 16)]
    assert list(out.columns) == ["SPY", "IBIT"]
