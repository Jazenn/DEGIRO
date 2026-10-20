"""Ingestion package for DEGIRO CSV exports."""

from __future__ import annotations

from backend.ingestion.account_parser import parse_account_csv, parse_trade_description, is_internal_cash_sweep
from backend.ingestion.transaction_parser import parse_transactions_csv
from backend.ingestion.normalizer import parse_degiro_number, compute_row_hash, shorten_name
from backend.ingestion.loader import load_degiro_csv
from backend.ingestion.service import TransactionIngestionService, IngestionResult

__all__ = [
    "load_degiro_csv",
    "parse_account_csv",
    "parse_transactions_csv",
    "parse_degiro_number",
    "parse_trade_description",
    "is_internal_cash_sweep",
    "compute_row_hash",
    "shorten_name",
    "TransactionIngestionService",
    "IngestionResult",
]
