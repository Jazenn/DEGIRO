"""Crypto price provider using CoinGecko and Binance public endpoints."""

from __future__ import annotations

import logging
from typing import Dict, Optional
import requests

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_crypto_quotes(timeout: float = 3.0) -> Dict[str, Dict[str, Optional[float]]]:
    """Fetch live crypto quotes for Bitcoin and Ethereum in EUR.

    Returns dict mapping ticker ('BTC-EUR', 'ETH-EUR') to dict with 'last', 'prev_close'.
    """
    quotes: Dict[str, Dict[str, Optional[float]]] = {
        "BTC-EUR": {"last": None, "prev_close": None},
        "ETH-EUR": {"last": None, "prev_close": None},
    }

    # 1. CoinGecko primary
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=eur&include_24hr_change=true"
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            if "bitcoin" in data and "eur" in data["bitcoin"]:
                btc_last = float(data["bitcoin"]["eur"])
                quotes["BTC-EUR"]["last"] = btc_last
                change_pct = data["bitcoin"].get("eur_24h_change")
                if change_pct is not None:
                    quotes["BTC-EUR"]["prev_close"] = btc_last / (1.0 + float(change_pct) / 100.0)

            if "ethereum" in data and "eur" in data["ethereum"]:
                eth_last = float(data["ethereum"]["eur"])
                quotes["ETH-EUR"]["last"] = eth_last
                change_pct = data["ethereum"].get("eur_24h_change")
                if change_pct is not None:
                    quotes["ETH-EUR"]["prev_close"] = eth_last / (1.0 + float(change_pct) / 100.0)
    except Exception as e:
        logger.debug("CoinGecko fetch failed: %s", e)

    # 2. Binance fallback for missing quotes
    pairs = [("BTCEUR", "BTC-EUR"), ("ETHEUR", "ETH-EUR")]
    for symbol, ticker in pairs:
        if quotes[ticker]["last"] is None:
            try:
                url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
                r = requests.get(url, headers=HEADERS, timeout=timeout)
                if r.status_code == 200:
                    data = r.json()
                    quotes[ticker]["last"] = float(data.get("lastPrice", 0.0))
                    quotes[ticker]["prev_close"] = float(data.get("prevClosePrice", 0.0))
            except Exception as e:
                logger.debug("Binance fallback failed for %s: %s", symbol, e)

    return quotes
