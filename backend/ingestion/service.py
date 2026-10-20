"""Transaction ingestion service for normalizing and deduplicating DEGIRO CSV exports."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import pandas as pd

from backend.ingestion.loader import load_degiro_csv


@dataclass
class IngestionResult:
    new_rows: int
    duplicates_skipped: int
    rows_processed: int
    transactions: pd.DataFrame = field(default_factory=pd.DataFrame)


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

    def __init__(self) -> None:
        self.total_rows_seen: int = 0
        self._seen_hashes: Set[str] = set()

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
        amount = row.get("amount")
        value = row.get("value", amount)
        payload = {
            "date": cls._stable_value(row.get("date")),
            "time": cls._stable_value(row.get("time")),
            "isin": cls._stable_value(row.get("isin")),
            "order_id": cls._stable_value(row.get("order_id")),
            "amount": cls._stable_value(amount),
            "value": cls._stable_value(value),
        }
        return hashlib.md5(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

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
        rows_processed = sum(1 for row in reader if any(cell.strip() for cell in row))

        parsed_transactions = load_degiro_csv(file_content)
        if parsed_transactions.empty:
            return IngestionResult(0, 0, rows_processed, parsed_transactions)

        transactions = []
        duplicates_skipped = 0
        for record in parsed_transactions.to_dict(orient="records"):
            row_hash = self._row_hash(record)
            if row_hash in self._seen_hashes:
                duplicates_skipped += 1
                continue
            self._seen_hashes.add(row_hash)
            record["row_hash"] = row_hash
            transactions.append(record)

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
        )
