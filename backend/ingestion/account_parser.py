"""Parser for DEGIRO Account.csv exports implementing the forensic grammar from Ticket #16."""

from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from backend.ingestion.identity import finalize_records
from backend.ingestion.normalizer import compute_row_hash, parse_degiro_number, shorten_name


def parse_trade_description(description: str) -> Tuple[Optional[str], float, float]:
    """Extract action ('BUY' | 'SELL'), quantity, and price from a trade description.

    Supports patterns like:
      - 'Koop 1 @ 170,1 EUR'
      - 'Koop 0,003472 @ 57.590,21 EUR'
      - 'Verkoop 4 @ 149,88 EUR'
      - 'Buy 10 @ 18.076 EUR'
    """
    if not description:
        return None, 0.0, 0.0

    desc = str(description).strip()
    match = re.search(
        r"(Koop|Verkoop|Buy|Sell)\s+([0-9.,]+)\s*@\s*([0-9.,]+)",
        desc,
        re.IGNORECASE,
    )
    if not match:
        return None, 0.0, 0.0

    action_word = match.group(1).upper()
    action = "BUY" if action_word in ("KOOP", "BUY") else "SELL"
    raw_qty = parse_degiro_number(match.group(2)) or 0.0
    raw_price = parse_degiro_number(match.group(3)) or 0.0

    signed_qty = raw_qty if action == "BUY" else -raw_qty
    return action, signed_qty, raw_price


def is_internal_cash_sweep(description: str, product: str) -> bool:
    """Identify if a row is an internal Flatex cash sweep (net-zero cash flow)."""
    d = str(description or "").lower()
    p = str(product or "").lower()

    if "cash sweep transfer" in d:
        return True
    if "overboeking" in d and ("geldrekening" in d or "flatex" in d):
        return True
    if "transfer" in d and ("cash account" in d or "flatex" in d):
        return True
    if any(word in d for word in ("deposit", "storting", "withdrawal", "reservation")):
        return False
    if "flatex euro bankaccount" in p or "nlflatexacnt" in p:
        return True
    return False


