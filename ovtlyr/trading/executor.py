import logging
from datetime import datetime
from typing import Optional, Dict, Any

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass

from ovtlyr.utils.math_utils import compute_mid_price

logger = logging.getLogger(__name__)


class TradeExecutor:
    """Submit and track option orders via Alpaca. Supports dry_run mode."""

    def __init__(self, trading_client: TradingClient, config: Dict[str, Any]):
        self.client = trading_client
        self.execution = config.get("execution", {})
        self.dry_run: bool = self.execution.get("dry_run", True)
        self.order_type: str = self.execution.get("order_type", "limit")
        self.buffer: float = self.execution.get("limit_price_buffer", 0.02)

        if self.dry_run:
            logger.warning(
                "TradeExecutor running in DRY-RUN mode — no real orders will be placed"
            )

    def buy_to_open(
        self,
        contract_symbol: str,
        qty: int,
        bid: float,
        ask: float,
    ) -> Optional[Dict]:
        """
        Place a limit buy order.
        Limit price = mid + buffer to improve fill probability.
        """
        mid = compute_mid_price(bid, ask)
        limit_price = round(mid * (1 + self.buffer), 2)

        logger.info(
            f"BUY TO OPEN | {contract_symbol} x{qty} | "
            f"bid={bid:.2f} ask={ask:.2f} limit={limit_price:.2f}"
            + (" [DRY RUN]" if self.dry_run else "")
        )

        if self.dry_run:
            return {
                "id": f"dryrun-{datetime.utcnow().isoformat()}",
                "symbol": contract_symbol,
                "qty": qty,
                "side": "buy",
                "limit_price": limit_price,
                "status": "dry_run",
                "dry_run": True,
            }

        return self._submit_limit_order(
            contract_symbol, qty, OrderSide.BUY, limit_price
        )

    def sell_to_close(
        self,
        contract_symbol: str,
        qty: int,
        bid: float,
        ask: float,
    ) -> Optional[Dict]:
        """
        Place a limit sell order.
        Limit price = mid - buffer (slightly below mid to improve fill).
        """
        mid = compute_mid_price(bid, ask)
        limit_price = round(mid * (1 - self.buffer), 2)
        limit_price = max(limit_price, 0.01)

        logger.info(
            f"SELL TO CLOSE | {contract_symbol} x{qty} | "
            f"bid={bid:.2f} ask={ask:.2f} limit={limit_price:.2f}"
            + (" [DRY RUN]" if self.dry_run else "")
        )

        if self.dry_run:
            return {
                "id": f"dryrun-{datetime.utcnow().isoformat()}",
                "symbol": contract_symbol,
                "qty": qty,
                "side": "sell",
                "limit_price": limit_price,
                "status": "dry_run",
                "dry_run": True,
            }

        return self._submit_limit_order(
            contract_symbol, qty, OrderSide.SELL, limit_price
        )

    def sell_to_open(
        self,
        contract_symbol: str,
        qty: int,
        bid: float,
        ask: float,
    ) -> Optional[Dict]:
        """
        Place a limit sell order to open a CSP position.
        Limit price = mid - buffer (sell slightly below mid for CSP fill).
        """
        mid = compute_mid_price(bid, ask)
        limit_price = round(mid * (1 - self.buffer), 2)
        limit_price = max(limit_price, 0.01)

        logger.info(
            f"SELL TO OPEN (CSP) | {contract_symbol} x{qty} | "
            f"bid={bid:.2f} ask={ask:.2f} limit={limit_price:.2f}"
            + (" [DRY RUN]" if self.dry_run else "")
        )

        if self.dry_run:
            return {
                "id": f"dryrun-{datetime.utcnow().isoformat()}",
                "symbol": contract_symbol,
                "qty": qty,
                "side": "sell",
                "limit_price": limit_price,
                "status": "dry_run",
                "dry_run": True,
            }

        return self._submit_limit_order(
            contract_symbol, qty, OrderSide.SELL, limit_price
        )

    def buy_to_close(
        self,
        contract_symbol: str,
        qty: int,
        bid: float,
        ask: float,
    ) -> Optional[Dict]:
        """
        Place a limit buy order to close a CSP position.
        Limit price = mid + buffer (buy slightly above mid to close CSP).
        """
        mid = compute_mid_price(bid, ask)
        limit_price = round(mid * (1 + self.buffer), 2)

        logger.info(
            f"BUY TO CLOSE (CSP) | {contract_symbol} x{qty} | "
            f"bid={bid:.2f} ask={ask:.2f} limit={limit_price:.2f}"
            + (" [DRY RUN]" if self.dry_run else "")
        )

        if self.dry_run:
            return {
                "id": f"dryrun-{datetime.utcnow().isoformat()}",
                "symbol": contract_symbol,
                "qty": qty,
                "side": "buy",
                "limit_price": limit_price,
                "status": "dry_run",
                "dry_run": True,
            }

        return self._submit_limit_order(
            contract_symbol, qty, OrderSide.BUY, limit_price
        )

    def _submit_limit_order(
        self,
        symbol: str,
        qty: int,
        side: OrderSide,
        limit_price: float,
    ) -> Optional[Dict]:
        try:
            req = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY,
                limit_price=limit_price,
            )
            order = self.client.submit_order(req)
            logger.info(
                f"Order submitted: {order.id} | {symbol} {side} x{qty} @ {limit_price}"
            )
            return {
                "id": str(order.id),
                "symbol": symbol,
                "qty": qty,
                "side": side.value,
                "limit_price": limit_price,
                "status": order.status.value if order.status else "pending",
                "dry_run": False,
            }
        except Exception as e:
            logger.error(f"Failed to submit order for {symbol}: {e}")
            return None

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Poll Alpaca for current order status."""
        if order_id.startswith("dryrun-"):
            return {"id": order_id, "status": "filled", "dry_run": True}
        try:
            order = self.client.get_order_by_id(order_id)
            return {
                "id": str(order.id),
                "status": order.status.value,
                "filled_avg_price": float(order.filled_avg_price)
                if order.filled_avg_price
                else None,
            }
        except Exception as e:
            logger.error(f"Failed to fetch order {order_id}: {e}")
            return None
