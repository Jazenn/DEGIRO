"""Unit tests for backend.engine package."""

import pandas as pd
import pytest

from backend.config import BackendConfig
from backend.engine.cash import (
    sort_transactions_chronologically,
    calculate_cash_balance,
    calculate_net_invested_capital,
)
from backend.engine.portfolio import compute_fifo_holdings
from backend.engine.rebalancer import RebalanceCalculator


def test_sort_transactions_chronologically_tie_breaker():
    df = pd.DataFrame([
        {"date": "15-10-2026", "time": "09:00", "csv_row_id": 1, "desc": "first in export (later)"},
        {"date": "15-10-2026", "time": "09:00", "csv_row_id": 2, "desc": "second in export (earlier)"},
        {"date": "14-10-2026", "time": "09:00", "csv_row_id": 0, "desc": "day before"},
    ])
    sorted_df = sort_transactions_chronologically(df)
    assert sorted_df.iloc[0]["desc"] == "day before"
    assert sorted_df.iloc[1]["desc"] == "second in export (earlier)"
    assert sorted_df.iloc[2]["desc"] == "first in export (later)"


def test_compute_fifo_holdings_math():
    df = pd.DataFrame([
        {
            "date": "01-01-2024", "time": "09:00", "raw_product": "VANGUARD FTSE ALL-WORLD",
            "isin": "IE00BK5BQT80", "action": "BUY", "quantity": 10.0, "price": 100.0,
            "csv_row_id": 3, "is_cash_sweep": False
        },
        {
            "date": "02-01-2024", "time": "09:00", "raw_product": "VANGUARD FTSE ALL-WORLD",
            "isin": "IE00BK5BQT80", "action": "BUY", "quantity": 5.0, "price": 120.0,
            "csv_row_id": 2, "is_cash_sweep": False
        },
        {
            "date": "03-01-2024", "time": "09:00", "raw_product": "VANGUARD FTSE ALL-WORLD",
            "isin": "IE00BK5BQT80", "action": "SELL", "quantity": -8.0, "price": 130.0,
            "csv_row_id": 1, "is_cash_sweep": False
        },
    ])
    # FIFO: 10 @ 100 -> sell 8 leaves (2 @ 100) + (5 @ 120) = 7 shares held.
    # Total remaining cost = (2 * 100) + (5 * 120) = 200 + 600 = 800.
    config = BackendConfig()
    holdings = compute_fifo_holdings(df, config=config, live_prices={"VWCE.DE": 150.0})

    assert len(holdings) == 1
    row = holdings.iloc[0]
    assert row["symbol"] == "VWCE.DE"
    assert row["shares_held"] == 7.0
    assert row["total_cost_eur"] == 800.0
    assert row["current_price_eur"] == 150.0
    assert row["total_value_eur"] == 1050.0
    assert row["unrealized_pnl_eur"] == 250.0


def test_rebalance_calculator_proportional_deposit():
    calc = RebalanceCalculator()
    plan = calc.calculate_deposit_plan(
        deposit_amount=500.0,
        portfolio_value=1500.0,
        rebalancing_targets={"A": 60.0, "B": 40.0},
        current_values={"A": 1100.0, "B": 400.0},
        prices={"A": 100.0, "B": 50.0},
    )
    # Target value after deposit: Total = 2000.
    # A target: 1200 (gap = 100)
    # B target: 800 (gap = 400)
    # Total gap = 500
    # Recommended buy: A gets 500 * (100/500) = 100 EUR (1 share @ 100)
    # B gets 500 * (400/500) = 400 EUR (8 shares @ 50)
    assert plan["recommended_buys"]["A"] == 100.0
    assert plan["recommended_buys"]["B"] == 400.0
    assert plan["estimated_shares"]["A"] == 1.0
    assert plan["estimated_shares"]["B"] == 8.0
    assert plan["total_buy_eur"] == 500.0
