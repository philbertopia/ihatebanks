"""
Synthetic options data generator using yfinance + Black-Scholes.

Downloads historical stock prices and computes what option prices/Greeks
would have been on each trading day. Saves daily Parquet snapshots to
data/cache/ in the same format as BacktestDataCollector.collect_and_cache().
"""

import math
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm

from ovtlyr.backtester.spx_expiry import has_same_day_expiry
from ovtlyr.utils.time_utils import (
    get_monthly_expirations,
    get_weekly_expirations,
    days_to_expiration,
    is_market_day,
)
from ovtlyr.utils.math_utils import (
    compute_intrinsic_value,
    compute_extrinsic_value,
    compute_extrinsic_pct,
    compute_spread_pct,
)

logger = logging.getLogger(__name__)

RISK_FREE_RATE = 0.05  # 5% annual, approximate
SPREAD_FACTOR = 0.01  # 1% of option price for synthetic bid/ask spread
MIN_DELTA_CALL = 0.60
MAX_DELTA_CALL = 0.95
MIN_DELTA_PUT = -0.70   # expanded to include ITM puts (delta -0.55 to -0.70)
MAX_DELTA_PUT = -0.10
# Strike grid: percentage of spot price, covering deep ITM calls
STRIKE_PCTS_CALL = [
    i / 100 for i in range(65, 100, 1)
]  # 65% to 99% of spot (for calls)
# Strike grid for OTM calls: above spot — needed for call credit spreads (CCS)
STRIKE_PCTS_OTM_CALL = [i / 100 for i in range(101, 116, 1)]  # 101% to 115% of spot
MIN_DELTA_OTM_CALL = 0.10  # OTM calls have lower delta (10-45%)
MAX_DELTA_OTM_CALL = 0.45
# Strike grid for puts: OTM puts (< spot) for CSP + ITM puts (> spot) for directional buys
STRIKE_PCTS_PUT = [i / 100 for i in range(85, 120, 1)]  # 85% to 119% of spot
# Finer grid for 0DTE puts: 85% to 99.5% of spot (short + long put for spread)
STRIKE_PCTS_PUT_0DTE = [i / 1000.0 for i in range(850, 1000, 5)]  # 0.85, 0.855, ..., 0.995
# 0DTE put delta range: short put ~5–25 delta (e.g. -0.25 to -0.05); long put deeper OTM (delta near 0)
# Include up to 0 so the long leg of the spread is in the chain
MIN_DELTA_PUT_0DTE = -0.70
MAX_DELTA_PUT_0DTE = 0.0
# Time to expiry for same-day options (hours to 4pm / 24 / 365)
HOURS_TO_CLOSE_0DTE = 6.0
T_0DTE_YEARS = (HOURS_TO_CLOSE_0DTE / 24.0) / 365.0


def _bsm_call(S: float, K: float, T: float, r: float, sigma: float) -> Dict[str, float]:
    """
    Black-Scholes-Merton for a European call option.

    Returns dict with: price, delta, gamma, theta, vega
    Returns None if inputs are invalid (T <= 0, sigma <= 0).
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return None

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    delta = norm.cdf(d1)
    gamma = norm.pdf(d1) / (S * sigma * sqrt_T)
    theta = (
        -S * norm.pdf(d1) * sigma / (2 * sqrt_T)
        - r * K * math.exp(-r * T) * norm.cdf(d2)
    ) / 365
    vega = S * norm.pdf(d1) * sqrt_T / 100  # per 1% move in IV

    return {
        "price": max(price, 0.01),
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
    }


def _bsm_put(S: float, K: float, T: float, r: float, sigma: float) -> Dict[str, float]:
    """
    Black-Scholes-Merton for a European put option.

    Returns dict with: price, delta, gamma, theta, vega
    Returns None if inputs are invalid (T <= 0, sigma <= 0).
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return None

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    delta = norm.cdf(d1) - 1  # put delta is negative
    gamma = norm.pdf(d1) / (S * sigma * sqrt_T)
    theta = (
        -S * norm.pdf(d1) * sigma / (2 * sqrt_T)
        + r * K * math.exp(-r * T) * norm.cdf(-d2)
    ) / 365
    vega = S * norm.pdf(d1) * sqrt_T / 100  # per 1% move in IV

    return {
        "price": max(price, 0.01),
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
    }


