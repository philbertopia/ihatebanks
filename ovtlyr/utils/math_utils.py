def compute_intrinsic_value(option_type: str, underlying_price: float, strike: float) -> float:
    """Intrinsic value of an option."""
    if option_type.lower() == "call":
        return max(underlying_price - strike, 0.0)
    else:
        return max(strike - underlying_price, 0.0)


def compute_extrinsic_value(ask_price: float, intrinsic_value: float) -> float:
    """Extrinsic (time) value. Never negative."""
    return max(ask_price - intrinsic_value, 0.0)


def compute_extrinsic_pct(extrinsic_value: float, ask_price: float) -> float:
    """Extrinsic as a fraction of the ask price. Returns 1.0 if ask is 0."""
    if ask_price <= 0:
        return 1.0
    return extrinsic_value / ask_price


def compute_spread_pct(bid: float, ask: float) -> float:
    """Bid/ask spread as a fraction of ask. Returns 1.0 if ask is 0."""
    if ask <= 0:
        return 1.0
    return (ask - bid) / ask


def compute_mid_price(bid: float, ask: float) -> float:
    return (bid + ask) / 2.0


def compute_unrealized_pnl(entry_price: float, current_price: float, qty: int) -> float:
    """PnL in dollars. Each contract covers 100 shares."""
    return (current_price - entry_price) * qty * 100


def compute_realized_pnl(entry_price: float, close_price: float, qty: int) -> float:
    """Realized PnL in dollars."""
    return (close_price - entry_price) * qty * 100
