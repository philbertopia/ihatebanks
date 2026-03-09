from datetime import date
from types import SimpleNamespace

import pandas as pd

from ovtlyr.backtester.engine import BacktestEngine


def _base_config(**strategy_overrides):
    strategy = {
        "target_delta": 0.80,
        "min_delta": 0.70,
        "delta_tolerance": 0.20,
        "max_extrinsic_pct": 0.30,
        "min_open_interest": 0,
        "require_open_interest": False,
        "max_spread_pct": 0.20,
        "max_spread_abs": 1.00,
        "min_dte": 1,
        "max_dte": 90,
        "option_type": "call",
        "prefer_monthly": False,
        "monthly_only": False,
        "avoid_final_week": False,
        "require_symbol_bullish_trend": False,
        "sit_in_cash_when_bearish": False,
        "max_positions": 1,
        "max_contracts_per_trade": 1,
        "max_contract_cost": 1000.0,
    }
    strategy.update(strategy_overrides)
    return {
        "strategy": strategy,
        "backtest": {"initial_capital": 1000.0},
        "execution": {"target_annual_vol": 1.0},
        "risk": {
            "portfolio_heat_cap_pct": 1.0,
            "max_pair_corr": 1.0,
            "max_high_corr_positions": 99,
            "max_symbol_notional_pct": 1.0,
            "kill_switch_expectancy_floor_r": -99.0,
            "kill_switch_lookback_trades": 999,
            "kill_switch_cooldown_days": 0,
            "macro_no_trade_window_hours": 0,
        },
    }


def _atr_rows(replacement_ask: float, expiration_date: str = "2024-02-16"):
    return pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "underlying": "AAA",
                "contract_symbol": "AAA240216C00025000",
                "option_type": "call",
                "strike": 25.0,
                "expiration_date": expiration_date,
                "bid": 5.0,
                "ask": 5.5,
                "delta": 0.80,
                "open_interest": 1000,
                "implied_volatility": 0.25,
                "underlying_price": 30.0,
            },
            {
                "date": "2024-01-03",
                "underlying": "AAA",
                "contract_symbol": "AAA240216C00025000",
                "option_type": "call",
                "strike": 25.0,
                "expiration_date": expiration_date,
                "bid": 5.8,
                "ask": 6.0,
                "delta": 0.86,
                "open_interest": 1000,
                "implied_volatility": 0.25,
                "underlying_price": 31.0,
            },
            {
                "date": "2024-01-04",
                "underlying": "AAA",
                "contract_symbol": "AAA240216C00025000",
                "option_type": "call",
                "strike": 25.0,
                "expiration_date": expiration_date,
                "bid": 7.5,
                "ask": 7.7,
                "delta": 0.92,
                "open_interest": 1000,
                "implied_volatility": 0.25,
                "underlying_price": 33.0,
            },
            {
                "date": "2024-01-04",
                "underlying": "AAA",
                "contract_symbol": "AAA240216C00028000",
                "option_type": "call",
                "strike": 28.0,
                "expiration_date": expiration_date,
                "bid": max(replacement_ask - 0.2, 0.01),
                "ask": replacement_ask,
                "delta": 0.80,
                "open_interest": 1000,
                "implied_volatility": 0.25,
                "underlying_price": 33.0,
            },
        ]
    )


def _relax_engine_guards(monkeypatch):
    monkeypatch.setattr(
        "ovtlyr.backtester.engine.correlation_gate",
        lambda **kwargs: (True, {}),
    )
    monkeypatch.setattr(
        "ovtlyr.backtester.engine.portfolio_heat_ok",
        lambda *args, **kwargs: (True, None, None),
    )
    monkeypatch.setattr(
        "ovtlyr.backtester.engine.kill_switch_state",
        lambda *args, **kwargs: {"active": False},
    )
    monkeypatch.setattr(
        "ovtlyr.backtester.engine.load_macro_calendar",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "ovtlyr.backtester.engine.macro_window_block",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        "ovtlyr.backtester.engine.compute_regime_state",
        lambda *args, **kwargs: SimpleNamespace(regime="bull", reasons=[]),
    )
    monkeypatch.setattr(
        "ovtlyr.backtester.engine.strategy_allowed",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "ovtlyr.backtester.engine.risk_budget_for_regime",
        lambda *args, **kwargs: {
            "max_new_positions": 1,
            "allocation_mult": 1.0,
            "heat_mult": 1.0,
        },
    )


