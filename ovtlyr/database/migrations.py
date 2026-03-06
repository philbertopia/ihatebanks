import sqlite3
import logging
import os

from ovtlyr.database.models import ALL_DDL

logger = logging.getLogger(__name__)


def initialize_db(db_path: str) -> None:
    """Create all tables if they don't exist. Safe to run on every startup."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        for ddl in ALL_DDL:
            cursor.execute(ddl)
        conn.commit()
        logger.info(f"Database initialized at {db_path}")
    finally:
        conn.close()
