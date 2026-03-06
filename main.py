#!/usr/bin/env python3
"""
OVTLYR Trading System — CLI Entry Point

Commands:
  scan       Full daily workflow: check positions → roll → scan → open → report
  positions  Refresh and display open positions only
  report     Print daily report without placing trades
  collect    Cache today's option chain data for backtesting
  generate   Generate synthetic historical options data (yfinance + Black-Scholes)
  backtest   Run backtester against cached data
  stats      Show aggregate PnL and win rate from DB
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Tuple

import yaml
from dotenv import load_dotenv

from ovtlyr.utils.logging_config import setup_logging
from ovtlyr.database.migrations import initialize_db
from ovtlyr.database.repository import Repository
from ovtlyr.api.client import get_clients
from ovtlyr.api.options_data import fetch_stock_trend_state
from ovtlyr.scanner.scanner import DailyScanner
from ovtlyr.positions.tracker import PositionTracker
from ovtlyr.positions.roller import PositionRoller
from ovtlyr.trading.executor import TradeExecutor
from ovtlyr.reporting.daily_report import DailyReport
from ovtlyr.reporting.stats import get_portfolio_stats
from ovtlyr.utils.time_utils import is_market_day
from ovtlyr.universe.profiles import available_universes, load_universe
from ovtlyr.scanner.selection import select_ranked_entries
from ovtlyr.backtester.stock_replacement_profiles import (
    apply_stock_replacement_variant,
    normalize_variant,
)
from ovtlyr.strategy.allocator import (
    AllocationDecision,
    compute_regime_state,
    risk_budget_for_regime,
    strategy_allowed,
)
from ovtlyr.strategy.risk_controls import (
    kill_switch_state,
    load_macro_calendar,
    macro_window_block,
    portfolio_heat_ok,
)

logger = logging.getLogger(__name__)

BACKTEST_RESULTS_PATH = "data/backtest_results.json"
BACKTEST_HISTORY_PATH = "data/backtest_history.json"
BACKTEST_RUNS_PATH = "data/backtest_runs.json"
WALKFORWARD_RUNS_PATH = "data/walkforward_runs.json"
WALKFORWARD_SUMMARY_PATH = "data/walkforward_summary.json"
STRATEGY_CATALOG_PATH = "data/strategy_catalog.json"


# ──────────────────────────────────────────────
#  Config helpers
# ──────────────────────────────────────────────


def load_config(settings_path: str = "config/settings.yaml") -> dict:
    with open(settings_path, "r") as f:
        return yaml.safe_load(f)


def load_watchlist(watchlist_path: str = "config/watchlist.yaml") -> list:
    # Backward-compatible wrapper.
    return load_universe("default", watchlist_path=watchlist_path)


def resolve_universe(args, config: dict) -> Tuple[str, List[str]]:
    profile = (getattr(args, "universe", None) or "").strip()
    if not profile:
        profile = str(config.get("execution", {}).get("universe_profile", "default"))

    symbols = load_universe(profile)
    if not symbols:
        logger.warning(
            f"Universe '{profile}' resolved to empty symbols; falling back to 'default'"
        )
        profile = "default"
        symbols = load_universe(profile)

    preview = ", ".join(symbols[:8])
    logger.info(
        f"Universe resolved: profile={profile} symbols={len(symbols)} preview=[{preview}]"
    )
    return profile, symbols


def _round_obj(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, list):
        return [_round_obj(v) for v in value]
    if isinstance(value, dict):
        return {k: _round_obj(v) for k, v in value.items()}
    return value


def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def _build_run_id(strategy_id: str, variant: str, period_key: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{strategy_id}:{variant}:{period_key}:{ts}"


def _resolve_period(
    data, start_arg: str = None, end_arg: str = None
) -> Tuple[date, date]:
    if "date" not in data.columns:
        raise ValueError("Cached data missing required 'date' column")

    data_min = date.fromisoformat(str(data["date"].min()))
    data_max = date.fromisoformat(str(data["date"].max()))

    start = date.fromisoformat(start_arg) if start_arg else data_min
    end = date.fromisoformat(end_arg) if end_arg else data_max

    if start > end:
        raise ValueError(f"Invalid period: start ({start}) > end ({end})")
    return start, end


def _trading_days_for_period(data, start: date, end: date) -> List[date]:
    out: List[date] = []
    for d in sorted(data["date"].unique()):
        dd = date.fromisoformat(str(d))
        if start <= dd <= end:
            out.append(dd)
    return out


def _equity_points_from_curve(
    trading_days: List[date], equity_curve: List[float]
) -> List[Tuple[date, float]]:
    points: List[Tuple[date, float]] = []
    usable = min(len(trading_days), len(equity_curve))
    for i in range(usable):
        points.append((trading_days[i], float(equity_curve[i])))
    return points


def _build_series(
    equity_curve: List[float],
    trade_pnls: List[float],
    equity_points: List[Tuple[date, float]],
) -> Dict[str, Any]:
    from ovtlyr.backtester.series import (
        compute_drawdown_curve,
        compute_monthly_returns,
        compute_rolling_win_rate,
    )

    return {
        "equity_curve": [float(v) for v in equity_curve],
        "drawdown_curve": compute_drawdown_curve(equity_curve),
        "rolling_win_rate": compute_rolling_win_rate(trade_pnls, window=20),
        "monthly_returns": compute_monthly_returns(equity_points),
    }


def _warmup_start_day(
    trading_days: List[date],
    test_start: date,
    lookback_days: int = 260,
) -> date:
    if not trading_days:
        return test_start
    try:
        idx = trading_days.index(test_start)
    except ValueError:
        return test_start
    return trading_days[max(0, idx - max(int(lookback_days), 0))]


def _metrics_from_equity_window(
    equity_points: List[Tuple[date, float]],
    start_day: date,
    end_day: date,
    base_metrics: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Compute return/sharpe/max-dd from a date-sliced equity series.
    Used by walk-forward so long-lookback indicators can warm up prior to test.
    """
    rows = [(d, float(v)) for d, v in equity_points if start_day <= d <= end_day]
    m = dict(base_metrics or {})
    if len(rows) < 2:
        m["total_return_pct"] = 0.0
        m["sharpe_ratio"] = 0.0
        m["max_drawdown_pct"] = 0.0
        return m

    vals = [v for _, v in rows]
    initial = vals[0]
    final = vals[-1]
    total_return = ((final - initial) / initial * 100.0) if initial > 0 else 0.0

    peak = max(vals[0], 0.0)
    max_dd = 0.0
    for v in vals:
        safe_v = max(v, 0.0)
        if safe_v > peak:
            peak = safe_v
        dd = (peak - safe_v) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    daily_returns = []
    for i in range(1, len(vals)):
        prev = vals[i - 1]
        if prev != 0:
            daily_returns.append((vals[i] - prev) / prev)
    sharpe = 0.0
    if daily_returns:
        mean_ret = sum(daily_returns) / len(daily_returns)
        std_ret = (
            sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns)
        ) ** 0.5
        annual_rf = 0.05 / 252
        if std_ret > 0:
            sharpe = ((mean_ret - annual_rf) / std_ret) * (252**0.5)

    m["initial_equity"] = initial
    m["final_equity"] = final
    m["total_return_pct"] = total_return
    m["sharpe_ratio"] = round(sharpe, 4)
    m["max_drawdown_pct"] = max_dd * 100.0
    return m


