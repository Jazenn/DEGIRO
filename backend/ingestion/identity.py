"""Stable identities and source evidence for normalized Transactions.

An order identifier identifies an order, not an execution. Preserve multiplicity
within each export and expose ambiguous overlap to the ingestion service.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import re
import pandas as pd


def finalize_records(records: list[dict], source_format: str) -> pd.DataFrame:
    occurrences = Counter()
    for record in records:
        date = pd.to_datetime(record["date"], dayfirst=not bool(re.match(r"^\d{4}-\d{2}-\d{2}$", record["date"])), errors="coerce")
        if pd.isna(date):
            raise ValueError(f"Invalid Transaction date at source row {record['csv_row_id'] + 2}")
        time = record.get("time") or ""
        if time and pd.isna(pd.to_datetime(date.strftime("%Y-%m-%d") + " " + time, errors="coerce")):
            raise ValueError(f"Invalid Transaction time at source row {record['csv_row_id'] + 2}")
        for field in ("amount", "quantity", "price", "balance"):
            if record.get(field) is None or not math.isfinite(float(record[field])):
                raise ValueError(f"Invalid Transaction {field} at source row {record['csv_row_id'] + 2}")
        record["normalized_date"] = date.strftime("%Y-%m-%d")
        record["source_format"] = source_format
        record["source_timezone"] = None
        record["asset_kind"] = "unverified"
        record["quote_symbol"] = None
        record["broker_asset_id"] = record["isin"] or record["raw_product"]
        record.setdefault("amount_currency", "")
        record.setdefault("quote_currency", "")
        diagnostics = ["source_timezone_unverified"]
        if record.get("action") in ("BUY", "SELL"):
            diagnostics.append("asset_kind_and_quote_mapping_unverified")
            if not record["isin"]:
                diagnostics.append("broker_asset_identity_unverified")
        if not record["amount_currency"]:
            diagnostics.append("amount_currency_unverified")
        elif record["amount_currency"] != "EUR":
            diagnostics.append("non_eur_cash_requires_dated_fx")
        description = record["description"].lower()
        if any(word in description for word in ("correct", "reversal", "reversed", "cancel", "annuler", "storno")):
            diagnostics.append("correction_requires_review")
        if record["type"] == "OTHER":
            diagnostics.append("transaction_classification_requires_review")
        record["diagnostics"] = diagnostics
        # Canonical economic fields permit Account/Transactions overlap without
        # treating the order id as a unique execution id. No precision truncation.
        identity = {
            "date": record["normalized_date"], "time": time, "asset": record["broker_asset_id"],
            "order_id": record["order_id"], "type": record["type"],
            "amount": str(record["amount"]), "quantity": str(record["quantity"]),
            "price": str(record["price"]),
        }
        if record["type"] not in ("BUY", "SELL", "FEE"):
            identity["description"] = record["description"]
        fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        occurrences[fingerprint] += 1
        occurrence = occurrences[fingerprint]
        record["identity_fingerprint"] = fingerprint
        record["identity_occurrence"] = occurrence
        record["row_hash"] = hashlib.md5(f"v2:{fingerprint}:{occurrence}".encode()).hexdigest()
        record["identity_version"] = "execution-v2"
    if records:
        ordered = sorted(records, key=lambda row: (row["normalized_date"], row["time"], -row["csv_row_id"]))
        previous = None
        for record in ordered:
            if record.get("balance_reported"):
                if previous is not None and not math.isclose(previous + record["amount"], record["balance"], abs_tol=0.011):
                    record["diagnostics"].append("cash_balance_discontinuity")
                previous = record["balance"]
        grouped = {}
        for record in records:
            if record.get("action") in ("BUY", "SELL"):
                key = (record["normalized_date"], record["time"], record["broker_asset_id"])
                grouped.setdefault(key, []).append(record)
        for group in grouped.values():
            if len({record["action"] for record in group}) > 1:
                for record in group:
                    record["diagnostics"].append("same_time_ordering_requires_review")
    return pd.DataFrame(records)
