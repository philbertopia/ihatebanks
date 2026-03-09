import json

import main


def test_persist_backtest_payload_keeps_capital_runs_separate(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "BACKTEST_RESULTS_PATH", str(tmp_path / "latest.json"))
    monkeypatch.setattr(main, "BACKTEST_HISTORY_PATH", str(tmp_path / "history.json"))
    monkeypatch.setattr(main, "BACKTEST_RUNS_PATH", str(tmp_path / "runs.json"))

    base_payload = {
        "strategy_id": "stock_replacement",
        "strategy_name": "Stock Replacement",
        "variant": "ditm_atr_credit_roll_small_account",
        "period_key": "2020-01",
        "generated_at": "2026-03-09T00:00:00Z",
        "start_date": "2020-01-01",
        "end_date": "2020-12-31",
        "metrics": {},
        "equity_curve": [1000.0],
    }

    payload_1k = {
        **base_payload,
        "run_id": "run-1k",
        "initial_capital": 1000.0,
    }
    payload_5k = {
        **base_payload,
        "run_id": "run-5k",
        "initial_capital": 5000.0,
    }

    main._persist_backtest_payload(payload_1k)
    main._persist_backtest_payload(payload_5k)

    with open(main.BACKTEST_HISTORY_PATH, "r") as f:
        history = json.load(f)
    with open(main.BACKTEST_RUNS_PATH, "r") as f:
        runs = json.load(f)

    assert len(history) == 2
    assert any("cap1000" in key for key in history)
    assert any("cap5000" in key for key in history)
    assert len(runs) == 2


def test_load_latest_oos_summary_treats_missing_capital_as_legacy_default(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        main, "WALKFORWARD_RUNS_PATH", str(tmp_path / "walkforward_runs.json")
    )

    payload = [
        {
            "strategy_id": "stock_replacement",
            "variant": "base",
            "universe_profile": "top_50",
            "generated_at": "2026-03-09T00:00:00Z",
            "oos_summary": {"pass_validation": True, "windows": 4},
        }
    ]
    with open(main.WALKFORWARD_RUNS_PATH, "w") as f:
        json.dump(payload, f)

    summary = main._load_latest_oos_summary(
        strategy_id="stock_replacement",
        variant="base",
        universe_profile="top_50",
        initial_capital=100000.0,
    )

    assert summary == {"pass_validation": True, "windows": 4}
    assert (
        main._build_walkforward_summary_key(
            "stock_replacement", "base", "top_50", 1000.0
        )
        == "stock_replacement|base|top_50|cap1000"
    )


def test_find_latest_backtest_run_requires_exact_period_match(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "BACKTEST_RUNS_PATH", str(tmp_path / "runs.json"))

    payload = [
        {
            "strategy_id": "intraday_open_close_options",
            "variant": "conservative",
            "universe_profile": "top_50",
            "start_date": "2015-01-02",
            "end_date": "2026-03-06",
            "generated_at": "2026-03-09T09:00:00Z",
            "metrics": {"total_return_pct": 100.0},
        },
        {
            "strategy_id": "intraday_open_close_options",
            "variant": "conservative",
            "universe_profile": "top_50",
            "start_date": "2020-01-01",
            "end_date": "2025-12-31",
            "generated_at": "2026-03-09T10:00:00Z",
            "metrics": {"total_return_pct": 999.0},
        },
    ]
    with open(main.BACKTEST_RUNS_PATH, "w") as f:
        json.dump(payload, f)

    result = main._find_latest_backtest_run(
        strategy_id="intraday_open_close_options",
        variant="conservative",
        universe_profile="top_50",
        start_date="2015-01-02",
        end_date="2026-03-06",
    )

    assert result is not None
    assert result["metrics"]["total_return_pct"] == 100.0


def test_rank_intraday_profitability_rows_prefers_return_then_sharpe():
    rows = [
        {
            "variant": "a",
            "total_return_pct": 120.0,
            "sharpe_ratio": 0.8,
            "profit_factor": 1.2,
            "max_drawdown_pct": 20.0,
            "total_trades": 100,
        },
        {
            "variant": "b",
            "total_return_pct": 150.0,
            "sharpe_ratio": 0.4,
            "profit_factor": 1.1,
            "max_drawdown_pct": 30.0,
            "total_trades": 120,
        },
        {
            "variant": "c",
            "total_return_pct": 120.0,
            "sharpe_ratio": 1.1,
            "profit_factor": 1.3,
            "max_drawdown_pct": 18.0,
            "total_trades": 90,
        },
    ]

    ranked = main._rank_intraday_profitability_rows(rows)

    assert [row["variant"] for row in ranked] == ["b", "c", "a"]
