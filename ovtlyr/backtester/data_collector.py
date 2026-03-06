"""
Collect and cache option chain snapshots for backtesting.

Alpaca only provides ~7 days of options history, so we build our own
dataset by running `python main.py collect` each trading day.
Each run saves a Parquet file to data/cache/.
"""

import logging
import os
from datetime import date
from typing import List

import pandas as pd

from ovtlyr.api.client import AlpacaClients
from ovtlyr.api.options_data import fetch_option_chain, fetch_underlying_price, snapshot_to_dict
from ovtlyr.scanner.expiration import get_target_expirations
from ovtlyr.utils.math_utils import compute_intrinsic_value, compute_extrinsic_value, compute_extrinsic_pct, compute_spread_pct
from ovtlyr.utils.time_utils import days_to_expiration

logger = logging.getLogger(__name__)

CACHE_DIR = "data/cache"


class BacktestDataCollector:
    def __init__(self, clients: AlpacaClients, config: dict):
        self.clients = clients
        self.config = config
        self.strategy = config.get("strategy", {})
        self.feed = config.get("alpaca", {}).get("feed", "indicative")

    def collect_and_cache(self, symbols: List[str], today: date = None) -> int:
        """
        Fetch current option chain data for all symbols and save to Parquet.
        Returns number of contracts cached.
        """
        if today is None:
            today = date.today()

        os.makedirs(CACHE_DIR, exist_ok=True)

        min_dte = self.strategy.get("min_dte", 8)
        max_dte = self.strategy.get("max_dte", 60)
        option_type = self.strategy.get("option_type", "call")

        all_rows = []

        for symbol in symbols:
            underlying_price = fetch_underlying_price(self.clients.stock_data, symbol)
            if not underlying_price:
                logger.warning(f"Skipping {symbol}: cannot fetch price")
                continue

            expirations = get_target_expirations(min_dte, max_dte, today, prefer_monthly=True)

            for exp_date in expirations:
                chain = fetch_option_chain(
                    client=self.clients.options_data,
                    symbol=symbol,
                    expiration_date_gte=exp_date,
                    expiration_date_lte=exp_date,
                    option_type=option_type,
                    feed=self.feed,
                )

                for contract_sym, snap in chain.items():
                    d = snapshot_to_dict(contract_sym, snap)
                    ask = d.get("ask", 0)
                    strike = d.get("strike", 0)
                    bid = d.get("bid", 0)

                    if ask <= 0:
                        continue

                    intrinsic = compute_intrinsic_value(option_type, underlying_price, strike)
                    extrinsic = compute_extrinsic_value(ask, intrinsic)

                    row = {
                        "date": today.isoformat(),
                        "underlying": symbol,
                        "contract_symbol": contract_sym,
                        "option_type": option_type,
                        "strike": strike,
                        "expiration_date": d.get("expiration_date", ""),
                        "dte": days_to_expiration(exp_date, today),
                        "bid": bid,
                        "ask": ask,
                        "delta": d.get("delta", 0),
                        "gamma": d.get("gamma", 0),
                        "theta": d.get("theta", 0),
                        "vega": d.get("vega", 0),
                        "implied_volatility": d.get("implied_volatility", 0),
                        "open_interest": d.get("open_interest"),  # None if not available (indicative feed)
                        "underlying_price": underlying_price,
                        "intrinsic_value": intrinsic,
                        "extrinsic_value": extrinsic,
                        "extrinsic_pct": compute_extrinsic_pct(extrinsic, ask),
                        "spread_pct": compute_spread_pct(bid, ask),
                    }
                    all_rows.append(row)

        if not all_rows:
            logger.warning("No data collected")
            return 0

        df = pd.DataFrame(all_rows)
        out_path = os.path.join(CACHE_DIR, f"{today.isoformat()}.parquet")
        df.to_parquet(out_path, index=False)
        logger.info(f"Cached {len(df)} contracts to {out_path}")
        return len(df)

    def load_cached_data(self) -> pd.DataFrame:
        """Load all Parquet files from the cache directory into a single DataFrame."""
        if not os.path.exists(CACHE_DIR):
            return pd.DataFrame()

        files = sorted(
            [f for f in os.listdir(CACHE_DIR) if f.endswith(".parquet")]
        )
        if not files:
            return pd.DataFrame()

        dfs = []
        for fname in files:
            path = os.path.join(CACHE_DIR, fname)
            try:
                dfs.append(pd.read_parquet(path))
            except Exception as e:
                logger.warning(f"Could not read {path}: {e}")

        if not dfs:
            return pd.DataFrame()

        combined = pd.concat(dfs, ignore_index=True)
        combined.sort_values("date", inplace=True)
        logger.info(f"Loaded {len(combined)} rows from {len(dfs)} cache files")
        return combined

    def generate_synthetic_data(self, symbols: list, start: date, end: date) -> int:
        """
        Generate synthetic historical options data using yfinance + Black-Scholes.
        Saves one Parquet per trading day to data/cache/.
        Returns number of days generated.
        """
        from ovtlyr.backtester.synthetic_generator import SyntheticGenerator
        gen = SyntheticGenerator(self.config)
        return gen.generate(symbols, start, end)

    def load_external_data(self, csv_path: str) -> pd.DataFrame:
        """
        Load externally-sourced options data (e.g. from Databento or CBOE DataShop).
        Expected columns:
          date, underlying, contract_symbol, option_type, strike, expiration_date,
          bid, ask, delta, gamma, theta, vega, open_interest, underlying_price
        """
        df = pd.read_csv(csv_path, parse_dates=["date"])
        # Compute derived columns if missing
        if "extrinsic_pct" not in df.columns:
            df["intrinsic_value"] = df.apply(
                lambda r: compute_intrinsic_value(r["option_type"], r["underlying_price"], r["strike"]),
                axis=1,
            )
            df["extrinsic_value"] = df.apply(
                lambda r: compute_extrinsic_value(r["ask"], r["intrinsic_value"]), axis=1
            )
            df["extrinsic_pct"] = df.apply(
                lambda r: compute_extrinsic_pct(r["extrinsic_value"], r["ask"]), axis=1
            )
        if "spread_pct" not in df.columns:
            df["spread_pct"] = df.apply(
                lambda r: compute_spread_pct(r["bid"], r["ask"]), axis=1
            )
        if "dte" not in df.columns:
            df["dte"] = df.apply(
                lambda r: (pd.to_datetime(r["expiration_date"]).date() - pd.to_datetime(r["date"]).date()).days,
                axis=1,
            )
        return df