def test_initial_capital_override_sets_starting_equity():
    data = _atr_rows(replacement_ask=5.8)
    config = _base_config()
    config["backtest"]["initial_capital"] = 5000.0
    engine = BacktestEngine(data, config)

    engine.run(date(2024, 1, 2), date(2024, 1, 2))

    assert engine.initial_capital == 5000.0
    assert engine.equity_curve[0] == 5000.0
    assert len(engine.equity_curve) >= 1


def test_atr_proxy_is_lagged_close_to_close():
    data = pd.DataFrame(
        [
            {"date": "2024-01-02", "underlying": "AAA", "underlying_price": 100.0},
            {"date": "2024-01-03", "underlying": "AAA", "underlying_price": 102.0},
            {"date": "2024-01-04", "underlying": "AAA", "underlying_price": 101.0},
        ]
    )
    engine = BacktestEngine(data, _base_config())

    engine._precompute_atr_proxy(window=2)

    assert "2024-01-03" not in engine._atr_proxy["AAA"]
    assert engine._atr_proxy["AAA"]["2024-01-04"] == 2.0


def test_atr_roll_trigger_requires_anchor_plus_atr():
    engine = BacktestEngine(_atr_rows(replacement_ask=5.8), _base_config())
    engine._atr_proxy = {"AAA": {"2024-01-04": 1.0}}

    pos = {
        "underlying": "AAA",
        "strategy_type": "stock_replacement",
        "roll_anchor_underlying_price": 30.0,
        "current_underlying_price": 30.9,
    }
    engine.strategy["atr_roll_enabled"] = True
    engine.strategy["atr_roll_multiple"] = 1.0

    assert engine._should_attempt_atr_roll(pos, "2024-01-04") is False
    pos["current_underlying_price"] = 31.0
    assert engine._should_attempt_atr_roll(pos, "2024-01-04") is True


def test_atr_roll_skips_debit_replacement(monkeypatch):
    _relax_engine_guards(monkeypatch)
    config = _base_config(atr_roll_enabled=True, atr_window=1, atr_roll_credit_only=True)
    engine = BacktestEngine(_atr_rows(replacement_ask=7.9), config)

    metrics = engine.run(date(2024, 1, 2), date(2024, 1, 4))

    assert metrics["rolls_executed"] == 0
    assert all(t.get("exit_reason") != "roll_atr_credit" for t in engine.closed_trades)


def test_atr_roll_resets_anchor_after_successful_reentry(monkeypatch):
    _relax_engine_guards(monkeypatch)
    config = _base_config(atr_roll_enabled=True, atr_window=1, atr_roll_credit_only=True)
    engine = BacktestEngine(_atr_rows(replacement_ask=5.8), config)

    metrics = engine.run(date(2024, 1, 2), date(2024, 1, 4))

    assert metrics["rolls_executed"] == 1
    assert any(t.get("exit_reason") == "roll_atr_credit" for t in engine.closed_trades)
    rolled_position = next(
        p for p in engine.positions if p["contract_symbol"] == "AAA240216C00028000"
    )
    assert rolled_position["roll_anchor_underlying_price"] == 33.0
    assert rolled_position["roll_anchor_date"] == "2024-01-04"


def test_final_week_roll_still_executes_without_atr(monkeypatch):
    _relax_engine_guards(monkeypatch)
    config = _base_config(atr_roll_enabled=False)
    engine = BacktestEngine(
        _atr_rows(replacement_ask=5.8, expiration_date="2024-01-10"),
        config,
    )

    metrics = engine.run(date(2024, 1, 2), date(2024, 1, 4))

    assert metrics["rolls_executed"] == 1
    assert any(t.get("exit_reason") == "roll" for t in engine.closed_trades)
