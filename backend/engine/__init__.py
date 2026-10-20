"""Financial calculation engine package."""

from __future__ import annotations

from backend.engine.cash import (
    calculate_cash_balance,
    calculate_net_invested_capital,
    sort_transactions_chronologically,
    build_cumulative_cash_series,
)
from backend.engine.portfolio import (
    compute_fifo_holdings,
    build_daily_equity_history,
)
from backend.engine.rebalancer import RebalanceCalculator
from backend.engine.portfolio_engine import (
    PortfolioCalculationEngine,
    HISTORY_COLUMNS,
    HOLDING_COLUMNS,
    refresh_portfolio_snapshots,
    SnapshotRefreshResult,
)

__all__ = [
    "calculate_cash_balance",
    "calculate_net_invested_capital",
    "sort_transactions_chronologically",
    "build_cumulative_cash_series",
    "compute_fifo_holdings",
    "build_daily_equity_history",
    "RebalanceCalculator",
    "PortfolioCalculationEngine",
    "HISTORY_COLUMNS",
    "HOLDING_COLUMNS",
    "refresh_portfolio_snapshots",
    "SnapshotRefreshResult",
]