def _occ_symbol(
    underlying: str, expiry: date, strike: float, option_type: str = "call"
) -> str:
    """Generate OCC-format option symbol for a call or put."""
    strike_int = int(round(strike * 1000))
    if option_type.lower() == "put":
        return f"{underlying}{expiry.strftime('%y%m%d')}P{strike_int:08d}"
    return f"{underlying}{expiry.strftime('%y%m%d')}C{strike_int:08d}"


class SyntheticGenerator:
    """
    Generates synthetic historical options chain data using yfinance prices
    and Black-Scholes pricing. Saves one Parquet file per trading day.
    """

    def __init__(self, config: dict):
        self.config = config
        # Always generate the full DTE range so any strategy can filter at query time.
        # Short-DTE strategies (8-60) and LEAPS (180-400) share the same cache files.
        self.min_dte = 8
        self.max_dte = 400
        self.cache_dir = Path(config.get("database", {}).get("cache_dir", "data/cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, symbols: List[str], start: date, end: date) -> int:
        """
        Generate synthetic option chain snapshots for all symbols and trading days
        between start and end (inclusive). Saves one Parquet per day.

        Returns the number of trading days processed.
        """
        logger.info(f"Downloading price history for {symbols} from {start} to {end}")

        # Download all symbols at once; add buffer for volatility computation
        buffer_start = start - timedelta(days=60)
        price_data = self._download_prices(symbols, buffer_start, end)

        if price_data.empty:
            logger.error("No price data downloaded from yfinance")
            return 0

        days_generated = 0
        current = start
        while current <= end:
            if not is_market_day(current):
                current += timedelta(days=1)
                continue

            rows = []
            for symbol in symbols:
                if symbol not in price_data.columns:
                    continue
                symbol_rows = self._generate_day(symbol, current, price_data[symbol])
                rows.extend(symbol_rows)

            if rows:
                df = pd.DataFrame(rows)
                out_path = self.cache_dir / f"{current.isoformat()}.parquet"
                df.to_parquet(out_path, index=False)
                days_generated += 1
                if days_generated % 50 == 0:
                    logger.info(
                        f"Generated {days_generated} days... (current: {current})"
                    )

            current += timedelta(days=1)

        logger.info(
            f"Synthetic data generation complete: {days_generated} trading days"
        )
        return days_generated

    def _download_prices(
        self, symbols: List[str], start: date, end: date
    ) -> pd.DataFrame:
        """Download adjusted close prices for all symbols. Returns wide DataFrame indexed by date."""
        try:
            raw = yf.download(
                symbols,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                auto_adjust=True,
                progress=False,
            )
            if raw.empty:
                return pd.DataFrame()

            # Extract Close prices; handle single vs multi-ticker shape
            if isinstance(raw.columns, pd.MultiIndex):
                prices = raw["Close"]
            else:
                # Single symbol
                prices = raw[["Close"]].rename(columns={"Close": symbols[0]})

            prices.index = pd.to_datetime(prices.index).date
            return prices
        except Exception as e:
            logger.error(f"yfinance download error: {e}")
            return pd.DataFrame()

    def _rolling_volatility(
        self, price_series: pd.Series, today: date, window: int = 30
    ) -> float:
        """
        Compute 30-day rolling historical volatility (annualized) as of `today`.
        Falls back to whole-series HV if window is too short, then 0.30 as last resort.
        """
        past = price_series[price_series.index <= today].tail(window + 1)
        if len(past) < 5:
            # Use all available history instead
            all_past = price_series[price_series.index <= today]
            if len(all_past) >= 2:
                log_returns = np.log(all_past.values[1:] / all_past.values[:-1])
                return float(np.std(log_returns) * math.sqrt(252))
            return 0.30  # last-resort fallback (30% IV, regime-neutral)

        log_returns = np.log(past.values[1:] / past.values[:-1])
        daily_vol = np.std(log_returns)
        return daily_vol * math.sqrt(252)  # annualize

    def _generate_day(
        self, symbol: str, today: date, price_series: pd.Series
    ) -> List[Dict[str, Any]]:
        """
        Generate option chain rows for one symbol on one trading day.
        Returns list of row dicts matching the Parquet schema.
        """
        # Get today's stock price
        if today not in price_series.index:
            return []
        S = float(price_series[today])
        if S <= 0 or math.isnan(S):
            return []

        sigma = self._rolling_volatility(price_series, today)
        # Weekly expirations for short-DTE range (swing strategies need 7-30 DTE)
        short_expiries = get_weekly_expirations(min_dte=7, max_dte=30, today=today)
        # Monthly expirations for longer DTE (better liquidity model for longer holds)
        long_expiries = get_monthly_expirations(
            min_dte=30, max_dte=self.max_dte, today=today
        )
        expirations = sorted(set(short_expiries + long_expiries))
        # Same-day (0 DTE) expiry on SPXW expiry days for SPX 0DTE backtest
        if has_same_day_expiry(today):
            expirations = sorted(set(expirations + [today]))

        rows = []

        # Generate CALL options
        for expiry in expirations:
            dte = days_to_expiration(expiry, today)
            T = T_0DTE_YEARS if dte == 0 else (dte / 365.0)
            if T <= 0:
                continue

            for strike_pct in STRIKE_PCTS_CALL:
                K = round(S * strike_pct, 2)
                bsm = _bsm_call(S, K, T, RISK_FREE_RATE, sigma)
                if bsm is None:
                    continue

                delta = bsm["delta"]
                if not (MIN_DELTA_CALL <= delta <= MAX_DELTA_CALL):
                    continue

                mid = bsm["price"]
                half_spread = max(mid * SPREAD_FACTOR, 0.01)
                ask = round(mid + half_spread, 2)
                bid = round(mid - half_spread, 2)
                bid = max(bid, 0.01)

                intrinsic = compute_intrinsic_value("call", S, K)
                extrinsic = compute_extrinsic_value(ask, intrinsic)
                extrinsic_pct = compute_extrinsic_pct(extrinsic, ask)
                spread_pct = compute_spread_pct(bid, ask)

                rows.append(
                    {
                        "date": today.isoformat(),
                        "underlying": symbol,
                        "contract_symbol": _occ_symbol(symbol, expiry, K, "call"),
                        "option_type": "call",
                        "strike": K,
                        "expiration_date": expiry.isoformat(),
                        "dte": dte,
                        "bid": bid,
                        "ask": ask,
                        "delta": round(delta, 4),
                        "gamma": round(bsm["gamma"], 6),
                        "theta": round(bsm["theta"], 4),
                        "vega": round(bsm["vega"], 4),
                        "implied_volatility": round(sigma, 4),
                        "open_interest": None,
                        "underlying_price": S,
                        "intrinsic_value": round(intrinsic, 2),
                        "extrinsic_value": round(extrinsic, 2),
                        "extrinsic_pct": round(extrinsic_pct, 4),
                        "spread_pct": round(spread_pct, 4),
                    }
                )

        # Generate OTM CALL options (for call credit spreads — CCS strategy)
        for expiry in expirations:
            dte = days_to_expiration(expiry, today)
            T = T_0DTE_YEARS if dte == 0 else (dte / 365.0)
            if T <= 0:
                continue

            for strike_pct in STRIKE_PCTS_OTM_CALL:
                K = round(S * strike_pct, 2)
                bsm = _bsm_call(S, K, T, RISK_FREE_RATE, sigma)
                if bsm is None:
                    continue

                delta = bsm["delta"]
                if not (MIN_DELTA_OTM_CALL <= delta <= MAX_DELTA_OTM_CALL):
                    continue

                mid = bsm["price"]
                half_spread = max(mid * SPREAD_FACTOR, 0.01)
                ask = round(mid + half_spread, 2)
                bid = round(mid - half_spread, 2)
                bid = max(bid, 0.01)

                intrinsic = compute_intrinsic_value("call", S, K)
                extrinsic = compute_extrinsic_value(ask, intrinsic)
                extrinsic_pct = compute_extrinsic_pct(extrinsic, ask)
                spread_pct = compute_spread_pct(bid, ask)

                rows.append(
                    {
                        "date": today.isoformat(),
                        "underlying": symbol,
                        "contract_symbol": _occ_symbol(symbol, expiry, K, "call"),
                        "option_type": "call",
                        "strike": K,
                        "expiration_date": expiry.isoformat(),
                        "dte": dte,
                        "bid": bid,
                        "ask": ask,
                        "delta": round(delta, 4),
                        "gamma": round(bsm["gamma"], 6),
                        "theta": round(bsm["theta"], 4),
                        "vega": round(bsm["vega"], 4),
                        "implied_volatility": round(sigma, 4),
                        "open_interest": None,
                        "underlying_price": S,
                        "intrinsic_value": round(intrinsic, 2),
                        "extrinsic_value": round(extrinsic, 2),
                        "extrinsic_pct": round(extrinsic_pct, 4),
                        "spread_pct": round(spread_pct, 4),
                    }
                )

        # Generate PUT options (for CSP strategy; 0DTE uses finer grid + 5-25 delta for SPX 0DTE engine)
        for expiry in expirations:
            dte = days_to_expiration(expiry, today)
            T = T_0DTE_YEARS if dte == 0 else (dte / 365.0)
            if T <= 0:
                continue
            is_0dte = dte == 0
            strike_pcts_put = STRIKE_PCTS_PUT_0DTE if is_0dte else STRIKE_PCTS_PUT
            min_delta_put = MIN_DELTA_PUT_0DTE if is_0dte else MIN_DELTA_PUT
            max_delta_put = MAX_DELTA_PUT_0DTE if is_0dte else MAX_DELTA_PUT

            for strike_pct in strike_pcts_put:
                K = round(S * strike_pct, 2)
                bsm = _bsm_put(S, K, T, RISK_FREE_RATE, sigma)
                if bsm is None:
                    continue

                delta = bsm["delta"]
                if not (min_delta_put <= delta <= max_delta_put):
                    continue

                mid = bsm["price"]
                spread_factor = SPREAD_FACTOR * 1.5 if is_0dte else SPREAD_FACTOR
                half_spread = max(mid * spread_factor, 0.01)
                ask = round(mid + half_spread, 2)
                bid = round(mid - half_spread, 2)
                bid = max(bid, 0.01)

                intrinsic = compute_intrinsic_value("put", S, K)
                extrinsic = compute_extrinsic_value(ask, intrinsic)
                extrinsic_pct = compute_extrinsic_pct(extrinsic, ask)
                spread_pct = compute_spread_pct(bid, ask)

                rows.append(
                    {
                        "date": today.isoformat(),
                        "underlying": symbol,
                        "contract_symbol": _occ_symbol(symbol, expiry, K, "put"),
                        "option_type": "put",
                        "strike": K,
                        "expiration_date": expiry.isoformat(),
                        "dte": dte,
                        "bid": bid,
                        "ask": ask,
                        "delta": round(delta, 4),
                        "gamma": round(bsm["gamma"], 6),
                        "theta": round(bsm["theta"], 4),
                        "vega": round(bsm["vega"], 4),
                        "implied_volatility": round(sigma, 4),
                        "open_interest": None,
                        "underlying_price": S,
                        "intrinsic_value": round(intrinsic, 2),
                        "extrinsic_value": round(extrinsic, 2),
                        "extrinsic_pct": round(extrinsic_pct, 4),
                        "spread_pct": round(spread_pct, 4),
                    }
                )

        return rows
