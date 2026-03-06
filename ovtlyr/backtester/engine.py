"""
Backtest engine for the OVTLYR deep-ITM stock replacement strategy.

Uses cached option chain data (collected via `python main.py collect`).
Reuses the same filter/roll logic as the live scanner.
"""

import logging
import math
from datetime import date, datetime
from typing import List, Dict, Any, Optional

import pandas as pd
from scipy.stats import norm

from ovtlyr.scanner.filters import filter_candidates
from ovtlyr.utils.math_utils import compute_intrinsic_value
from ovtlyr.backtester.position_sizing import (
    cap_symbol_notional,
    risk_budget_contracts,
    vol_target_contracts,
)
from ovtlyr.backtester.execution_model import (
    adjust_fill_price,
    expected_slippage_bps,
    get_execution_settings,
    summarize_execution_realism,
)
from ovtlyr.backtester.metrics import compute_metrics
from ovtlyr.strategy.allocator import (
    compute_regime_state,
    risk_budget_for_regime,
    strategy_allowed,
)
from ovtlyr.strategy.risk_controls import (
    correlation_gate,
    kill_switch_state,
    load_macro_calendar,
    macro_window_block,
    portfolio_heat_ok,
)

logger = logging.getLogger(__name__)

RISK_FREE_RATE = 0.05


def _bsm_call(S: float, K: float, T: float, sigma: float, r: float = RISK_FREE_RATE):
    """Black-Scholes call price and delta. Returns (price, delta)."""
    if T <= 0 or sigma <= 0:
        intrinsic = max(S - K, 0.0)
        delta = 1.0 if S > K else 0.0
        return intrinsic, delta
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    delta = norm.cdf(d1)
    return max(price, 0.0), delta


def _bsm_put(S: float, K: float, T: float, sigma: float, r: float = RISK_FREE_RATE):
    """Black-Scholes put price and delta. Returns (price, delta). Delta is negative."""
    if T <= 0 or sigma <= 0:
        intrinsic = max(K - S, 0.0)
        delta = -1.0 if S < K else 0.0
        return intrinsic, delta
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    delta = norm.cdf(d1) - 1  # put delta is negative
    return max(price, 0.0), delta


