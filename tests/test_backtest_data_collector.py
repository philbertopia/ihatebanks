from datetime import date

import pandas as pd

from ovtlyr.backtester.data_collector import BacktestDataCollector


def test_load_cached_data_respects_file_date_window(tmp_path, monkeypatch):
    monkeypatch.setattr("ovtlyr.backtester.data_collector.CACHE_DIR", str(tmp_path))

    for day in ["2024-01-02", "2024-01-03", "2024-01-04"]:
        pd.DataFrame(
            [
                {
                    "date": day,
                    "underlying": "AAA",
                    "contract_symbol": f"AAA-{day}",
                    "ask": 1.0,
                }
            ]
        ).to_parquet(tmp_path / f"{day}.parquet", index=False)

    collector = BacktestDataCollector(clients=None, config={})
    data = collector.load_cached_data(start=date(2024, 1, 3), end=date(2024, 1, 4))

    assert sorted(data["date"].unique().tolist()) == ["2024-01-03", "2024-01-04"]
