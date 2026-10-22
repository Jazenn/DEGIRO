"""Cash calculation engine for DEGIRO account balances and external cash flows."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import pandas as pd


def sort_transactions_chronologically(df: pd.DataFrame) -> pd.DataFrame:
    """Sort transactions forward in time using DEGIRO tie-breaking rules.

    Primary: Datetime (date + time) ASC
    Tie-breaker: csv_row_id DESC (original DEGIRO export is reverse chronological,
    so higher row index within the same minute executed earlier).
    """
    if df.empty:
        return df.copy()

    df_out = df.copy()
    if "date" in df_out.columns:
        date_str = df_out.get("normalized_date", df_out["date"]).astype(str)
        time_str = df_out["time"].astype(str) if "time" in df_out.columns else "00:00"
        # Parse day-first dates (e.g. 15-10-2026)
        df_out["_dt"] = pd.to_datetime(
            date_str + " " + time_str,
            dayfirst="normalized_date" not in df_out,
            errors="coerce",
        )
    else:
        df_out["_dt"] = pd.Timestamp.now()

    if "csv_row_id" not in df_out.columns:
        df_out["csv_row_id"] = list(range(len(df_out)))

    df_sorted = df_out.sort_values(
        by=["_dt", "csv_row_id"],
        ascending=[True, False],
    ).reset_index(drop=True)

    df_sorted = df_sorted.drop(columns=["_dt"], errors="ignore")
    return df_sorted


def calculate_cash_balance(df: pd.DataFrame) -> float:
    """Calculate current free cash balance from non-sweep cash ledger entries."""
    if df.empty:
        return 0.0

    # Filter out internal cash sweeps (FlatexDEGIRO Bank net-zero transfers)
    is_sweep = df["is_cash_sweep"] if "is_cash_sweep" in df.columns else False
    df_ledger = df[~is_sweep]

    if "amount" not in df_ledger.columns:
        return 0.0

    return float(round(df_ledger["amount"].sum(), 2))


def calculate_net_invested_capital(df: pd.DataFrame) -> float:
    """Calculate cumulative net external deposited capital.

    Follows the 3-row iDEAL lifecycle (+X reservation, -X reservation release, +X settled deposit)
    where internal sweeps are excluded. Net sum of external deposits and withdrawals.
    """
    if df.empty:
        return 0.0

    is_sweep = df["is_cash_sweep"] if "is_cash_sweep" in df.columns else False
    df_ledger = df[~is_sweep]

    if "type" not in df_ledger.columns or "amount" not in df_ledger.columns:
        return 0.0

    deposits_and_withdrawals = df_ledger[df_ledger["type"].isin(["DEPOSIT", "WITHDRAWAL"])]
    return float(round(deposits_and_withdrawals["amount"].sum(), 2))


def build_cumulative_cash_series(df: pd.DataFrame) -> pd.Series:
    """Build daily historical cash balance series."""
    if df.empty:
        return pd.Series(dtype=float)

    df_sorted = sort_transactions_chronologically(df)
    is_sweep = df_sorted["is_cash_sweep"] if "is_cash_sweep" in df_sorted.columns else False
    df_ledger = df_sorted[~is_sweep].copy()

    df_ledger["parsed_date"] = pd.to_datetime(df_ledger.get("normalized_date", df_ledger["date"]), dayfirst="normalized_date" not in df_ledger, errors="coerce")
    df_ledger = df_ledger.dropna(subset=["parsed_date"])

    daily_mutation = df_ledger.groupby("parsed_date")["amount"].sum()
    daily_cash = daily_mutation.cumsum()
    return daily_cash
