import logging
from datetime import date
from typing import List, Dict, Any

from ovtlyr.utils.math_utils import (
    compute_intrinsic_value,
    compute_extrinsic_value,
    compute_extrinsic_pct,
    compute_spread_pct,
)
from ovtlyr.utils.time_utils import days_to_expiration, get_third_friday, is_final_week

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  Individual filter functions
# ──────────────────────────────────────────────


def passes_delta_filter(
    delta: float, target: float = 0.80, tolerance: float = 0.10
) -> bool:
    """
    Accept options within ±tolerance of the target delta.
    Works for both positive (calls) and negative (puts) delta targets.
    """
    return abs(delta - target) <= tolerance


def passes_extrinsic_filter(extrinsic_pct: float, max_pct: float = 0.30) -> bool:
    return extrinsic_pct <= max_pct


def passes_open_interest_filter(
    open_interest, min_oi: int = 500, require: bool = False
) -> bool:
    """
    When open_interest is None (indicative feed doesn't include OI),
    allow through unless require=True is set explicitly.
    """
    if open_interest is None:
        return not require  # unknown OI: allow unless strictly required
    try:
        return int(open_interest) >= min_oi
    except (ValueError, TypeError):
        return not require


def passes_spread_filter(spread_pct: float, max_spread_pct: float = 0.10) -> bool:
    return spread_pct <= max_spread_pct


# ──────────────────────────────────────────────
#  Composite scoring
# ──────────────────────────────────────────────


def score_candidate(data: Dict[str, Any]) -> float:
    """
    Weighted composite score 0-100. Higher = better candidate.

    Components:
      40% - Delta proximity to 0.80 (closer = higher)
      30% - Low extrinsic % (lower = higher)
      20% - Open interest (higher = higher, capped at 10k)
      10% - Tight spread (lower = higher)
    """
    delta = data.get("delta", 0)
    extrinsic_pct = data.get("extrinsic_pct", 1.0)
    oi = data.get("open_interest", 0) or 0
    spread_pct = data.get("spread_pct", 1.0)

    # Delta component: 1 - normalized distance from 0.80 (max distance is tolerance 0.10)
    delta_score = max(0, 1 - abs(delta - 0.80) / 0.10) * 40

    # Extrinsic component: linear from 0% (best=30pts) to 30% (worst=0pts)
    extrinsic_score = max(0, 1 - extrinsic_pct / 0.30) * 30

    # OI component: log scale up to 10k OI
    import math

    oi_score = min(math.log10(max(oi, 1)) / math.log10(10_000), 1.0) * 20

    # Spread component: linear from 0% (best=10pts) to 10% (worst=0pts)
    spread_score = max(0, 1 - spread_pct / 0.10) * 10

    return round(delta_score + extrinsic_score + oi_score + spread_score, 2)


def score_csp_candidate(data: Dict[str, Any], target_delta: float = -0.30) -> float:
    """
    CSP-specific scoring for puts. Higher = better candidate.

    Components:
      35% - Delta proximity to target (closer = higher)
      35% - Credit/collateral ratio (higher = higher)
      20% - Open interest (higher = higher, capped at 10k)
      10% - Tight spread (lower = higher)
    """
    delta = data.get("delta", 0)
    bid = data.get("bid", 0)
    strike = data.get("strike", 1)
    oi = data.get("open_interest", 0) or 0
    spread_pct = data.get("spread_pct", 1.0)

    collateral = strike * 100
    credit_ratio = bid / collateral if collateral > 0 else 0

    import math

    delta_tolerance = 0.10
    delta_score = max(0, 1 - abs(delta - target_delta) / delta_tolerance) * 35

    credit_score = min(credit_ratio * 1000, 35) * 1.0

    oi_score = min(math.log10(max(oi, 1)) / math.log10(10_000), 1.0) * 20

    spread_score = max(0, 1 - spread_pct / 0.15) * 10

    return round(delta_score + credit_score + oi_score + spread_score, 2)


# ──────────────────────────────────────────────
#  Master filter
# ──────────────────────────────────────────────


