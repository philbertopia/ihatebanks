"""
Polygon.io option snapshot validator.
Fetches real option chain snapshots and compares to synthetic Parquet cache.

Cache format: data/cache/YYYY-MM-DD.parquet (all underlyings per day).
Each row has: underlying, option_type, strike, expiration_date, bid, ask, delta, ...

Usage:
    python main.py validate-polygon --underlying SPY
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

POLYGON_BASE = "https://api.polygon.io"


def fetch_option_snapshot(underlying: str, api_key: str) -> list:
    """Fetch all option contract snapshots for an underlying from Polygon.

    Paginates automatically using next_url. Returns a flat list of result dicts.
    """
    url = f"{POLYGON_BASE}/v3/snapshot/options/{underlying}"
    params: dict = {"apiKey": api_key, "limit": 250}
    results = []
    page = 0
    while url:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("results", [])
        results.extend(batch)
        url = data.get("next_url")
        params = {"apiKey": api_key}  # next_url already carries its own query params
        page += 1
        logger.debug("[Polygon] page %d — %d contracts fetched so far", page, len(results))
        if page > 40:  # safety: stop after ~10 000 contracts
            logger.warning("[Polygon] Pagination limit reached, stopping early")
            break
    logger.info("[Polygon] Fetched %d contracts for %s", len(results), underlying)
    return results


def load_cache_for_underlying(cache_dir: str, underlying: str) -> pd.DataFrame:
    """Load the most recent date-based Parquet file and filter to *underlying*."""
    cache_path = Path(cache_dir)
    files = sorted(cache_path.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No Parquet files found in {cache_dir}")

    parquet_file = files[-1]  # most recent date
    logger.info("[Polygon] Loading cache file: %s", parquet_file)
    df = pd.read_parquet(parquet_file)

    if "underlying" not in df.columns:
        raise ValueError(f"Cache file {parquet_file} has no 'underlying' column")

    subset = df[df["underlying"] == underlying].copy()
    if subset.empty:
        raise ValueError(
            f"No rows for underlying '{underlying}' in {parquet_file}. "
            f"Available: {sorted(df['underlying'].unique())[:10]}"
        )

    # Compute mid_price if not present
    if "mid_price" not in subset.columns:
        subset["mid_price"] = (
            pd.to_numeric(subset.get("bid", 0), errors="coerce")
            + pd.to_numeric(subset.get("ask", 0), errors="coerce")
        ) / 2.0

    # Normalise expiration column name
    if "expiration_date" in subset.columns and "expiration" not in subset.columns:
        subset = subset.rename(columns={"expiration_date": "expiration"})

    logger.info(
        "[Polygon] Cache rows for %s: %d (file: %s)",
        underlying,
        len(subset),
        parquet_file.name,
    )
    return subset


def validate_cache_vs_polygon(
    cache_dir: str,
    underlying: str,
    api_key: str,
    date_str: Optional[str] = None,  # reserved for future date-pinning
) -> pd.DataFrame:
    """Compare synthetic Parquet cache to live Polygon option snapshots.

    Loads the most recent cached Parquet file for *underlying*, fetches live
    snapshots from Polygon, inner-joins on (strike, expiration, option_type),
    and computes delta / price deltas.

    Returns a DataFrame with columns:
        contract_symbol, strike, expiration, option_type,
        delta, poly_delta, delta_diff,
        mid_price, poly_mid, mid_diff, mid_diff_pct
    """
    synthetic = load_cache_for_underlying(cache_dir, underlying)

    # Fetch Polygon snapshots
    poly_rows = fetch_option_snapshot(underlying, api_key)
    if not poly_rows:
        raise ValueError(f"Polygon returned no data for {underlying}")

    # Build normalised Polygon DataFrame
    records = []
    for r in poly_rows:
        d = r.get("details") or {}
        g = r.get("greeks") or {}
        q = r.get("last_quote") or {}
        bid = q.get("bid")
        ask = q.get("ask")
        mid = (bid + ask) / 2.0 if bid is not None and ask is not None else None
        records.append(
            {
                "poly_symbol": r.get("ticker", ""),
                "strike": d.get("strike_price"),
                "expiration": d.get("expiration_date"),
                "option_type": str(d.get("contract_type", "")).lower(),
                "poly_delta": g.get("delta"),
                "poly_bid": bid,
                "poly_ask": ask,
                "poly_mid": mid,
                "poly_iv": r.get("implied_volatility"),
            }
        )
    poly_df = pd.DataFrame(records)

    if poly_df.empty:
        raise ValueError(f"Polygon returned empty results for {underlying}")

    # Normalise join key dtypes
    for df in (synthetic, poly_df):
        df["strike"] = pd.to_numeric(df["strike"], errors="coerce").round(2)
        df["expiration"] = df["expiration"].astype(str).str[:10]  # YYYY-MM-DD
        df["option_type"] = df["option_type"].str.lower().str.strip()

    merged = pd.merge(
        synthetic,
        poly_df,
        on=["strike", "expiration", "option_type"],
        how="inner",
    )

    if merged.empty:
        logger.warning(
            "[Polygon] No overlapping contracts matched between cache and Polygon. "
            "Check that expiration dates are in YYYY-MM-DD format and strikes match."
        )
        return merged

    merged["delta_diff"] = (
        pd.to_numeric(merged["delta"], errors="coerce")
        - pd.to_numeric(merged["poly_delta"], errors="coerce")
    )
    merged["mid_diff"] = (
        pd.to_numeric(merged["mid_price"], errors="coerce")
        - pd.to_numeric(merged["poly_mid"], errors="coerce")
    )
    poly_mid_safe = pd.to_numeric(merged["poly_mid"], errors="coerce").replace(0.0, float("nan"))
    merged["mid_diff_pct"] = merged["mid_diff"] / poly_mid_safe

    # Select output columns (keep what's available)
    symbol_col = "contract_symbol" if "contract_symbol" in merged.columns else "poly_symbol"
    out_cols = [
        symbol_col, "strike", "expiration", "option_type",
        "delta", "poly_delta", "delta_diff",
        "mid_price", "poly_mid", "mid_diff", "mid_diff_pct",
    ]
    out_cols = [c for c in out_cols if c in merged.columns]
    return merged[out_cols].reset_index(drop=True)


def print_validation_report(
    df: pd.DataFrame,
    max_delta_deviation: float = 0.03,
) -> None:
    """Print a summary validation report to stdout."""
    if df.empty:
        print("No overlapping contracts to compare.")
        return

    n = len(df)
    delta_flagged = df[df["delta_diff"].abs() > max_delta_deviation]
    mid_flagged = df[df["mid_diff_pct"].abs() > 0.20]

    print(f"\n{'=' * 60}")
    print(f"  Polygon Validation Report  ({n} contracts matched)")
    print(f"{'=' * 60}")

    print(f"\nDelta comparison  (synthetic - Polygon):")
    print(df["delta_diff"].describe().to_string())
    print(
        f"\n  Contracts with |delta_diff| > {max_delta_deviation}: "
        f"{len(delta_flagged)} ({len(delta_flagged)/n*100:.1f}%)"
    )

    print(f"\nMid-price comparison  (synthetic - Polygon, %):")
    print(df["mid_diff_pct"].describe().to_string())
    print(
        f"\n  Contracts with |mid_diff_pct| > 20%: "
        f"{len(mid_flagged)} ({len(mid_flagged)/n*100:.1f}%)"
    )

    if not delta_flagged.empty:
        sym_col = "contract_symbol" if "contract_symbol" in delta_flagged.columns else "poly_symbol"
        display_cols = [c for c in [sym_col, "strike", "expiration", "option_type",
                                    "delta", "poly_delta", "delta_diff"] if c in delta_flagged.columns]
        print(f"\nTop delta outliers (|diff| > {max_delta_deviation}):")
        print(
            delta_flagged[display_cols]
            .sort_values("delta_diff", key=abs, ascending=False)
            .head(10)
            .to_string(index=False)
        )
    print()
