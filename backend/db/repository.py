"""Transaction repository for Neon PostgreSQL degiro_transactions table."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd
import psycopg2.extras

from backend.db.connection import get_db_connection

logger = logging.getLogger(__name__)

INSERT_TX_SQL = """
INSERT INTO degiro_transactions (
    row_hash, date, time, value_date, product, isin,
    description, fx, amount, balance, order_id, csv_row_id
) VALUES (
    %(row_hash)s, %(date)s, %(time)s, %(value_date)s, %(product)s, %(isin)s,
    %(description)s, %(fx)s, %(amount)s, %(balance)s, %(order_id)s, %(csv_row_id)s
)
ON CONFLICT (row_hash) DO NOTHING
"""


class TransactionRepository:
    """Manages transaction persistence in degiro_transactions table."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = database_url

    def save_transactions(self, df: pd.DataFrame) -> Tuple[int, int]:
        """Save normalized transactions to Neon with idempotency.

        Returns: (inserted_count, skipped_count)
        """
        if df.empty:
            return 0, 0

        # Check existing hashes to accurately report inserted vs skipped
        hashes = [str(h) for h in df["row_hash"].tolist() if pd.notna(h)]
        existing_hashes = set()

        with get_db_connection(self.database_url) as conn:
            with conn.cursor() as cur:
                if hashes:
                    cur.execute(
                        "SELECT row_hash FROM degiro_transactions WHERE row_hash = ANY(%s)",
                        (hashes,),
                    )
                    existing_hashes = {row[0] for row in cur.fetchall()}

                new_rows = []
                skipped_count = 0
                for _, row in df.iterrows():
                    h = str(row.get("row_hash") or "")
                    if h in existing_hashes:
                        skipped_count += 1
                        continue

                    # Format date properly
                    d = row.get("date")
                    vd = row.get("value_date") or d

                    new_rows.append({
                        "row_hash": h,
                        "date": str(d) if d else None,
                        "time": str(row.get("time") or ""),
                        "value_date": str(vd) if vd else None,
                        "product": str(row.get("product") or ""),
                        "isin": str(row.get("isin") or ""),
                        "description": str(row.get("description") or ""),
                        "fx": float(row.get("fx") or 0.0),
                        "amount": float(row.get("amount") or 0.0),
                        "balance": float(row.get("balance") or 0.0),
                        "order_id": str(row.get("order_id") or ""),
                        "csv_row_id": int(row.get("csv_row_id") or 0),
                    })

                if new_rows:
                    psycopg2.extras.execute_batch(cur, INSERT_TX_SQL, new_rows)

        inserted_count = len(new_rows)
        return inserted_count, skipped_count

    def load_transactions(self) -> pd.DataFrame:
        """Load all stored transactions ordered chronologically."""
        with get_db_connection(self.database_url) as conn:
            df = pd.read_sql(
                """
                SELECT id, row_hash, date::text as date, time, value_date::text as value_date,
                       product, isin, description, fx, amount, balance, order_id, csv_row_id
                FROM degiro_transactions
                ORDER BY date ASC, time ASC, csv_row_id DESC
                """,
                conn,
            )
        return df

    def clear_transactions(self) -> None:
        """Truncate all stored transactions."""
        with get_db_connection(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM degiro_transactions")
