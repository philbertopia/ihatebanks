import logging
from datetime import date, datetime
from typing import Dict, Any, Optional, Tuple

from ovtlyr.api.client import AlpacaClients
from ovtlyr.api.options_data import fetch_snapshots, snapshot_to_dict
from ovtlyr.database.repository import Repository
from ovtlyr.trading.executor import TradeExecutor

logger = logging.getLogger(__name__)


class PositionRoller:
    """
    Rolls a position that has triggered the 65-delta rule or final-week rule.
    Closes the existing position and opens a new one at ~80 delta.
    """

    def __init__(
        self,
        clients: AlpacaClients,
        executor: TradeExecutor,
        repo: Repository,
        config: Dict[str, Any],
    ):
        self.clients = clients
        self.executor = executor
        self.repo = repo
        self.config = config
        self.feed = config.get("alpaca", {}).get("feed", "indicative")

    def roll_position(
        self,
        position: Dict,
        replacement: Optional[Dict],
        roll_reason: str,
    ) -> bool:
        """
        Execute a roll:
        1. Sell to close the existing position
        2. Buy to open the replacement
        3. Update database records

        Returns True on success (or dry_run success).
        """
        old_sym = position["contract_symbol"]
        underlying = position["underlying"]
        qty = position["qty"]

        # ── Step 1: Get current quote for the old position ──
        old_snap = fetch_snapshots(self.clients.options_data, [old_sym], self.feed)
        old_data = snapshot_to_dict(old_sym, old_snap[old_sym]) if old_sym in old_snap else {}
        old_bid = old_data.get("bid", position.get("current_price", 0))
        old_ask = old_data.get("ask", old_bid)

        if old_bid <= 0:
            logger.error(f"Cannot roll {old_sym}: zero bid price")
            return False

        # ── Step 2: Sell to close old position ──
        close_order = self.executor.sell_to_close(old_sym, qty, old_bid, old_ask)
        if close_order is None:
            logger.error(f"Roll failed: could not close {old_sym}")
            return False

        close_price = close_order.get("limit_price", old_bid)
        realized_pnl = self.repo.mark_position_rolled(position["id"], close_price)

        self.repo.insert_trade({
            "position_id": position["id"],
            "trade_type": "roll_close",
            "contract_symbol": old_sym,
            "underlying": underlying,
            "side": "sell",
            "qty": qty,
            "price": close_price,
            "delta_at_trade": position.get("current_delta"),
            "alpaca_order_id": close_order.get("id"),
            "status": "filled" if close_order.get("dry_run") else "pending",
            "notes": f"Roll reason: {roll_reason}",
        })

        logger.info(
            f"ROLLED CLOSE | {old_sym} | price={close_price:.2f} | "
            f"realized_pnl=${realized_pnl:.2f}"
        )

        # ── Step 3: Open replacement (if found) ──
        if replacement is None:
            logger.warning(f"No replacement found for {underlying} — position closed without re-entry")
            return True

        new_sym = replacement["contract_symbol"]
        new_ask = replacement["ask"]
        new_bid = replacement["bid"]

        open_order = self.executor.buy_to_open(new_sym, qty, new_bid, new_ask)
        if open_order is None:
            logger.error(f"Roll partially failed: could not open replacement {new_sym}")
            return False

        entry_price = open_order.get("limit_price", new_ask)

        new_position_id = self.repo.insert_position({
            "underlying": underlying,
            "contract_symbol": new_sym,
            "option_type": replacement.get("option_type", "call"),
            "strike": replacement["strike"],
            "expiration_date": replacement["expiration_date"],
            "qty": qty,
            "entry_price": entry_price,
            "entry_date": datetime.utcnow().isoformat(),
            "entry_delta": replacement.get("delta"),
            "entry_extrinsic_pct": replacement.get("extrinsic_pct"),
            "entry_underlying_price": replacement.get("underlying_price"),
            "current_delta": replacement.get("delta"),
            "current_price": entry_price,
            "status": "open",
            "alpaca_order_id": open_order.get("id"),
            "notes": f"Rolled from {old_sym} ({roll_reason})",
        })

        self.repo.insert_trade({
            "position_id": new_position_id,
            "trade_type": "roll_open",
            "contract_symbol": new_sym,
            "underlying": underlying,
            "side": "buy",
            "qty": qty,
            "price": entry_price,
            "delta_at_trade": replacement.get("delta"),
            "underlying_price_at_trade": replacement.get("underlying_price"),
            "alpaca_order_id": open_order.get("id"),
            "status": "filled" if open_order.get("dry_run") else "pending",
            "notes": f"Roll open replacing {old_sym}",
        })

        logger.info(
            f"ROLLED OPEN   | {new_sym} | d={replacement.get('delta'):.2f} | "
            f"price={entry_price:.2f}"
        )
        return True
