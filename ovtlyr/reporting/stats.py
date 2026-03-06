from typing import Dict, Any
from ovtlyr.database.repository import Repository


def get_portfolio_stats(repo: Repository) -> Dict[str, Any]:
    """Return aggregate portfolio stats from the DB."""
    summary = repo.get_pnl_summary()
    open_positions = repo.get_open_positions()

    portfolio_delta = sum(
        (p.get("current_delta") or p.get("entry_delta", 0)) * p["qty"]
        for p in open_positions
    )

    return {
        **summary,
        "portfolio_delta": round(portfolio_delta, 4),
    }