def parse_account_csv(file_bytes_or_buffer: Any) -> pd.DataFrame:
    """Parse raw Account.csv bytes into a normalized DataFrame following the Ticket #16 grammar.

    Guarantees:
      - Multi-column shift handling for currency columns.
      - Extraction of trade quantities (including fractional crypto with empty ISIN).
      - Tagging of internal cash sweeps (Flatex) so they do not distort external capital.
      - Deterministic 32-character hexadecimal MD5 row hashing.
      - Maintenance of `csv_row_id` for chronological tie-breaking `(date ASC, time ASC, csv_row_id DESC)`.
    """
    if isinstance(file_bytes_or_buffer, bytes):
        buffer = io.BytesIO(file_bytes_or_buffer)
    elif isinstance(file_bytes_or_buffer, str):
        buffer = io.StringIO(file_bytes_or_buffer)
    else:
        buffer = file_bytes_or_buffer

    df_raw = pd.read_csv(buffer, sep=None, engine="python", index_col=False, dtype=str, keep_default_na=False)
    # Clean and lower header strings
    df_raw.columns = [str(c).strip().lower() for c in df_raw.columns]

    cols = df_raw.columns.tolist()

    def find_col(candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in cols:
                return c
        return None

    c_date = find_col(["datum", "date"])
    c_time = find_col(["tijd", "time"])
    c_val_date = find_col(["valutadatum", "value date", "valuedate"])
    c_prod = find_col(["product"])
    c_isin = find_col(["isin"])
    c_desc = find_col(["omschrijving", "description"])
    c_fx = find_col(["fx"])
    c_order = find_col(["order id", "order_id"])

    # Locate Mutation and Balance column indices to handle DEGIRO's multi-column shift
    # Typical header: Datum, Tijd, Valutadatum, Product, ISIN, Omschrijving, FX, Mutatie, Unnamed: 8, Saldo, Unnamed: 10, Order Id
    idx_mut = None
    idx_saldo = None
    for i, c in enumerate(cols):
        if c in ("mutatie", "change", "amount"):
            idx_mut = i
        elif c in ("saldo", "balance"):
            idx_saldo = i

    records = []
    for row_idx, (_, row) in enumerate(df_raw.iterrows()):
        d = str(row[c_date]).strip() if c_date and pd.notna(row[c_date]) else ""
        t = str(row[c_time]).strip() if c_time and pd.notna(row[c_time]) else ""
        vd = str(row[c_val_date]).strip() if c_val_date and pd.notna(row[c_val_date]) else d
        prod = str(row[c_prod]).strip() if c_prod and pd.notna(row[c_prod]) else ""
        isin = str(row[c_isin]).strip() if c_isin and pd.notna(row[c_isin]) else ""
        desc = str(row[c_desc]).strip() if c_desc and pd.notna(row[c_desc]) else ""
        order_id = str(row[c_order]).strip() if c_order and pd.notna(row[c_order]) else ""
        fx = parse_degiro_number(row[c_fx]) if c_fx and pd.notna(row[c_fx]) else 0.0

        # Resolve mutation (amount) handling currency shift
        amount = None
        amount_currency = ""
        mutation_raw = None
        if idx_mut is not None:
            mut_val = row.iloc[idx_mut]
            # If Mutatie column contains currency code (EUR, USD, etc.), amount is in next column
            if isinstance(mut_val, str) and mut_val.strip().upper() in {"EUR", "USD", "GBP", "CHF", "SEK", "NOK", "DKK", "PLN", "CZK", "CAD", "AUD", "JPY", "HKD"}:
                if idx_mut + 1 < len(row):
                    mutation_raw = str(row.iloc[idx_mut + 1]).strip()
                    amount = parse_degiro_number(mutation_raw)
                    amount_currency = mut_val.strip().upper()
            else:
                mutation_raw = str(mut_val).strip()
                amount = parse_degiro_number(mutation_raw)

        # Resolve balance handling currency shift
        balance = 0.0
        if idx_saldo is not None:
            saldo_val = row.iloc[idx_saldo]
            if isinstance(saldo_val, str) and saldo_val.strip().upper() in {"EUR", "USD", "GBP", "CHF", "SEK", "NOK", "DKK", "PLN", "CZK", "CAD", "AUD", "JPY", "HKD"}:
                if idx_saldo + 1 < len(row):
                    balance = parse_degiro_number(row.iloc[idx_saldo + 1])
            else:
                balance = parse_degiro_number(saldo_val)

        mutation_present = bool(mutation_raw)
        # Sweep notifications can carry a balance without a monetary mutation.
        # Preserve them as source evidence; a missing required posting or a
        # malformed nonblank number remains invalid.
        informational_sweep = mutation_raw == "" and is_internal_cash_sweep(desc, prod)
        if informational_sweep:
            amount = 0.0
        elif amount is None:
            raise ValueError(f"Invalid Transaction amount at source row {row_idx + 2}")
        quote_currency_match = re.search(r"@.*?\b([A-Z]{3})\b", desc)
        quote_currency = quote_currency_match.group(1) if quote_currency_match else ""

        # Extract trade details
        action, signed_qty, price = parse_trade_description(desc)
        if re.match(r"^(koop|verkoop|buy|sell)\b", desc, re.IGNORECASE) and (action is None or not signed_qty or price <= 0):
            raise ValueError(f"Invalid Transaction quantity or price at source row {row_idx + 2}")
        is_sweep = is_internal_cash_sweep(desc, prod)

        # Categorize transaction type
        tx_type = "OTHER"
        if is_sweep:
            tx_type = "CASH_SWEEP"
        elif action in ("BUY", "SELL"):
            tx_type = action
        elif any(w in desc.lower() for w in ("reservation", "reservering")):
            tx_type = "RESERVATION"
        elif any(w in desc.lower() for w in ("terugstorting", "withdrawal")):
            tx_type = "WITHDRAWAL"
        elif any(w in desc.lower() for w in ("ideal", "deposit", "storting")):
            tx_type = "DEPOSIT"
        elif any(w in desc.lower() for w in ("transactiekosten", "aansluitingskosten", "kosten van derden", "fee")):
            tx_type = "FEE"
        elif any(w in desc.lower() for w in ("dividend", "dividendbelasting")):
            tx_type = "DIVIDEND"
        elif "interest" in desc.lower():
            tx_type = "INTEREST"
        elif "promotie" in desc.lower():
            tx_type = "PROMOTION"

        # Deterministic row hash
        row_hash = compute_row_hash(d, t, isin, order_id, amount, desc)

        records.append({
            "date": d,
            "time": t,
            "value_date": vd,
            "product": shorten_name(prod),
            "raw_product": prod,
            "isin": isin,
            "description": desc,
            "fx": fx or 0.0,
            "amount_currency": amount_currency,
            "quote_currency": quote_currency,
            "balance_reported": idx_saldo is not None,
            "mutation_present": mutation_present,
            "source_record": {str(k): (None if pd.isna(v) else str(v)) for k, v in row.items()},
            "amount": amount,
            "balance": balance,
            "order_id": order_id,
            "csv_row_id": int(row_idx),
            "action": action,
            "quantity": signed_qty,
            "price": price,
            "type": tx_type,
            "is_cash_sweep": is_sweep,
            "row_hash": row_hash,
        })

    return finalize_records(records, "account")
