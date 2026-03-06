import sqlite3
import logging
from datetime import datetime, date, timezone
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Whitelisted columns per table — prevents SQL injection via dynamic INSERT keys
_POSITION_COLS = frozenset({
    "underlying", "contract_symbol", "option_type", "strike", "expiration_date",
    "qty", "entry_price", "entry_date", "entry_delta", "entry_extrinsic_pct",
    "entry_underlying_price", "current_delta", "current_price", "status",
    "close_date", "close_price", "close_reason", "realized_pnl",
    "alpaca_order_id", "notes", "updated_at",
})

_TRADE_COLS = frozenset({
    "position_id", "trade_type", "contract_symbol", "underlying", "side",
    "qty", "price", "commission", "delta_at_trade", "underlying_price_at_trade",
    "alpaca_order_id", "status", "trade_date", "notes",
})

_SCAN_RESULT_COLS = frozenset({
    "scan_date", "underlying", "contract_symbol", "strike", "expiration_date",
    "dte", "delta", "ask", "bid", "spread_pct", "open_interest",
    "extrinsic_value", "extrinsic_pct", "implied_volatility", "score", "action_taken",
})

_DAILY_STATS_COLS = frozenset({
    "stat_date", "open_positions", "positions_rolled", "positions_closed",
    "positions_opened", "total_pnl_unrealized", "total_pnl_realized",
    "portfolio_delta", "notes",
})


def _check_cols(data: Dict, allowed: frozenset, table: str) -> None:
    unknown = set(data.keys()) - allowed
    if unknown:
        raise ValueError(f"Unknown columns for {table}: {unknown}")


