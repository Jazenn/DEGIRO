"""Normalization, hashing, and numeric parsing for DEGIRO CSV exports."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Optional


def parse_degiro_number(val: Any) -> Optional[float]:
    """Parse a DEGIRO exported number (Dutch or English format) to a float.

    Dutch format: 1.234,56
    English format: 1,234.56
    """
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    for cur in ("EUR", "USD", "GBP", "CHF"):
        s = s.replace(cur, "")
    s = s.strip()

    if not s or s.lower() in ("nan", "none", "-", ""):
        return None

    last_comma = s.rfind(",")
    last_dot = s.rfind(".")

    if last_comma > last_dot:
        # European format: 1.234,56 -> 1234.56
        s = s.replace(".", "").replace(",", ".")
    elif last_dot > last_comma:
        # Anglo format: 1,234.56 -> 1234.56
        s = s.replace(",", "")
    elif last_comma != -1:
        # Only comma exists: 1234,56 -> 1234.56
        s = s.replace(",", ".")

    try:
        return float(s)
    except ValueError:
        return None


def compute_row_hash(
    date: str,
    time: str,
    isin: str,
    order_id: str,
    amount: float,
    description: str = "",
) -> str:
    """Compute a deterministic 32-character hexadecimal MD5 hash for a transaction row."""
    norm_date = (date or "").strip()
    norm_time = (time or "").strip()
    norm_isin = (isin or "").strip().upper()
    norm_order = (order_id or "").strip().lower()
    norm_amount = f"{float(amount):.4f}" if amount is not None else "0.0000"
    norm_desc = (description or "").strip()

    raw_key = f"{norm_date}|{norm_time}|{norm_isin}|{norm_order}|{norm_amount}|{norm_desc}"
    return hashlib.md5(raw_key.encode("utf-8")).hexdigest()


def shorten_name(name: Any) -> str:
    """Shorten product name for mobile readability."""
    if not name or not isinstance(name, str):
        return str(name or "")
    n = name.upper()
    if "VANGUARD" in n:
        return "All-World"
    if "STRACKERS" in n or "XTRACKERS" in n:
        return "Ex-USA"
    if "ISHARES" in n:
        return "Europe"
    if "FUTUREOFDEFENCE" in n or "HANETF" in n or "FUTURE OF DEFENCE" in n:
        return "FOD"
    return name
