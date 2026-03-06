"""SQLite schema definitions as SQL strings."""

POSITIONS_DDL = """
CREATE TABLE IF NOT EXISTS positions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    underlying              TEXT NOT NULL,
    contract_symbol         TEXT NOT NULL UNIQUE,
    option_type             TEXT NOT NULL DEFAULT 'call',
    strike                  REAL NOT NULL,
    expiration_date         TEXT NOT NULL,
    qty                     INTEGER NOT NULL DEFAULT 1,
    entry_price             REAL NOT NULL,
    entry_date              TEXT NOT NULL,
    entry_delta             REAL,
    entry_extrinsic_pct     REAL,
    entry_underlying_price  REAL,
    current_delta           REAL,
    current_price           REAL,
    status                  TEXT NOT NULL DEFAULT 'open',
    close_date              TEXT,
    close_price             REAL,
    close_reason            TEXT,
    realized_pnl            REAL,
    alpaca_order_id         TEXT,
    notes                   TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

TRADES_DDL = """
CREATE TABLE IF NOT EXISTS trades (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id                 INTEGER REFERENCES positions(id),
    trade_type                  TEXT NOT NULL,
    contract_symbol             TEXT NOT NULL,
    underlying                  TEXT NOT NULL,
    side                        TEXT NOT NULL,
    qty                         INTEGER NOT NULL,
    price                       REAL NOT NULL,
    commission                  REAL DEFAULT 0,
    delta_at_trade              REAL,
    underlying_price_at_trade   REAL,
    alpaca_order_id             TEXT,
    status                      TEXT DEFAULT 'pending',
    trade_date                  TEXT NOT NULL DEFAULT (datetime('now')),
    notes                       TEXT
)
"""

SCAN_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS scan_results (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_date           TEXT NOT NULL,
    underlying          TEXT NOT NULL,
    contract_symbol     TEXT NOT NULL,
    strike              REAL NOT NULL,
    expiration_date     TEXT NOT NULL,
    dte                 INTEGER NOT NULL,
    delta               REAL NOT NULL,
    ask                 REAL NOT NULL,
    bid                 REAL NOT NULL,
    spread_pct          REAL NOT NULL,
    open_interest       INTEGER,
    extrinsic_value     REAL NOT NULL,
    extrinsic_pct       REAL NOT NULL,
    implied_volatility  REAL,
    score               REAL,
    action_taken        TEXT DEFAULT 'none',
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

DAILY_STATS_DDL = """
CREATE TABLE IF NOT EXISTS daily_stats (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_date               TEXT NOT NULL UNIQUE,
    open_positions          INTEGER DEFAULT 0,
    positions_rolled        INTEGER DEFAULT 0,
    positions_closed        INTEGER DEFAULT 0,
    positions_opened        INTEGER DEFAULT 0,
    total_pnl_unrealized    REAL DEFAULT 0,
    total_pnl_realized      REAL DEFAULT 0,
    portfolio_delta         REAL DEFAULT 0,
    notes                   TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

ALL_DDL = [POSITIONS_DDL, TRADES_DDL, SCAN_RESULTS_DDL, DAILY_STATS_DDL]