def _heuristic_correlation_frame(symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """
    Lightweight correlation proxy for live scan ranking.
    This avoids loading heavy historical datasets in the scan path.
    """
    buckets = {
        "XLK": {
            "AAPL",
            "MSFT",
            "NVDA",
            "AMD",
            "AVGO",
            "ADBE",
            "ORCL",
            "CSCO",
            "QCOM",
            "INTU",
            "AMAT",
            "TXN",
            "NOW",
        },
        "XLC": {"GOOGL", "META", "NFLX"},
        "XLY": {"AMZN", "TSLA", "HD", "MCD", "NKE", "BKNG"},
        "XLF": {"JPM", "BAC", "GS", "V", "MA"},
        "XLV": {"LLY", "JNJ", "ABBV", "MRK", "UNH", "TMO", "DHR", "ISRG"},
        "XLE": {"XOM", "CVX"},
        "XLP": {"WMT", "COST", "PG", "KO", "PEP"},
        "XLI": {"CAT", "GE"},
        "SPY_QQQ": {"SPY", "QQQ"},
    }

    def _bucket(sym: str) -> str:
        s = str(sym).upper()
        for name, members in buckets.items():
            if s in members:
                return name
        return "OTHER"

    syms = [str(s).upper() for s in symbols if str(s).strip()]
    out: Dict[str, Dict[str, float]] = {}
    for a in syms:
        out[a] = {}
        ba = _bucket(a)
        for b in syms:
            bb = _bucket(b)
            if a == b:
                out[a][b] = 1.0
            elif ba == "SPY_QQQ" and bb == "SPY_QQQ":
                out[a][b] = 0.90
            elif ba == bb and ba != "OTHER":
                out[a][b] = 0.82
            elif "SPY_QQQ" in {ba, bb}:
                out[a][b] = 0.65
            else:
                out[a][b] = 0.35
    return out


def _latest_closed_trades(repo: Repository, n: int) -> List[Dict[str, Any]]:
    rows = repo.get_all_closed_trades_for_backtest()
    rows = sorted(rows, key=lambda r: str(r.get("close_date", "")))
    return rows[-max(int(n), 1) :]


def _build_allocation_decision(
    config: Dict[str, Any],
    strategy_id: str,
    variant: str,
    market_trend: Dict[str, Any] | None = None,
) -> AllocationDecision:
    risk_cfg = config.get("risk", {})
    strategy_cfg = config.get("strategy", {})
    now = datetime.now()
    macro_events = load_macro_calendar("config/macro_calendar.yaml")
    macro_blocked = macro_window_block(
        now,
        macro_events,
        window_hours=float(risk_cfg.get("macro_no_trade_window_hours", 6)),
    )

    day_ctx = {
        "is_bullish_trend": bool(market_trend.get("is_bullish", False))
        if market_trend
        else False,
        "is_bearish_trend": bool(market_trend.get("is_bearish", False))
        if market_trend
        else False,
        # Live scan does not yet compute robust breadth/HV30 locally; use conservative defaults.
        "hv30": float(strategy_cfg.get("vix_proxy_override", 0.20)),
        "breadth_pct": float(strategy_cfg.get("breadth_proxy_override", 60.0)),
        "macro_blocked": macro_blocked,
        "vix_max_threshold": float(strategy_cfg.get("vix_max_threshold", 0.40)),
        "breadth_min_pct": float(strategy_cfg.get("breadth_min_pct", 50.0)),
    }
    regime = compute_regime_state(day_ctx)
    allowed = strategy_allowed(strategy_id, variant, regime)
    budget = risk_budget_for_regime(regime)
    reason = ", ".join(regime.reasons) if regime.reasons else regime.regime
    return AllocationDecision(
        allowed=allowed, regime=regime, budget=budget, reason=reason
    )


def _load_latest_oos_summary(
    strategy_id: str, variant: str, universe_profile: str
) -> Dict[str, Any] | None:
    rows = _load_json(WALKFORWARD_RUNS_PATH, [])
    if not isinstance(rows, list):
        return None
    candidates = [
        r
        for r in rows
        if str(r.get("strategy_id")) == str(strategy_id)
        and str(r.get("variant")) == str(variant)
    ]
    if not candidates:
        return None
    target_profile = str(universe_profile or "")
    exact = [
        r
        for r in candidates
        if str(r.get("universe_profile", "")) == target_profile
    ]
    if exact:
        exact.sort(key=lambda r: str(r.get("generated_at", "")), reverse=True)
        return exact[0].get("oos_summary")

    # Backward compatibility: allow legacy rows with blank universe profile.
    if target_profile:
        legacy_blank = [
            r for r in candidates if str(r.get("universe_profile", "")) == ""
        ]
        if legacy_blank:
            legacy_blank.sort(key=lambda r: str(r.get("generated_at", "")), reverse=True)
            return legacy_blank[0].get("oos_summary")

    # Last resort for unknown/blank profile: use latest for strategy+variant.
    candidates.sort(key=lambda r: str(r.get("generated_at", "")), reverse=True)
    return candidates[0].get("oos_summary")


def _profile_matches(row_profile: Any, target_profile: str) -> bool:
    row = str(row_profile or "")
    target = str(target_profile or "")
    if row == target:
        return True
    # Backward compatibility for old payloads that had blank profile metadata.
    return row == "" and target != ""


def _attach_oos_to_backtest_payloads(
    strategy_id: str,
    variant: str,
    universe_profile: str,
    oos_summary: Dict[str, Any],
    walkforward_id: str,
) -> None:
    runs = _load_json(BACKTEST_RUNS_PATH, [])
    if isinstance(runs, list):
        changed = False
        for row in runs:
            if (
                str(row.get("strategy_id")) == str(strategy_id)
                and str(row.get("variant")) == str(variant)
                and _profile_matches(row.get("universe_profile", ""), universe_profile)
            ):
                row["oos_summary"] = oos_summary
                row["walkforward_id"] = walkforward_id
                changed = True
        if changed:
            with open(BACKTEST_RUNS_PATH, "w") as f:
                json.dump(_round_obj(runs), f, indent=2)

    history = _load_json(BACKTEST_HISTORY_PATH, {})
    if isinstance(history, dict):
        changed = False
        for key, row in history.items():
            if not isinstance(row, dict):
                continue
            if (
                str(row.get("strategy_id")) == str(strategy_id)
                and str(row.get("variant")) == str(variant)
                and _profile_matches(row.get("universe_profile", ""), universe_profile)
            ):
                row["oos_summary"] = oos_summary
                row["walkforward_id"] = walkforward_id
                history[key] = row
                changed = True
        if changed:
            with open(BACKTEST_HISTORY_PATH, "w") as f:
                json.dump(_round_obj(history), f, indent=2)

    latest = _load_json(BACKTEST_RESULTS_PATH, {})
    if isinstance(latest, dict):
        if (
            str(latest.get("strategy_id")) == str(strategy_id)
            and str(latest.get("variant")) == str(variant)
            and _profile_matches(latest.get("universe_profile", ""), universe_profile)
        ):
            latest["oos_summary"] = oos_summary
            latest["walkforward_id"] = walkforward_id
            with open(BACKTEST_RESULTS_PATH, "w") as f:
                json.dump(_round_obj(latest), f, indent=2)


def _persist_backtest_payload(payload: Dict[str, Any]) -> None:
    os.makedirs("data", exist_ok=True)
    payload = _round_obj(payload)

    with open(BACKTEST_RESULTS_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    history = _load_json(BACKTEST_HISTORY_PATH, {})
    history_key = f"{payload.get('strategy_id')}|{payload.get('variant')}|{payload.get('period_key')}"
    history[history_key] = payload
    with open(BACKTEST_HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)

    runs = _load_json(BACKTEST_RUNS_PATH, [])
    if not isinstance(runs, list):
        runs = []
    runs.append(payload)
    with open(BACKTEST_RUNS_PATH, "w") as f:
        json.dump(runs, f, indent=2)


def _print_backtest_metrics(title: str, metrics: Dict[str, Any]) -> None:
    print("\n" + "=" * 50)
    print(f"  {title}")
    print("=" * 50)
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:<30} {v:.4f}")
        else:
            print(f"  {k:<30} {v}")
    print("=" * 50)


# ──────────────────────────────────────────────
#  Command implementations
# ──────────────────────────────────────────────


def cmd_scan(args, config, repo, clients):
    """Full daily workflow."""
    from datetime import date

    today = date.today()

    if not is_market_day(today) and not args.force:
        logger.warning(
            f"Today ({today}) is not a trading day. Use --force to override."
        )
        print(
            f"⚠  Today ({today}) is not a market day. Exiting. Use --force to run anyway."
        )
        return

    universe_profile, universe_symbols = resolve_universe(args, config)
    logger.info(
        f"Starting daily scan for {len(universe_symbols)} symbols on {today} "
        f"(profile={universe_profile})"
    )

    executor = TradeExecutor(clients.trading, config)
    scanner = DailyScanner(clients, repo, config)
    tracker = PositionTracker(clients, repo, config)
    roller = PositionRoller(clients, executor, repo, config)

    rolls_executed = []
    positions_opened = []
    risk_events: List[str] = []
    risk_cfg = config.get("risk", {})
    strategy_cfg = config.get("strategy", {})
    market_symbol = strategy_cfg.get("market_trend_symbol", "SPY")
    market_trend = fetch_stock_trend_state(
        client=clients.stock_data,
        symbol=market_symbol,
        ema_fast=int(strategy_cfg.get("trend_ema_fast", 10)),
        ema_medium=int(strategy_cfg.get("trend_ema_medium", 20)),
        ema_slow=int(strategy_cfg.get("trend_ema_slow", 50)),
        lookback_days=int(strategy_cfg.get("trend_lookback_days", 180)),
    )
    alloc_decision = _build_allocation_decision(
        config=config,
        strategy_id=strategy_cfg.get("strategy_type", "stock_replacement"),
        variant=strategy_cfg.get("variant", "base"),
        market_trend=market_trend,
    )
    enforce_allocator_live = bool(
        config.get("execution", {}).get("enforce_allocator_live", False)
    )
    logger.info(
        "Allocator regime=%s allowed=%s reason=%s budget=%s enforce_live=%s",
        alloc_decision.regime.regime,
        alloc_decision.allowed,
        alloc_decision.reason,
        alloc_decision.budget,
        enforce_allocator_live,
    )

    # ── 1. Check existing positions ──
    position_actions = tracker.check_all_positions(today)

    # ── 2. Roll flagged positions ──
    for position, action in position_actions:
        if action.startswith("roll"):
            logger.info(f"Rolling {position['contract_symbol']} — reason: {action}")
            replacement = scanner.find_replacement_for_roll(
                position["underlying"], today
            )
            success = roller.roll_position(position, replacement, action)
            if success:
                msg = f"{position['contract_symbol']} → {replacement['contract_symbol'] if replacement else 'CLOSED'} ({action})"
                rolls_executed.append(msg)

        elif action == "expired":
            logger.warning(
                f"Position {position['contract_symbol']} appears expired — manual review needed"
            )

    # ── 3. Scan for new opportunities ──
    all_candidates = []
    if strategy_cfg.get("sit_in_cash_when_bearish", False):
        if market_trend and market_trend.get("is_bearish", False):
            logger.warning(
                "Market trend filter bearish on %s: px=%.2f ema%s=%.2f ema%s=%.2f ema%s=%.2f | "
                "sit-in-cash mode active, skipping new entries",
                market_symbol,
                market_trend["price"],
                strategy_cfg.get("trend_ema_fast", 10),
                market_trend["ema_fast"],
                strategy_cfg.get("trend_ema_medium", 20),
                market_trend["ema_medium"],
                strategy_cfg.get("trend_ema_slow", 50),
                market_trend["ema_slow"],
            )
        else:
            all_candidates = scanner.run(universe_symbols)
    else:
        all_candidates = scanner.run(universe_symbols)

    # ── 4. Open new positions (respecting max_positions limit) ──
    max_positions = config.get("execution", {}).get("max_positions", 10)
    open_positions_live = repo.get_open_positions()
    open_count = len(open_positions_live)
    open_underlyings = [p.get("underlying", "") for p in open_positions_live]

    if enforce_allocator_live and not alloc_decision.allowed:
        risk_events.append(f"allocator_block:{alloc_decision.reason}")
        ranked_entries = []
    else:
        corr_frame = _heuristic_correlation_frame(
            list(
                {*(c.get("underlying", "") for c in all_candidates), *open_underlyings}
            )
        )
        ranked_entries = select_ranked_entries(
            all_candidates,
            max_positions=max_positions,
            open_underlyings=open_underlyings,
            corr_frame=corr_frame,
            max_pair_corr=float(risk_cfg.get("max_pair_corr", 0.75)),
            max_high_corr_positions=int(risk_cfg.get("max_high_corr_positions", 2)),
        )

    kill_state = kill_switch_state(
        recent_trades=_latest_closed_trades(
            repo, int(risk_cfg.get("kill_switch_lookback_trades", 30))
        ),
        lookback_trades=int(risk_cfg.get("kill_switch_lookback_trades", 30)),
        expectancy_floor_r=float(risk_cfg.get("kill_switch_expectancy_floor_r", -0.15)),
        cooldown_days=int(risk_cfg.get("kill_switch_cooldown_days", 5)),
        today=today,
    )
    if kill_state.get("active"):
        msg = f"kill_switch_active_until:{kill_state.get('cooldown_until')} expectancy_r={kill_state.get('expectancy_r')}"
        risk_events.append(msg)
        logger.warning("Risk control %s", msg)
        if enforce_allocator_live:
            ranked_entries = []

    summary = repo.get_pnl_summary()
    equity_est = (
        100_000.0
        + float(summary.get("total_realized_pnl", 0.0) or 0.0)
        + float(summary.get("total_unrealized_pnl", 0.0) or 0.0)
    )
    heat_cap = float(risk_cfg.get("portfolio_heat_cap_pct", 0.08)) * float(
        alloc_decision.budget.get("heat_mult", 1.0)
    )
    max_new_positions_budget = int(
        alloc_decision.budget.get("max_new_positions", max_positions)
    )
    logger.info(
        "Entry ranking prepared: %d contracts reduced to %d ranked entries",
        len(all_candidates),
        len(ranked_entries),
    )
    if risk_events:
        logger.info("Risk control events: %s", "; ".join(risk_events))
    opened_today = 0
    for candidate in ranked_entries:
        if open_count >= max_positions:
            logger.info(
                f"Max positions ({max_positions}) reached — stopping new entries"
            )
            break
        if opened_today >= max_new_positions_budget:
            logger.info(
                "Allocator budget reached (%d new positions) — stopping new entries",
                max_new_positions_budget,
            )
            break

        underlying = candidate.get("underlying", "")
        qty = config.get("execution", {}).get("contracts_per_trade", 1)
        est_price = float(candidate.get("ask", 0.0) or 0.0)
        candidate_risk = est_price * qty * 100.0 * 0.20
        heat_ok, current_heat, next_heat = portfolio_heat_ok(
            open_positions_live,
            candidate_risk=candidate_risk,
            equity=equity_est,
            heat_cap_pct=heat_cap,
        )
        if not heat_ok:
            msg = (
                f"heat_cap_block:{underlying} current={current_heat:.4f} "
                f"next={next_heat:.4f} cap={heat_cap:.4f}"
            )
            if enforce_allocator_live:
                logger.warning(msg)
                continue
            logger.info("[SHADOW] %s", msg)

        # Execute buy
        order = executor.buy_to_open(
            candidate["contract_symbol"],
            qty=qty,
            bid=candidate["bid"],
            ask=candidate["ask"],
        )

        if order:
            pos_id = repo.insert_position(
                {
                    "underlying": underlying,
                    "contract_symbol": candidate["contract_symbol"],
                    "option_type": candidate.get("option_type", "call"),
                    "strike": candidate["strike"],
                    "expiration_date": candidate["expiration_date"],
                    "qty": qty,
                    "entry_price": order.get("limit_price", candidate["ask"]),
                    "entry_date": datetime.now(timezone.utc).isoformat(),
                    "entry_delta": candidate.get("delta"),
                    "entry_extrinsic_pct": candidate.get("extrinsic_pct"),
                    "entry_underlying_price": candidate.get("underlying_price"),
                    "current_delta": candidate.get("delta"),
                    "current_price": order.get("limit_price", candidate["ask"]),
                    "status": "open",
                    "alpaca_order_id": order.get("id"),
                }
            )

            repo.insert_trade(
                {
                    "position_id": pos_id,
                    "trade_type": "open",
                    "contract_symbol": candidate["contract_symbol"],
                    "underlying": underlying,
                    "side": "buy",
                    "qty": qty,
                    "price": order.get("limit_price", candidate["ask"]),
                    "delta_at_trade": candidate.get("delta"),
                    "underlying_price_at_trade": candidate.get("underlying_price"),
                    "alpaca_order_id": order.get("id"),
                    "status": "filled" if not order.get("dry_run") else "pending",
                }
            )

            # Update scan result
            try:
                today_results = repo.get_scan_results_for_date(today.isoformat())
                for sr in today_results:
                    if sr["contract_symbol"] == candidate["contract_symbol"]:
                        repo.mark_scan_result_opened(sr["id"])
                        break
            except Exception:
                pass

            positions_opened.append(candidate)
            open_count += 1
            opened_today += 1
            open_positions_live.append(
                {
                    "underlying": underlying,
                    "qty": qty,
                    "entry_price": order.get("limit_price", candidate["ask"]),
                    "stop_loss_pct": 0.20,
                }
            )

    # ── 5. Record daily stats ──
    open_positions = repo.get_open_positions()
    from ovtlyr.utils.math_utils import compute_unrealized_pnl as upnl

    unrealized = sum(
        upnl(p["entry_price"], p.get("current_price") or p["entry_price"], p["qty"])
        for p in open_positions
    )
    portfolio_delta = sum(
        (p.get("current_delta") or p.get("entry_delta", 0)) * p["qty"]
        for p in open_positions
    )
    repo.upsert_daily_stats(
        {
            "stat_date": today.isoformat(),
            "open_positions": len(open_positions),
            "positions_rolled": len(rolls_executed),
            "positions_opened": len(positions_opened),
            "total_pnl_unrealized": unrealized,
            "portfolio_delta": portfolio_delta,
            "notes": "; ".join(risk_events) if risk_events else None,
        }
    )

    # ── 6. Generate report ──
    DailyReport(
        repo=repo,
        scan_candidates=all_candidates,
        rolls_executed=rolls_executed,
        positions_opened=positions_opened,
    ).generate()


def cmd_positions(args, config, repo, clients):
    """Refresh and display open positions."""
    tracker = PositionTracker(clients, repo, config)
    tracker.check_all_positions()
    DailyReport(repo=repo).generate()


def cmd_report(args, config, repo, clients):
    """Print report without trading."""
    scan_results = repo.get_scan_results_for_date(date.today().isoformat())
    DailyReport(repo=repo, scan_candidates=scan_results).generate()


def cmd_stats(args, config, repo, clients):
    """Show aggregate stats."""
    stats = get_portfolio_stats(repo)
    print("\n" + "=" * 50)
    print("  OVTLYR PORTFOLIO STATISTICS")
    print("=" * 50)
    for k, v in stats.items():
        if isinstance(v, float):
            print(f"  {k:<30} {v:.4f}")
        else:
            print(f"  {k:<30} {v}")
    print("=" * 50)


def cmd_collect(args, config, repo, clients):
    """Collect and cache today's option chain data for backtesting."""
    from ovtlyr.backtester.data_collector import BacktestDataCollector

    universe_profile, universe_symbols = resolve_universe(args, config)
    collector = BacktestDataCollector(clients, config)
    saved = collector.collect_and_cache(universe_symbols)
    print(
        f"Collected and cached data for {saved} contracts across {len(universe_symbols)} symbols "
        f"(profile={universe_profile})"
    )


def cmd_generate(args, config, repo, clients):
    """Generate synthetic historical options data using yfinance + Black-Scholes."""
    from datetime import date, timedelta
    from ovtlyr.backtester.synthetic_generator import SyntheticGenerator

    universe_profile, universe_symbols = resolve_universe(args, config)

    end = date.today()
    if args.end:
        end = date.fromisoformat(args.end)

    start = end - timedelta(days=365 * 2)  # default: 2 years
    if args.start:
        start = date.fromisoformat(args.start)

    print(f"Generating synthetic options data for {universe_symbols}")
    print(f"Universe profile: {universe_profile} ({len(universe_symbols)} symbols)")
    print(f"Date range: {start} to {end}")
    print(
        "Downloading price history from yfinance and computing Black-Scholes prices..."
    )

    gen = SyntheticGenerator(config)
    days = gen.generate(universe_symbols, start, end)

    print(f"\nDone. Generated data for {days} trading days.")
    print(
        f"Saved to data/cache/ — run 'python main.py backtest' to simulate the strategy."
    )


def cmd_intraday_report(args, config, repo, clients):
    """Generate one-day intraday open→close candidate ranking report."""
    from ovtlyr.backtester.data_collector import BacktestDataCollector
    from ovtlyr.backtester.intraday_options_engine import (
        generate_intraday_candidate_report,
    )
    from ovtlyr.backtester.intraday_report import write_intraday_report_files
    from tabulate import tabulate

    collector = BacktestDataCollector(clients, config)
    data = collector.load_cached_data()
    if data.empty:
        print(
            "No cached data found. Run 'python main.py generate' or 'python main.py collect' first."
        )
        return

    report_day = date.fromisoformat(args.date) if args.date else date.today()
    universe_profile, universe_symbols = resolve_universe(args, config)
    print(f"Universe profile: {universe_profile} ({len(universe_symbols)} symbols)")
    print(f"Generating intraday candidate report for {report_day} ({args.variant}) ...")

    report = generate_intraday_candidate_report(
        data=data,
        report_date=report_day,
        variant_name=args.variant or "baseline",
        universe_symbols=universe_symbols,
        top_n=int(args.top or 15),
        min_qualifiers=int(args.min_qualifiers or 30),
    )
    md_path, json_path = write_intraday_report_files(report)

    print("\n" + "=" * 72)
    print(f"INTRADAY CANDIDATE REPORT — {report.report_date} ({report.variant})")
    print("=" * 72)
    print(f"Scanned contracts:   {report.total_contracts}")
    print(
        f"Qualified contracts: {report.qualified_contracts} (target {report.min_qualifiers})"
    )
    print(
        "Data quality:        "
        f"observed={report.data_quality_breakdown.get('observed', 0)} "
        f"mixed={report.data_quality_breakdown.get('mixed', 0)} "
        f"modeled={report.data_quality_breakdown.get('modeled', 0)}"
    )
    if report.warning:
        print(f"Warning: {report.warning}")

    rows = []
    for i, row in enumerate(report.top_picks[: int(args.top or 15)], start=1):
        rows.append(
            [
                i,
                row.get("ticker"),
                row.get("option_type", "").upper(),
                row.get("expiry"),
                row.get("strike"),
                row.get("composite_edge_score"),
                row.get("vol_oi_ratio"),
                row.get("itm_depth_pct"),
                row.get("atr_pct"),
                row.get("entry_limit"),
            ]
        )
    if rows:
        print(
            tabulate(
                rows,
                headers=[
                    "Rank",
                    "Ticker",
                    "Type",
                    "Expiry",
                    "Strike",
                    "Edge",
                    "Vol/OI",
                    "ITM%",
                    "ATR%",
                    "Entry",
                ],
                floatfmt=".3f",
            )
        )
    else:
        print("No qualifying contracts found.")

    print(f"\nSaved markdown: {md_path}")
    print(f"Saved json:     {json_path}")


def cmd_backtest(args, config, repo, clients):
    """Run stock-replacement backtest and persist rich payload for dashboard analytics."""
    from ovtlyr.backtester.engine import BacktestEngine
    from ovtlyr.backtester.data_collector import BacktestDataCollector

    strategy_id = args.strategy_id or "stock_replacement"
    strategy_name = args.strategy_name or "Stock Replacement"
    variant = args.variant or "base"
    normalized_variant = (
        normalize_variant(variant) if strategy_id == "stock_replacement" else variant
    )

    effective_config = config
    if strategy_id == "stock_replacement":
        effective_config = apply_stock_replacement_variant(config, normalized_variant)
        print(f"Stock-replacement variant: {normalized_variant}")

    collector = BacktestDataCollector(clients, effective_config)
    data = collector.load_cached_data()
    if data.empty:
        print(
            "No cached data found. Run 'python main.py collect' or 'python main.py generate' first."
        )
        return

    print(f"Loaded {len(data)} rows of cached option data")
    universe_profile, universe_symbols = resolve_universe(args, config)
    print(f"Universe profile: {universe_profile} ({len(universe_symbols)} symbols)")
    try:
        start, end = _resolve_period(data, args.start, args.end)
    except ValueError as e:
        print(f"Cannot run backtest: {e}")
        return

    print(f"Running backtest from {start} to {end} ...")
    intraday_report = None
    candidate_count_total = 0
    candidate_count_qualified = 0
    data_quality_breakdown = None
    rejection_counts = None
    execution_window = None
    component_metrics = None

    # Check if this is a wheel strategy
    strategy_type = effective_config.get("strategy", {}).get("strategy_type", "")
    is_wheel = strategy_type == "wheel"

    if is_wheel:
        from ovtlyr.backtester.wheel_engine import run_wheel_backtest

        metrics = run_wheel_backtest(data, effective_config, start, end)
        trading_days = _trading_days_for_period(data, start, end)
        equity_curve = metrics.get("equity_curve", [100000])
        trade_pnls = [
            float(t.get("realized_pnl", 0.0)) for t in metrics.get("closed_trades", [])
        ]
        equity_points = _equity_points_from_curve(trading_days, equity_curve)
        strategy_parameters = effective_config.get("strategy", {})
        engine_type = args.engine_type or "ovtlyr_wheel_engine"
        assumptions_mode = args.assumptions_mode or "realistic_priced"
    elif strategy_id == "stock_replacement":
        engine = BacktestEngine(data, effective_config)
        metrics = engine.run(start, end)
        trading_days = _trading_days_for_period(data, start, end)
        equity_curve = [float(v) for v in engine.equity_curve]
        trade_pnls = [float(t.get("realized_pnl", 0.0)) for t in engine.closed_trades]
        equity_points = _equity_points_from_curve(trading_days, equity_curve)
        strategy_parameters = effective_config.get("strategy", {})
        engine_type = args.engine_type or "ovtlyr_stock_replacement_engine"
        assumptions_mode = args.assumptions_mode or "realistic_priced"
    else:
        from ovtlyr.backtester.openclaw_engines import run_openclaw_variant

        output = run_openclaw_variant(
            data=data,
            config=config,
            start_date=start,
            end_date=end,
            strategy_id=strategy_id,
            assumptions_mode=normalized_variant,
            universe_symbols=universe_symbols,
        )
        metrics = output.metrics
        trading_days = _trading_days_for_period(data, start, end)
        equity_curve = [float(v) for v in output.equity_curve]
        trade_pnls = [float(v) for v in output.trade_pnls]
        equity_points = output.equity_points or _equity_points_from_curve(
            trading_days, equity_curve
        )
        strategy_parameters = output.strategy_parameters
        engine_type = output.engine_type
        assumptions_mode = output.assumptions_mode
        intraday_report = output.intraday_report
        candidate_count_total = int(output.candidate_count_total or 0)
        candidate_count_qualified = int(output.candidate_count_qualified or 0)
        data_quality_breakdown = output.data_quality_breakdown
        rejection_counts = output.rejection_counts
        execution_window = output.execution_window
        component_metrics = output.component_metrics

    _print_backtest_metrics("BACKTEST RESULTS", metrics)

    period_key = start.strftime("%Y-%m")
    oos_summary = _load_latest_oos_summary(
        strategy_id=strategy_id,
        variant=normalized_variant,
        universe_profile=universe_profile,
    )
    execution_realism = {
        k: metrics.get(k)
        for k in [
            "avg_slippage_bps",
            "spread_cost_pct",
            "fill_rate",
            "partial_fill_rate",
            "slippage_cost_total",
        ]
        if k in metrics
    }
    risk_control_events = {
        "allocator_block_days": metrics.get("allocator_block_days"),
        "kill_switch_block_days": metrics.get("kill_switch_block_days"),
        "macro_block_days": metrics.get("macro_block_days"),
        "kill_switch_active": metrics.get("kill_switch_active"),
        "kill_switch_expectancy_r": metrics.get("kill_switch_expectancy_r"),
    }
    payload = {
        "run_id": _build_run_id(strategy_id, normalized_variant, period_key),
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "variant": normalized_variant,
        "engine_type": engine_type,
        "assumptions_mode": assumptions_mode,
        "strategy_parameters": strategy_parameters,
        "feature_time_mode": strategy_parameters.get("feature_time_mode")
        if isinstance(strategy_parameters, dict)
        else None,
        "data_quality_policy": strategy_parameters.get("data_quality_policy")
        if isinstance(strategy_parameters, dict)
        else None,
        "component_metrics": component_metrics,
        "intraday_report": intraday_report,
        "allocator_state": {
            "regime_source": "backtest",
            "enforced": True,
        },
        "risk_control_events": risk_control_events,
        "execution_realism": execution_realism or None,
        "candidate_count_total": candidate_count_total,
        "candidate_count_qualified": candidate_count_qualified,
        "data_quality_breakdown": data_quality_breakdown,
        "rejection_counts": rejection_counts,
        "execution_window": execution_window,
        "data_range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "trading_days": len(trading_days),
            "rows": int(len(data)),
        },
        "universe_profile": universe_profile,
        "universe_size": len(universe_symbols),
        "universe": ",".join(universe_symbols),
        "notes": args.notes or "",
        "period_key": period_key,
        "walkforward_id": (oos_summary or {}).get("walkforward_id"),
        "oos_summary": oos_summary,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "equity_curve": equity_curve,
        "series": _build_series(equity_curve, trade_pnls, equity_points),
        "metrics": metrics,
    }

    _persist_backtest_payload(payload)
    print(
        "\nResults saved to data/backtest_results.json (visible in dashboard /backtest)"
    )


