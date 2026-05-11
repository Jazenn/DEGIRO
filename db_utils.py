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
    key_fields = ["date", "time", "isin", "description", "amount", "balance", "order_id"]
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
        if key == "history":
            try:
                with self._conn() as conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        cur.execute("SELECT data FROM degiro_history_snapshots WHERE key = %s", (key,))
                        row = cur.fetchone()
                        if row: return row["data"] or {}
            except Exception: pass
            return {}
            
        if key == "prices":
            try:
                with self._conn() as conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        cur.execute("SELECT ticker, live_price, prev_close, midnight_price, market_open, updated_at FROM degiro_price_snapshots")
                        rows = cur.fetchall()
                        if rows:
                            latest_ts = str(rows[0]["updated_at"])
                            res = {
                                "batch_live": {r["ticker"]: r["live_price"] for r in rows if r["live_price"] is not None},
                                "batch_prev": {r["ticker"]: r["prev_close"] for r in rows if r["prev_close"] is not None},
                                "batch_mid": {r["ticker"]: r["midnight_price"] for r in rows if r["midnight_price"] is not None},
                                "batch_open": {r["ticker"]: r["market_open"] for r in rows if r["market_open"] is not None},
                                "timestamp": latest_ts
                            }
                            return res
            except Exception: pass
            return {}
        return {}

    def save_snapshot(self, key: str, data: dict):
        """Sla een snapshot op (upsert)."""
        if key == "history":
            try:
                with self._conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO degiro_history_snapshots (key, data)
                            VALUES (%s, %s)
                            ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                        """, (key, json.dumps(data)))
            except Exception as e:
                st.error(f"DB: kan history snapshot niet opslaan: {e}")
            return

        if key == "prices":
            try:
                tickers = set()
                for subkey in ["batch_live", "batch_prev", "batch_mid", "batch_open"]:
                    if subkey in data:
                        tickers.update(data[subkey].keys())
                        
                records = []
                for t in tickers:
                    records.append((
                        t,
                        data.get("batch_live", {}).get(t),
                        data.get("batch_prev", {}).get(t),
                        data.get("batch_mid", {}).get(t),
                        data.get("batch_open", {}).get(t)
                    ))
                
                with self._conn() as conn:
                    with conn.cursor() as cur:
                        for rec in records:
                            cur.execute("""
                                INSERT INTO degiro_price_snapshots (ticker, live_price, prev_close, midnight_price, market_open, updated_at)
                                VALUES (%s, %s, %s, %s, %s, NOW())
                                ON CONFLICT (ticker) DO UPDATE SET 
                                    live_price = COALESCE(EXCLUDED.live_price, degiro_price_snapshots.live_price),
                                    prev_close = COALESCE(EXCLUDED.prev_close, degiro_price_snapshots.prev_close),
                                    midnight_price = COALESCE(EXCLUDED.midnight_price, degiro_price_snapshots.midnight_price),
                                    market_open = COALESCE(EXCLUDED.market_open, degiro_price_snapshots.market_open),
                                    updated_at = NOW()
                            """, rec)
            except Exception as e:
                st.error(f"DB: kan price snapshot niet opslaan: {e}")

    def clear_snapshot(self, key: str):
        """Verwijder een snapshot op basis van de key."""
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    if key == "history":
                        cur.execute("DELETE FROM degiro_history_snapshots WHERE key = %s", (key,))
                    elif key == "prices":
                        cur.execute("DELETE FROM degiro_price_snapshots")
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Config                                                               #
    # ------------------------------------------------------------------ #

    def load_config(self) -> dict:
        """Laad de portfolio-configuratie (assets, settings, mappings) uit relationele tabellen."""
        config = {"assets": {}, "settings": {}, "mappings": {}}
        try:
            with self._conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    # Settings
                    cur.execute("SELECT setting_key, setting_value FROM degiro_settings")
                    for row in cur.fetchall():
                        try:
                            config["settings"][row["setting_key"]] = float(row["setting_value"])
                        except ValueError:
                            config["settings"][row["setting_key"]] = row["setting_value"]
                            
                    # Mappings
                    cur.execute("SELECT mapping_key, ticker FROM degiro_mappings")
                    for row in cur.fetchall():
                        config["mappings"][row["mapping_key"]] = row["ticker"]
                        
                    # Assets
                    cur.execute("SELECT product_key, display_name, target_pct, t1_sell, t1_buy, buy_budget FROM degiro_assets")
                    for row in cur.fetchall():
                        asset = {
                            "target_pct": float(row["target_pct"]) if row["target_pct"] is not None else 0.0,
                            "display_name": row["display_name"]
                        }
                        if row["t1_sell"] is not None or row["t1_buy"] is not None:
                            asset["trading_strategy"] = {
                                "t1_sell": float(row["t1_sell"]) if row["t1_sell"] is not None else None,
                                "t1_buy": float(row["t1_buy"]) if row["t1_buy"] is not None else None,
                                "buy_budget": float(row["buy_budget"]) if row["buy_budget"] is not None else None
                            }
                        config["assets"][row["product_key"]] = asset
            return config
        except Exception as e:
            return config

    def save_config(self, data: dict):
        """Sla de portfolio-configuratie op (upsert in relationele tabellen)."""
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    # Settings
                    settings = data.get("settings", {})
                    for k, v in settings.items():
                        cur.execute("""
                            INSERT INTO degiro_settings (setting_key, setting_value)
                            VALUES (%s, %s)
                            ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = NOW()
                        """, (k, str(v)))
                        
                    # Mappings
                    mappings = data.get("mappings", {})
                    for k, v in mappings.items():
                        cur.execute("""
                            INSERT INTO degiro_mappings (mapping_key, ticker)
                            VALUES (%s, %s)
                            ON CONFLICT (mapping_key) DO UPDATE SET ticker = EXCLUDED.ticker, updated_at = NOW()
                        """, (k, str(v)))
                        
                    # Assets
                    assets = data.get("assets", {})
                    for k, v in assets.items():
                        t1_sell = None
                        t1_buy = None
                        buy_budget = None
                        ts = v.get("trading_strategy", {})
                        if ts:
                            t1_sell = ts.get("t1_sell")
                            t1_buy = ts.get("t1_buy")
                            buy_budget = ts.get("buy_budget")
                            
                        cur.execute("""
                            INSERT INTO degiro_assets (product_key, display_name, target_pct, t1_sell, t1_buy, buy_budget)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (product_key) DO UPDATE SET 
                                display_name = EXCLUDED.display_name,
                                target_pct = EXCLUDED.target_pct,
                                t1_sell = EXCLUDED.t1_sell,
                                t1_buy = EXCLUDED.t1_buy,
                                buy_budget = EXCLUDED.buy_budget,
                                updated_at = NOW()
                        """, (
                            k, 
                            v.get("display_name"), 
                            v.get("target_pct", 0.0), 
                            t1_sell, 
                            t1_buy, 
                            buy_budget
                        ))
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
