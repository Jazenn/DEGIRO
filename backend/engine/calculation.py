"""Canonical, deterministic calculation boundary; adapters own all I/O.

The Decimal ledger and to_read_model are authoritative for new consumers. Legacy
DataFrame fields retain the existing dashboard adapter until migration acceptance.
Normalized dates retain broker-local semantics: timezone verification is pending.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Mapping, Any
import pandas as pd

from backend.engine.ledger import Ledger, calculate_ledger, number, eur_rate
from backend.config import BackendConfig
from backend.engine.cash import calculate_cash_balance, calculate_net_invested_capital
from backend.engine.portfolio import compute_fifo_holdings


@dataclass(frozen=True)
class ObservedPrice:
    price_eur: float | Decimal | str
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
    ledger: Ledger

    def to_read_model(self) -> dict:
        """Versioned JSON contract for new consumers; decimal values are strings.

        Legacy DataFrame/cash fields intentionally stay outside this contract.
        """
        def encode(value):
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, dict):
                return {key: encode(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [encode(item) for item in value]
            return value
        return encode({
            "ledger_version": self.ledger_version,
            "settings_version": self.settings_version,
            "calculation_version": "decimal-accounting-v1",
            "cutoff": self.cutoff,
            "ledger": asdict(self.ledger),
            "observed_prices": {symbol: {**asdict(quote), "price_eur": number(quote.price_eur)}
                                for symbol, quote in self.observed_prices.items()},
            "diagnostics": tuple(sorted(set(self.diagnostics + self.ledger.diagnostics))),
        })


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
    if "is_cash_sweep" in frame:
        frame["is_cash_sweep"] = frame["is_cash_sweep"].astype(bool)
    diagnostics = sorted({diagnostic for values in frame.get("diagnostics", []) for diagnostic in values})
    blockers = {"correction_requires_review", "cash_balance_discontinuity", "same_time_ordering_requires_review", "transaction_classification_requires_review"}.intersection(diagnostics)
    if blockers:
        raise ValueError("Transaction review required: " + ", ".join(sorted(blockers)))
    if "amount_currency" in frame and (~frame["amount_currency"].fillna("").isin(["", "EUR"])).any():
        if any(eur_rate(row, settings) is None for row in frame.to_dict("records") if row.get("amount_currency") not in ("", "EUR")):
            raise ValueError("non_eur_cash_requires_dated_fx: cannot publish an EUR cash balance")
    if not frame.empty:
        timezone = settings.get("source_timezone", {})
        verified_timezone = timezone.get("verified") is True and bool(timezone.get("evidence"))
        if not verified_timezone:
            diagnostics.append("source_timezone_unverified:cutoff_eligibility_unavailable:legacy_wall_time_filter")
        times = frame.get("time", pd.Series("00:00", index=frame.index))
        dates = pd.to_datetime(frame.get("normalized_date", frame["date"]).astype(str) + " " + times.astype(str), dayfirst="normalized_date" not in frame, errors="coerce")
        if dates.isna().any():
            raise ValueError("Normalized Transactions contain invalid dates")
        if verified_timezone:
            dates = dates.dt.tz_localize(timezone["name"], ambiguous="raise", nonexistent="raise")
            frame = frame.loc[dates <= end].copy()
        else:
            frame = frame.loc[dates <= end.tz_localize(None)].copy()
    for symbol, quote in observed_prices.items():
        observation = pd.Timestamp(quote.observed_at)
        if (not Decimal(str(quote.price_eur)).is_finite() or number(quote.price_eur) <= 0
                or quote.currency != "EUR" or not quote.provider
                or observation.tzinfo is None or pd.isna(observation)
                or observation > end or quote.adjustment_basis != "unadjusted"):
            raise ValueError(f"Observed price is unusable for {symbol}")
    prices = {symbol: float(quote.price_eur) for symbol, quote in observed_prices.items()}
    holdings = compute_fifo_holdings(frame, config=config, live_prices=prices)
    if not holdings.empty:
        for symbol in holdings["symbol"]:
            if symbol not in prices:
                diagnostics.append(f"missing_observed_price:{symbol}:legacy_cost_valuation")
    ledger = calculate_ledger(frame, observed_prices, settings, end)
    legacy_cash_frame = frame.copy()
    if not frame.empty:
        legacy_cash_frame["amount"] = [float(number(row["amount"]) * (eur_rate(row, settings) or Decimal(1))) for row in frame.to_dict("records")]
    return CalculationReport(
        ledger_version, settings_version, "canonical-v1", end.isoformat(),
        holdings, calculate_cash_balance(legacy_cash_frame), calculate_net_invested_capital(legacy_cash_frame),
        dict(observed_prices), tuple(sorted(set(diagnostics + list(ledger.diagnostics)))), ledger,
    )