def cmd_backtest_walkforward(args, config, repo, clients):
    """Run walk-forward validation and persist OOS summaries."""
    from ovtlyr.backtester.data_collector import BacktestDataCollector
    from ovtlyr.backtester.engine import BacktestEngine
    from ovtlyr.backtester.openclaw_engines import run_openclaw_variant
    from ovtlyr.backtester.walkforward import (
        generate_walkforward_windows,
        summarize_oos_runs,
    )

    strategy_id = args.strategy_id or "stock_replacement"
    strategy_name = args.strategy_name or "Stock Replacement"
    variant = args.variant or "base"
    normalized_variant = (
        normalize_variant(variant) if strategy_id == "stock_replacement" else variant
    )

    collector = BacktestDataCollector(clients, config)
    data = collector.load_cached_data()
    if data.empty:
        print(
            "No cached data found. Run 'python main.py collect' or 'python main.py generate' first."
        )
        return

    universe_profile, universe_symbols = resolve_universe(args, config)
    print(f"Universe profile: {universe_profile} ({len(universe_symbols)} symbols)")
    try:
        start, end = _resolve_period(data, args.start, args.end)
    except ValueError as e:
        print(f"Cannot run walk-forward: {e}")
        return

    train_days = int(args.train_days or 504)
    test_days = int(args.test_days or 126)
    step_days = int(args.step_days or 126)
    days = _trading_days_for_period(data, start, end)
    windows = generate_walkforward_windows(days, train_days, test_days, step_days)
    if not windows:
        print("No walk-forward windows fit in selected period.")
        return

    print(
        f"Running walk-forward for {strategy_id}|{normalized_variant} "
        f"({len(windows)} windows: train={train_days}, test={test_days}, step={step_days})"
    )

    is_wheel_wf = strategy_id == "stock_replacement" and normalized_variant.startswith("wheel_")

    wf_rows: List[Dict[str, Any]] = []
    oos_metrics: List[Dict[str, Any]] = []
    for w in windows:
        if is_wheel_wf:
            from ovtlyr.backtester.wheel_engine import run_wheel_backtest
            effective_config = apply_stock_replacement_variant(config, normalized_variant)
            wf_metrics = run_wheel_backtest(data, effective_config, w.test_start, w.test_end)
            m = {k: v for k, v in wf_metrics.items() if k not in ("equity_curve", "closed_trades")}
        elif strategy_id == "stock_replacement":
            effective_config = apply_stock_replacement_variant(
                config, normalized_variant
            )
            engine = BacktestEngine(data, effective_config)
            m = engine.run(w.test_start, w.test_end)
        else:
            # Warm up long-lookback indicators before the OOS window so strategies
            # relying on MA200/HV20 don't produce artificial zero-trade windows.
            warm_start = w.test_start
            if strategy_id != "intraday_open_close_options":
                warm_start = _warmup_start_day(days, w.test_start, lookback_days=260)
            output = run_openclaw_variant(
                data=data,
                config=config,
                start_date=warm_start,
                end_date=w.test_end,
                strategy_id=strategy_id,
                assumptions_mode=normalized_variant,
                universe_symbols=universe_symbols,
            )
            m = output.metrics
            if warm_start < w.test_start:
                m = _metrics_from_equity_window(
                    output.equity_points,
                    start_day=w.test_start,
                    end_day=w.test_end,
                    base_metrics=m,
                )
        oos_metrics.append(m)
        wf_rows.append(
            {
                "window_index": w.index,
                "train_start": w.train_start.isoformat(),
                "train_end": w.train_end.isoformat(),
                "test_start": w.test_start.isoformat(),
                "test_end": w.test_end.isoformat(),
                "metrics": _round_obj(m),
            }
        )

    # Family-aware OOS thresholds — credit spreads are high-Sharpe by design;
    # equity-style strategies (wheel, stock replacement) have naturally lower Sharpe.
    _FAMILY_THRESHOLDS = {
        "wheel":                        {"sharpe": 0.40, "max_dd": 35.0},
        "stock_replacement":            {"sharpe": 0.30, "max_dd": 35.0},
        "openclaw_call_credit_spread":  {"sharpe": 0.70, "max_dd": 30.0},
        "openclaw_put_credit_spread":   {"sharpe": 0.70, "max_dd": 30.0},
    }
    if is_wheel_wf:
        _family_key = "wheel"
    elif strategy_id == "stock_replacement":
        _family_key = "stock_replacement"
    else:
        _family_key = strategy_id
    _fam_defaults = _FAMILY_THRESHOLDS.get(_family_key, {"sharpe": 0.70, "max_dd": 30.0})
    sharpe_threshold = getattr(args, "sharpe_threshold", None) or _fam_defaults["sharpe"]
    max_dd_threshold = getattr(args, "max_dd_threshold", None) or _fam_defaults["max_dd"]

    oos_summary = summarize_oos_runs(
        oos_metrics,
        sharpe_threshold=sharpe_threshold,
        max_dd_threshold=max_dd_threshold,
    )
    wf_id = _build_run_id(
        strategy_id, normalized_variant, f"wf-{start.strftime('%Y%m')}"
    )
    oos_summary["walkforward_id"] = wf_id

    payload = {
        "walkforward_id": wf_id,
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "variant": normalized_variant,
        "universe_profile": universe_profile,
        "universe_size": len(universe_symbols),
        "universe": ",".join(universe_symbols),
        "train_days": train_days,
        "test_days": test_days,
        "step_days": step_days,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "oos_summary": _round_obj(oos_summary),
        "windows": wf_rows,
    }

    os.makedirs("data", exist_ok=True)
    wf_runs = _load_json(WALKFORWARD_RUNS_PATH, [])
    if not isinstance(wf_runs, list):
        wf_runs = []
    wf_runs.append(payload)
    with open(WALKFORWARD_RUNS_PATH, "w") as f:
        json.dump(_round_obj(wf_runs), f, indent=2)

    wf_summary = _load_json(WALKFORWARD_SUMMARY_PATH, {})
    if not isinstance(wf_summary, dict):
        wf_summary = {}
    key = f"{strategy_id}|{normalized_variant}|{universe_profile}"
    wf_summary[key] = {
        "walkforward_id": wf_id,
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "variant": normalized_variant,
        "universe_profile": universe_profile,
        "generated_at": payload["generated_at"],
        "oos_summary": _round_obj(oos_summary),
    }
    with open(WALKFORWARD_SUMMARY_PATH, "w") as f:
        json.dump(_round_obj(wf_summary), f, indent=2)

    _attach_oos_to_backtest_payloads(
        strategy_id=strategy_id,
        variant=normalized_variant,
        universe_profile=universe_profile,
        oos_summary=_round_obj(oos_summary),
        walkforward_id=wf_id,
    )

    print("\n" + "=" * 72)
    print("WALK-FORWARD SUMMARY")
    print("=" * 72)
    print(f"Strategy: {strategy_id} | {normalized_variant}")
    print(f"Windows:  {oos_summary.get('windows')}")
    print(f"OOS Avg Return: {oos_summary.get('avg_total_return_pct', 0.0):+.2f}%")
    print(f"OOS Avg Sharpe: {oos_summary.get('avg_sharpe_ratio', 0.0):.2f}")
    print(f"OOS Avg Max DD: {oos_summary.get('avg_max_drawdown_pct', 0.0):.2f}%")
    print(f"Pass Validation: {oos_summary.get('pass_validation')}")
    print("=" * 72)
    print(f"Saved: {WALKFORWARD_RUNS_PATH}")
    print(f"Saved: {WALKFORWARD_SUMMARY_PATH}")


