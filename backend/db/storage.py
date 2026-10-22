"""Database storage adapter maintaining backward compatibility for legacy DBStorage interface."""

from __future__ import annotations

import hashlib
import json
import math
import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import pandas as pd
import psycopg2
import psycopg2.extras

from backend.db.transaction_records import pack_transaction, unpack_transactions
from backend.db.connection import get_db_connection
from backend.ingestion.normalizer import compute_row_hash


def _safe_val(val: Any) -> Any:
    """Convert pandas/numpy types to JSON/SQL-serializable Python types."""
    if isinstance(val, pd.Timestamp):
        return val.isoformat() if not pd.isna(val) else None
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, float):
        return float(val)
    if isinstance(val, int):
        return int(val)
    if isinstance(val, (list, dict, tuple)):
        return val
    if pd.isna(val):
        return None
    return val


def _compute_row_hash(row: dict) -> str:
    """Canonical row hash computed via backend.ingestion.normalizer.compute_row_hash."""
    return compute_row_hash(
        date=str(row.get("date", "")).strip(),
        time=str(row.get("time", "")).strip(),
        isin=str(row.get("isin", "")).strip(),
        order_id=str(row.get("order_id", "")).strip(),
        amount=row.get("amount", 0.0),
        description=str(row.get("description", "")).strip(),
    )


def _compute_legacy_row_hash(row: dict) -> str:
    """Historical JSON-based row hash kept for backward compatibility with pre-migration Neon rows."""
    order_id = str(row.get("order_id", "")).strip()
    amount = str(row.get("amount", "")).strip()

    if order_id and order_id.lower() not in ("nan", "none", ""):
        isin = str(row.get("isin", "")).strip()
        key_data = {"order_id": order_id, "amount": amount, "isin": isin}
    else:
        desc = str(row.get("description", "")).strip()
        date = str(row.get("date", "")).strip()
        time = str(row.get("time", "")).strip()
        isin = str(row.get("isin", "")).strip()
        key_data = {"date": date, "time": time, "isin": isin, "description": desc, "amount": amount}

    return hashlib.md5(json.dumps(key_data, sort_keys=True).encode("utf-8")).hexdigest()


