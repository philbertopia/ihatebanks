from ovtlyr.scanner.selection import select_ranked_entries


def test_select_ranked_entries_one_best_per_underlying_and_global_sort():
    candidates = [
        {"underlying": "AAPL", "contract_symbol": "AAPL1", "score": 50.0},
        {"underlying": "AAPL", "contract_symbol": "AAPL2", "score": 62.0},
        {"underlying": "MSFT", "contract_symbol": "MSFT1", "score": 55.0},
        {"underlying": "TSLA", "contract_symbol": "TSLA1", "score": 70.0},
    ]

    selected = select_ranked_entries(candidates, max_positions=10)
    assert [x["underlying"] for x in selected] == ["TSLA", "AAPL", "MSFT"]
    assert selected[1]["contract_symbol"] == "AAPL2"


def test_select_ranked_entries_respects_max_positions():
    candidates = [
        {"underlying": "AAPL", "contract_symbol": "AAPL", "score": 60.0},
        {"underlying": "MSFT", "contract_symbol": "MSFT", "score": 59.0},
        {"underlying": "TSLA", "contract_symbol": "TSLA", "score": 58.0},
    ]
    selected = select_ranked_entries(candidates, max_positions=2)
    assert len(selected) == 2
    assert [x["underlying"] for x in selected] == ["AAPL", "MSFT"]