def cmd_backtest_batch(args, config, repo, clients):
    """Run all OpenClaw strategy/mode variants and persist each run."""
    from ovtlyr.backtester.data_collector import BacktestDataCollector
    from ovtlyr.backtester.openclaw_engines import run_openclaw_variant

    collector = BacktestDataCollector(clients, config)
    data = collector.load_cached_data()
    if data.empty:
        print(
            "No cached data found. Run 'python main.py generate' or 'python main.py collect' first."
        )
        return

    try:
        start, end = _resolve_period(data, args.start, args.end)
    except ValueError as e:
        print(f"Cannot run backtest batch: {e}")
        return

    universe_profile, universe_symbols = resolve_universe(args, config)
    print(f"Universe profile: {universe_profile} ({len(universe_symbols)} symbols)")

    matrix = [
        (
            "intraday_open_close_options",
            "Intraday Open-Close Options",
            "baseline",
            "Baseline intraday open→close options strategy",
        ),
        (
            "intraday_open_close_options",
            "Intraday Open-Close Options",
            "conservative",
            "Conservative intraday risk profile",
        ),
        (
            "intraday_open_close_options",
            "Intraday Open-Close Options",
            "aggressive",
            "Aggressive intraday risk profile",
        ),
        (
            "intraday_open_close_options",
            "Intraday Open-Close Options",
            "oos_hardened",
            "OOS-hardened intraday profile with strict liquidity and execution-quality gates",
        ),
        (
            "intraday_open_close_options",
            "Intraday Open-Close Options",
            "wf_v1_liquidity_guard",
            "Validation sweep v1: liquidity-focused low-turnover profile",
        ),
        (
            "intraday_open_close_options",
            "Intraday Open-Close Options",
            "wf_v2_flow_strict",
            "Validation sweep v2: stricter unusual-flow and execution-quality profile",
        ),
        (
            "intraday_open_close_options",
            "Intraday Open-Close Options",
            "wf_v3_regime_strict",
            "Validation sweep v3: strict symbol + SPY lagged regime gating",
        ),
        (
            "intraday_open_close_options",
            "Intraday Open-Close Options",
            "wf_v4_validated_candidate",
            "Validation sweep v4: blended candidate profile for pass-promotion",
        ),
        (
            "openclaw_stock_options",
            "OpenClaw Stock Options",
            "legacy_replica",
            "Legacy OpenClaw stock-options assumptions",
        ),
        (
            "openclaw_stock_options",
            "OpenClaw Stock Options",
            "realistic_priced",
            "Realistic stock-options fills and friction",
        ),
        (
            "openclaw_put_credit_spread",
            "OpenClaw Put Credit Spread",
            "legacy_replica",
            "Legacy regime-filtered put credit spread assumptions",
        ),
        (
            "openclaw_put_credit_spread",
            "OpenClaw Put Credit Spread",
            "realistic_priced",
            "Realistic regime-filtered put credit spread assumptions",
        ),
        (
            "openclaw_put_credit_spread",
            "OpenClaw Put Credit Spread",
            "pcs_trend_baseline",
            "Trend-filtered PCS with volatility-target sizing baseline profile",
        ),
        (
            "openclaw_put_credit_spread",
            "OpenClaw Put Credit Spread",
            "pcs_trend_defensive",
            "Trend-filtered PCS defensive profile with lower target annual volatility",
        ),
        (
            "openclaw_put_credit_spread",
            "OpenClaw Put Credit Spread",
            "pcs_income_plus",
            "Higher-opportunity income variant (slightly higher risk and throughput)",
        ),
        (
            "openclaw_put_credit_spread",
            "OpenClaw Put Credit Spread",
            "pcs_balanced_plus",
            "Balanced premium-capture variant with tighter downside guardrails",
        ),
        (
            "openclaw_put_credit_spread",
            "OpenClaw Put Credit Spread",
            "pcs_conservative_turnover",
            "Conservative sizing with faster winner harvesting",
        ),
        (
            "openclaw_put_credit_spread",
            "OpenClaw Put Credit Spread",
            "pcs_vix_optimal",
            "Legacy params + HV30 gate for moderate-volatility premium collection",
        ),
        (
            "openclaw_tqqq_swing",
            "OpenClaw TQQQ Swing",
            "legacy_replica",
            "Legacy OpenClaw TQQQ swing assumptions",
        ),
        (
            "openclaw_tqqq_swing",
            "OpenClaw TQQQ Swing",
            "realistic_priced",
            "Realistic TQQQ swing assumptions with tighter risk",
        ),
        (
            "openclaw_hybrid",
            "OpenClaw Hybrid",
            "legacy_replica",
            "Legacy blended stock-options + TQQQ hybrid",
        ),
        (
            "openclaw_hybrid",
            "OpenClaw Hybrid",
            "realistic_priced",
            "Realistic blended stock-options + TQQQ hybrid",
        ),
        (
            "research_putwrite_spy",
            "Research PutWrite SPY",
            "baseline",
            "Systematic monthly cash-secured put selling with trend+volatility gate",
        ),
        (
            "research_putwrite_spy",
            "Research PutWrite SPY",
            "defensive",
            "Defensive putwrite profile with lower allocation and tighter vol window",
        ),
        (
            "research_buywrite_spy",
            "Research BuyWrite SPY",
            "baseline",
            "Systematic covered-call overwrite on SPY with trend+volatility gate",
        ),
        (
            "research_buywrite_spy",
            "Research BuyWrite SPY",
            "defensive",
            "Defensive covered-call profile with lower premium assumptions",
        ),
        (
            "research_collar_spy",
            "Research Collar SPY",
            "baseline",
            "Long SPY + protective put - covered call collar",
        ),
        (
            "research_collar_spy",
            "Research Collar SPY",
            "defensive",
            "Defensive collar profile with wider put buffer",
        ),
        # Stock-replacement upgraded variants
        (
            "stock_replacement",
            "Stock Replacement",
            "base",
            "Baseline stock-replacement profile with allocator/risk controls",
        ),
        (
            "stock_replacement",
            "Stock Replacement",
            "full_filter_stack",
            "Stacked market/symbol filters with allocator/risk controls",
        ),
        (
            "stock_replacement",
            "Stock Replacement",
            "full_filter_20pos",
            "Top-50 diversified stock-replacement profile (20 max positions)",
        ),
        (
            "stock_replacement",
            "Stock Replacement",
            "full_filter_iv_rs",
            "Risk-adjusted stock-replacement profile with IV-rank + relative strength",
        ),
        # CSP variants - uses stock_replacement engine with CSP config
        (
            "stock_replacement",
            "CSP Delta-30 50% PT Roll Delta",
            "csp_d30_pt50_roll_delta",
            "CSP: -0.30 delta, 50% profit target, roll on delta < -0.10",
        ),
        (
            "stock_replacement",
            "CSP Delta-30 50% PT Roll DTE",
            "csp_d30_pt50_roll_dte",
            "CSP: -0.30 delta, 50% profit target, roll on 7 DTE",
        ),
        (
            "stock_replacement",
            "CSP Delta-30 Ride to Expiry Roll Delta",
            "csp_d30_ride_roll_delta",
            "CSP: -0.30 delta, ride to expiry, roll on delta < -0.10",
        ),
        (
            "stock_replacement",
            "CSP Delta-30 Ride to Expiry Roll DTE",
            "csp_d30_ride_roll_dte",
            "CSP: -0.30 delta, ride to expiry, roll on 7 DTE",
        ),
        (
            "stock_replacement",
            "CSP Delta-20 50% PT Roll Delta",
            "csp_d20_pt50_roll_delta",
            "CSP: -0.20 delta, 50% profit target, roll on delta < -0.10",
        ),
        (
            "stock_replacement",
            "CSP Delta-20 50% PT Roll DTE",
            "csp_d20_pt50_roll_dte",
            "CSP: -0.20 delta, 50% profit target, roll on 7 DTE",
        ),
        (
            "stock_replacement",
            "CSP Delta-20 Ride to Expiry Roll Delta",
            "csp_d20_ride_roll_delta",
            "CSP: -0.20 delta, ride to expiry, roll on delta < -0.10",
        ),
        (
            "stock_replacement",
            "CSP Delta-20 Ride to Expiry Roll DTE",
            "csp_d20_ride_roll_dte",
            "CSP: -0.20 delta, ride to expiry, roll on 7 DTE",
        ),
        # LEAPS-style long-duration calls (180-400 DTE)
        (
            "stock_replacement",
            "LEAPS Stock Replacement",
            "leaps_80d",
            "LEAPS: 0.80 delta, 180-400 DTE, 50% profit target — buy once hold for a year",
        ),
        (
            "stock_replacement",
            "LEAPS Deep ITM",
            "leaps_85d",
            "LEAPS: 0.85 delta, 180-400 DTE, deeper ITM for near-pure intrinsic value",
        ),
        (
            "stock_replacement",
            "LEAPS Gated",
            "leaps_gated",
            "LEAPS: full regime + IV rank + RS filter gates — quality entries only",
        ),
        (
            "stock_replacement",
            "LEAPS Defensive",
            "leaps_defensive",
            "LEAPS: 0.85 delta + SPY trend block + IV rank — sits in cash during bear markets",
        ),
        # Wheel strategy (CSP → Covered Call → repeat)
        (
            "stock_replacement",
            "Wheel Strategy",
            "wheel_d30_c30",
            "Wheel: sell -0.30 delta CSP → if assigned sell 0.30 delta covered call",
        ),
        (
            "stock_replacement",
            "Wheel Conservative",
            "wheel_d20_c30",
            "Wheel: conservative -0.20 delta CSP → 0.30 delta covered call",
        ),
        (
            "stock_replacement",
            "Wheel Aggressive",
            "wheel_d40_c30",
            "Wheel: aggressive -0.40 delta CSP (high assignment probability) → 0.30 delta CC",
        ),
        # Call Credit Spread — bearish/neutral on SPY/QQQ
        (
            "openclaw_call_credit_spread",
            "Call Credit Spread Baseline",
            "ccs_baseline",
            "CCS baseline: sell 4.5% OTM call, buy 5% OTM call — neutral/bearish regime",
        ),
        (
            "openclaw_call_credit_spread",
            "Call Credit Spread VIX Regime",
            "ccs_vix_regime",
            "CCS VIX regime: only enter when HV20 > 18% (elevated vol = expensive calls)",
        ),
        (
            "openclaw_call_credit_spread",
            "Call Credit Spread Defensive",
            "ccs_defensive",
            "CCS defensive: 6% OTM short strike, tighter sizing — lower delta, lower risk",
        ),
    ]
    period_key = start.strftime("%Y-%m")

    print(
        f"Running strategy batch backtests from {start} to {end} ({len(matrix)} variants)"
    )
    results = []
    for strategy_id, strategy_name, mode, default_note in matrix:
        print(f"\n[{strategy_id}|{mode}] running...")

        is_stock_replacement_variant = strategy_id == "stock_replacement"
        is_csp_variant = is_stock_replacement_variant and mode.startswith("csp_")
        is_wheel_variant = is_stock_replacement_variant and mode.startswith("wheel_")

        if is_wheel_variant:
            # Route wheel variants through wheel_engine
            from ovtlyr.backtester.stock_replacement_profiles import (
                apply_stock_replacement_variant,
            )
            from ovtlyr.backtester.wheel_engine import run_wheel_backtest

            effective_config = apply_stock_replacement_variant(config, mode)
            metrics = run_wheel_backtest(data, effective_config, start, end)
            trading_days = _trading_days_for_period(data, start, end)
            equity_curve = [float(v) for v in metrics.get("equity_curve", [100000])]
            trade_pnls = [
                float(t.get("realized_pnl", 0.0))
                for t in metrics.get("closed_trades", [])
            ]
            equity_points = _equity_points_from_curve(trading_days, equity_curve)

            output_metrics = {k: v for k, v in metrics.items() if k not in ("equity_curve", "closed_trades")}
            output_equity_curve = equity_curve
            output_series = {
                "equity_curve": equity_curve,
                "drawdown_curve": [],
                "rolling_win_rate": [],
                "monthly_returns": [],
            }
            output_universe = ",".join(universe_symbols)
            output_engine_type = "ovtlyr_wheel_engine"
            output_assumptions_mode = "wheel_strategy"
            output_strategy_params = effective_config.get("strategy", {})
            output_comp_metrics = None
            output_intraday = None
            output_cand_total = 0
            output_cand_qual = 0
            output_dq_breakdown = None
            output_rejection_counts = None
            output_exec_window = None

        elif is_stock_replacement_variant:
            # Use BacktestEngine for stock-replacement family (calls + CSP variants)
            from ovtlyr.backtester.stock_replacement_profiles import (
                apply_stock_replacement_variant,
            )
            from ovtlyr.backtester.engine import BacktestEngine

            effective_config = apply_stock_replacement_variant(config, mode)
            engine = BacktestEngine(data, effective_config)
            metrics = engine.run(start, end)
            trading_days = _trading_days_for_period(data, start, end)
            equity_curve = [float(v) for v in engine.equity_curve]
            trade_pnls = [
                float(t.get("realized_pnl", 0.0)) for t in engine.closed_trades
            ]
            equity_points = _equity_points_from_curve(trading_days, equity_curve)

            output_metrics = metrics
            output_equity_curve = equity_curve
            output_series = {
                "equity_curve": equity_curve,
                "drawdown_curve": [],
                "rolling_win_rate": [],
                "monthly_returns": [],
            }
            output_universe = ",".join(universe_symbols)
            output_engine_type = (
                "ovtlyr_csp_engine" if is_csp_variant else "ovtlyr_stock_replacement_engine"
            )
            output_assumptions_mode = (
                "csp_strategy" if is_csp_variant else "realistic_priced"
            )
            output_strategy_params = effective_config.get("strategy", {})
            output_comp_metrics = None
            output_intraday = None
            output_cand_total = 0
            output_cand_qual = 0
            output_dq_breakdown = None
            output_exec_window = None
        else:
            # Use OpenClaw engine for other strategies
            output = run_openclaw_variant(
                data=data,
                config=config,
                start_date=start,
                end_date=end,
                strategy_id=strategy_id,
                assumptions_mode=mode,
                universe_symbols=universe_symbols,
            )
            output_metrics = output.metrics
            output_equity_curve = output.equity_curve
            output_series = output.series
            output_universe = output.universe
            output_engine_type = output.engine_type
            output_assumptions_mode = output.assumptions_mode
            output_strategy_params = output.strategy_parameters
            output_comp_metrics = output.component_metrics
            output_intraday = output.intraday_report
            output_cand_total = int(output.candidate_count_total or 0)
            output_cand_qual = int(output.candidate_count_qualified or 0)
            output_dq_breakdown = output.data_quality_breakdown
            output_rejection_counts = output.rejection_counts
            output_exec_window = output.execution_window

        oos_summary = _load_latest_oos_summary(
            strategy_id=strategy_id,
            variant=mode,
            universe_profile=universe_profile,
        )
        execution_realism = {
            k: output_metrics.get(k)
            for k in [
                "avg_slippage_bps",
                "spread_cost_pct",
                "fill_rate",
                "partial_fill_rate",
                "slippage_cost_total",
            ]
            if k in output_metrics
        }
        risk_control_events = {
            "allocator_block_days": output_metrics.get("allocator_block_days"),
            "kill_switch_block_days": output_metrics.get("kill_switch_block_days"),
            "macro_block_days": output_metrics.get("macro_block_days"),
            "kill_switch_active": output_metrics.get("kill_switch_active"),
            "kill_switch_expectancy_r": output_metrics.get("kill_switch_expectancy_r"),
        }
        payload = {
            "run_id": _build_run_id(strategy_id, mode, period_key),
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "variant": mode,
            "engine_type": output_engine_type,
            "assumptions_mode": output_assumptions_mode,
            "strategy_parameters": output_strategy_params,
            "feature_time_mode": output_strategy_params.get("feature_time_mode")
            if isinstance(output_strategy_params, dict)
            else None,
            "data_quality_policy": output_strategy_params.get("data_quality_policy")
            if isinstance(output_strategy_params, dict)
            else None,
            "component_metrics": output_comp_metrics,
            "intraday_report": output_intraday,
            "allocator_state": {
                "regime_source": "backtest",
                "enforced": True,
            },
            "risk_control_events": risk_control_events,
            "execution_realism": execution_realism or None,
            "candidate_count_total": output_cand_total,
            "candidate_count_qualified": output_cand_qual,
            "data_quality_breakdown": output_dq_breakdown,
            "rejection_counts": output_rejection_counts,
            "execution_window": output_exec_window,
            "data_range": {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "trading_days": int(output_metrics.get("trading_days", 0)),
                "rows": int(len(data)),
            },
            "universe_profile": universe_profile,
            "universe_size": len(universe_symbols),
            "universe": output_universe,
            "notes": args.notes or default_note,
            "period_key": period_key,
            "walkforward_id": (oos_summary or {}).get("walkforward_id"),
            "oos_summary": oos_summary,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "equity_curve": output_equity_curve,
            "series": output_series,
            "metrics": output_metrics,
        }
        _persist_backtest_payload(payload)
        results.append(payload)
        m = output_metrics
        print(
            f"  return={m.get('total_return_pct', 0.0):+.2f}% | "
            f"win_rate={m.get('win_rate', 0.0):.2f}% | "
            f"pf={m.get('profit_factor', 0.0):.2f}"
        )

    print("\n" + "=" * 72)
    print("STRATEGY BATCH COMPLETE")
    print("=" * 72)
    for r in results:
        m = r["metrics"]
        print(
            f"{r['strategy_id']}|{r['variant']}: "
            f"return={m.get('total_return_pct', 0.0):+.2f}%  "
            f"win={m.get('win_rate', 0.0):.2f}%  "
            f"pf={m.get('profit_factor', 0.0):.2f}"
        )
    print("\nDashboard data updated (latest run + history + runs log).")


