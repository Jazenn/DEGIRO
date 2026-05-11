"""
db_utils.py — PostgreSQL storage backend voor DEGIRO Dashboard.

Provider-agnostisch: werkt met Neon, Supabase, Railway, of elke andere
PostgreSQL provider. Alleen een DATABASE_URL is nodig.

Vereiste tabellen: zie setup_db.sql
"""

import hashlib
import json
import math
import os
import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st
from contextlib import contextmanager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_secret(key: str) -> str:
    """Lees een secret uit env vars of Streamlit secrets."""
    if key in os.environ:
        return os.environ[key]
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    raise KeyError(f"Secret '{key}' niet gevonden in env vars of Streamlit secrets.")


def _compute_row_hash(row: dict) -> str:
    """Deterministisch MD5-hash voor deduplicatie op DB niveau."""
    key_fields = ["date", "time", "isin", "description", "amount", "order_id"]
    key_data = {k: str(row.get(k, "") or "").strip() for k in key_fields}
    return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()


def _safe_val(val):
    """Converteer pandas/numpy types naar JSON-serialiseerbare Python types."""
    if isinstance(val, pd.Timestamp):
        return val.isoformat() if not pd.isna(val) else None
    if isinstance(val, float) and math.isnan(val):
        return None
    if hasattr(val, "item"):   # numpy scalar
        return val.item()
    return val


# ---------------------------------------------------------------------------
# DBStorage
# ---------------------------------------------------------------------------

class DBStorage:
    """
    PostgreSQL storage backend voor DEGIRO Dashboard.
    Werkt met elke PostgreSQL provider via een DATABASE_URL.

    Alle tabellen hebben een 'degiro_' prefix zodat ze veilig naast andere
    projecten in dezelfde database kunnen bestaan.

    Interface:
      load_transactions()      -> pd.DataFrame
      save_transactions(df)    -> int (aantal nieuw ingevoegde rijen)
      clear_transactions()
      load_snapshot(key)       -> dict
      save_snapshot(key, data)
      clear_snapshot(key)
      load_config()            -> dict
      save_config(data)
      load_history_df()        -> pd.DataFrame
      save_history_df(df)
    """

    def __init__(self):
        self._dsn = _get_secret("DATABASE_URL")

    @contextmanager
    def _conn(self):
        """Context manager die automatisch commit/rollback en close doet."""
        conn = psycopg2.connect(self._dsn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Transactions                                                         #
    # ------------------------------------------------------------------ #

    def load_transactions(self) -> pd.DataFrame:
        """Haal alle transacties op als DataFrame."""
        try:
            with self._conn() as conn:
                df = pd.read_sql(
                    "SELECT * FROM degiro_transactions ORDER BY date, time, csv_row_id",
                    conn
                )
        except Exception as e:
            st.error(f"DB: kan transacties niet laden: {e}")
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        # Verwijder interne DB kolommen
        for col in ["id", "row_hash", "created_at"]:
            if col in df.columns:
                df = df.drop(columns=[col])

        # Zorg voor correcte types
        for col in ["date", "value_date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        for col in ["amount", "balance", "fx"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        return df

    def save_transactions(self, df: pd.DataFrame) -> int:
        """
        UPSERT transacties — bestaande rijen (op row_hash) worden overgeslagen.
        Geeft aantal nieuw ingevoegde rijen terug.
        """
        if df.empty:
            return 0

        keep_cols = [
            "date", "time", "value_date", "product", "isin",
            "description", "fx", "amount", "balance", "order_id", "csv_row_id"
        ]
        df_save = df[[c for c in keep_cols if c in df.columns]].copy()

        # Converteer datum kolommen naar strings
        for col in ["date", "value_date"]:
            if col in df_save.columns:
                df_save[col] = pd.to_datetime(df_save[col], errors="coerce")
                df_save[col] = df_save[col].dt.strftime("%Y-%m-%d").where(
                    df_save[col].notna(), None
                )

        records = []
        for _, row in df_save.iterrows():
            rec = {k: _safe_val(v) for k, v in row.items()}
            rec["row_hash"] = _compute_row_hash(rec)
            records.append(rec)

        if not records:
            return 0

        cols = list(records[0].keys())
        placeholders = ", ".join([f"%({c})s" for c in cols])
        col_names = ", ".join(cols)

        sql = f"""
            INSERT INTO degiro_transactions ({col_names})
            VALUES ({placeholders})
            ON CONFLICT (row_hash) DO NOTHING
        """

        inserted = 0
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    for rec in records:
                        cur.execute(sql, rec)
                        inserted += cur.rowcount
        except Exception as e:
            st.error(f"DB: kan transacties niet opslaan: {e}")

        return inserted

    def clear_transactions(self):
        """Verwijder alle transacties."""
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM degiro_transactions")
        except Exception as e:
            st.error(f"DB: kan transacties niet wissen: {e}")

    # ------------------------------------------------------------------ #
    # Snapshots (koersen, geschiedenis)                                   #
    # ------------------------------------------------------------------ #

    def load_snapshot(self, key: str) -> dict:
        """Laad een JSON-snapshot op basis van de key ('prices', 'history')."""
        try:
            with self._conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT data FROM degiro_snapshots WHERE key = %s", (key,)
                    )
                    row = cur.fetchone()
                    if row:
                        return row["data"] or {}
        except Exception:
            pass
        return {}

    def save_snapshot(self, key: str, data: dict):
        """Sla een JSON-snapshot op (upsert)."""
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO degiro_snapshots (key, data)
                        VALUES (%s, %s)
                        ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data,
                                                        updated_at = NOW()
                    """, (key, json.dumps(data)))
        except Exception as e:
            st.error(f"DB: kan snapshot '{key}' niet opslaan: {e}")

    def clear_snapshot(self, key: str):
        """Verwijder een snapshot op basis van de key."""
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM degiro_snapshots WHERE key = %s", (key,))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Config                                                               #
    # ------------------------------------------------------------------ #

    def load_config(self) -> dict:
        """Laad de portfolio-configuratie (assets, settings, mappings)."""
        try:
            with self._conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT value FROM degiro_config WHERE key = 'target_config'"
                    )
                    row = cur.fetchone()
                    if row:
                        return row["value"] or {}
        except Exception:
            pass
        return {}

    def save_config(self, data: dict):
        """Sla de portfolio-configuratie op (upsert)."""
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO degiro_config (key, value)
                        VALUES ('target_config', %s)
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value,
                                                        updated_at = NOW()
                    """, (json.dumps(data),))
        except Exception as e:
            st.error(f"DB: kan config niet opslaan: {e}")

    # ------------------------------------------------------------------ #
    # History DataFrame helpers (gebruikt door fetcher)                   #
    # ------------------------------------------------------------------ #

    def load_history_df(self) -> pd.DataFrame:
        """Laad portfolio-geschiedenis als DataFrame vanuit 'history' snapshot."""
        data = self.load_snapshot("history")
        if not data or "records" not in data:
            return pd.DataFrame()
        try:
            df = pd.DataFrame(data["records"])
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()

    def save_history_df(self, df: pd.DataFrame):
        """Sla portfolio-geschiedenis op als JSON-snapshot."""
        if df.empty:
            return
        df_copy = df.copy()
        # Converteer timestamps voor JSON-serialisatie
        for col in df_copy.select_dtypes(
            include=["datetime64[ns]", "datetime64[ns, UTC]"]
        ).columns:
            df_copy[col] = df_copy[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
        records = df_copy.where(df_copy.notna(), None).to_dict(orient="records")
        self.save_snapshot("history", {"records": records})
