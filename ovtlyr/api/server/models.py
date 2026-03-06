from pydantic import BaseModel
from typing import Optional


class Position(BaseModel):
    id: int
    underlying: str
    contract_symbol: str
    option_type: str
    strike: float
    expiration_date: str
    qty: int
    entry_price: float
    entry_date: str
    entry_delta: Optional[float] = None
    entry_extrinsic_pct: Optional[float] = None
    entry_underlying_price: Optional[float] = None
    current_delta: Optional[float] = None
    current_price: Optional[float] = None
    status: str
    close_date: Optional[str] = None
    close_price: Optional[float] = None
    close_reason: Optional[str] = None
    realized_pnl: Optional[float] = None
    unrealized_pnl: float = 0.0
    notes: Optional[str] = None


class PortfolioStats(BaseModel):
    open_positions: int
    portfolio_delta: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    total_closed: int
    winners: int
    losers: int
    win_rate: float
    profit_factor: float
    gross_profit: float
    gross_loss: float
    avg_pnl: Optional[float] = None


class ScanResult(BaseModel):
    id: int
    scan_date: str
    underlying: str
    contract_symbol: str
    strike: float
    expiration_date: str
    dte: int
    delta: float
    ask: float
    bid: float
    spread_pct: float
    open_interest: Optional[int] = None
    extrinsic_value: float
    extrinsic_pct: float
    implied_volatility: Optional[float] = None
    score: Optional[float] = None
    action_taken: str


class DailyStats(BaseModel):
    stat_date: str
    open_positions: int
    positions_opened: int
    positions_rolled: int
    positions_closed: int
    total_pnl_unrealized: float
    total_pnl_realized: float
    portfolio_delta: float
