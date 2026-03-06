from datetime import date
from typing import List

from ovtlyr.utils.time_utils import (
    get_third_friday,
    get_monthly_expirations,
    is_final_week,
    days_to_expiration,
)

__all__ = [
    "get_third_friday",
    "get_monthly_expirations",
    "is_final_week",
    "days_to_expiration",
    "get_target_expirations",
]


def get_target_expirations(
    min_dte: int,
    max_dte: int,
    today: date = None,
    prefer_monthly: bool = True,
    include_weekly_fallback: bool = True,
) -> List[date]:
    """
    Return expiration dates to scan.
    Primary: monthly (3rd Fridays). Fallback: weekly if no monthlies found.
    """
    if today is None:
        today = date.today()

    monthlies = get_monthly_expirations(min_dte, max_dte, today)
    if monthlies or not include_weekly_fallback:
        return monthlies

    # Weekly fallback: every Friday in the DTE window (skip final week)
    weeklies: List[date] = []
    d = today
    from datetime import timedelta
    while (d - today).days <= max_dte:
        if d.weekday() == 4:  # Friday
            dte = (d - today).days
            if min_dte <= dte <= max_dte and not is_final_week(d, today):
                weeklies.append(d)
        d += timedelta(days=1)
    return weeklies
