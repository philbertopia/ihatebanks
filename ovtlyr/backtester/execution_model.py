from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ExecutionSettings:
    block_first_minutes: int = 5
    open_slippage_mult: float = 1.30
    midday_slippage_mult: float = 0.90
    close_slippage_mult: float = 1.15


def get_execution_settings(config: Dict) -> ExecutionSettings:
    exe = config.get("execution", {}) if isinstance(config, dict) else {}
    return ExecutionSettings(
        block_first_minutes=int(exe.get("block_first_minutes", 5) or 5),
        open_slippage_mult=float(exe.get("open_slippage_mult", 1.30) or 1.30),
        midday_slippage_mult=float(exe.get("midday_slippage_mult", 0.90) or 0.90),
        close_slippage_mult=float(exe.get("close_slippage_mult", 1.15) or 1.15),
    )


def _tod_mult(tod_bucket: str, settings: ExecutionSettings) -> float:
    b = str(tod_bucket or "midday").lower()
    if b == "open":
        return settings.open_slippage_mult
    if b == "close":
        return settings.close_slippage_mult
    return settings.midday_slippage_mult


def expected_slippage_bps(
    spread_pct: float,
    tod_bucket: str,
    settings: ExecutionSettings,
    data_quality: str = "observed",
) -> float:
    s = max(float(spread_pct), 0.0)
    q = str(data_quality or "observed").lower()
    quality_mult = 1.0 if q == "observed" else (1.10 if q == "mixed" else 1.25)
    # Convert spread % to bps and apply conservative fraction.
    return s * 10_000.0 * 0.35 * _tod_mult(tod_bucket, settings) * quality_mult


def adjust_fill_price(
    price: float,
    spread_abs: float,
    side: str,
    tod_bucket: str,
    settings: ExecutionSettings,
    data_quality: str = "observed",
) -> float:
    px = max(float(price), 0.01)
    sp = max(float(spread_abs), 0.0)
    q = str(data_quality or "observed").lower()
    quality_mult = 1.0 if q == "observed" else (1.10 if q == "mixed" else 1.25)
    slip = sp * 0.35 * _tod_mult(tod_bucket, settings) * quality_mult
    if str(side or "buy").lower() == "buy":
        return max(0.01, px + slip)
    return max(0.01, px - slip)


def partial_fill_ratio(
    liquidity_score: float,
    tod_bucket: str,
    settings: ExecutionSettings,
) -> float:
    liq = max(0.0, min(float(liquidity_score), 1.0))
    tod_mult = _tod_mult(tod_bucket, settings)
    # Better liquidity => closer to full fill. Open/close generally less efficient.
    ratio = (0.40 + 0.60 * liq) / max(tod_mult, 0.5)
    return max(0.0, min(ratio, 1.0))


# -----------------------------------------------------------------------------
# SPX 0DTE short put spread fill model (credit spread: sell spread = receive credit)
# -----------------------------------------------------------------------------

FillMode = str  # "conservative" | "base" | "optimistic"


def spread_fill_credit_entry(
    short_put_bid: float,
    short_put_ask: float,
    long_put_bid: float,
    long_put_ask: float,
    fill_mode: str = "base",
    base_pct_of_spread: float = 0.15,
    spread_multiplier: float = 1.0,
) -> float:
    """
    Credit received when selling the put spread (short put at short_*, long put at long_*).
    Conservative = worst leg (short at bid, long at ask). Optimistic = mid. Base = mid - pct of spread.
    spread_multiplier: apply to effective spread (e.g. 1.5-3x in fast markets).
    """
    short_bid = max(float(short_put_bid), 0.0)
    short_ask = max(float(short_put_ask), short_bid + 1e-6)
    long_bid = max(float(long_put_bid), 0.0)
    long_ask = max(float(long_put_ask), long_bid + 1e-6)
    # Worst credit (conservative): we receive short bid, pay long ask
    worst_credit = short_bid - long_ask
    # Best credit: we receive short ask, pay long bid (theoretical best)
    best_credit = short_ask - long_bid
    mid_short = (short_bid + short_ask) / 2.0
    mid_long = (long_bid + long_ask) / 2.0
    mid_credit = mid_short - mid_long
    spread_width = max((best_credit - worst_credit) * spread_multiplier, 0.0)
    mode = str(fill_mode or "base").lower()
    if mode == "conservative":
        return round(worst_credit, 4)
    if mode == "optimistic":
        return round(mid_credit, 4)
    # base: mid minus fraction of spread (worse fill)
    pct = max(0.0, min(1.0, float(base_pct_of_spread)))
    return round(max(worst_credit, mid_credit - pct * spread_width), 4)


def spread_fill_debit_exit(
    short_put_bid: float,
    short_put_ask: float,
    long_put_bid: float,
    long_put_ask: float,
    fill_mode: str = "base",
    base_pct_of_spread: float = 0.15,
    spread_multiplier: float = 1.0,
) -> float:
    """
    Debit paid when buying back the put spread (buy short, sell long).
    Conservative = worst (pay short ask, receive long bid). Optimistic = mid. Base = mid + pct of spread.
    """
    short_bid = max(float(short_put_bid), 0.0)
    short_ask = max(float(short_put_ask), short_bid + 1e-6)
    long_bid = max(float(long_put_bid), 0.0)
    long_ask = max(float(long_put_ask), long_bid + 1e-6)
    # Worst debit: pay short ask, receive long bid
    worst_debit = short_ask - long_bid
    best_debit = short_bid - long_ask
    mid_short = (short_bid + short_ask) / 2.0
    mid_long = (long_bid + long_ask) / 2.0
    mid_debit = mid_short - mid_long
    spread_width = max((worst_debit - best_debit) * spread_multiplier, 0.0)
    mode = str(fill_mode or "base").lower()
    if mode == "conservative":
        return round(worst_debit, 4)
    if mode == "optimistic":
        return round(mid_debit, 4)
    pct = max(0.0, min(1.0, float(base_pct_of_spread)))
    return round(min(worst_debit, mid_debit + pct * spread_width), 4)


def summarize_execution_realism(
    slippage_bps: List[float],
    spread_cost_total: float,
    slippage_cost_total: float,
    filled: int,
    partial: int,
    attempted: int,
) -> Dict:
    avg_slip = (sum(slippage_bps) / len(slippage_bps)) if slippage_bps else 0.0
    fill_rate = (filled / attempted) if attempted > 0 else 0.0
    partial_rate = (partial / filled) if filled > 0 else 0.0
    return {
        "avg_slippage_bps": round(avg_slip, 4),
        "spread_cost_pct": round((spread_cost_total / max(abs(slippage_cost_total) + 1e-9, 1.0)) * 100.0, 4),
        "fill_rate": round(fill_rate, 6),
        "partial_fill_rate": round(partial_rate, 6),
        "slippage_cost_total": round(float(slippage_cost_total), 4),
    }

