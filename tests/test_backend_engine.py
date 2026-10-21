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


def test_rebalance_calculator_whole_shares_for_stocks_and_exact_for_crypto():
    calc = RebalanceCalculator()
    # Deposit 100 EUR into stock priced at 124.8 EUR (previously gave 0.8 shares)
    plan = calc.calculate_deposit_plan(
        deposit_amount=100.0,
        portfolio_value=1248.0,
        rebalancing_targets={"VWCE": 100.0},
        current_values={"VWCE": 1248.0},
        prices={"VWCE": 124.8},
        round_to_whole_shares=True,
        is_crypto={"VWCE": False},
    )
    assert plan["estimated_shares"]["VWCE"] == 1.0
    assert plan["recommended_buys"]["VWCE"] == 124.8


def test_rebalance_calculator_allow_selling_overweight_crypto_to_buy_stock():
    calc = RebalanceCalculator()
    # BTC is overweight (800 vs 200 target). VWCE is underweight (200 vs 800 target).
    # Deposit is 0 EUR. With allow_selling=True, BTC is sold to buy VWCE whole shares.
    plan = calc.calculate_deposit_plan(
        deposit_amount=0.0,
        portfolio_value=1000.0,
        rebalancing_targets={"VWCE": 80.0, "BTC": 20.0},
        current_values={"VWCE": 200.0, "BTC": 800.0},
        prices={"VWCE": 100.0, "BTC": 50000.0},
        allow_selling=True,
        round_to_whole_shares=True,
        is_crypto={"VWCE": False, "BTC": True},
    )
    assert plan["total_sell_eur"] > 0
    assert plan["recommended_sells"]["BTC"] == 600.0
    assert plan["estimated_shares_to_sell"]["BTC"] == 600.0 / 50000.0
    assert plan["recommended_buys"]["VWCE"] == 600.0
    assert plan["estimated_shares"]["VWCE"] == 6.0
