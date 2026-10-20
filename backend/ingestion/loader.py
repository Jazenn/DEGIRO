"""CSV loader dispatching to Account or Transactions parser."""

from __future__ import annotations

import io
from typing import Any
import pandas as pd

from backend.ingestion.account_parser import parse_account_csv
from backend.ingestion.transaction_parser import parse_transactions_csv


def load_degiro_csv(file_bytes_or_buffer: Any) -> pd.DataFrame:
    """Load a DEGIRO CSV file (Account or Transactions format) into a normalized DataFrame."""
    if isinstance(file_bytes_or_buffer, bytes):
        raw_head = file_bytes_or_buffer[:1024].decode("utf-8", errors="ignore").lower()
        buf = io.BytesIO(file_bytes_or_buffer)
    elif isinstance(file_bytes_or_buffer, str):
        raw_head = file_bytes_or_buffer[:1024].lower()
        buf = io.StringIO(file_bytes_or_buffer)
    else:
        # File-like object
        pos = file_bytes_or_buffer.tell() if hasattr(file_bytes_or_buffer, "tell") else None
        head_sample = file_bytes_or_buffer.read(1024)
        if isinstance(head_sample, bytes):
            raw_head = head_sample.decode("utf-8", errors="ignore").lower()
        else:
            raw_head = str(head_sample).lower()
        if pos is not None and hasattr(file_bytes_or_buffer, "seek"):
            file_bytes_or_buffer.seek(pos)
        buf = file_bytes_or_buffer

    # If first line contains 'aantal' or 'quantity', it's a Transactions export
    if "aantal" in raw_head or "quantity" in raw_head:
        return parse_transactions_csv(buf)
    return parse_account_csv(buf)
