"""Transaction ingestion service for normalizing and deduplicating DEGIRO CSV exports."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import pandas as pd

from backend.ingestion.loader import load_degiro_csv
from backend.ingestion.identity import IDENTITY_VERSION
from backend.ingestion.normalizer import compute_row_hash, parse_degiro_number


@dataclass
class IngestionResult:
    new_rows: int
    duplicates_skipped: int
    rows_processed: int
    transactions: pd.DataFrame = field(default_factory=pd.DataFrame)
    accepted: bool = True
    diagnostics: tuple[str, ...] = ()
    audit_transactions: pd.DataFrame = field(default_factory=pd.DataFrame)


class TransactionIngestionService:
    """Normalize and deduplicate DEGIRO CSV exports."""

    HEADER_ALIASES: Dict[str, List[str]] = {
        "date": ["date", "datum", "transaction date", "date of transaction"],
        "time": ["time", "tijd", "transaction time"],
        "product": ["product", "productnaam", "name", "fonds", "security"],
        "isin": ["isin", "isin code", "isin / ticker"],
        "quantity": ["quantity", "aantal"],
        "price": ["price", "koers", "unit price"],
        "value": [
            "value",
            "waarde",
            "waarde eur",
            "value eur",
            "lokale waarde",
            "local value",
            "waarde in lokale valuta",
            "value in local currency",
        ],
        "amount": ["amount", "mutatie", "change"],
        "balance": ["balance", "saldo"],
        "description": ["description", "omschrijving"],
        "order_id": ["order_id", "order id", "orderid"],
        "fx": ["fx", "autofx kosten", "autofx fee"],
    }

    def __init__(self, existing_transactions: pd.DataFrame | None = None) -> None:
        existing = existing_transactions if existing_transactions is not None else pd.DataFrame()
        if not existing.empty and ("identity_version" not in existing or not existing["identity_version"].eq(IDENTITY_VERSION).all()):
            raise ValueError("legacy_identity_requires_review: reconcile prior collapsed executions before migration")
        self._seen_hashes = set(existing.get("row_hash", []))
        self._multiplicities = Counter(existing.get("identity_fingerprint", []))
        self.total_rows_seen = len(self._seen_hashes)

    @staticmethod
    def _normalize_header_name(header: str) -> str:
        return str(header or "").strip().lower().replace("\ufeff", "")

    @classmethod
    def _stable_value(cls, value: Any) -> str:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return ""
        if isinstance(value, (pd.Timestamp,)):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, float):
            return format(value, ".15g")
        return str(value).strip()

    @classmethod
    def _row_hash(cls, row: dict) -> str:
        r = dict(row) if not isinstance(row, dict) else row
        amount_raw = r.get("amount", r.get("value", 0.0))
        amount = parse_degiro_number(amount_raw) if amount_raw is not None else 0.0
        return compute_row_hash(
            date=cls._stable_value(r.get("date")),
            time=cls._stable_value(r.get("time")),
            isin=cls._stable_value(r.get("isin")),
            order_id=cls._stable_value(r.get("order_id")),
            amount=amount if amount is not None else 0.0,
            description=cls._stable_value(r.get("description", "")),
        )

    @classmethod
    def _validate_headers(cls, headers: list[str]) -> None:
        normalized = {cls._normalize_header_name(header) for header in headers}
        available = {
            key
            for key, aliases in cls.HEADER_ALIASES.items()
            if normalized.intersection(aliases)
        }
        if not {"date", "product"}.issubset(available):
            raise ValueError(
                "Unsupported DEGIRO CSV format: expected transaction columns were not found."
            )
        if not ({"quantity", "description"} & available):
            raise ValueError(
                "Unsupported DEGIRO CSV format: expected Account.csv or Transactions.csv columns."
            )
        if "quantity" in available and not ({"value", "amount"} & available):
            raise ValueError(
                "Unsupported DEGIRO CSV format: transaction exports require a value column."
            )
        if "quantity" not in available and "amount" not in available:
            raise ValueError(
                "Unsupported DEGIRO CSV format: account exports require an amount column."
            )

    def ingest_csv(self, file_content: bytes) -> IngestionResult:
        if not file_content or not file_content.strip():
            return IngestionResult(0, 0, 0)

        try:
            text = file_content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("Unsupported DEGIRO CSV format: file must be UTF-8 encoded.") from error

        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t")
        except csv.Error as error:
            raise ValueError("Unsupported DEGIRO CSV format: could not detect CSV delimiter.") from error

        reader = csv.reader(io.StringIO(text), dialect=dialect)
        headers = next(reader, None)
        if not headers:
            raise ValueError("Unsupported DEGIRO CSV format: missing headers.")
        self._validate_headers(headers)
        rows_processed = 0
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue
            rows_processed += 1
            if len(row) != len(headers):
                raise ValueError(f"Invalid Transaction column count at source row {rows_processed + 1}")

        parsed_transactions = load_degiro_csv(file_content)
        if parsed_transactions.empty:
            return IngestionResult(0, 0, rows_processed, parsed_transactions)

        counts = Counter(parsed_transactions["identity_fingerprint"])
        diagnostics = sorted({diagnostic for values in parsed_transactions["diagnostics"] for diagnostic in values})
        review = bool({"correction_requires_review", "cash_balance_discontinuity", "same_time_ordering_requires_review", "transaction_classification_requires_review", "non_eur_cash_requires_dated_fx"}.intersection(diagnostics))
        if any(self._multiplicities[key] and self._multiplicities[key] != count for key, count in counts.items()):
            diagnostics.append("ambiguous_overlap_multiplicity")
            review = True
        if review:
            return IngestionResult(0, 0, rows_processed, accepted=False,
                                   diagnostics=tuple(diagnostics), audit_transactions=parsed_transactions)
        transactions = []
        duplicates_skipped = 0
        for record in parsed_transactions.to_dict(orient="records"):
            row_hash = record.get("row_hash") or self._row_hash(record)
            if row_hash in self._seen_hashes:
                duplicates_skipped += 1
                continue
            self._seen_hashes.add(row_hash)
            record["row_hash"] = row_hash
            transactions.append(record)

        self._multiplicities.update({key: count for key, count in counts.items() if key not in self._multiplicities})
        self.total_rows_seen = len(self._seen_hashes)
        cols = list(parsed_transactions.columns)
        if "row_hash" not in cols:
            cols.append("row_hash")
        unique_transactions = pd.DataFrame(transactions, columns=cols)
        return IngestionResult(
            new_rows=len(unique_transactions),
            duplicates_skipped=duplicates_skipped,
            rows_processed=rows_processed,
            transactions=unique_transactions,
            diagnostics=tuple(diagnostics), audit_transactions=parsed_transactions,
        )