class DBStorage:
    """Unified PostgreSQL storage backend supporting transactions and snapshots."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL")

    @contextmanager
    def _conn(self):
        url = self.database_url or os.environ.get("DATABASE_URL")
        if not url:
            raise KeyError("DATABASE_URL is not configured in environment variables.")
        conn = psycopg2.connect(url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def load_transactions(self) -> pd.DataFrame:
        """Load stored transactions chronologically."""
        try:
            with self._conn() as conn:
                df = pd.read_sql(
                    """
                    SELECT id, row_hash, date::text as date, time, value_date::text as value_date,
                           product, isin, description, fx, amount, balance, order_id, csv_row_id, normalized_record
                    FROM degiro_transactions
                    ORDER BY date ASC, time ASC, csv_row_id DESC
                    """,
                    conn,
                )
                return unpack_transactions(df)
        except Exception:
            return pd.DataFrame()

    def save_transactions(self, df: pd.DataFrame) -> int:
        """Save normalized transactions to Neon with idempotency."""
        if df.empty:
            return 0

        df_save = df.copy()
        for col in ["date", "value_date"]:
            if col in df_save.columns and pd.api.types.is_datetime64_any_dtype(df_save[col]):
                df_save[col] = df_save[col].dt.strftime("%Y-%m-%d").where(
                    df_save[col].notna(), None
                )

        records = []
        for _, row in df_save.iterrows():
            rec = {k: _safe_val(v) for k, v in row.items()}
            if not rec.get("row_hash"):
                rec["row_hash"] = _compute_row_hash(rec)
            records.append(rec)

        if not records:
            return 0

        cols = list(pack_transaction(records[0]).keys())
        placeholders = ", ".join([f"%({c})s" for c in cols])
        col_names = ", ".join(cols)

        sql = f"""
            INSERT INTO degiro_transactions ({col_names})
            VALUES ({placeholders})
            ON CONFLICT (row_hash) DO NOTHING
        """

        inserted = 0
        legacy_hash_by_row_hash = {
            rec["row_hash"]: legacy_hash
            for rec in records
            if (legacy_hash := _compute_legacy_row_hash(rec)) != rec["row_hash"]
        }
        with self._conn() as conn:
            with conn.cursor() as cur:
                existing_legacy_hashes = set()
                if legacy_hash_by_row_hash:
                    cur.execute(
                        "SELECT row_hash FROM degiro_transactions WHERE row_hash = ANY(%s)",
                        (list(legacy_hash_by_row_hash.values()),),
                    )
                    existing_legacy_hashes = {row[0] for row in cur.fetchall()}

                for rec in records:
                    if legacy_hash_by_row_hash.get(rec["row_hash"]) in existing_legacy_hashes:
                        if rec.get("identity_version") == "execution-v2":
                            raise ValueError("legacy_identity_requires_review: reconcile prior collapsed executions before migration")
                        continue
                    cur.execute(sql, pack_transaction(rec))
                    inserted += cur.rowcount

        return inserted

    def clear_transactions(self) -> None:
        """Clear all transactions."""
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM degiro_transactions")
        except Exception:
            pass

    def save_portfolio_snapshots(
        self, history: pd.DataFrame, holdings: pd.DataFrame
    ) -> None:
        """Atomically replace the current holdings and upsert portfolio history."""
        history_columns = [
            "date",
            "total_equity_eur",
            "invested_capital_eur",
            "cash_balance_eur",
            "unrealized_pnl_eur",
            "unrealized_pnl_pct",
        ]
        holding_columns = [
            "symbol",
            "name",
            "isin",
            "shares_held",
            "current_price_eur",
            "total_value_eur",
            "total_cost_eur",
            "unrealized_pnl_eur",
            "actual_pct",
            "target_pct",
            "drift_pct",
            "recommended_action_eur",
        ]

        history_rows = []
        for record in history.reindex(columns=history_columns).to_dict(orient="records"):
            safe_record = {key: _safe_val(value) for key, value in record.items()}
            safe_record["date"] = pd.Timestamp(safe_record["date"]).date()
            history_rows.append(safe_record)

        holding_rows = [
            {key: _safe_val(value) for key, value in record.items()}
            for record in holdings.reindex(columns=holding_columns).to_dict(orient="records")
        ]

        with self._conn() as conn:
            with conn.cursor() as cur:
                for record in history_rows:
                    cur.execute(
                        """
                        INSERT INTO portfolio_daily_history (
                            date, total_equity_eur, invested_capital_eur,
                            cash_balance_eur, unrealized_pnl_eur, unrealized_pnl_pct
                        ) VALUES (
                            %(date)s, %(total_equity_eur)s, %(invested_capital_eur)s,
                            %(cash_balance_eur)s, %(unrealized_pnl_eur)s, %(unrealized_pnl_pct)s
                        )
                        ON CONFLICT (date) DO UPDATE SET
                            total_equity_eur = EXCLUDED.total_equity_eur,
                            invested_capital_eur = EXCLUDED.invested_capital_eur,
                            cash_balance_eur = EXCLUDED.cash_balance_eur,
                            unrealized_pnl_eur = EXCLUDED.unrealized_pnl_eur,
                            unrealized_pnl_pct = EXCLUDED.unrealized_pnl_pct,
                            updated_at = NOW()
                        """,
                        record,
                    )

                cur.execute("DELETE FROM current_asset_holdings")
                for record in holding_rows:
                    cur.execute(
                        """
                        INSERT INTO current_asset_holdings (
                            symbol, name, isin, shares_held, current_price_eur,
                            total_value_eur, total_cost_eur, unrealized_pnl_eur,
                            actual_pct, target_pct, drift_pct, recommended_action_eur
                        ) VALUES (
                            %(symbol)s, %(name)s, %(isin)s, %(shares_held)s, %(current_price_eur)s,
                            %(total_value_eur)s, %(total_cost_eur)s, %(unrealized_pnl_eur)s,
                            %(actual_pct)s, %(target_pct)s, %(drift_pct)s, %(recommended_action_eur)s
                        )
                        """,
                        record,
                    )
