from datetime import date, datetime, timedelta

from ovtlyr.strategy.risk_controls import (
    correlation_gate,
    kill_switch_state,
    macro_window_block,
    portfolio_heat_ok,
)


def test_macro_window_block_date_level():
    events = [{"name": "CPI", "datetime": datetime(2026, 3, 12, 8, 30)}]
    assert macro_window_block(date(2026, 3, 12), events, 6) is True
    assert macro_window_block(date(2026, 3, 13), events, 6) is False


def test_portfolio_heat_ok_blocks_above_cap():
    open_positions = [
        {"qty": 1, "entry_price": 10.0, "stop_loss_pct": 0.20},  # risk = 200
    ]
    allowed, current_heat, next_heat = portfolio_heat_ok(
        open_positions=open_positions,
        candidate_risk=900.0,
        equity=10_000.0,
        heat_cap_pct=0.10,
    )
    assert round(current_heat, 4) == 0.02
    assert next_heat > 0.10
    assert allowed is False


def test_correlation_gate_blocks_when_cluster_limit_hit():
    corr = {
        "AAPL": {"MSFT": 0.86, "NVDA": 0.83},
        "MSFT": {"AAPL": 0.86, "NVDA": 0.81},
        "NVDA": {"AAPL": 0.83, "MSFT": 0.81},
    }
    ok, info = correlation_gate(
        candidate_symbol="AAPL",
        open_symbols=["MSFT", "NVDA"],
        corr_frame=corr,
        max_corr=0.75,
        max_cluster=2,
    )
    assert ok is False
    assert info["high_corr_count"] >= 2


def test_kill_switch_triggers_and_respects_cooldown():
    today = date(2026, 3, 5)
    losing_trades = [{"realized_pnl": -100.0, "risk_unit": 100.0} for _ in range(12)]
    state = kill_switch_state(
        recent_trades=losing_trades,
        lookback_trades=30,
        expectancy_floor_r=-0.15,
        cooldown_days=5,
        today=today,
    )
    assert state["active"] is True
    assert state["triggered"] is True

    still_active = kill_switch_state(
        recent_trades=[],
        lookback_trades=30,
        expectancy_floor_r=-0.15,
        cooldown_days=5,
        today=today + timedelta(days=1),
        existing_state=state,
    )
    assert still_active["active"] is True

