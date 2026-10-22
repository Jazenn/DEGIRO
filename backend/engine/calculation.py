"""Canonical, deterministic calculation boundary; adapters own all I/O.

This first contract retains existing FIFO behavior. Accounting corrections belong
here and in its delegated ledger functions, never in a second consumer runtime.
Normalized dates retain broker-local semantics: timezone verification is pending.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Any
import pandas as pd

from backend.config import BackendConfig
from backend.engine.cash import calculate_cash_balance, calculate_net_invested_capital
from backend.engine.portfolio import compute_fifo_holdings


@dataclass(frozen=True)
class ObservedPrice:
    price_eur: float
    observed_at: str
    provider: str
    currency: str = "EUR"
    adjustment_basis: str = "unadjusted"
    retrieved_at: str | None = None


@dataclass(frozen=True)
class CalculationReport:
    ledger_version: str
    settings_version: str
    calculation_version: str
    cutoff: str
    holdings: pd.DataFrame
    cash_balance_eur: float
    net_external_contributions_eur: float
    observed_prices: Mapping[str, ObservedPrice]
    diagnostics: tuple[str, ...]


def calculate_portfolio(
    transactions: pd.DataFrame,
    *,
    observed_prices: Mapping[str, ObservedPrice],
    settings: Mapping[str, Any],
    ledger_version: str,
    settings_version: str,
    cutoff: str,
) -> CalculationReport:
    """Calculate an already normalized ledger through an explicit cutoff.

    Callers supply the accepted ledger/settings versions and observed EUR quotes.
    No file, provider, database or wall clock is consulted. Missing prices retain
    legacy cost valuation with an explicit coverage diagnostic, never a claim of
    observed market value. Naive source timestamps are compared in their source
    calendar until verified timezone normalization is implemented.
    """
    end = pd.Timestamp(cutoff)
    if pd.isna(end) or end.tzinfo is None:
        raise ValueError("cutoff must include a timezone")
    if not ledger_version or not settings_version:
        raise ValueError("ledger_version and settings_version must be nonempty")
    config = BackendConfig(dict(settings) or {"assets": {}})
    frame = transactions.copy(deep=True)
    diagnostics = []
    if not frame.empty:
        diagnostics.append("source_timezone_unverified:cutoff_eligibility_unavailable:legacy_wall_time_filter")
        times = frame.get("time", pd.Series("00:00", index=frame.index))
        dates = pd.to_datetime(frame["date"].astype(str) + " " + times.astype(str), dayfirst=True, errors="coerce")
        if dates.isna().any():
            raise ValueError("Normalized Transactions contain invalid dates")
        frame = frame.loc[dates <= end.tz_localize(None)].copy()
    for symbol, quote in observed_prices.items():
        observation = pd.Timestamp(quote.observed_at)
        if (not math.isfinite(quote.price_eur) or quote.price_eur <= 0
                or quote.currency != "EUR" or not quote.provider
                or observation.tzinfo is None or pd.isna(observation)
                or observation > end or quote.adjustment_basis != "unadjusted"):
            raise ValueError(f"Observed price is unusable for {symbol}")
    prices = {symbol: quote.price_eur for symbol, quote in observed_prices.items()}
    holdings = compute_fifo_holdings(frame, config=config, live_prices=prices)
    if not holdings.empty:
        for symbol in holdings["symbol"]:
            if symbol not in prices:
                diagnostics.append(f"missing_observed_price:{symbol}:legacy_cost_valuation")
    return CalculationReport(
        ledger_version, settings_version, "canonical-v1", end.isoformat(),
        holdings, calculate_cash_balance(frame), calculate_net_invested_capital(frame),
        dict(observed_prices), tuple(diagnostics),
    )
