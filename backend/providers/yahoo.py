"""Yahoo Finance market data provider."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_yahoo_live_prices(tickers: List[str]) -> Dict[str, float]:
    """Fetch live closing prices for multiple tickers via Yahoo Finance."""
    valid_tickers = sorted(set(t for t in tickers if t))
    if not valid_tickers:
        return {}

    results = {t: 0.0 for t in valid_tickers}
    try:
        tickers_str = " ".join(valid_tickers)
        data = yf.download(
            tickers_str,
            period="1d",
            group_by="ticker",
            progress=False,
            threads=True,
        )
        for t in valid_tickers:
            try:
                if len(valid_tickers) == 1:
                    if not data.empty and "Close" in data:
                        close_vals = data["Close"].dropna()
                        if not close_vals.empty:
                            results[t] = float(close_vals.iloc[-1])
                else:
                    if t in data and "Close" in data[t]:
                        close_vals = data[t]["Close"].dropna()
                        if not close_vals.empty:
                            results[t] = float(close_vals.iloc[-1])
            except Exception:
                pass
    except Exception as e:
        logger.debug("YF batch download error: %s", e)

    # Fallback to fast_info for tickers that returned 0
    for t in valid_tickers:
        if results.get(t, 0.0) <= 0:
            try:
                p = yf.Ticker(t).fast_info.last_price
                if p:
                    results[t] = float(p)
            except Exception:
                pass

    return results


def fetch_yahoo_historical_prices(
    tickers: List[str],
    start_date: str,
) -> Dict[str, Dict[str, float]]:
    """Fetch daily closing prices keyed by ticker and ISO date string (YYYY-MM-DD)."""
    valid_tickers = sorted(set(t for t in tickers if t))
    if not valid_tickers:
        return {}

    try:
        data = yf.download(
            valid_tickers,
            start=start_date,
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
    except Exception as e:
        logger.debug("YF historical download error: %s", e)
        return {t: {} for t in valid_tickers}

    if data.empty:
        return {t: {} for t in valid_tickers}

    result: Dict[str, Dict[str, float]] = {}
    for t in valid_tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if t not in data.columns.get_level_values(0):
                    result[t] = {}
                    continue
                close = data[t]["Close"]
            elif "Close" in data.columns:
                close = data["Close"]
            else:
                result[t] = {}
                continue

            close_num = pd.to_numeric(close, errors="coerce").dropna()
            if close_num.index.tz is not None:
                close_num.index = close_num.index.tz_localize(None)

            result[t] = {
                date.strftime("%Y-%m-%d"): float(price)
                for date, price in close_num.items()
                if price > 0
            }
        except Exception:
            result[t] = {}

    return result
