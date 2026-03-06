from fastapi import APIRouter
from typing import List
from datetime import datetime

from ovtlyr.api.server.models import Position
from ovtlyr.database.repository import Repository
from ovtlyr.utils.math_utils import compute_unrealized_pnl

router = APIRouter()
DB_PATH = "db/ovtlyr.db"


def _enrich(pos: dict) -> dict:
    entry = pos.get("entry_price", 0) or 0
    raw_current = pos.get("current_price")
    current = raw_current if raw_current is not None else entry
    qty = pos.get("qty", 1) or 1
    pos["unrealized_pnl"] = compute_unrealized_pnl(entry, current, qty)
    return pos


@router.get("/positions", response_model=List[Position])
def get_open_positions():
    repo = Repository(DB_PATH)
    positions = repo.get_open_positions()
    return [_enrich(p) for p in positions]


@router.get("/positions/history", response_model=List[Position])
def get_position_history():
    repo = Repository(DB_PATH)
    positions = repo.get_all_closed_trades_for_backtest()
    return [_enrich(p) for p in positions]