def _update_intraday_catalog_validation(
    sweep_variants: List[str], promoted_variant: str | None
) -> None:
    catalog = _load_json(STRATEGY_CATALOG_PATH, [])
    if not isinstance(catalog, list):
        return

    defaults = {
        "wf_v1_liquidity_guard": {
            "description": "Validation sweep v1 with strict liquidity and low turnover constraints.",
            "hypothesis": "Tighter liquidity thresholds and one-trade-per-day cap improve OOS stability.",
        },
        "wf_v2_flow_strict": {
            "description": "Validation sweep v2 with stricter unusual-flow thresholds and execution constraints.",
            "hypothesis": "Higher flow-quality requirements improve edge reliability out-of-sample.",
        },
        "wf_v3_regime_strict": {
            "description": "Validation sweep v3 with lagged symbol trend + SPY regime alignment.",
            "hypothesis": "Regime-aligned direction filtering should reduce adverse intraday entries.",
        },
        "wf_v4_validated_candidate": {
            "description": "Validation sweep v4 blended candidate profile tuned for pass criteria.",
            "hypothesis": "Balanced constraints may deliver positive OOS return with acceptable Sharpe/DD.",
        },
    }

    seen = {str(e.get("variant", "")) for e in catalog if str(e.get("strategy_id", "")) == "intraday_open_close_options"}
    for variant in sweep_variants:
        if variant not in seen:
            meta = defaults.get(variant, {"description": "", "hypothesis": ""})
            catalog.append(
                {
                    "strategy_id": "intraday_open_close_options",
                    "strategy_name": "Intraday Open-Close Options",
                    "variant": variant,
                    "status": "experimental",
                    "champion": False,
                    "validated": False,
                    "universe_note": "Uses selected universe profile (default top_50) with validation-focused lagged features",
                    "description": meta["description"],
                    "hypothesis": meta["hypothesis"],
                }
            )

    changed = False
    for row in catalog:
        if str(row.get("strategy_id", "")) != "intraday_open_close_options":
            continue
        variant = str(row.get("variant", ""))
        if variant in sweep_variants:
            desired_validated = bool(promoted_variant and variant == promoted_variant)
            if row.get("status") != "experimental":
                row["status"] = "experimental"
                changed = True
            if bool(row.get("validated", False)) != desired_validated:
                row["validated"] = desired_validated
                changed = True

    if changed:
        with open(STRATEGY_CATALOG_PATH, "w") as f:
            json.dump(catalog, f, indent=2)


