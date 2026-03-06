import logging
from datetime import date
from typing import Dict, List, Optional

import pandas as pd
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import (
    OptionChainRequest,
    OptionSnapshotRequest,
    StockBarsRequest,
    StockLatestTradeRequest,
)
from alpaca.data.timeframe import TimeFrame

logger = logging.getLogger(__name__)


def fetch_option_chain(
    client: OptionHistoricalDataClient,
    symbol: str,
    expiration_date_gte: date,
    expiration_date_lte: date,
    option_type: str = "call",
    feed: str = "indicative",
) -> Dict:
    """
    Fetch the option chain snapshot for a symbol and expiration range.
    Returns dict keyed by contract symbol.
    """
    try:
        req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=expiration_date_gte,
            expiration_date_lte=expiration_date_lte,
            type=option_type,
            feed=feed,
        )
        chain = client.get_option_chain(req)
        logger.debug(f"Fetched {len(chain)} contracts for {symbol} exp {expiration_date_gte}–{expiration_date_lte}")
        return chain
    except Exception as e:
        logger.warning(f"Failed to fetch option chain for {symbol}: {e}")
        return {}


def fetch_snapshots(
    client: OptionHistoricalDataClient,
    contract_symbols: List[str],
    feed: str = "indicative",
) -> Dict:
    """
    Fetch snapshots for specific contract symbols (for position monitoring).
    Returns dict keyed by contract symbol.
    """
    if not contract_symbols:
        return {}
    try:
        req = OptionSnapshotRequest(
            symbol_or_symbols=contract_symbols,
            feed=feed,
        )
        snapshots = client.get_option_snapshot(req)
        return snapshots
    except Exception as e:
        logger.warning(f"Failed to fetch snapshots for {contract_symbols}: {e}")
        return {}


def fetch_underlying_price(
    client: StockHistoricalDataClient,
    symbol: str,
) -> Optional[float]:
    """Get the latest trade price for the underlying stock."""
    try:
        req = StockLatestTradeRequest(symbol_or_symbols=symbol)
        trades = client.get_stock_latest_trade(req)
        trade = trades.get(symbol)
        if trade:
            return float(trade.price)
    except Exception as e:
        logger.warning(f"Failed to fetch price for {symbol}: {e}")
    return None


def fetch_stock_trend_state(
    client: StockHistoricalDataClient,
    symbol: str,
    ema_fast: int = 10,
    ema_medium: int = 20,
    ema_slow: int = 50,
    lookback_days: int = 180,
) -> Optional[Dict]:
    """
    Fetch daily bars and compute a simple trend-template state:
      - bullish: ema_fast > ema_medium and price > ema_slow
      - bearish: ema_fast < ema_medium and price < ema_slow
    """
    from datetime import datetime, timedelta, timezone

    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=max(lookback_days, ema_slow * 4))
        req = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        bars = client.get_stock_bars(req)
        bars_df = getattr(bars, "df", None)
        if bars_df is None or len(bars_df) == 0:
            return None

        df = bars_df.reset_index()
        df.columns = [str(c).lower() for c in df.columns]
        if "symbol" not in df.columns:
            df["symbol"] = symbol

        # Keep only requested symbol in case response includes multiple symbols.
        sym = str(symbol).upper()
        df = df[df["symbol"].astype(str).str.upper() == sym]
        if df.empty or "close" not in df.columns:
            return None

        if "timestamp" in df.columns:
            df = df.sort_values("timestamp")
        closes = pd.to_numeric(df["close"], errors="coerce").dropna()
        if len(closes) < (ema_slow + 5):
            return None

        ema_f = closes.ewm(span=ema_fast, adjust=False).mean().iloc[-1]
        ema_m = closes.ewm(span=ema_medium, adjust=False).mean().iloc[-1]
        ema_s = closes.ewm(span=ema_slow, adjust=False).mean().iloc[-1]
        price = float(closes.iloc[-1])

        is_bullish = (ema_f > ema_m) and (price > ema_s)
        is_bearish = (ema_f < ema_m) and (price < ema_s)

        return {
            "symbol": sym,
            "price": round(price, 4),
            "ema_fast": round(float(ema_f), 4),
            "ema_medium": round(float(ema_m), 4),
            "ema_slow": round(float(ema_s), 4),
            "is_bullish": bool(is_bullish),
            "is_bearish": bool(is_bearish),
        }
    except Exception as e:
        logger.warning(f"Failed to fetch trend template for {symbol}: {e}")
        return None


def snapshot_to_dict(symbol: str, snap) -> Dict:
    """
    Flatten an Alpaca OptionSnapshot object into a plain dict
    for use with the filter/scoring logic.
    """
    greeks = getattr(snap, "greeks", None)
    latest_quote = getattr(snap, "latest_quote", None)
    latest_trade = getattr(snap, "latest_trade", None)

    bid = float(getattr(latest_quote, "bid_price", 0) or 0) if latest_quote else 0.0
    ask = float(getattr(latest_quote, "ask_price", 0) or 0) if latest_quote else 0.0
    last = float(getattr(latest_trade, "price", 0) or 0) if latest_trade else 0.0

    delta = float(getattr(greeks, "delta", 0) or 0) if greeks else 0.0
    gamma = float(getattr(greeks, "gamma", 0) or 0) if greeks else 0.0
    theta = float(getattr(greeks, "theta", 0) or 0) if greeks else 0.0
    vega = float(getattr(greeks, "vega", 0) or 0) if greeks else 0.0
    iv = float(getattr(snap, "implied_volatility", 0) or 0)

    # Parse contract details from the symbol if not directly available
    # Alpaca option symbol format: AAPL240119C00150000
    #   underlying (variable length), YYMMDD, C/P, 8-digit strike * 1000
    contract_details = _parse_contract_symbol(symbol)

    return {
        "contract_symbol": symbol,
        "underlying": contract_details.get("underlying", ""),
        "option_type": contract_details.get("option_type", "call"),
        "strike": contract_details.get("strike", 0.0),
        "expiration_date": contract_details.get("expiration_date", ""),
        "bid": bid,
        "ask": ask,
        "last": last,
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "implied_volatility": iv,
        "open_interest": getattr(snap, "open_interest", None),
    }


def _parse_contract_symbol(symbol: str) -> Dict:
    """
    Parse OCC option symbol into components.
    Format: {underlying}{YYMMDD}{C/P}{8-digit-strike}
    Strike is stored as integer * 1000 (e.g. 150000 = $150.00).
    """
    try:
        # Find where the date starts (6 consecutive digits preceded by letters)
        import re
        match = re.match(r"^([A-Z]+)(\d{6})([CP])(\d{8})$", symbol)
        if match:
            underlying = match.group(1)
            date_str = match.group(2)
            opt_type = "call" if match.group(3) == "C" else "put"
            strike = int(match.group(4)) / 1000.0
            exp_date = f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"
            return {
                "underlying": underlying,
                "option_type": opt_type,
                "strike": strike,
                "expiration_date": exp_date,
            }
    except Exception:
        pass
    return {}