class Repository:
    """All database read/write operations."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ──────────────── POSITIONS ────────────────

    def insert_position(self, data: Dict[str, Any]) -> int:
        data.setdefault("entry_date", datetime.now(timezone.utc).isoformat())
        data.setdefault("status", "open")
        _check_cols(data, _POSITION_COLS, "positions")
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        sql = f"INSERT INTO positions ({cols}) VALUES ({placeholders})"
        with self._connect() as conn:
            cur = conn.execute(sql, list(data.values()))
            conn.commit()
            return cur.lastrowid

    def update_position(self, position_id: int, updates: Dict[str, Any]) -> None:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        sql = f"UPDATE positions SET {set_clause} WHERE id = ?"
        with self._connect() as conn:
            conn.execute(sql, list(updates.values()) + [position_id])
            conn.commit()

    def get_open_positions(self) -> List[Dict]:
        sql = "SELECT * FROM positions WHERE status = 'open' ORDER BY entry_date"
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]

    def get_position_by_symbol(self, contract_symbol: str) -> Optional[Dict]:
        sql = "SELECT * FROM positions WHERE contract_symbol = ?"
        with self._connect() as conn:
            row = conn.execute(sql, (contract_symbol,)).fetchone()
        return dict(row) if row else None

    def get_open_position_by_underlying(self, underlying: str) -> Optional[Dict]:
        sql = "SELECT * FROM positions WHERE underlying = ? AND status = 'open' LIMIT 1"
        with self._connect() as conn:
            row = conn.execute(sql, (underlying,)).fetchone()
        return dict(row) if row else None

    def close_position(self, position_id: int, close_price: float, reason: str) -> float:
        """Close a position, compute and store realized PnL. Returns realized PnL."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT entry_price, qty FROM positions WHERE id = ?", (position_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Position {position_id} not found")
            entry_price, qty = row["entry_price"], row["qty"]
            realized_pnl = (close_price - entry_price) * qty * 100
            conn.execute(
                """UPDATE positions SET status='closed', close_date=?, close_price=?,
                   close_reason=?, realized_pnl=?, updated_at=? WHERE id=?""",
                (now, close_price, reason, realized_pnl, now, position_id),
            )
            conn.commit()
        return realized_pnl

    def mark_position_rolled(self, position_id: int, close_price: float) -> float:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT entry_price, qty FROM positions WHERE id = ?", (position_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Position {position_id} not found")
            realized_pnl = (close_price - row["entry_price"]) * row["qty"] * 100
            conn.execute(
                """UPDATE positions SET status='rolled', close_date=?, close_price=?,
                   close_reason='rolled', realized_pnl=?, updated_at=? WHERE id=?""",
                (now, close_price, realized_pnl, now, position_id),
            )
            conn.commit()
        return realized_pnl

    # ──────────────── TRADES ────────────────

    def insert_trade(self, data: Dict[str, Any]) -> int:
        data.setdefault("trade_date", datetime.now(timezone.utc).isoformat())
        _check_cols(data, _TRADE_COLS, "trades")
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        sql = f"INSERT INTO trades ({cols}) VALUES ({placeholders})"
        with self._connect() as conn:
            cur = conn.execute(sql, list(data.values()))
            conn.commit()
            return cur.lastrowid

    def update_trade_status(self, trade_id: int, status: str, fill_price: float = None) -> None:
        updates: Dict[str, Any] = {"status": status}
        if fill_price is not None:
            updates["price"] = fill_price
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        sql = f"UPDATE trades SET {set_clause} WHERE id = ?"
        with self._connect() as conn:
            conn.execute(sql, list(updates.values()) + [trade_id])
            conn.commit()

    def get_trades_for_position(self, position_id: int) -> List[Dict]:
        sql = "SELECT * FROM trades WHERE position_id = ? ORDER BY trade_date"
        with self._connect() as conn:
            rows = conn.execute(sql, (position_id,)).fetchall()
        return [dict(r) for r in rows]

    # ──────────────── SCAN RESULTS ────────────────

    def insert_scan_result(self, data: Dict[str, Any]) -> int:
        data.setdefault("scan_date", date.today().isoformat())
        _check_cols(data, _SCAN_RESULT_COLS, "scan_results")
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        sql = f"INSERT INTO scan_results ({cols}) VALUES ({placeholders})"
        with self._connect() as conn:
            cur = conn.execute(sql, list(data.values()))
            conn.commit()
            return cur.lastrowid

    def get_scan_results_for_date(self, scan_date: str) -> List[Dict]:
        sql = "SELECT * FROM scan_results WHERE scan_date = ? ORDER BY score DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, (scan_date,)).fetchall()
        return [dict(r) for r in rows]

    def mark_scan_result_opened(self, scan_result_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE scan_results SET action_taken='opened' WHERE id=?",
                (scan_result_id,),
            )
            conn.commit()

    # ──────────────── DAILY STATS ────────────────

    def upsert_daily_stats(self, data: Dict[str, Any]) -> None:
        data.setdefault("stat_date", date.today().isoformat())
        _check_cols(data, _DAILY_STATS_COLS, "daily_stats")
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        sql = (
            f"INSERT INTO daily_stats ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(stat_date) DO UPDATE SET "
            + ", ".join(f"{k}=excluded.{k}" for k in data if k != "stat_date")
        )
        with self._connect() as conn:
            conn.execute(sql, list(data.values()))
            conn.commit()

    # ──────────────── AGGREGATES ────────────────

    def get_pnl_summary(self, start_date: str = None, end_date: str = None) -> Dict:
        where = ""
        params: list = []
        if start_date:
            where += " AND close_date >= ?"
            params.append(start_date)
        if end_date:
            where += " AND close_date <= ?"
            params.append(end_date)

        sql = f"""
            SELECT
                COUNT(*) as total_closed,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winners,
                SUM(CASE WHEN realized_pnl <= 0 THEN 1 ELSE 0 END) as losers,
                SUM(realized_pnl) as total_realized_pnl,
                SUM(CASE WHEN realized_pnl > 0 THEN realized_pnl ELSE 0 END) as gross_profit,
                SUM(CASE WHEN realized_pnl <= 0 THEN realized_pnl ELSE 0 END) as gross_loss,
                AVG(realized_pnl) as avg_pnl
            FROM positions
            WHERE status IN ('closed', 'rolled') {where}
        """
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
        result = dict(row) if row else {}

        # Unrealized PnL from open positions
        open_rows = self.get_open_positions()
        unrealized = sum(
            (p.get("current_price", p["entry_price"]) - p["entry_price"]) * p["qty"] * 100
            for p in open_rows
        )
        result["total_unrealized_pnl"] = unrealized
        result["open_positions"] = len(open_rows)

        total = result.get("total_closed", 0) or 0
        winners = result.get("winners", 0) or 0
        result["win_rate"] = (winners / total * 100) if total > 0 else 0.0

        gross_profit = result.get("gross_profit", 0) or 0
        gross_loss = abs(result.get("gross_loss", 0) or 0)
        result["profit_factor"] = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        return result

    def get_all_closed_trades_for_backtest(self) -> List[Dict]:
        sql = "SELECT * FROM positions WHERE status IN ('closed', 'rolled') ORDER BY close_date"
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