def cmd_intraday_sweep_validate(args, config, repo, clients):
    sweep_variants = [
        "wf_v1_liquidity_guard",
        "wf_v2_flow_strict",
        "wf_v3_regime_strict",
        "wf_v4_validated_candidate",
    ]

    start = args.start or "2020-01-01"
    end = args.end or "2025-12-31"
    universe = args.universe or "top_50"
    train_days = int(args.train_days or 504)
    test_days = int(args.test_days or 126)
    step_days = int(args.step_days or 126)

    print("\n" + "=" * 72)
    print("INTRADAY SWEEP VALIDATION")
    print("=" * 72)
    print(
        f"Strategy: intraday_open_close_options | Variants={len(sweep_variants)} | "
        f"Period={start} to {end} | Universe={universe}"
    )
    print(
        f"Walk-forward: train={train_days}, test={test_days}, step={step_days}"
    )

    for variant in sweep_variants:
        print("\n" + "-" * 72)
        print(f"Running variant: {variant}")

        back_args = argparse.Namespace(**vars(args))
        back_args.strategy_id = "intraday_open_close_options"
        back_args.strategy_name = "Intraday Open-Close Options"
        back_args.variant = variant
        back_args.start = start
        back_args.end = end
        back_args.universe = universe
        back_args.notes = f"intraday_sweep_validate:{variant}"
        cmd_backtest(back_args, config, repo, clients)

        wf_args = argparse.Namespace(**vars(args))
        wf_args.strategy_id = "intraday_open_close_options"
        wf_args.strategy_name = "Intraday Open-Close Options"
        wf_args.variant = variant
        wf_args.start = start
        wf_args.end = end
        wf_args.universe = universe
        wf_args.train_days = train_days
        wf_args.test_days = test_days
        wf_args.step_days = step_days
        cmd_backtest_walkforward(wf_args, config, repo, clients)

    runs = _load_json(BACKTEST_RUNS_PATH, [])
    if not isinstance(runs, list):
        runs = []

    scoreboard = []
    for variant in sweep_variants:
        candidates = [
            r
            for r in runs
            if str(r.get("strategy_id")) == "intraday_open_close_options"
            and str(r.get("variant")) == variant
            and _profile_matches(r.get("universe_profile", ""), universe)
        ]
        if not candidates:
            continue
        candidates.sort(key=lambda r: str(r.get("generated_at", "")), reverse=True)
        latest = candidates[0]
        m = latest.get("metrics", {}) or {}
        oos = latest.get("oos_summary", {}) or {}
        scoreboard.append(
            {
                "variant": variant,
                "pass_validation": bool(oos.get("pass_validation", False)),
                "oos_sharpe": float(oos.get("avg_sharpe_ratio", 0.0) or 0.0),
                "oos_max_dd": float(oos.get("avg_max_drawdown_pct", 0.0) or 0.0),
                "oos_return": float(oos.get("avg_total_return_pct", 0.0) or 0.0),
                "latest_return": float(m.get("total_return_pct", 0.0) or 0.0),
                "latest_win_rate": float(m.get("win_rate", 0.0) or 0.0),
                "latest_pf": float(m.get("profit_factor", 0.0) or 0.0),
                "run_id": latest.get("run_id", ""),
            }
        )

    scoreboard.sort(
        key=lambda r: (
            0 if r["pass_validation"] else 1,
            -r["oos_sharpe"],
            r["oos_max_dd"],
            -r["oos_return"],
        )
    )

    promoted_variant = None
    for row in scoreboard:
        if row["pass_validation"]:
            promoted_variant = row["variant"]
            break

    if bool(args.promote_pass):
        _update_intraday_catalog_validation(sweep_variants, promoted_variant)

    print("\n" + "=" * 72)
    print("INTRADAY SWEEP SCOREBOARD")
    print("=" * 72)
    for row in scoreboard:
        print(
            f"{row['variant']}: "
            f"PASS={row['pass_validation']} | "
            f"OOS Sharpe={row['oos_sharpe']:.4f} | "
            f"OOS DD={row['oos_max_dd']:.4f}% | "
            f"OOS Return={row['oos_return']:+.4f}% | "
            f"Return={row['latest_return']:+.2f}% | "
            f"WR={row['latest_win_rate']:.2f}% | PF={row['latest_pf']:.2f}"
        )

    if promoted_variant:
        print(f"\nPromoted validated intraday variant: {promoted_variant}")
    else:
        print("\nNo variant passed validation. All sweep variants remain experimental.")


