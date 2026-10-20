"""DEGIRO Backend Package.

Modular architecture for DEGIRO transaction ingestion, FIFO valuation,
market price providers, and Neon PostgreSQL pre-aggregated snapshots.
"""

from __future__ import annotations

from backend.config import BackendConfig
from backend.ingestion import load_degiro_csv
from backend.engine import (
    calculate_cash_balance,
    calculate_net_invested_capital,
    compute_fifo_holdings,
    build_daily_equity_history,
    RebalanceCalculator,
)

__all__ = [
    "BackendConfig",
    "load_degiro_csv",
    "calculate_cash_balance",
    "calculate_net_invested_capital",
    "compute_fifo_holdings",
    "build_daily_equity_history",
    "RebalanceCalculator",
]
