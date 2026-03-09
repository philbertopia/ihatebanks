"""
SPX/SPXW expiration calendar and contract constants for 0DTE backtesting.

Cboe timeline:
- 2010-2015: SPX Weeklys Friday only.
- Early 2016: Wednesday and Monday Weeklys added (M/W/F).
- 2022: Tuesday and Thursday added → expirations every weekday.
"""
from __future__ import annotations

from datetime import date
from typing import List

# SPX/SPXW contract constants
SPX_MULTIPLIER = 100
"""Index point to dollar: 1 point = $100 per contract."""

# Trading ceases 3:00 p.m. CT (4:00 p.m. ET). Safe proxy for hard time-exit.
TIME_EXIT_ET_HOUR = 15
TIME_EXIT_ET_MINUTE = 45


def spxw_expiries_for_date(d: date) -> List[date]:
    """
    Return same-day expiry date if the given date has an SPXW expiration, else empty.

    Logic:
    - 2010-2015: Friday only.
    - 2016-2021: Monday, Wednesday, Friday.
    - 2022+: All weekdays (Mon-Fri).
    """
    if d.year < 2010:
        return []
    weekday = d.weekday()  # 0=Mon, 4=Fri
    if d.year <= 2015:
        if weekday == 4:  # Friday
            return [d]
        return []
    if d.year <= 2021:
        if weekday in (0, 2, 4):  # Mon, Wed, Fri
            return [d]
        return []
    # 2022+
    if weekday < 5:  # Mon-Fri
        return [d]
    return []


def has_same_day_expiry(d: date) -> bool:
    """True if there is an SPXW expiring on date d."""
    return len(spxw_expiries_for_date(d)) > 0


def spxw_expiry_calendar(start: date, end: date) -> List[date]:
    """Return sorted list of dates in [start, end] that have an SPXW same-day expiry."""
    from datetime import timedelta
    out: List[date] = []
    current = start
    while current <= end:
        if has_same_day_expiry(current):
            out.append(current)
        current += timedelta(days=1)
    return out


def sub_period_key(d: date) -> str:
    """
    Cboe regime break for sub-period reporting.
    Returns: "pre_2016" | "2016_2021" | "2022_present"
    """
    if d.year <= 2015:
        return "pre_2016"
    if d.year <= 2021:
        return "2016_2021"
    return "2022_present"
