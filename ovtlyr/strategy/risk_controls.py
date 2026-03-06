from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_macro_calendar(path: str = "config/macro_calendar.yaml") -> List[Dict[str, Any]]:
    """
    Load deterministic macro calendar events from local YAML.
    Expected schema:
      events:
        - name: FOMC
          datetime: "2026-03-18T14:00:00-04:00"
    """
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return []

    out: List[Dict[str, Any]] = []
    for ev in data.get("events", []) or []:
        dt_raw = ev.get("datetime")
        if not dt_raw:
            continue
        try:
            ev_dt = datetime.fromisoformat(str(dt_raw))
        except ValueError:
            continue
        out.append(
            {
                "name": str(ev.get("name", "macro")),
                "datetime": ev_dt,
                "impact": str(ev.get("impact", "high")),
            }
        )
    return out


def macro_window_block(
    day: datetime | date,
    calendar_events: Sequence[Dict[str, Any]],
    window_hours: float,
) -> bool:
    """
    Return True if `day` falls within +/- window_hours of any macro event.
    If `day` is date-only, block when an event lands on that same date.
    """
    if not calendar_events:
        return False

    if isinstance(day, date) and not isinstance(day, datetime):
        d = day
        return any(
            isinstance(ev.get("datetime"), datetime)
            and ev["datetime"].date() == d
            for ev in calendar_events
        )

    now = day if isinstance(day, datetime) else datetime.combine(day, datetime.min.time())
    window = timedelta(hours=max(_safe_float(window_hours, 0.0), 0.0))
    for ev in calendar_events:
        ev_dt = ev.get("datetime")
        if not isinstance(ev_dt, datetime):
            continue
        if abs(now - ev_dt) <= window:
            return True
    return False


def portfolio_heat_ok(
    open_positions: Sequence[Dict[str, Any]],
    candidate_risk: float,
    equity: float,
    heat_cap_pct: float,
) -> Tuple[bool, float, float]:
    """
    Heat = sum(position risk) / equity
    candidate_risk should be expressed in dollars.
    Returns: (allowed, current_heat, next_heat)
    """
    eq = max(_safe_float(equity, 0.0), 1.0)
    cap = max(_safe_float(heat_cap_pct, 0.0), 0.0)
    open_risk = 0.0

    for p in open_positions:
        qty = int(_safe_float(p.get("qty"), 1))
        entry = _safe_float(p.get("entry_price"), 0.0)
        stop_loss_pct = _safe_float(p.get("stop_loss_pct"), 0.20)
        if stop_loss_pct <= 0:
            stop_loss_pct = 0.20
        open_risk += max(entry * qty * 100.0 * stop_loss_pct, 0.0)

    current_heat = open_risk / eq
    next_heat = (open_risk + max(_safe_float(candidate_risk, 0.0), 0.0)) / eq
    return (next_heat <= cap), current_heat, next_heat


def correlation_gate(
    candidate_symbol: str,
    open_symbols: Iterable[str],
    corr_frame: Any,
    max_corr: float,
    max_cluster: int,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Gate a candidate based on pairwise correlations vs currently-open symbols.
    corr_frame can be:
      - pandas.DataFrame with symbol index+columns
      - dict[str, dict[str, float]]
    """
    cand = str(candidate_symbol or "").upper()
    opens = [str(s).upper() for s in open_symbols if str(s).strip()]
    max_corr_v = max(_safe_float(max_corr, 0.75), 0.0)
    cluster_cap = max(int(_safe_float(max_cluster, 2)), 1)

    if not cand or not opens or corr_frame is None:
        return True, {"high_corr_count": 0, "blocked": False}

    def _corr(a: str, b: str) -> float:
        if hasattr(corr_frame, "loc"):
            try:
                return _safe_float(corr_frame.loc[a, b], 0.0)
            except Exception:
                return 0.0
        if isinstance(corr_frame, dict):
            return _safe_float(corr_frame.get(a, {}).get(b, 0.0), 0.0)
        return 0.0

    high = 0
    pairs: List[Tuple[str, float]] = []
    for sym in opens:
        c = abs(_corr(cand, sym))
        if c >= max_corr_v:
            high += 1
            pairs.append((sym, c))
    blocked = high >= cluster_cap
    return (not blocked), {
        "high_corr_count": high,
        "blocked": blocked,
        "pairs": pairs,
        "threshold": max_corr_v,
        "cluster_cap": cluster_cap,
    }


def _trade_r_multiple(trade: Dict[str, Any]) -> float:
    pnl = _safe_float(trade.get("realized_pnl"), 0.0)
    if "risk_unit" in trade:
        risk_unit = max(abs(_safe_float(trade.get("risk_unit"), 0.0)), 1.0)
    else:
        qty = max(int(_safe_float(trade.get("qty"), 1)), 1)
        entry = _safe_float(trade.get("entry_price"), 0.0)
        stop_loss_pct = _safe_float(trade.get("stop_loss_pct"), 0.20)
        if stop_loss_pct <= 0:
            stop_loss_pct = 0.20
        risk_unit = max(abs(entry * qty * 100.0 * stop_loss_pct), 100.0)
    return pnl / risk_unit


def kill_switch_state(
    recent_trades: Sequence[Dict[str, Any]],
    lookback_trades: int,
    expectancy_floor_r: float,
    cooldown_days: int,
    today: Optional[date] = None,
    existing_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Trade-level kill switch driven by rolling expectancy in R multiples.
    """
    lb = max(int(_safe_float(lookback_trades, 30)), 1)
    floor = _safe_float(expectancy_floor_r, -0.15)
    cd_days = max(int(_safe_float(cooldown_days, 5)), 1)
    tday = today or date.today()
    state = dict(existing_state or {})

    cooldown_until = state.get("cooldown_until")
    if isinstance(cooldown_until, str):
        try:
            cooldown_until = date.fromisoformat(cooldown_until)
        except ValueError:
            cooldown_until = None

    if isinstance(cooldown_until, date) and tday <= cooldown_until:
        return {
            "active": True,
            "cooldown_until": cooldown_until.isoformat(),
            "expectancy_r": _safe_float(state.get("expectancy_r"), 0.0),
            "lookback_count": int(_safe_float(state.get("lookback_count"), 0)),
            "triggered": False,
        }

    sample = list(recent_trades)[-lb:]
    if not sample:
        return {
            "active": False,
            "cooldown_until": None,
            "expectancy_r": 0.0,
            "lookback_count": 0,
            "triggered": False,
        }

    rs = [_trade_r_multiple(t) for t in sample]
    expectancy = sum(rs) / max(len(rs), 1)
    triggered = expectancy < floor and len(rs) >= min(10, lb)

    if triggered:
        until = tday + timedelta(days=cd_days)
        return {
            "active": True,
            "cooldown_until": until.isoformat(),
            "expectancy_r": round(expectancy, 6),
            "lookback_count": len(rs),
            "triggered": True,
        }

    return {
        "active": False,
        "cooldown_until": None,
        "expectancy_r": round(expectancy, 6),
        "lookback_count": len(rs),
        "triggered": False,
    }