def filter_candidates(
    chain: Dict,
    underlying_price: float,
    config: Dict[str, Any],
    today: date = None,
) -> List[Dict]:
    """
    Apply all OVTLYR strategy filters to an option chain snapshot dict.
    Returns sorted list (best first) of qualifying contract dicts.

    `chain` is keyed by contract_symbol and values are snapshot objects
    or pre-flattened dicts from options_data.snapshot_to_dict().
    """
    if today is None:
        today = date.today()

    strategy = config.get(
        "strategy", config
    )  # allow passing full config or strategy sub-dict
    target_delta = strategy.get("target_delta", 0.80)
    delta_tolerance = strategy.get("delta_tolerance", 0.10)
    max_extrinsic_pct = strategy.get("max_extrinsic_pct", 0.30)
    min_oi = strategy.get("min_open_interest", 500)
    require_oi = strategy.get("require_open_interest", False)
    max_spread_pct = strategy.get("max_spread_pct", 0.10)
    option_type = strategy.get("option_type", "call")
    min_dte = int(strategy.get("min_dte", 0) or 0)
    max_dte = int(strategy.get("max_dte", 10_000) or 10_000)
    monthly_only = bool(strategy.get("monthly_only", False))

    results: List[Dict] = []

    for contract_symbol, snap in chain.items():
        # Accept either pre-flattened dict or raw snapshot
        if isinstance(snap, dict):
            d = snap
        else:
            from ovtlyr.api.options_data import snapshot_to_dict

            d = snapshot_to_dict(contract_symbol, snap)

        # Skip if we can't determine key values
        ask = d.get("ask", 0)
        bid = d.get("bid", 0)
        delta = d.get("delta", 0)
        oi = d.get("open_interest")
        exp_date_str = d.get("expiration_date", "")
        strike = d.get("strike", 0)
        opt_type = d.get("option_type", "call")

        # Only the configured option type
        if opt_type.lower() != option_type.lower():
            continue

        # Skip zero-price or no-quote contracts
        if ask <= 0 or bid < 0:
            continue

        # Parse expiration date
        try:
            from datetime import date as date_cls

            exp_date = date_cls.fromisoformat(exp_date_str) if exp_date_str else None
        except ValueError:
            continue

        if exp_date is None:
            continue

        # Skip final week
        if is_final_week(exp_date, today):
            continue

        dte = days_to_expiration(exp_date, today)
        if dte < min_dte or dte > max_dte:
            continue

        if monthly_only:
            monthly_exp = get_third_friday(exp_date.year, exp_date.month)
            if exp_date != monthly_exp:
                continue

        # Compute derived values using the actual contract's option type (not strategy default)
        intrinsic = compute_intrinsic_value(opt_type, underlying_price, strike)
        extrinsic = compute_extrinsic_value(ask, intrinsic)
        ext_pct = compute_extrinsic_pct(extrinsic, ask)
        spread_pct = compute_spread_pct(bid, ask)

        # Apply filters
        if not passes_delta_filter(delta, target_delta, delta_tolerance):
            continue
        if not passes_extrinsic_filter(ext_pct, max_extrinsic_pct):
            continue
        if not passes_open_interest_filter(oi, min_oi, require=require_oi):
            continue
        if not passes_spread_filter(spread_pct, max_spread_pct):
            continue

        candidate = {
            **d,
            "dte": dte,
            "intrinsic_value": round(intrinsic, 4),
            "extrinsic_value": round(extrinsic, 4),
            "extrinsic_pct": round(ext_pct, 4),
            "spread_pct": round(spread_pct, 4),
            "underlying_price": underlying_price,
        }
        strategy_type = strategy.get("strategy_type", "stock_replacement")
        if strategy_type == "csp":
            candidate["score"] = score_csp_candidate(candidate, target_delta)
        else:
            candidate["score"] = score_candidate(candidate)
        results.append(candidate)

    results.sort(key=lambda x: x["score"], reverse=True)
    logger.debug(
        f"filter_candidates: {len(results)} qualifying contracts from {len(chain)} total"
    )
    return results
