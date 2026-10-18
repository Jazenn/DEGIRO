import pandas as pd
import pytest

from contextlib import contextmanager
from unittest.mock import patch

from db_utils import DBStorage
from portfolio_calculation import PortfolioCalculationEngine
from snapshot_worker import refresh_portfolio_snapshots
from transaction_ingestion import TransactionIngestionService


def test_current_holdings_calculates_fifo_cost_basis_after_partial_sale():
    transactions = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Koop 10 @ 100",
                "amount": -1000.0,
            },
            {
                "date": "2024-01-02",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Koop 5 @ 120",
                "amount": -600.0,
            },
            {
                "date": "2024-01-03",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Verkoop 8 @ 130",
                "amount": 1040.0,
            },
        ]
    )

    holdings = PortfolioCalculationEngine().compute_current_holdings(
        transactions,
        prices={"IE00TEST1234": 150.0},
    )

    holding = holdings.iloc[0]
    assert holding["shares_held"] == pytest.approx(7.0)
    assert holding["total_cost_eur"] == pytest.approx(800.0)
    assert holding["total_value_eur"] == pytest.approx(1050.0)
    assert holding["unrealized_pnl_eur"] == pytest.approx(250.0)


def test_current_holdings_uses_execution_price_in_description_not_fees_in_cash_amount():
    transactions = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Koop 10 @ 100,00 EUR",
                "amount": -1001.0,
            }
        ]
    )

    holding = PortfolioCalculationEngine().compute_current_holdings(
        transactions,
        prices={"IE00TEST1234": 110.0},
    ).iloc[0]

    assert holding["total_cost_eur"] == pytest.approx(1000.0)
    assert holding["unrealized_pnl_eur"] == pytest.approx(100.0)


def test_ingested_transactions_produce_fifo_holdings():
    csv_content = (
        "Date;Time;Product;ISIN;Quantity;Price;Value;Order ID\n"
        "01-01-2024;09:00;Example ETF;IE00TEST1234;10;100;-1000;buy-1\n"
        "02-01-2024;09:00;Example ETF;IE00TEST1234;5;120;-600;buy-2\n"
        "03-01-2024;09:00;Example ETF;IE00TEST1234;-8;130;1040;sell-1\n"
    ).encode("utf-8")
    imported = TransactionIngestionService().ingest_csv(csv_content).transactions

    holdings = PortfolioCalculationEngine().compute_current_holdings(
        imported,
        prices={"IE00TEST1234": 150.0},
    )

    assert holdings.iloc[0]["shares_held"] == pytest.approx(7.0)
    assert holdings.iloc[0]["total_cost_eur"] == pytest.approx(800.0)


def test_daily_history_carries_holdings_forward_and_tracks_cash_and_contributions():
    transactions = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "time": "09:00",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Storting",
                "amount": 1000.0,
                "balance": 1000.0,
            },
            {
                "date": "2024-01-02",
                "time": "09:00",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Koop 5 @ 100",
                "amount": -500.0,
                "balance": 500.0,
            },
        ]
    )

    history = PortfolioCalculationEngine().compute_daily_history(
        transactions,
        prices={"IE00TEST1234": 120.0},
        historical_prices={
            "IE00TEST1234": {
                "2024-01-01": 100.0,
                "2024-01-02": 110.0,
                "2024-01-03": 120.0,
            }
        },
    )

    assert history["total_equity_eur"].tolist() == pytest.approx([1000.0, 1050.0, 1100.0])
    assert history["invested_capital_eur"].tolist() == pytest.approx([1000.0, 1000.0, 1000.0])
    assert history["cash_balance_eur"].tolist() == pytest.approx([1000.0, 500.0, 500.0])
    assert history["unrealized_pnl_eur"].tolist() == pytest.approx([0.0, 50.0, 100.0])


def test_daily_history_accepts_zero_reported_cash_balance():
    transactions = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Storting",
                "amount": 500.0,
                "balance": 500.0,
            },
            {
                "date": "2024-01-02",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Koop 5 @ 100",
                "amount": -500.0,
                "balance": 0.0,
            },
        ]
    )

    history = PortfolioCalculationEngine().compute_daily_history(
        transactions,
        prices={"IE00TEST1234": 100.0},
    )

    assert history["cash_balance_eur"].tolist() == pytest.approx([500.0, 0.0])


