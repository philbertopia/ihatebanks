from __future__ import annotations

import math


def vol_target_contracts(
    equity: float,
    option_price: float,
    underlying_annual_vol: float,
    target_annual_vol: float,
    contract_multiplier: int = 100,
    min_contracts: int = 1,
    max_contracts: int = 10,
) -> int:
    """
    Vol-targeted contracts estimate.
    """
    eq = max(float(equity), 1.0)
    px = max(float(option_price), 0.01)
    uvol = max(float(underlying_annual_vol), 0.01)
    tvol = max(float(target_annual_vol), 0.01)
    per_contract_daily_risk = (px * contract_multiplier) * (uvol / math.sqrt(252.0))
    target_daily_risk = (eq * tvol) / math.sqrt(252.0)
    qty = int(target_daily_risk // max(per_contract_daily_risk, 1.0))
    qty = max(int(min_contracts), qty)
    qty = min(int(max_contracts), qty)
    return qty


def risk_budget_contracts(
    allocation_dollars: float,
    option_price: float,
    contract_multiplier: int = 100,
    min_contracts: int = 1,
    max_contracts: int = 10,
) -> int:
    alloc = max(float(allocation_dollars), 0.0)
    px = max(float(option_price), 0.01)
    qty = int(alloc // (px * contract_multiplier))
    qty = max(int(min_contracts), qty)
    qty = min(int(max_contracts), qty)
    return qty


def cap_symbol_notional(
    contracts: int,
    option_price: float,
    equity: float,
    max_symbol_notional_pct: float,
    contract_multiplier: int = 100,
) -> int:
    qty = max(int(contracts), 0)
    px = max(float(option_price), 0.01)
    eq = max(float(equity), 1.0)
    cap_pct = max(float(max_symbol_notional_pct), 0.0)
    cap_notional = eq * cap_pct
    max_qty = int(cap_notional // (px * contract_multiplier))
    if max_qty <= 0:
        return 0
    return min(qty, max_qty)

