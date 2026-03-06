from datetime import date, timedelta
import calendar
from typing import List


def get_third_friday(year: int, month: int) -> date:
    """Return the 3rd Friday of the given month (standard monthly expiration)."""
    c = calendar.monthcalendar(year, month)
    fridays = [week[calendar.FRIDAY] for week in c if week[calendar.FRIDAY] != 0]
    if len(fridays) < 3:
        raise ValueError(f"Month {month}/{year} has fewer than 3 Fridays (unexpected calendar)")
    return date(year, month, fridays[2])


def get_monthly_expirations(min_dte: int, max_dte: int, today: date = None) -> List[date]:
    """Return 3rd Friday dates whose DTE falls within [min_dte, max_dte].
    Filters out dates in the final week (DTE <= 7)."""
    if today is None:
        today = date.today()

    expirations: List[date] = []
    # Check up to 6 months ahead to be safe
    for offset in range(7):
        year = today.year + (today.month + offset - 1) // 12
        month = (today.month + offset - 1) % 12 + 1
        exp = get_third_friday(year, month)
        dte = (exp - today).days
        if min_dte <= dte <= max_dte and not is_final_week(exp, today):
            expirations.append(exp)

    return sorted(expirations)


def is_final_week(expiration_date: date, today: date = None) -> bool:
    """Return True if the expiration is 7 or fewer calendar days away."""
    if today is None:
        today = date.today()
    return (expiration_date - today).days <= 7


def days_to_expiration(expiration_date: date, today: date = None) -> int:
    """Calendar days until expiration."""
    if today is None:
        today = date.today()
    return (expiration_date - today).days


def is_market_day(d: date = None) -> bool:
    """Rough check: Monday-Friday, not a weekend. Does not account for holidays."""
    if d is None:
        d = date.today()
    return d.weekday() < 5
