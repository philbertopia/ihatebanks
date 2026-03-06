from datetime import date, timedelta

from ovtlyr.backtester.walkforward import (
    generate_walkforward_windows,
    summarize_oos_runs,
)


def test_generate_walkforward_windows_basic():
    start = date(2024, 1, 1)
    days = [start + timedelta(days=i) for i in range(0, 400)]
    windows = generate_walkforward_windows(days, train_days=200, test_days=50, step_days=50)
    assert len(windows) >= 3
    assert windows[0].train_start == days[0]
    assert windows[0].test_start == days[200]


def test_summarize_oos_runs_pass_and_fail():
    pass_rows = [
        {"total_return_pct": 12.0, "sharpe_ratio": 0.9, "max_drawdown_pct": 18.0},
        {"total_return_pct": 8.0, "sharpe_ratio": 0.8, "max_drawdown_pct": 22.0},
    ]
    pass_summary = summarize_oos_runs(pass_rows)
    assert pass_summary["pass_validation"] is True

    fail_rows = [
        {"total_return_pct": -4.0, "sharpe_ratio": 0.2, "max_drawdown_pct": 45.0},
        {"total_return_pct": 1.0, "sharpe_ratio": 0.1, "max_drawdown_pct": 40.0},
    ]
    fail_summary = summarize_oos_runs(fail_rows)
    assert fail_summary["pass_validation"] is False

