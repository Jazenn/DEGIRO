"""Parser for DEGIRO Transactions.csv exports for backward compatibility."""

from __future__ import annotations

import io
from typing import Any, List, Optional
import pandas as pd

from backend.ingestion.identity import finalize_records
from backend.ingestion.normalizer import compute_row_hash, parse_degiro_number, shorten_name


def parse_transactions_csv(file_bytes_or_buffer: Any) -> pd.DataFrame:
    """Parse a DEGIRO Transactions.csv export into normalized transaction records."""
    if isinstance(file_bytes_or_buffer, bytes):
        buffer = io.BytesIO(file_bytes_or_buffer)
    elif isinstance(file_bytes_or_buffer, str):
        buffer = io.StringIO(file_bytes_or_buffer)
    else:
        buffer = file_bytes_or_buffer

    df_raw = pd.read_csv(buffer, sep=None, engine="python", dtype=str, keep_default_na=False)
    df_raw.columns = [str(c).strip().lower() for c in df_raw.columns]
    cols = df_raw.columns.tolist()

    def find_col(candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in cols:
                return c
        return None

    c_date = find_col(["datum", "date"])
    c_time = find_col(["tijd", "time"])
    c_prod = find_col(["product"])
    c_isin = find_col(["isin"])
    c_qty = find_col(["aantal", "quantity"])
    c_price = find_col(["koers", "price"])
    c_val = find_col([
        "waarde eur", "value eur", "waarde", "value", "lokale waarde",
        "waarde in lokale valuta", "local value", "value in local currency",
    ])
    c_fx = find_col(["autofx kosten", "autofx fee", "fx"])
    c_fee = find_col(["transactiekosten en/of kosten van derden eur", "transaction costs", "fee"])
    c_order = find_col(["order_id", "order id"])

    records = []
    for row_idx, row in df_raw.iterrows():
        d = str(row[c_date]).strip() if c_date and pd.notna(row[c_date]) else ""
        t = str(row[c_time]).strip() if c_time and pd.notna(row[c_time]) else ""
        prod = str(row[c_prod]).strip() if c_prod and pd.notna(row[c_prod]) else ""
        isin = str(row[c_isin]).strip() if c_isin and pd.notna(row[c_isin]) else ""

        order_id = ""
        if c_order and pd.notna(row[c_order]):
            order_id = str(row[c_order]).strip()
        elif "unnamed: 17" in cols and pd.notna(row["unnamed: 17"]):
            order_id = str(row["unnamed: 17"]).strip()

        qty = parse_degiro_number(row[c_qty]) if c_qty else 0.0
        price = parse_degiro_number(row[c_price]) if c_price else 0.0
        val = parse_degiro_number(row[c_val]) if c_val else 0.0
        fx = parse_degiro_number(row[c_fx]) if c_fx else 0.0
        fee = parse_degiro_number(row[c_fee]) if c_fee else 0.0

        for column, value in ((c_fx, fx), (c_fee, fee)):
            if column and str(row[column]).strip() and value is None:
                raise ValueError(f"Invalid Transaction numeric field at source row {row_idx + 2}")

        # In DEGIRO Transactions.csv, crypto trades often export with empty 'Aantal'. Calculate it:
        if (qty is None or qty == 0.0) and price and price > 0 and val and val != 0:
            calc_qty = abs(val) / price
            qty = calc_qty if val < 0 else -calc_qty

        if qty is None or not qty or price is None or price <= 0 or val is None:
            raise ValueError(f"Invalid Transaction quantity, price or amount at source row {row_idx + 2}")
        # Quantity carries direction; normalize unsigned value variants as well.
        action = "BUY" if qty > 0 else "SELL"
        val = -abs(val) if action == "BUY" else abs(val)
        desc = f"{'Koop' if action == 'BUY' else 'Verkoop'} {abs(qty or 0)} @ {price or 0} EUR"

        amount_currency = "EUR" if c_val and "eur" in c_val else ""
        quote_currency = ""
        if c_price and cols.index(c_price) + 1 < len(cols):
            candidate = row.iloc[cols.index(c_price) + 1]
            if isinstance(candidate, str) and len(candidate.strip()) == 3 and candidate.strip().isalpha():
                quote_currency = candidate.strip().upper()
        if c_val and cols.index(c_val) + 1 < len(cols):
            candidate = row.iloc[cols.index(c_val) + 1]
            if isinstance(candidate, str) and len(candidate.strip()) == 3 and candidate.strip().isalpha():
                amount_currency = candidate.strip().upper()
        source_record = {str(k): (None if pd.isna(v) else str(v)) for k, v in row.items()}
        # Trade record
        row_hash = compute_row_hash(d, t, isin, order_id, val or 0.0, desc)
        records.append({
            "date": d,
            "time": t,
            "value_date": d,
            "product": shorten_name(prod),
            "raw_product": prod,
            "isin": isin,
            "description": desc,
            "fx": fx or 0.0,
            "amount_currency": amount_currency,
            "quote_currency": quote_currency,
            "balance_reported": False,
            "source_record": source_record,
            "amount": val or 0.0,
            "balance": 0.0,
            "order_id": order_id,
            "csv_row_id": int(row_idx),
            "action": action,
            "quantity": qty or 0.0,
            "price": price or 0.0,
            "type": action,
            "is_cash_sweep": False,
            "row_hash": row_hash,
        })

        # If transaction fee is recorded on this row, produce the paired fee record matching Account.csv
        if fee and abs(fee) > 0:
            fee_amount = -abs(fee)
            fee_desc = "DEGIRO Transactiekosten en/of kosten van derden"
            fee_hash = compute_row_hash(d, t, isin, order_id, fee_amount, fee_desc)
            records.append({
                "date": d,
                "time": t,
                "value_date": d,
                "product": shorten_name(prod),
                "raw_product": prod,
                "isin": isin,
                "description": fee_desc,
                "fx": 0.0,
                "amount_currency": "EUR" if c_fee and "eur" in c_fee else amount_currency,
                "quote_currency": "",
                "balance_reported": False,
                "source_record": source_record,
                "amount": fee_amount,
                "balance": 0.0,
                "order_id": order_id,
                "csv_row_id": int(row_idx),
                "action": None,
                "quantity": 0.0,
                "price": 0.0,
                "type": "FEE",
                "is_cash_sweep": False,
                "row_hash": fee_hash,
            })

    return finalize_records(records, "transactions")
