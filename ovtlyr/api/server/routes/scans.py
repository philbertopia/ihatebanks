from fastapi import APIRouter
from typing import List
from datetime import date

from ovtlyr.api.server.models import ScanResult
from ovtlyr.database.repository import Repository

router = APIRouter()
DB_PATH = "db/ovtlyr.db"


def _to_model(r: dict) -> ScanResult:
    return ScanResult(
        id=r["id"],
        scan_date=r["scan_date"],
        underlying=r["underlying"],
        contract_symbol=r["contract_symbol"],
        strike=r["strike"],
        expiration_date=r["expiration_date"],
        dte=r["dte"],
        delta=r["delta"],
        ask=r["ask"],
        bid=r["bid"],
        spread_pct=r["spread_pct"],
        open_interest=r.get("open_interest"),
        extrinsic_value=r["extrinsic_value"],
        extrinsic_pct=r["extrinsic_pct"],
        implied_volatility=r.get("implied_volatility"),
        score=r.get("score"),
        action_taken=r.get("action_taken", "none"),
    )


@router.get("/scans/today", response_model=List[ScanResult])
def get_todays_scans():
    repo = Repository(DB_PATH)
    results = repo.get_scan_results_for_date(date.today().isoformat())
    return [_to_model(r) for r in results]


@router.get("/scans/{scan_date}", response_model=List[ScanResult])
def get_scans_for_date(scan_date: str):
    repo = Repository(DB_PATH)
    results = repo.get_scan_results_for_date(scan_date)
    return [_to_model(r) for r in results]
