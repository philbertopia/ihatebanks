import logging
from datetime import date
from typing import Dict, List, Tuple, Any

from ovtlyr.api.client import AlpacaClients
from ovtlyr.api.options_data import fetch_snapshots, snapshot_to_dict
from ovtlyr.database.repository import Repository
from ovtlyr.utils.time_utils import days_to_expiration, is_final_week

logger = logging.getLogger(__name__)


class PositionTracker:
    """
    Refreshes live Greeks for all open positions and flags positions
    that need to be rolled (delta < 65 rule or final week gamma risk).
    """

    def __init__(self, clients: AlpacaClients, repo: Repository, config: Dict[str, Any]):
        self.clients = clients
        self.repo = repo
        self.strategy = config.get("strategy", {})
        self.feed = config.get("alpaca", {}).get("feed", "indicative")

    def check_all_positions(self, today: date = None) -> List[Tuple[Dict, str]]:
        """
        Returns list of (position_dict, action) where action is:
          "hold"              - no action needed
          "roll_delta"        - delta dropped below min_delta
          "roll_final_week"   - entering final week of expiration
          "expired"           - past expiration date
        """
        if today is None:
            today = date.today()

        open_positions = self.repo.get_open_positions()
        if not open_positions:
            logger.info("No open positions to check")
            return []

        contract_symbols = [p["contract_symbol"] for p in open_positions]
        logger.info(f"Refreshing Greeks for {len(contract_symbols)} open position(s)")

        snapshots = fetch_snapshots(self.clients.options_data, contract_symbols, self.feed)

        results: List[Tuple[Dict, str]] = []

        for pos in open_positions:
            sym = pos["contract_symbol"]
            snap = snapshots.get(sym)

            if snap:
                data = snapshot_to_dict(sym, snap)
                current_delta = data.get("delta", pos.get("current_delta", 0))
                current_price = data.get("ask", data.get("last", pos.get("current_price", 0)))

                # Update DB with fresh data
                self.repo.update_position(pos["id"], {
                    "current_delta": current_delta,
                    "current_price": current_price,
                })
                pos["current_delta"] = current_delta
                pos["current_price"] = current_price
            else:
                logger.warning(f"No snapshot returned for {sym} — using stored values")
                current_delta = pos.get("current_delta") or pos.get("entry_delta", 0)

            # Determine action
            action = self._determine_action(pos, today)
            logger.info(
                f"  {sym} | d={pos.get('current_delta', 'N/A'):.3f} | "
                f"action={action}"
            )
            results.append((pos, action))

        return results

    def _determine_action(self, pos: Dict, today: date) -> str:
        min_delta = self.strategy.get("min_delta", 0.65)
        current_delta = pos.get("current_delta") or pos.get("entry_delta", 0)

        exp_str = pos.get("expiration_date", "")
        try:
            exp_date = date.fromisoformat(exp_str)
        except (ValueError, TypeError):
            logger.warning(f"Cannot parse expiration date '{exp_str}' for {pos['contract_symbol']}")
            return "hold"

        # Already expired
        if exp_date < today:
            return "expired"

        # Final week gamma risk
        if is_final_week(exp_date, today):
            return "roll_final_week"

        # 65 Delta Rule — roll back to 80
        if current_delta < min_delta:
            return "roll_delta"

        return "hold"
