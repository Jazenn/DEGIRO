"""Snapshot repository for portfolio_daily_history, current_asset_holdings, and price tables."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
import pandas as pd
import psycopg2.extras

from backend.db.connection import get_db_connection

logger = logging.getLogger(__name__)

UPSERT_HISTORY_SQL = """
INSERT INTO portfolio_daily_history (
    date, total_equity_eur, invested_capital_eur,
    cash_balance_eur, unrealized_pnl_eur, unrealized_pnl_pct, updated_at
) VALUES (
    %(date)s, %(total_equity_eur)s, %(invested_capital_eur)s,
    %(cash_balance_eur)s, %(unrealized_pnl_eur)s, %(unrealized_pnl_pct)s, NOW()
)
ON CONFLICT (date) DO UPDATE SET
    total_equity_eur = EXCLUDED.total_equity_eur,
    invested_capital_eur = EXCLUDED.invested_capital_eur,
    cash_balance_eur = EXCLUDED.cash_balance_eur,
    unrealized_pnl_eur = EXCLUDED.unrealized_pnl_eur,
    unrealized_pnl_pct = EXCLUDED.unrealized_pnl_pct,
    updated_at = NOW()
"""

INSERT_HOLDING_SQL = """
INSERT INTO current_asset_holdings (
    symbol, name, isin, shares_held, current_price_eur,
    total_value_eur, total_cost_eur, unrealized_pnl_eur,
    actual_pct, target_pct, drift_pct, recommended_action_eur, updated_at
) VALUES (
    %(symbol)s, %(name)s, %(isin)s, %(shares_held)s, %(current_price_eur)s,
    %(total_value_eur)s, %(total_cost_eur)s, %(unrealized_pnl_eur)s,
    %(actual_pct)s, %(target_pct)s, %(drift_pct)s, %(recommended_action_eur)s, NOW()
)
"""


class SnapshotRepository:
    """Manages pre-aggregated snapshot persistence for frontend reads."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = database_url

    def save_portfolio_snapshots(
        self,
        history_df: pd.DataFrame,
        holdings_df: pd.DataFrame,
    ) -> None:
        """Atomically persist daily equity history and current holdings snapshots."""
        history_records = history_df.to_dict(orient="records") if not history_df.empty else []
        holding_records = holdings_df.to_dict(orient="records") if not holdings_df.empty else []

        with get_db_connection(self.database_url) as conn:
            with conn.cursor() as cur:
                if history_records:
                    psycopg2.extras.execute_batch(cur, UPSERT_HISTORY_SQL, history_records)

                # Replace current holdings table
                cur.execute("DELETE FROM current_asset_holdings")
                if holding_records:
                    psycopg2.extras.execute_batch(cur, INSERT_HOLDING_SQL, holding_records)

    def load_holdings(self) -> pd.DataFrame:
        """Load current asset holdings snapshot."""
        with get_db_connection(self.database_url) as conn:
            return pd.read_sql(
                "SELECT * FROM current_asset_holdings ORDER BY total_value_eur DESC",
                conn,
            )

    def load_equity_history(self) -> pd.DataFrame:
        """Load historical daily equity snapshot."""
        with get_db_connection(self.database_url) as conn:
            return pd.read_sql(
                "SELECT * FROM portfolio_daily_history ORDER BY date ASC",
                conn,
            )

    def save_price_snapshots(self, quotes: Dict[str, Dict[str, float]]) -> None:
        """Save price snapshots for tickers into degiro_price_snapshots table."""
        if not quotes:
            return

        records = []
        for ticker, q in quotes.items():
            records.append({
                "ticker": ticker,
                "live_price": float(q.get("last") or 0.0),
                "prev_close": float(q.get("prev_close") or 0.0),
                "midnight_price": float(q.get("midnight") or 0.0),
                "market_open": float(q.get("open") or 0.0),
            })

        sql = """
        INSERT INTO degiro_price_snapshots (
            ticker, live_price, prev_close, midnight_price, market_open, updated_at
        ) VALUES (
            %(ticker)s, %(live_price)s, %(prev_close)s, %(midnight_price)s, %(market_open)s, NOW()
        )
        ON CONFLICT (ticker) DO UPDATE SET
            live_price = EXCLUDED.live_price,
            prev_close = EXCLUDED.prev_close,
            midnight_price = EXCLUDED.midnight_price,
            market_open = EXCLUDED.market_open,
            updated_at = NOW()
        """
        with get_db_connection(self.database_url) as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, sql, records)
