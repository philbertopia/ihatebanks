import pandas as pd

from main import _filter_backtest_data_to_universe


def test_filter_backtest_data_to_universe_restricts_underlyings():
    frame = pd.DataFrame(
        [
            {"date": "2024-01-02", "underlying": "AAPL", "value": 1},
            {"date": "2024-01-02", "underlying": "MSFT", "value": 2},
            {"date": "2024-01-02", "underlying": "qqq", "value": 3},
        ]
    )

    out = _filter_backtest_data_to_universe(frame, ["MSFT", "QQQ"])

    assert set(out["underlying"]) == {"MSFT", "qqq"}
    assert len(frame) == 3
