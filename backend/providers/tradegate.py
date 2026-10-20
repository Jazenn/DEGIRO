"""TradeGate Exchange price fetcher for European stocks and ETFs."""

from __future__ import annotations

import logging
from typing import Dict, Optional
import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_tradegate_quote(isin: str, timeout: float = 3.0) -> Dict[str, Optional[float]]:
    """Fetch real-time quote for an ISIN from TradeGate.

    Returns dict with keys: 'last', 'close', 'open'.
    """
    clean_isin = (isin or "").strip().upper()
    result: Dict[str, Optional[float]] = {"last": None, "close": None, "open": None}

    if len(clean_isin) != 12 or clean_isin.startswith("XFC"):
        return result

    url = f"https://www.tradegate.de/refresh.php?isin={clean_isin}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                for k in ("last", "close", "open"):
                    val = data.get(k)
                    if val is not None:
                        try:
                            # Handle European float formatted as string or number
                            num_str = str(val).replace(".", "").replace(",", ".")
                            result[k] = float(num_str)
                        except (ValueError, TypeError):
                            pass
    except Exception as e:
        logger.debug("TradeGate fetch error for %s: %s", clean_isin, e)

    return result
