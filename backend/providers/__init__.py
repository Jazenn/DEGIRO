"""Price providers package uniting TradeGate, CoinGecko, Binance, and Yahoo Finance."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from backend.config import BackendConfig
from backend.providers.tradegate import fetch_tradegate_quote
from backend.providers.coingecko import fetch_crypto_quotes
from backend.providers.yahoo import fetch_yahoo_live_prices, fetch_yahoo_historical_prices

logger = logging.getLogger(__name__)


class PriceService:
    """Unified price service querying primary execution venues with fallbacks."""

    def __init__(self, config: Optional[BackendConfig] = None) -> None:
        self.config = config or BackendConfig()

    def get_live_prices_batch(self, tickers: List[str]) -> Dict[str, float]:
        """Fetch real-time prices for a list of tickers.

        1. Fetches crypto quotes from CoinGecko / Binance for 'BTC-EUR', 'ETH-EUR'.
        2. Fetches TradeGate quotes for mapped ISINs.
        3. Falls back to Yahoo Finance for missing quotes.
        """
        valid_tickers = sorted(set(t for t in tickers if t))
        results: Dict[str, float] = {t: 0.0 for t in valid_tickers}

        if not valid_tickers:
            return results

        # 1. Crypto quotes
        crypto_tickers = [t for t in valid_tickers if "BTC" in t or "ETH" in t]
        if crypto_tickers:
            crypto_quotes = fetch_crypto_quotes()
            for ct in crypto_tickers:
                q = crypto_quotes.get(ct, {}).get("last")
                if q and q > 0:
                    results[ct] = float(q)

        # 2. TradeGate quotes for traditional assets
        stock_tickers = [t for t in valid_tickers if t not in crypto_tickers]
        # Invert mapping to find ISIN for ticker
        mappings = self.config.get_mappings()
        ticker_to_isin = {}
        for isin_candidate, t in mappings.items():
            if t in stock_tickers and len(isin_candidate) == 12 and not isin_candidate.startswith("XFC"):
                ticker_to_isin[t] = isin_candidate

        unresolved_stocks = []
        for t in stock_tickers:
            isin = ticker_to_isin.get(t)
            if isin:
                tg = fetch_tradegate_quote(isin)
                if tg.get("last"):
                    results[t] = float(tg["last"])
                    continue
            unresolved_stocks.append(t)

        # 3. Yahoo Finance fallback for unresolved stocks or crypto
        if unresolved_stocks:
            yf_quotes = fetch_yahoo_live_prices(unresolved_stocks)
            for t, p in yf_quotes.items():
                if p > 0:
                    results[t] = p

        return results

    def get_historical_prices_batch(
        self,
        tickers: List[str],
        start_date: str,
    ) -> Dict[str, Dict[str, float]]:
        """Fetch daily closing prices from start_date forward."""
        return fetch_yahoo_historical_prices(tickers, start_date)


__all__ = [
    "PriceService",
    "fetch_tradegate_quote",
    "fetch_crypto_quotes",
    "fetch_yahoo_live_prices",
    "fetch_yahoo_historical_prices",
]