def main():
    load_dotenv()

    config = load_config()

    log_cfg = config.get("logging", {})
    setup_logging(
        level=log_cfg.get("level", "INFO"),
        log_file=log_cfg.get("file", "logs/ovtlyr.log"),
        max_bytes=log_cfg.get("max_bytes", 5_242_880),
        backup_count=log_cfg.get("backup_count", 3),
    )

    db_path = config.get("database", {}).get("path", "db/ovtlyr.db")
    initialize_db(db_path)
    repo = Repository(db_path)

    clients = get_clients(paper=config.get("alpaca", {}).get("paper", True))

    parser = argparse.ArgumentParser(
        prog="ovtlyr",
        description="OVTLYR Options Trading System",
    )
    parser.add_argument(
        "command",
        choices=[
            "scan",
            "positions",
            "report",
            "stats",
            "collect",
            "generate",
            "backtest",
            "backtest-batch",
            "intraday-report",
            "backtest-walkforward",
            "intraday-sweep-validate",
        ],
    )
    parser.add_argument(
        "--force", action="store_true", help="Force run even on non-market days"
    )
    parser.add_argument(
        "--universe",
        type=str,
        default=None,
        help=f"Universe profile name (available: {', '.join(available_universes())})",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date for generate/backtest (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date for generate/backtest (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date for intraday-report (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--top", type=int, default=15, help="Top N picks for intraday-report"
    )
    parser.add_argument(
        "--min-qualifiers",
        type=int,
        default=30,
        help="Minimum qualifier target for intraday-report",
    )
    parser.add_argument(
        "--strategy-id",
        type=str,
        default="stock_replacement",
        help="Backtest strategy id tag",
    )
    parser.add_argument(
        "--strategy-name",
        type=str,
        default="Stock Replacement",
        help="Backtest strategy display name",
    )
    parser.add_argument(
        "--variant", type=str, default="base", help="Backtest strategy variant id"
    )
    parser.add_argument(
        "--engine-type", type=str, default="", help="Backtest engine type metadata"
    )
    parser.add_argument(
        "--assumptions-mode",
        type=str,
        default="realistic_priced",
        help="Assumptions mode metadata for run payload",
    )
    parser.add_argument(
        "--notes", type=str, default="", help="Optional notes for this backtest run"
    )
    parser.add_argument(
        "--train-days",
        type=int,
        default=504,
        help="Walk-forward train window (trading days)",
    )
    parser.add_argument(
        "--test-days",
        type=int,
        default=126,
        help="Walk-forward test window (trading days)",
    )
    parser.add_argument(
        "--step-days",
        type=int,
        default=126,
        help="Walk-forward step size (trading days)",
    )
    parser.add_argument(
        "--sharpe-threshold",
        type=float,
        default=None,
        help="Override OOS Sharpe threshold for walk-forward validation (default: family-specific)",
    )
    parser.add_argument(
        "--max-dd-threshold",
        type=float,
        default=None,
        help="Override OOS max-drawdown threshold for walk-forward validation (default: family-specific)",
    )
    parser.add_argument(
        "--promote-pass",
        action="store_true",
        help="Promote best passing sweep variant in strategy catalog",
    )
    parser.add_argument(
        "--no-promote-pass",
        dest="promote_pass",
        action="store_false",
        help="Do not promote sweep variants even if one passes",
    )
    parser.set_defaults(promote_pass=True)

    args = parser.parse_args()

    commands = {
        "scan": cmd_scan,
        "positions": cmd_positions,
        "report": cmd_report,
        "stats": cmd_stats,
        "collect": cmd_collect,
        "generate": cmd_generate,
        "backtest": cmd_backtest,
        "backtest-batch": cmd_backtest_batch,
        "intraday-report": cmd_intraday_report,
        "backtest-walkforward": cmd_backtest_walkforward,
        "intraday-sweep-validate": cmd_intraday_sweep_validate,
    }

    commands[args.command](args, config, repo, clients)


if __name__ == "__main__":
    main()