class BacktestEngine:
    def __init__(self, data: pd.DataFrame, config: Dict[str, Any]):
        self.data = data
        self.config = config
        self.strategy = config.get("strategy", {})
        self.positions: List[Dict] = []
        self.closed_trades: List[Dict] = []
        self.equity_curve: List[float] = []
        self.initial_capital = 100_000.0
        # Precomputed EMA trend states: {symbol: {date_str: {is_bullish, is_bearish}}}
        self._trend_states: Dict[str, Dict[str, Dict]] = {}
        # VIX proxy: SPY 30-day historical volatility, keyed by date_str
        self._hv30: Dict[str, float] = {}
        # Market breadth: % of universe symbols above MA200, keyed by date_str
        self._breadth_pct: Dict[str, float] = {}
        # Order block: N-day rolling high per symbol, {symbol: {date_str: high}}
        self._nd_high: Dict[str, Dict[str, float]] = {}
        # Momentum rank: per-day dict of {symbol: rank_percentile (0-100)}
        # where 100 = strongest momentum in the universe on that day
        self._momentum_ranks: Dict[
            str, Dict[str, float]
        ] = {}  # {date_str: {symbol: pct}}
        # IV rank: per-day per-symbol IV rank percentile (0=cheap, 100=expensive)
        self._iv_ranks: Dict[
            str, Dict[str, float]
        ] = {}  # {date_str: {symbol: iv_rank_pct}}

    def _precompute_trend_states(
        self,
        ema_fast: int = 10,
        ema_medium: int = 20,
        ema_slow: int = 50,
    ) -> None:
        """
        Precompute EMA trend state for every (symbol, date) pair using the
        underlying_price time series in the cached data.

        A symbol is "bullish" on a given day when:
            EMA(fast) > EMA(medium)  AND  price > EMA(slow)

        Results stored in self._trend_states[symbol][date_str].
        """
        if "underlying_price" not in self.data.columns:
            return

        # One unique price per (date, underlying) — take the first if multiple rows
        price_df = (
            self.data[["date", "underlying", "underlying_price"]]
            .drop_duplicates(subset=["date", "underlying"])
            .sort_values("date")
        )

        for symbol, grp in price_df.groupby("underlying"):
            grp = grp.sort_values("date").copy()
            prices = grp["underlying_price"].astype(float)
            grp["ema_f"] = prices.ewm(span=ema_fast, adjust=False).mean()
            grp["ema_m"] = prices.ewm(span=ema_medium, adjust=False).mean()
            grp["ema_s"] = prices.ewm(span=ema_slow, adjust=False).mean()
            grp["is_bullish"] = (grp["ema_f"] > grp["ema_m"]) & (prices > grp["ema_s"])
            grp["is_bearish"] = (grp["ema_f"] < grp["ema_m"]) & (prices < grp["ema_s"])

            self._trend_states[str(symbol)] = {
                str(row["date"]): {
                    "is_bullish": bool(row["is_bullish"]),
                    "is_bearish": bool(row["is_bearish"]),
                }
                for _, row in grp.iterrows()
            }

    def _precompute_signal_states(
        self,
        spy_symbol: str = "SPY",
        ma200_window: int = 200,
        nd_lookback: int = 30,
    ) -> None:
        """
        Precompute VIX proxy (HV30 of SPY), market breadth (% above MA200),
        and N-day rolling highs (order blocks) from underlying_price in the cache.
        All self-contained — no external data sources required.
        """
        if "underlying_price" not in self.data.columns:
            return

        price_df = (
            self.data[["date", "underlying", "underlying_price"]]
            .drop_duplicates(subset=["date", "underlying"])
            .sort_values("date")
        )

        # --- HV30 of SPY: annualised 30-day historical volatility ---
        spy_grp = price_df[price_df["underlying"] == spy_symbol].sort_values("date")
        if not spy_grp.empty:
            spy_p = spy_grp.set_index("date")["underlying_price"].astype(float)
            log_ret = spy_p.pct_change().apply(
                lambda r: math.log(1.0 + r) if pd.notna(r) and r > -1 else 0.0
            )
            hv30_series = log_ret.rolling(30).std() * math.sqrt(252)
            for d, v in hv30_series.items():
                if pd.notna(v):
                    self._hv30[str(d)] = float(v)

        # --- Market breadth: % of universe symbols with price > MA200 ---
        all_syms = list(price_df["underlying"].unique())
        # Build {sym: Series(date -> bool above_ma200)}
        above_map: Dict[str, pd.Series] = {}
        for sym, grp in price_df.groupby("underlying"):
            grp = grp.sort_values("date").copy()
            prices = grp.set_index("date")["underlying_price"].astype(float)
            ma200 = prices.rolling(ma200_window, min_periods=1).mean()
            above_map[str(sym)] = (prices > ma200).rename(str(sym))

        all_dates = sorted(price_df["date"].unique())
        for d in all_dates:
            d_str = str(d)
            above = sum(
                1
                for sym in all_syms
                if sym in above_map
                and d_str in above_map[sym].index
                and bool(above_map[sym][d_str])
            )
            total = sum(
                1
                for sym in all_syms
                if sym in above_map and d_str in above_map[sym].index
            )
            self._breadth_pct[d_str] = (above / total * 100.0) if total > 0 else 100.0

        # --- N-day rolling high per symbol (order block resistance) ---
        for sym, grp in price_df.groupby("underlying"):
            grp = grp.sort_values("date").copy()
            prices = grp["underlying_price"].astype(float)
            rolling_high = prices.rolling(nd_lookback, min_periods=1).max()
            self._nd_high[str(sym)] = {
                str(row["date"]): float(rh)
                for (_, row), rh in zip(grp.iterrows(), rolling_high)
            }

        logger.info(
            "[BT] Signal states: HV30 computed for %d days, breadth for %d days, "
            "N-day highs for %d symbols",
            len(self._hv30),
            len(self._breadth_pct),
            len(self._nd_high),
        )

    def _precompute_momentum_ranks(self, lookback_days: int = 90) -> None:
        """
        Precompute per-day momentum rank percentile for each symbol.

        Momentum = (price_today / price_N_days_ago) - 1  (N = lookback_days).
        On each day, symbols are ranked within the universe; each symbol gets
        a percentile score 0–100 where 100 = strongest momentum.

        Results stored in self._momentum_ranks[date_str][symbol] = percentile.
        """
        if "underlying_price" not in self.data.columns:
            return

        price_df = (
            self.data[["date", "underlying", "underlying_price"]]
            .drop_duplicates(subset=["date", "underlying"])
            .sort_values("date")
        )

        # Build {symbol: Series(date -> price)} for fast lookback
        price_series: Dict[str, pd.Series] = {}
        for sym, grp in price_df.groupby("underlying"):
            price_series[str(sym)] = grp.set_index("date")["underlying_price"].astype(
                float
            )

        all_dates = sorted(price_df["date"].unique())
        date_list = [str(d) for d in all_dates]

        for i, d_str in enumerate(date_list):
            # Find the date ~lookback_days ago (by index, not calendar)
            past_idx = max(0, i - lookback_days)
            past_d_str = date_list[past_idx]

            scores: Dict[str, float] = {}
            for sym, series in price_series.items():
                p_now = series.get(d_str)
                p_past = series.get(past_d_str)
                if p_now is not None and p_past is not None and p_past > 0:
                    scores[sym] = float(p_now) / float(p_past) - 1.0

            if not scores:
                self._momentum_ranks[d_str] = {}
                continue

            # Convert raw returns to rank percentiles (0–100)
            sorted_syms = sorted(scores, key=lambda s: scores[s])
            n = len(sorted_syms)
            self._momentum_ranks[d_str] = {
                sym: (rank / (n - 1) * 100.0) if n > 1 else 50.0
                for rank, sym in enumerate(sorted_syms)
            }

        logger.info(
            "[BT] Momentum ranks computed for %d days (%d-day lookback)",
            len(self._momentum_ranks),
            lookback_days,
        )

    def _precompute_iv_rank(self, lookback_days: int = 252) -> None:
        """
        Per-symbol IV rank percentile over a rolling window.
        IV rank 0 = historically cheap options (best time to BUY calls).
        IV rank 100 = historically expensive (avoid buying).
        Uses median implied_volatility across all contracts per (symbol, date).
        """
        if "implied_volatility" not in self.data.columns:
            return

        iv_df = (
            self.data[["date", "underlying", "implied_volatility"]]
            .dropna(subset=["implied_volatility"])
            .groupby(["date", "underlying"])["implied_volatility"]
            .median()
            .reset_index()
            .rename(columns={"implied_volatility": "iv_median"})
            .sort_values("date")
        )

        for sym, grp in iv_df.groupby("underlying"):
            grp = grp.sort_values("date").copy()
            iv_s = grp.set_index("date")["iv_median"].astype(float)
            roll_min = iv_s.rolling(lookback_days, min_periods=20).min()
            roll_max = iv_s.rolling(lookback_days, min_periods=20).max()
            iv_rank = (iv_s - roll_min) / (roll_max - roll_min + 1e-9) * 100.0
            for d, v in iv_rank.items():
                if pd.notna(v):
                    self._iv_ranks.setdefault(str(d), {})[str(sym)] = float(v)

        logger.info(
            "[BT] IV rank computed for %d symbols (%d-day lookback)",
            len(iv_df["underlying"].unique()),
            lookback_days,
        )

    def _build_correlation_frame(
        self, lookback_days: int = 90
    ) -> Dict[str, Dict[str, float]]:
        """
        Build simple correlation matrix from underlying daily returns.
        """
        if "underlying_price" not in self.data.columns:
            return {}
        px = (
            self.data[["date", "underlying", "underlying_price"]]
            .drop_duplicates(subset=["date", "underlying"])
            .pivot(index="date", columns="underlying", values="underlying_price")
            .sort_index()
        )
        if px.empty:
            return {}
        px = px.tail(max(int(lookback_days), 20))
        ret = px.pct_change(fill_method=None).dropna(how="all")
        if ret.empty:
            return {}
        corr = ret.corr().fillna(0.0)
        return {
            str(i): {str(j): float(corr.loc[i, j]) for j in corr.columns}
            for i in corr.index
        }

    def _trend_state(self, symbol: str, day_str: str) -> Optional[Dict[str, bool]]:
        return self._trend_states.get(str(symbol), {}).get(str(day_str))

    def _symbol_is_bullish(self, symbol: str, day_str: str) -> bool:
        """Return True if symbol trend is bullish on the given date."""
        state = self._trend_state(symbol, day_str)
        if state is None:
            # Match live scanner behavior: skip entries when trend state is unknown.
            return False
        return bool(state.get("is_bullish", False))

    def _symbol_is_bearish(self, symbol: str, day_str: str) -> bool:
        state = self._trend_state(symbol, day_str)
        if state is None:
            return False
        return bool(state.get("is_bearish", False))

    def run(self, start_date, end_date) -> Dict:
        """Simulate the strategy over the date range in the cached data."""
        # Normalize date types
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)

        # Read trend-gate config
        require_symbol_trend = self.strategy.get("require_symbol_bullish_trend", False)
        sit_in_cash = self.strategy.get("sit_in_cash_when_bearish", False)
        market_symbol = str(self.strategy.get("market_trend_symbol", "SPY")).upper()
        ema_fast = int(self.strategy.get("trend_ema_fast", 10))
        ema_medium = int(self.strategy.get("trend_ema_medium", 20))
        ema_slow = int(self.strategy.get("trend_ema_slow", 50))

        # New market-signal gates
        vix_gate = bool(self.strategy.get("vix_gate_enabled", False))
        vix_max = float(self.strategy.get("vix_max_threshold", 0.40))
        vix_min = float(self.strategy.get("vix_min_threshold", 0.0))
        breadth_gate = bool(self.strategy.get("breadth_gate_enabled", False))
        breadth_min = float(self.strategy.get("breadth_min_pct", 50.0))
        ob_gate = bool(self.strategy.get("order_block_gate_enabled", False))
        ob_lookback = int(self.strategy.get("order_block_lookback", 30))
        ob_buffer = float(self.strategy.get("order_block_buffer_pct", 0.03))
        sector_gate = bool(self.strategy.get("require_sector_trend", False))

        # Momentum rank filter
        momentum_filter = bool(self.strategy.get("momentum_rank_enabled", False))
        momentum_lookback = int(self.strategy.get("momentum_lookback_days", 90))
        momentum_min_pct = float(self.strategy.get("momentum_min_rank_pct", 50.0))

        # IV rank gate: only enter when options are cheap vs. symbol's own history
        iv_rank_gate = bool(self.strategy.get("iv_rank_gate_enabled", False))
        iv_rank_max = float(self.strategy.get("iv_rank_max_pct", 40.0))
        iv_rank_lookback = int(self.strategy.get("iv_rank_lookback_days", 252))

        # Relative strength gate: only enter when stock >= benchmark over lookback
        rs_gate = bool(self.strategy.get("rs_gate_enabled", False))
        rs_lookback = int(self.strategy.get("rs_lookback_days", 90))
        rs_benchmark = str(self.strategy.get("rs_benchmark_symbol", "SPY")).upper()

        # Plan M exit rules
        exit_on_bearish_cross = bool(self.strategy.get("exit_on_bearish_cross", False))
        profit_target_pct = float(self.strategy.get("profit_target_pct", 0.0))
        stop_loss_pct = float(self.strategy.get("stop_loss_pct", 0.0))
        plan_m_active = (
            exit_on_bearish_cross or profit_target_pct > 0 or stop_loss_pct > 0
        )

        # CSP-specific config
        strategy_type = self.strategy.get("strategy_type", "stock_replacement")
        is_csp = strategy_type == "csp"
        is_wheel = strategy_type == "wheel"
        wheel_call_delta = self.strategy.get("wheel_call_delta", 0.30)
        self.stock_positions = []

        if is_csp:
            csp_collateral_per_contract = 10000
            position_multiplier = int(self.strategy.get("position_size_multiplier", 1))

        if is_csp:
            csp_collateral_per_contract = (
                10000  # Default: strike * 100 for ~10k stock price
            )

        risk_cfg = self.config.get("risk", {})
        heat_cap_pct = float(risk_cfg.get("portfolio_heat_cap_pct", 0.08))
        max_pair_corr = float(risk_cfg.get("max_pair_corr", 0.75))
        max_high_corr_positions = int(risk_cfg.get("max_high_corr_positions", 2))
        kill_lookback = int(risk_cfg.get("kill_switch_lookback_trades", 30))
        kill_floor = float(risk_cfg.get("kill_switch_expectancy_floor_r", -0.15))
        kill_cooldown = int(risk_cfg.get("kill_switch_cooldown_days", 5))
        macro_window_hours = float(risk_cfg.get("macro_no_trade_window_hours", 6))
        target_annual_vol = float(
            self.config.get("execution", {}).get("target_annual_vol", 0.18)
        )
        max_symbol_notional_pct = float(risk_cfg.get("max_symbol_notional_pct", 0.20))
        max_contracts_per_trade = int(self.strategy.get("max_contracts_per_trade", 3))
        macro_events = load_macro_calendar("config/macro_calendar.yaml")
        kill_state: Dict[str, Any] = {}
        corr_frame = self._build_correlation_frame(
            lookback_days=max(momentum_lookback, rs_lookback, 90)
        )
        exec_settings = get_execution_settings(self.config)
        slippage_bps: List[float] = []
        spread_cost_total = 0.0
        slippage_cost_total = 0.0
        fills_attempted = 0
        fills_completed = 0

        # Sector ETF map (covers the default 10-symbol tech-heavy universe).
        # Note: intentionally limited to growth/tech stocks — applying a sector
        # gate to defensive sectors (XLV, XLP, XLF) would be overly restrictive
        # since those sector ETFs spend long periods below trend thresholds.
        _SECTOR_MAP = {
            "AAPL": "XLK",
            "MSFT": "XLK",
            "NVDA": "XLK",
            "AMD": "XLK",
            "AMZN": "XLC",
            "GOOGL": "XLC",
            "META": "XLC",
            "TSLA": "XLY",
        }

        # Precompute trend states if any EMA gate is active
        if require_symbol_trend or sit_in_cash or sector_gate or exit_on_bearish_cross:
            logger.info("[BT] Precomputing EMA trend states...")
            self._precompute_trend_states(ema_fast, ema_medium, ema_slow)

        # Precompute signal states if any new gate is active
        if vix_gate or breadth_gate or ob_gate:
            logger.info("[BT] Precomputing VIX proxy / breadth / order-block states...")
            self._precompute_signal_states(market_symbol, 200, ob_lookback)

        # Precompute momentum ranks if momentum or RS filter is active
        if momentum_filter or rs_gate:
            logger.info("[BT] Precomputing momentum ranks...")
            self._precompute_momentum_ranks(max(momentum_lookback, rs_lookback))

        # Precompute IV ranks if IV rank gate is active
        if iv_rank_gate:
            logger.info("[BT] Precomputing IV ranks...")
            self._precompute_iv_rank(iv_rank_lookback)

        trading_days = sorted(self.data["date"].unique())
        trading_days = [
            d
            for d in trading_days
            if start_date <= date.fromisoformat(str(d)) <= end_date
        ]

        cash = self.initial_capital
        self.equity_curve = [cash]
        rolls_count = 0
        cash_days = 0  # days where market regime blocked new entries
        allocator_block_days = 0
        kill_switch_block_days = 0
        macro_block_days = 0

        for day_str in trading_days:
            today = date.fromisoformat(str(day_str))
            day_data = self.data[self.data["date"] == day_str]

            # 1. Update existing positions with current prices
            self._update_positions(day_data, today)

            # 2. Handle expirations
            expired = self._handle_expirations(today, cash)
            cash += sum(e["proceeds"] for e in expired)

            # 2b. Plan M exits — profit target, stop loss, bearish cross (runs before roll check)
            if plan_m_active:
                plan_m_to_close = []
                for pos in list(self.positions):
                    reason = self._check_plan_m_exits(
                        pos,
                        day_str,
                        exit_on_bearish_cross,
                        profit_target_pct,
                        stop_loss_pct,
                    )
                    if reason:
                        plan_m_to_close.append((pos, reason))

                for pos, reason in plan_m_to_close:
                    self.positions.remove(pos)
                    bid_px = float(
                        pos.get("current_bid", pos.get("current_price", pos["entry_price"]) * 0.99)
                    )
                    ask_px = float(pos.get("current_ask", pos.get("current_price", pos["entry_price"])))
                    spread_abs = max(ask_px - bid_px, 0.01)
                    close_price = adjust_fill_price(
                        price=bid_px,
                        spread_abs=spread_abs,
                        side="sell",
                        tod_bucket="close",
                        settings=exec_settings,
                        data_quality="mixed",
                    )
                    slippage_bps.append(
                        expected_slippage_bps(
                            spread_pct=spread_abs / max(close_price, 1e-6),
                            tod_bucket="close",
                            settings=exec_settings,
                            data_quality="mixed",
                        )
                    )
                    spread_cost_total += spread_abs * pos["qty"] * 100.0
                    slippage_cost_total += max(bid_px - close_price, 0.0) * pos["qty"] * 100.0
                    proceeds = close_price * pos["qty"] * 100
                    cash += proceeds
                    realized = (close_price - pos["entry_price"]) * pos["qty"] * 100
                    pos["close_date"] = today.isoformat()
                    pos["close_price"] = close_price
                    pos["realized_pnl"] = realized
                    pos["exit_reason"] = reason
                    self.closed_trades.append(pos)
                    logger.debug(
                        f"[BT] Plan M exit ({reason}) {pos['contract_symbol']} @ {close_price:.2f} pnl=${realized:.2f}"
                    )

            # CSP profit target exits
            if is_csp:
                csp_to_close = []
                for pos in list(self.positions):
                    reason = self._check_csp_exit(pos, day_str)
                    if reason:
                        csp_to_close.append((pos, reason))

                for pos, reason in csp_to_close:
                    self.positions.remove(pos)
                    ask_px = float(
                        pos.get("current_ask", pos.get("current_price", pos["entry_price"]) * 1.01)
                    )
                    bid_px = float(pos.get("current_bid", max(ask_px - 0.05, 0.01)))
                    spread_abs = max(ask_px - bid_px, 0.01)
                    close_price = adjust_fill_price(
                        price=ask_px,
                        spread_abs=spread_abs,
                        side="buy",
                        tod_bucket="close",
                        settings=exec_settings,
                        data_quality="mixed",
                    )
                    slippage_bps.append(
                        expected_slippage_bps(
                            spread_pct=spread_abs / max(close_price, 1e-6),
                            tod_bucket="close",
                            settings=exec_settings,
                            data_quality="mixed",
                        )
                    )
                    spread_cost_total += spread_abs * pos["qty"] * 100.0
                    slippage_cost_total += max(close_price - ask_px, 0.0) * pos["qty"] * 100.0
                    cost = close_price * pos["qty"] * 100
                    collateral = pos.get("collateral", pos.get("strike", 100) * 100)
                    cash += collateral * pos["qty"]  # return locked collateral
                    cash -= cost  # pay to buy back short put
                    realized = pos.get("entry_credit", pos["entry_price"] * 100) - cost
                    pos["close_date"] = today.isoformat()
                    pos["close_price"] = close_price
                    pos["realized_pnl"] = realized
                    pos["exit_reason"] = reason
                    self.closed_trades.append(pos)
                    logger.debug(
                        f"[BT] CSP exit ({reason}) {pos['contract_symbol']} @ {close_price:.2f} pnl=${realized:.2f}"
                    )

            # Market regime gate - cash mode when market trend template is bearish.
            market_bearish = sit_in_cash and self._symbol_is_bearish(
                market_symbol, day_str
            )

            # VIX proxy gate: block entries when SPY HV30 is out of acceptable range
            hv30_today = self._hv30.get(day_str, 0.0)
            vix_blocked = vix_gate and (
                hv30_today > vix_max or (vix_min > 0.0 and hv30_today < vix_min)
            )

            # Breadth gate: block entries when too few stocks are above their MA200
            breadth_today = self._breadth_pct.get(day_str, 100.0)
            breadth_blocked = breadth_gate and breadth_today < breadth_min

            # Combined market-regime block (any one gate suffices to block entries)
            market_regime_blocked = market_bearish or vix_blocked or breadth_blocked
            macro_blocked = macro_window_block(today, macro_events, macro_window_hours)
            regime_state = compute_regime_state(
                {
                    "is_bullish_trend": self._symbol_is_bullish(market_symbol, day_str),
                    "is_bearish_trend": self._symbol_is_bearish(market_symbol, day_str),
                    "hv30": hv30_today,
                    "breadth_pct": breadth_today,
                    "macro_blocked": macro_blocked,
                    "vix_max_threshold": vix_max,
                    "breadth_min_pct": breadth_min,
                }
            )
            alloc_allowed = strategy_allowed(
                strategy_type, self.strategy.get("variant", ""), regime_state
            )
            alloc_budget = risk_budget_for_regime(regime_state)
            if not alloc_allowed:
                market_regime_blocked = True
                allocator_block_days += 1
            if macro_blocked:
                macro_block_days += 1

            kill_state = kill_switch_state(
                recent_trades=self.closed_trades,
                lookback_trades=kill_lookback,
                expectancy_floor_r=kill_floor,
                cooldown_days=kill_cooldown,
                today=today,
                existing_state=kill_state,
            )
            if kill_state.get("active"):
                market_regime_blocked = True
                kill_switch_block_days += 1

            # 3. Check roll conditions
            to_roll = [p for p in self.positions if self._needs_roll(p, today)]
            for pos in to_roll:
                self.positions.remove(pos)
                if is_csp:
                    # Buy back short put at ask; return locked collateral
                    ask_px = float(
                        pos.get("current_ask", pos.get("current_price", pos["entry_price"]))
                    )
                    bid_px = float(pos.get("current_bid", max(ask_px - 0.05, 0.01)))
                    spread_abs = max(ask_px - bid_px, 0.01)
                    buy_back = adjust_fill_price(
                        price=ask_px,
                        spread_abs=spread_abs,
                        side="buy",
                        tod_bucket="close",
                        settings=exec_settings,
                        data_quality="mixed",
                    )
                    slippage_bps.append(
                        expected_slippage_bps(
                            spread_pct=spread_abs / max(buy_back, 1e-6),
                            tod_bucket="close",
                            settings=exec_settings,
                            data_quality="mixed",
                        )
                    )
                    spread_cost_total += spread_abs * pos["qty"] * 100.0
                    slippage_cost_total += max(buy_back - ask_px, 0.0) * pos["qty"] * 100.0
                    cost_to_buy_back = buy_back * pos["qty"] * 100
                    collateral = pos.get("collateral", pos.get("strike", 100) * 100)
                    cash += collateral * pos["qty"]
                    cash -= cost_to_buy_back
                    realized = (
                        pos.get("entry_credit", pos["entry_price"] * 100)
                        - cost_to_buy_back
                    )
                    close_price = buy_back
                else:
                    # Sell long call at bid
                    bid_px = float(pos.get("current_bid", pos["entry_price"] * 0.99))
                    ask_px = float(pos.get("current_ask", pos.get("current_price", pos["entry_price"])))
                    spread_abs = max(ask_px - bid_px, 0.01)
                    close_price = adjust_fill_price(
                        price=bid_px,
                        spread_abs=spread_abs,
                        side="sell",
                        tod_bucket="close",
                        settings=exec_settings,
                        data_quality="mixed",
                    )
                    slippage_bps.append(
                        expected_slippage_bps(
                            spread_pct=spread_abs / max(close_price, 1e-6),
                            tod_bucket="close",
                            settings=exec_settings,
                            data_quality="mixed",
                        )
                    )
                    spread_cost_total += spread_abs * pos["qty"] * 100.0
                    slippage_cost_total += max(bid_px - close_price, 0.0) * pos["qty"] * 100.0
                    cash += close_price * pos["qty"] * 100
                    realized = (close_price - pos["entry_price"]) * pos["qty"] * 100
                pos["close_date"] = today.isoformat()
                pos["close_price"] = close_price
                pos["realized_pnl"] = realized
                self.closed_trades.append(pos)
                rolls_count += 1
                logger.debug(
                    f"[BT] Rolled {pos['contract_symbol']} @ {close_price:.2f} pnl=${realized:.2f}"
                )

                # Open replacement only if symbol trend is still bullish and market regime allows entries.
                sym_ok = (not require_symbol_trend) or self._symbol_is_bullish(
                    pos["underlying"], day_str
                )
                if sym_ok and not market_regime_blocked:
                    replacement = self._find_replacement(
                        day_data, pos["underlying"], today
                    )
                    if replacement is not None:
                        if is_csp:
                            fills_attempted += 1
                            rep_bid = float(replacement["bid"])
                            rep_ask = float(replacement.get("ask", rep_bid + 0.05))
                            rep_spread = max(rep_ask - rep_bid, 0.01)
                            rep_fill = adjust_fill_price(
                                price=rep_bid,
                                spread_abs=rep_spread,
                                side="sell",
                                tod_bucket="open",
                                settings=exec_settings,
                                data_quality="mixed",
                            )
                            slippage_bps.append(
                                expected_slippage_bps(
                                    spread_pct=rep_spread / max(rep_fill, 1e-6),
                                    tod_bucket="open",
                                    settings=exec_settings,
                                    data_quality="mixed",
                                )
                            )
                            spread_cost_total += rep_spread * pos["qty"] * 100.0
                            slippage_cost_total += max(rep_bid - rep_fill, 0.0) * pos["qty"] * 100.0
                            new_credit = rep_fill * pos["qty"] * 100
                            new_collateral = replacement["strike"] * 100 * pos["qty"]
                            if cash >= new_collateral:
                                fills_completed += 1
                                cash += new_credit
                                cash -= new_collateral
                                self.positions.append(
                                    {
                                        **replacement,
                                        "qty": pos["qty"],
                                        "entry_price": rep_fill,
                                        "entry_credit": new_credit,
                                        "collateral": replacement["strike"] * 100,
                                        "entry_date": today.isoformat(),
                                        "current_price": rep_fill,
                                        "current_ask": rep_ask,
                                    }
                                )
                        else:
                            fills_attempted += 1
                            rep_ask = float(replacement["ask"])
                            rep_bid = float(replacement.get("bid", max(rep_ask - 0.05, 0.01)))
                            rep_spread = max(rep_ask - rep_bid, 0.01)
                            rep_fill = adjust_fill_price(
                                price=rep_ask,
                                spread_abs=rep_spread,
                                side="buy",
                                tod_bucket="open",
                                settings=exec_settings,
                                data_quality="mixed",
                            )
                            slippage_bps.append(
                                expected_slippage_bps(
                                    spread_pct=rep_spread / max(rep_fill, 1e-6),
                                    tod_bucket="open",
                                    settings=exec_settings,
                                    data_quality="mixed",
                                )
                            )
                            spread_cost_total += rep_spread * pos["qty"] * 100.0
                            slippage_cost_total += max(rep_fill - rep_ask, 0.0) * pos["qty"] * 100.0
                            cost = rep_fill * pos["qty"] * 100
                            if cash >= cost:
                                fills_completed += 1
                                cash -= cost
                                self.positions.append(
                                    {
                                        **replacement,
                                        "qty": pos["qty"],
                                        "entry_price": rep_fill,
                                        "entry_date": today.isoformat(),
                                        "current_price": rep_fill,
                                        "current_bid": rep_bid,
                                    }
                                )

            # 4. Market regime gate — sit in cash if any market-wide block is active
            if market_regime_blocked:
                cash_days += 1
                # Still track equity but don't open new positions
                if is_csp:
                    unrealized = self._compute_csp_unrealized(self.positions)
                else:
                    unrealized = sum(
                        (p.get("current_price", p["entry_price"]) - p["entry_price"])
                        * p["qty"]
                        * 100
                        for p in self.positions
                    )
                self.equity_curve.append(cash + unrealized)
                continue

            # 5. Scan for new opportunities
            max_pos = int(
                self.strategy.get("max_positions")
                or self.config.get("execution", {}).get("max_positions", 10)
            )
            max_new_positions_budget = int(
                alloc_budget.get("max_new_positions", max_pos)
            )
            opened_today = 0
            seen_underlyings = {p["underlying"] for p in self.positions}

            for underlying in day_data["underlying"].unique():
                if len(self.positions) >= max_pos:
                    break
                if opened_today >= max_new_positions_budget:
                    break
                if underlying in seen_underlyings:
                    continue

                # Symbol-level trend gate
                if require_symbol_trend and not self._symbol_is_bullish(
                    str(underlying), day_str
                ):
                    continue

                sym_data = day_data[day_data["underlying"] == underlying]
                underlying_price_pre = (
                    sym_data["underlying_price"].iloc[0] if not sym_data.empty else 0.0
                )

                # Order block gate: skip if price is within buffer_pct below N-day high (resistance zone)
                if ob_gate:
                    nd_high = self._nd_high.get(str(underlying), {}).get(day_str, 0.0)
                    if (
                        nd_high > 0
                        and nd_high * (1.0 - ob_buffer)
                        <= underlying_price_pre
                        < nd_high
                    ):
                        continue

                # Sector ETF trend gate: require sector ETF to be bullish
                if sector_gate:
                    sector_etf = _SECTOR_MAP.get(str(underlying).upper())
                    if sector_etf:
                        if not self._symbol_is_bullish(sector_etf, day_str):
                            continue

                # Momentum rank gate: only enter stocks above min rank percentile
                if momentum_filter:
                    rank = self._momentum_ranks.get(day_str, {}).get(str(underlying))
                    if rank is None or rank < momentum_min_pct:
                        continue

                # IV rank gate: only enter when options are cheap vs. symbol's own history
                if iv_rank_gate:
                    iv_rank = self._iv_ranks.get(day_str, {}).get(str(underlying))
                    if iv_rank is None or iv_rank > iv_rank_max:
                        continue

                # Relative strength gate: only enter when stock >= benchmark over lookback
                if rs_gate:
                    sym_ret = self._momentum_ranks.get(day_str, {}).get(str(underlying))
                    spy_ret = self._momentum_ranks.get(day_str, {}).get(rs_benchmark)
                    if sym_ret is None or spy_ret is None or sym_ret < spy_ret:
                        continue

                corr_ok, _corr_info = correlation_gate(
                    candidate_symbol=str(underlying),
                    open_symbols=seen_underlyings,
                    corr_frame=corr_frame,
                    max_corr=max_pair_corr,
                    max_cluster=max_high_corr_positions,
                )
                if not corr_ok:
                    continue

                chain = {
                    row["contract_symbol"]: row.to_dict()
                    for _, row in sym_data.iterrows()
                }
                underlying_price = (
                    sym_data["underlying_price"].iloc[0] if not sym_data.empty else 0
                )

                candidates = filter_candidates(
                    chain, underlying_price, self.config, today
                )
                if not candidates:
                    continue

                best = candidates[0]

                if is_csp:
                    fills_attempted += 1
                    est_vol = max(
                        float(best.get("implied_volatility", hv30_today or 0.20)), 0.05
                    )
                    alloc_dollars = (
                        cash * 0.03 * float(alloc_budget.get("allocation_mult", 1.0))
                    )
                    qty_budget = risk_budget_contracts(
                        allocation_dollars=alloc_dollars,
                        option_price=max(best["bid"], 0.25),
                        min_contracts=1,
                        max_contracts=max_contracts_per_trade,
                    )
                    qty_vol = vol_target_contracts(
                        equity=cash,
                        option_price=max(best["bid"], 0.25),
                        underlying_annual_vol=est_vol,
                        target_annual_vol=target_annual_vol,
                        min_contracts=1,
                        max_contracts=max_contracts_per_trade,
                    )
                    qty = max(1, min(position_multiplier, qty_budget, qty_vol))
                    qty = cap_symbol_notional(
                        contracts=qty,
                        option_price=max(best["strike"], 1.0),
                        equity=cash,
                        max_symbol_notional_pct=max_symbol_notional_pct,
                    )
                    if qty < 1:
                        continue
                    candidate_risk = max(best["strike"] * 100.0 * qty * 0.20, 100.0)
                    heat_ok, _, _ = portfolio_heat_ok(
                        self.positions,
                        candidate_risk=candidate_risk,
                        equity=self.equity_curve[-1],
                        heat_cap_pct=heat_cap_pct
                        * float(alloc_budget.get("heat_mult", 1.0)),
                    )
                    if not heat_ok:
                        continue
                    entry_bid = float(best["bid"])
                    entry_ask = float(best.get("ask", entry_bid + 0.05))
                    entry_spread = max(entry_ask - entry_bid, 0.01)
                    entry_fill = adjust_fill_price(
                        price=entry_bid,
                        spread_abs=entry_spread,
                        side="sell",
                        tod_bucket="open",
                        settings=exec_settings,
                        data_quality="mixed",
                    )
                    slippage_bps.append(
                        expected_slippage_bps(
                            spread_pct=entry_spread / max(entry_fill, 1e-6),
                            tod_bucket="open",
                            settings=exec_settings,
                            data_quality="mixed",
                        )
                    )
                    spread_cost_total += entry_spread * qty * 100.0
                    slippage_cost_total += max(entry_bid - entry_fill, 0.0) * qty * 100.0
                    credit = entry_fill * qty * 100
                    collateral_per_contract = best["strike"] * 100
                    total_collateral = collateral_per_contract * qty
                    if cash >= total_collateral:
                        fills_completed += 1
                        cash += credit
                        cash -= total_collateral
                        self.positions.append(
                            {
                                **best,
                                "qty": qty,
                                "entry_price": entry_fill,
                                "entry_credit": credit,
                                "collateral": collateral_per_contract,
                                "entry_date": today.isoformat(),
                                "current_price": entry_fill,
                                "current_bid": entry_bid,
                                "current_ask": entry_ask,
                                "stop_loss_pct": stop_loss_pct
                                if stop_loss_pct > 0
                                else 0.20,
                            }
                        )
                        seen_underlyings.add(underlying)
                        opened_today += 1
                else:
                    fills_attempted += 1
                    est_vol = max(
                        float(best.get("implied_volatility", hv30_today or 0.20)), 0.05
                    )
                    alloc_dollars = (
                        cash * 0.03 * float(alloc_budget.get("allocation_mult", 1.0))
                    )
                    qty_budget = risk_budget_contracts(
                        allocation_dollars=alloc_dollars,
                        option_price=max(best["ask"], 0.25),
                        min_contracts=1,
                        max_contracts=max_contracts_per_trade,
                    )
                    qty_vol = vol_target_contracts(
                        equity=cash,
                        option_price=max(best["ask"], 0.25),
                        underlying_annual_vol=est_vol,
                        target_annual_vol=target_annual_vol,
                        min_contracts=1,
                        max_contracts=max_contracts_per_trade,
                    )
                    qty = max(1, min(qty_budget, qty_vol))
                    qty = cap_symbol_notional(
                        contracts=qty,
                        option_price=max(best["ask"], 0.25),
                        equity=cash,
                        max_symbol_notional_pct=max_symbol_notional_pct,
                    )
                    if qty < 1:
                        continue
                    eff_stop = (stop_loss_pct / 100.0) if stop_loss_pct > 0 else 0.20
                    candidate_risk = max(best["ask"] * qty * 100.0 * eff_stop, 100.0)
                    heat_ok, _, _ = portfolio_heat_ok(
                        self.positions,
                        candidate_risk=candidate_risk,
                        equity=self.equity_curve[-1],
                        heat_cap_pct=heat_cap_pct
                        * float(alloc_budget.get("heat_mult", 1.0)),
                    )
                    if not heat_ok:
                        continue
                    entry_ask = float(best["ask"])
                    entry_bid = float(best.get("bid", max(entry_ask - 0.05, 0.01)))
                    entry_spread = max(entry_ask - entry_bid, 0.01)
                    entry_fill = adjust_fill_price(
                        price=entry_ask,
                        spread_abs=entry_spread,
                        side="buy",
                        tod_bucket="open",
                        settings=exec_settings,
                        data_quality="mixed",
                    )
                    slippage_bps.append(
                        expected_slippage_bps(
                            spread_pct=entry_spread / max(entry_fill, 1e-6),
                            tod_bucket="open",
                            settings=exec_settings,
                            data_quality="mixed",
                        )
                    )
                    spread_cost_total += entry_spread * qty * 100.0
                    slippage_cost_total += max(entry_fill - entry_ask, 0.0) * qty * 100.0
                    cost = entry_fill * qty * 100
                    if cash >= cost:
                        fills_completed += 1
                        cash -= cost
                        self.positions.append(
                            {
                                **best,
                                "qty": qty,
                                "entry_price": entry_fill,
                                "entry_date": today.isoformat(),
                                "current_price": entry_fill,
                                "current_bid": entry_bid,
                                "current_ask": entry_ask,
                                "stop_loss_pct": stop_loss_pct
                                if stop_loss_pct > 0
                                else 0.20,
                            }
                        )
                        seen_underlyings.add(underlying)
                        opened_today += 1

            # 5. Equity snapshot
            if is_csp:
                unrealized = self._compute_csp_unrealized(self.positions)
            else:
                unrealized = sum(
                    (p.get("current_price", p["entry_price"]) - p["entry_price"])
                    * p["qty"]
                    * 100
                    for p in self.positions
                )
            self.equity_curve.append(cash + unrealized)

        # Close any remaining open positions at last known price
        for pos in self.positions:
            if is_csp:
                ask_px = float(pos.get("current_ask", pos.get("current_price", pos["entry_price"])))
                bid_px = float(pos.get("current_bid", max(ask_px - 0.05, 0.01)))
                spread_abs = max(ask_px - bid_px, 0.01)
                close_price = adjust_fill_price(
                    price=ask_px,
                    spread_abs=spread_abs,
                    side="buy",
                    tod_bucket="close",
                    settings=exec_settings,
                    data_quality="mixed",
                )
                slippage_bps.append(
                    expected_slippage_bps(
                        spread_pct=spread_abs / max(close_price, 1e-6),
                        tod_bucket="close",
                        settings=exec_settings,
                        data_quality="mixed",
                    )
                )
                spread_cost_total += spread_abs * pos["qty"] * 100.0
                slippage_cost_total += max(close_price - ask_px, 0.0) * pos["qty"] * 100.0
                collateral = pos.get("collateral", pos.get("strike", 100) * 100)
                cost = close_price * pos["qty"] * 100
                realized = pos.get("entry_credit", pos["entry_price"] * 100) - cost
                cash += collateral * pos["qty"]
                cash -= cost
            else:
                bid_px = float(pos.get("current_bid", pos.get("current_price", pos["entry_price"])))
                ask_px = float(pos.get("current_ask", pos.get("current_price", pos["entry_price"])))
                spread_abs = max(ask_px - bid_px, 0.01)
                close_price = adjust_fill_price(
                    price=bid_px,
                    spread_abs=spread_abs,
                    side="sell",
                    tod_bucket="close",
                    settings=exec_settings,
                    data_quality="mixed",
                )
                slippage_bps.append(
                    expected_slippage_bps(
                        spread_pct=spread_abs / max(close_price, 1e-6),
                        tod_bucket="close",
                        settings=exec_settings,
                        data_quality="mixed",
                    )
                )
                spread_cost_total += spread_abs * pos["qty"] * 100.0
                slippage_cost_total += max(bid_px - close_price, 0.0) * pos["qty"] * 100.0
                realized = (close_price - pos["entry_price"]) * pos["qty"] * 100
            pos["close_date"] = str(end_date)
            pos["close_price"] = close_price
            pos["realized_pnl"] = realized
            self.closed_trades.append(pos)

        metrics = compute_metrics(self.closed_trades, self.equity_curve)
        metrics["rolls_executed"] = rolls_count
        metrics["trading_days"] = len(trading_days)
        metrics["cash_days"] = cash_days
        metrics["allocator_block_days"] = allocator_block_days
        metrics["kill_switch_block_days"] = kill_switch_block_days
        metrics["macro_block_days"] = macro_block_days
        metrics["kill_switch_active"] = bool(kill_state.get("active"))
        metrics["kill_switch_expectancy_r"] = float(kill_state.get("expectancy_r", 0.0))
        metrics.update(
            summarize_execution_realism(
                slippage_bps=slippage_bps,
                spread_cost_total=spread_cost_total,
                slippage_cost_total=slippage_cost_total,
                filled=fills_completed,
                partial=0,
                attempted=fills_attempted,
            )
        )
        return metrics

    def _update_positions(self, day_data: pd.DataFrame, today: date) -> None:
        """
        Update current price, bid, delta for each open position.

        For synthetic data: the original contract symbol won't appear in later days
        (because strikes are generated fresh each day as % of spot price). So we
        reprice the original strike using BSM with today's underlying price and
        volatility, which correctly tracks the position's fair value over time.
        """
        for pos in self.positions:
            sym = pos["contract_symbol"]
            # Try exact symbol match (live data or same-day synthetic)
            match = day_data[day_data["contract_symbol"] == sym]
            if not match.empty:
                row = match.iloc[0]
                pos["current_price"] = float(row["ask"])
                pos["current_bid"] = float(row["bid"])
                pos["current_delta"] = float(row["delta"])
                pos["current_underlying_price"] = float(row["underlying_price"])
                continue

            # Synthetic data fallback: reprice the original strike with BSM
            sym_data = day_data[day_data["underlying"] == pos["underlying"]]
            if sym_data.empty:
                continue

            S = float(sym_data["underlying_price"].iloc[0])
            sigma = float(sym_data["implied_volatility"].mean())
            K = float(pos["strike"])

            try:
                exp = date.fromisoformat(str(pos["expiration_date"]))
                T = max((exp - today).days / 365.0, 0.0)
            except (ValueError, TypeError):
                continue

            is_put = pos.get("option_type", "call").lower() == "put"
            if is_put:
                mid, delta = _bsm_put(S, K, T, sigma)
            else:
                mid, delta = _bsm_call(S, K, T, sigma)
            spread = max(mid * 0.01, 0.01)
            pos["current_price"] = round(mid + spread, 2)
            pos["current_bid"] = round(max(mid - spread, 0.01), 2)
            pos["current_ask"] = round(mid + spread, 2)
            pos["current_delta"] = round(delta, 4)
            pos["current_underlying_price"] = S

    def _handle_expirations(self, today: date, cash: float) -> List[Dict]:
        expired = []
        remaining = []
        for pos in self.positions:
            try:
                exp = date.fromisoformat(str(pos["expiration_date"]))
            except (ValueError, TypeError):
                remaining.append(pos)
                continue

            if exp < today:
                S = pos.get("current_underlying_price") or pos.get("underlying_price")
                if not S:
                    logger.warning(
                        f"[BT] No underlying price for {pos['contract_symbol']} at expiration, skipping"
                    )
                    remaining.append(pos)
                    continue

                is_csp_pos = pos.get("strategy_type") == "csp" or "entry_credit" in pos

                if is_csp_pos:
                    collateral = pos.get("collateral", pos.get("strike", 100) * 100)
                    entry_credit = pos.get("entry_credit", pos["entry_price"] * 100)
                    intrinsic = compute_intrinsic_value("put", S, pos["strike"])
                    cost_to_close = intrinsic * pos["qty"] * 100
                    realized = entry_credit - cost_to_close
                    pos["close_date"] = today.isoformat()
                    pos["close_price"] = intrinsic
                    pos["realized_pnl"] = realized
                    pos["exit_reason"] = "expired"
                    self.closed_trades.append(pos)
                    expired.append(
                        {
                            # return locked collateral, pay to close intrinsic
                            "proceeds": collateral * pos["qty"] - cost_to_close,
                            "realized_pnl": realized,
                        }
                    )
                    logger.debug(
                        f"[BT] CSP Expired {pos['contract_symbol']} S={S:.2f} strike={pos['strike']} intrinsic={intrinsic:.2f} pnl=${realized:.2f}"
                    )
                else:
                    intrinsic = compute_intrinsic_value(
                        pos.get("option_type", "call"), S, pos["strike"]
                    )
                    proceeds = intrinsic * pos["qty"] * 100
                    realized = (intrinsic - pos["entry_price"]) * pos["qty"] * 100
                    pos["close_date"] = today.isoformat()
                    pos["close_price"] = intrinsic
                    pos["realized_pnl"] = realized
                    self.closed_trades.append(pos)
                    expired.append({"proceeds": proceeds, "realized_pnl": realized})
                    logger.debug(
                        f"[BT] Expired {pos['contract_symbol']} intrinsic={intrinsic:.2f}"
                    )
            else:
                remaining.append(pos)

        self.positions = remaining
        return expired

    def _check_plan_m_exits(
        self,
        pos: dict,
        day_str: str,
        exit_on_bearish_cross: bool,
        profit_target_pct: float,
        stop_loss_pct: float,
    ) -> Optional[str]:
        """Return exit reason if a Plan M rule fires, else None.

        Plan M rules (from Chris Uhl):
        - Profit target: +30% gain on the option contract
        - Stop loss:     -20% loss on the option contract
        - Bearish cross: underlying's 10 EMA crosses below 20 EMA
        """
        entry = float(pos.get("entry_price", 0))
        if entry <= 0:
            return None
        current = float(pos.get("current_price", entry))
        pnl_pct = (current - entry) / entry * 100.0

        if profit_target_pct > 0 and pnl_pct >= profit_target_pct:
            return "profit_target"
        if stop_loss_pct > 0 and pnl_pct <= -stop_loss_pct:
            return "stop_loss"
        if exit_on_bearish_cross and self._symbol_is_bearish(
            str(pos.get("underlying", "")), day_str
        ):
            return "bearish_cross"
        return None

    def _needs_roll(self, pos: Dict, today: date) -> bool:
        strategy_type = self.strategy.get("strategy_type", "stock_replacement")

        if strategy_type == "csp":
            return self._needs_csp_roll(pos, today)
        else:
            return self._needs_stock_replacement_roll(pos, today)

    def _needs_stock_replacement_roll(self, pos: Dict, today: date) -> bool:
        min_delta = self.strategy.get("min_delta", 0.65)
        current_delta = (
            pos.get("current_delta") or pos.get("entry_delta") or pos.get("delta")
        )
        if current_delta is None:
            logger.warning(
                f"[BT] No delta found for {pos['contract_symbol']}, skipping roll check"
            )
            return False

        try:
            exp = date.fromisoformat(str(pos["expiration_date"]))
            dte = (exp - today).days
            if dte <= 7:
                return True
        except (ValueError, TypeError):
            pass

        return current_delta < min_delta

    def _needs_csp_roll(self, pos: Dict, today: date) -> bool:
        roll_trigger = self.strategy.get("roll_trigger", "dte")

        if roll_trigger == "delta":
            roll_delta_threshold = self.strategy.get("roll_delta_threshold", -0.10)
            current_delta = (
                pos.get("current_delta") or pos.get("entry_delta") or pos.get("delta")
            )
            if current_delta is None:
                logger.warning(
                    f"[BT] No delta found for {pos['contract_symbol']}, skipping roll check"
                )
                return False
            return current_delta > roll_delta_threshold
        else:
            roll_dte_threshold = self.strategy.get("roll_dte_threshold", 7)
            try:
                exp = date.fromisoformat(str(pos["expiration_date"]))
                dte = (exp - today).days
                return dte <= roll_dte_threshold
            except (ValueError, TypeError):
                return False

    def _check_csp_exit(self, pos: Dict, day_str: str) -> Optional[str]:
        exit_strategy = self.strategy.get("exit_strategy", "ride_to_expiry")

        if exit_strategy == "profit_target":
            profit_target_ratio = self.strategy.get("profit_target_ratio", 0.50)
            entry_credit = pos.get("entry_credit", pos.get("entry_price", 0) * 100)
            current_price = pos.get("current_price", pos.get("entry_price", 0))
            current_credit = current_price * 100
            pnl_pct = (
                (entry_credit - current_credit) / entry_credit
                if entry_credit > 0
                else 0
            )
            if pnl_pct >= profit_target_ratio:
                return "profit_target"

        return None

    def _compute_csp_unrealized(self, positions: List[Dict]) -> float:
        """
        CSP equity accounting:
          At entry: cash -= collateral, cash += credit.
          So cash is reduced by (collateral - credit). The locked collateral
          is still ours but is NOT in cash. We must add it back to unrealized
          so that equity = cash + unrealized reflects true portfolio value.
          Net per position: collateral * qty + (entry_credit - current_credit) * qty
        """
        unrealized = 0.0
        for p in positions:
            entry_credit = p.get("entry_credit", p["entry_price"] * 100)
            current_price = p.get("current_price", p["entry_price"])
            current_credit = current_price * 100
            collateral = p.get("collateral", p.get("strike", 100) * 100)
            qty = p.get("qty", 1)
            unrealized += collateral * qty + (entry_credit - current_credit) * qty
        return unrealized

    def _find_replacement(
        self, day_data: pd.DataFrame, underlying: str, today: date
    ) -> Optional[Dict]:
        sym_data = day_data[day_data["underlying"] == underlying]
        if sym_data.empty:
            return None

        chain = {
            row["contract_symbol"]: row.to_dict() for _, row in sym_data.iterrows()
        }
        underlying_price = sym_data["underlying_price"].iloc[0]
        candidates = filter_candidates(chain, underlying_price, self.config, today)
        return candidates[0] if candidates else None