def test_daily_history_reports_unrealized_gain_after_fifo_sale():
    transactions = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "time": "08:00",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Storting",
                "amount": 1000.0,
                "balance": 1000.0,
            },
            {
                "date": "2024-01-01",
                "time": "09:00",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Koop 10 @ 100",
                "amount": -1000.0,
                "balance": 0.0,
            },
            {
                "date": "2024-01-02",
                "time": "09:00",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Verkoop 5 @ 130",
                "amount": 650.0,
                "balance": 650.0,
            },
        ]
    )

    history = PortfolioCalculationEngine().compute_daily_history(
        transactions,
        prices={"IE00TEST1234": 100.0},
    )

    assert history.iloc[-1]["total_equity_eur"] == pytest.approx(1150.0)
    assert history.iloc[-1]["unrealized_pnl_eur"] == pytest.approx(0.0)


def test_database_storage_persists_history_and_current_holdings_snapshots():
    executed = []

    class Cursor:
        rowcount = 1

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, sql, parameters=None):
            executed.append((sql, parameters))

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def connection():
        yield Connection()

    storage = DBStorage.__new__(DBStorage)
    history = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2024-01-01"),
                "total_equity_eur": 1000.0,
                "invested_capital_eur": 1000.0,
                "cash_balance_eur": 500.0,
                "unrealized_pnl_eur": 0.0,
                "unrealized_pnl_pct": 0.0,
            }
        ]
    )
    holdings = pd.DataFrame(
        [
            {
                "symbol": "IE00TEST1234",
                "name": "Example ETF",
                "isin": "IE00TEST1234",
                "shares_held": 5.0,
                "current_price_eur": 100.0,
                "total_value_eur": 500.0,
                "total_cost_eur": 450.0,
                "unrealized_pnl_eur": 50.0,
                "actual_pct": 50.0,
                "target_pct": 60.0,
                "drift_pct": -10.0,
                "recommended_action_eur": 0.0,
            }
        ]
    )

    with patch.object(storage, "_conn", side_effect=connection):
        storage.save_portfolio_snapshots(history, holdings)

    sql_statements = [sql for sql, _ in executed]
    assert any("INSERT INTO portfolio_daily_history" in sql for sql in sql_statements)
    assert any("DELETE FROM current_asset_holdings" in sql for sql in sql_statements)
    assert any("INSERT INTO current_asset_holdings" in sql for sql in sql_statements)


def test_snapshot_refresh_fetches_quotes_and_persists_calculated_read_models():
    transactions = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "time": "09:00",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Storting",
                "amount": 1000.0,
                "balance": 1000.0,
            },
            {
                "date": "2024-01-02",
                "time": "09:00",
                "product": "Example ETF",
                "isin": "IE00TEST1234",
                "description": "Koop 5 @ 100",
                "amount": -500.0,
                "balance": 500.0,
            },
        ]
    )

    class Storage:
        saved = None

        def load_transactions(self):
            return transactions

        def save_portfolio_snapshots(self, history, holdings):
            self.saved = history, holdings

    class PriceProvider:
        def resolve_ticker(self, product, isin):
            assert product == "Example ETF"
            assert isin == "IE00TEST1234"
            return "EXAMPLE"

        def get_live_prices_batch(self, tickers):
            assert tickers == ["EXAMPLE"]
            return {"EXAMPLE": 120.0}

        def get_historical_prices_batch(self, tickers, start_date):
            assert tickers == ["EXAMPLE"]
            assert start_date == "2024-01-01"
            return {
                "EXAMPLE": {
                    "2024-01-01": 100.0,
                    "2024-01-02": 110.0,
                }
            }

    class Configuration:
        def get_assets(self):
            return {"IE00TEST1234": {"target_pct": 60.0}}

    storage = Storage()
    result = refresh_portfolio_snapshots(
        storage,
        PriceProvider(),
        Configuration(),
        as_of_date="2024-01-02",
    )

    assert result.history_rows == 2
    assert result.holding_rows == 1
    assert result.quotes_requested == 1
    history, holdings = storage.saved
    assert history.iloc[-1]["total_equity_eur"] == pytest.approx(1100.0)
    assert holdings.iloc[0]["current_price_eur"] == pytest.approx(120.0)
    assert holdings.iloc[0]["target_pct"] == pytest.approx(60.0)
