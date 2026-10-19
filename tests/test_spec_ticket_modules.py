import io
import hashlib
import json
from contextlib import contextmanager
from unittest.mock import patch

import pandas as pd
import pytest

from db_utils import DBStorage
from portfolio_calculation import PortfolioCalculationEngine
from rebalance_calculator import RebalanceCalculator
from transaction_ingestion import TransactionIngestionService


def test_transaction_ingestion_service_handles_dutch_and_english_headers_and_idempotency():
    dutch_csv = io.StringIO(
        "Datum;Product;ISIN;Aantal;Koers;Waarde;Saldo\n"
        "01-01-2024;Vanguard FTSE All-World UCITS ETF;IE00BK5BQT80;10;100;1000;5000\n"
        "02-01-2024;Vanguard FTSE All-World UCITS ETF;IE00BK5BQT80;5;110;550;4450\n"
    )
    english_csv = io.StringIO(
        "Date;Product;ISIN;Quantity;Price;Value;Balance\n"
        "03-01-2024;Bitcoin;XFC000A2YY6Q;0.5;50000;25000;4200\n"
    )

    service = TransactionIngestionService()
    first = service.ingest_csv(dutch_csv.getvalue().encode("utf-8"))
    second = service.ingest_csv(dutch_csv.getvalue().encode("utf-8"))
    third = service.ingest_csv(english_csv.getvalue().encode("utf-8"))

    assert first.new_rows == 2
    assert second.new_rows == 0
    assert second.duplicates_skipped == 2
    assert third.new_rows == 1
    assert service.total_rows_seen == 3


def test_transaction_ingestion_service_returns_normalized_rows_with_stable_hashes():
    csv_content = (
        "Date;Time;Product;ISIN;Quantity;Price;Value;Order ID\n"
        "03-01-2024;09:30;Example ETF;IE00TEST1234;2;50;100;order-1\n"
        "03-01-2024;09:30;Example ETF;IE00TEST1234;2;50;100;order-1\n"
    ).encode("utf-8")

    result = TransactionIngestionService().ingest_csv(csv_content)

    assert result.rows_processed == 2
    assert result.new_rows == 1
    assert result.duplicates_skipped == 1
    assert len(result.transactions) == 1
    transaction = result.transactions.iloc[0]
    assert transaction["isin"] == "IE00TEST1234"
    assert transaction["amount"] == pytest.approx(100.0)
    assert transaction["row_hash"] == TransactionIngestionService._row_hash(transaction)
    repeated = TransactionIngestionService().ingest_csv(csv_content)
    assert repeated.transactions.iloc[0]["row_hash"] == transaction["row_hash"]


def test_transaction_ingestion_service_parses_account_csv_cash_flows():
    account_csv = (
        "Datum;Tijd;Valutadatum;Product;ISIN;Omschrijving;Mutatie;Saldo;Order ID\n"
        "01-01-2024;09:00;01-01-2024;DEGIRO;NLFLATEXACNT;Storting;500,00;500,00;\n"
        "02-01-2024;09:30;02-01-2024;Example ETF;IE00TEST1234;Koop 2 @ 50;-100,00;400,00;order-1\n"
    ).encode("utf-8")
    transactions_csv = (
        "Date;Time;Product;ISIN;Quantity;Price;Value;Order ID\n"
        "02-01-2024;09:30;Example ETF;IE00TEST1234;2;50;-100;order-1\n"
    ).encode("utf-8")

    service = TransactionIngestionService()
    result = service.ingest_csv(account_csv)
    overlapping = service.ingest_csv(transactions_csv)

    assert result.rows_processed == 2
    assert result.new_rows == 2
    assert result.transactions.iloc[0]["amount"] == pytest.approx(500.0)
    assert result.transactions.iloc[0]["description"] == "Storting"
    assert result.transactions.iloc[1]["description"] == "Koop 2 @ 50"
    assert overlapping.new_rows == 0
    assert overlapping.duplicates_skipped == 1


def test_transaction_ingestion_service_rejects_unrecognized_csv_with_a_descriptive_error():
    with pytest.raises(ValueError, match="Unsupported DEGIRO CSV format"):
        TransactionIngestionService().ingest_csv(b"not,a,degiro,export\n1,2,3,4\n")


def test_database_storage_uses_ingestion_hashes_to_skip_reuploads():
    csv_content = (
        "Date;Time;Product;ISIN;Quantity;Price;Value;Order ID\n"
        "03-01-2024;09:30;Example ETF;IE00TEST1234;2;50;100;order-1\n"
    ).encode("utf-8")
    transactions = TransactionIngestionService().ingest_csv(csv_content).transactions
    stored_hashes = set()

    class Cursor:
        rowcount = 0
        results = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, sql, record):
            if sql.lstrip().startswith("SELECT"):
                self.results = [(value,) for value in record[0] if value in stored_hashes]
                return
            row_hash = record["row_hash"]
            self.rowcount = 0 if row_hash in stored_hashes else 1
            stored_hashes.add(row_hash)

        def fetchall(self):
            return self.results

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def connection():
        yield Connection()

    storage = DBStorage.__new__(DBStorage)
    with patch.object(storage, "_conn", side_effect=connection):
        assert storage.save_transactions(transactions) == 1
        assert transactions.iloc[0]["row_hash"] in stored_hashes
        assert storage.save_transactions(transactions) == 0


def test_database_storage_skips_rows_with_legacy_hashes():
    csv_content = (
        "Date;Time;Product;ISIN;Quantity;Price;Value;Order ID\n"
        "03-01-2024;09:30;Example ETF;IE00TEST1234;2;50;100;order-1\n"
    ).encode("utf-8")
    transactions = TransactionIngestionService().ingest_csv(csv_content).transactions
    legacy_payload = {"order_id": "order-1", "amount": "100.0", "isin": "IE00TEST1234"}
    legacy_hash = hashlib.md5(
        json.dumps(legacy_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    stored_hashes = {legacy_hash}

    class Cursor:
        rowcount = 0
        results = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, sql, record):
            if sql.lstrip().startswith("SELECT"):
                self.results = [(value,) for value in record[0] if value in stored_hashes]
                return
            row_hash = record["row_hash"]
            self.rowcount = 0 if row_hash in stored_hashes else 1
            stored_hashes.add(row_hash)

        def fetchall(self):
            return self.results

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def connection():
        yield Connection()

    storage = DBStorage.__new__(DBStorage)
    with patch.object(storage, "_conn", side_effect=connection):
        assert storage.save_transactions(transactions) == 0
    assert stored_hashes == {legacy_hash}


def test_rebalance_calculator_only_buys_underweight_assets():
    calculator = RebalanceCalculator()
    rebalancing_targets = {"All-World": 0.60, "Bitcoin": 0.20, "Europe": 0.20}
    current_values = {"All-World": 200.0, "Bitcoin": 600.0, "Europe": 200.0}
    deposit = 500.0

    plan = calculator.calculate_deposit_plan(
        deposit_amount=deposit,
        portfolio_value=sum(current_values.values()),
        rebalancing_targets=rebalancing_targets,
        current_values=current_values,
        prices={"All-World": 100.0, "Bitcoin": 50000.0, "Europe": 50.0},
    )

    assert plan["total_buy_eur"] == pytest.approx(deposit)
    assert plan["recommended_buys"]["All-World"] > 0
    assert plan["recommended_buys"]["Bitcoin"] == pytest.approx(0.0)
    assert plan["recommended_buys"]["Europe"] > 0
    assert all(value >= 0 for value in plan["recommended_buys"].values())


def test_rebalance_calculator_zero_deposit_returns_zero_buys():
    calculator = RebalanceCalculator()
    rebalancing_targets = {"All-World": 0.60, "Bitcoin": 0.20, "Europe": 0.20}
    current_values = {"All-World": 200.0, "Bitcoin": 600.0, "Europe": 200.0}

    plan = calculator.calculate_deposit_plan(
        deposit_amount=0.0,
        portfolio_value=sum(current_values.values()),
        rebalancing_targets=rebalancing_targets,
        current_values=current_values,
    )

    assert plan["total_buy_eur"] == pytest.approx(0.0)
    assert all(val == 0.0 for val in plan["recommended_buys"].values())
    assert plan["underweight_assets"] == []


def test_rebalance_calculator_all_balanced_returns_zero_buys_when_no_gap():
    calculator = RebalanceCalculator()
    rebalancing_targets = {"All-World": 0.50, "Bitcoin": 0.50}
    current_values = {"All-World": 500.0, "Bitcoin": 500.0}

    plan = calculator.calculate_deposit_plan(
        deposit_amount=0.0,
        portfolio_value=1000.0,
        rebalancing_targets=rebalancing_targets,
        current_values=current_values,
    )

    assert plan["total_buy_eur"] == pytest.approx(0.0)
    assert plan["recommended_buys"]["All-World"] == 0.0
    assert plan["recommended_buys"]["Bitcoin"] == 0.0


def test_rebalance_calculator_single_underweight_asset_receives_full_deposit():
    calculator = RebalanceCalculator()
    rebalancing_targets = {"All-World": 0.60, "Bitcoin": 0.20, "Europe": 0.20}
    # VWCE: 800 (target 660), BTC: 250 (target 220), IMAE: 50 (target 220)
    # Projected total with deposit 100 is 1200:
    # VWCE target: 720 (< 800), BTC target: 240 (< 250), IMAE target: 240 (> 50)
    current_values = {"All-World": 800.0, "Bitcoin": 250.0, "Europe": 50.0}
    deposit = 100.0

    plan = calculator.calculate_deposit_plan(
        deposit_amount=deposit,
        portfolio_value=1100.0,
        rebalancing_targets=rebalancing_targets,
        current_values=current_values,
        prices={"All-World": 100.0, "Bitcoin": 50000.0, "Europe": 50.0},
    )

    assert plan["underweight_assets"] == ["Europe"]
    assert plan["recommended_buys"]["Europe"] == pytest.approx(deposit)
    assert plan["recommended_buys"]["All-World"] == 0.0
    assert plan["recommended_buys"]["Bitcoin"] == 0.0
    assert plan["total_buy_eur"] == pytest.approx(deposit)
    assert plan["estimated_shares"]["Europe"] == pytest.approx(deposit / 50.0)


def test_rebalance_calculator_deposit_larger_than_drift_enforces_non_negative_buys():
    calculator = RebalanceCalculator()
    rebalancing_targets = {"All-World": 0.60, "Bitcoin": 0.20, "Europe": 0.20}
    current_values = {"All-World": 580.0, "Bitcoin": 250.0, "Europe": 170.0}
    deposit = 5000.0

    plan = calculator.calculate_deposit_plan(
        deposit_amount=deposit,
        portfolio_value=1000.0,
        rebalancing_targets=rebalancing_targets,
        current_values=current_values,
        prices={"All-World": 100.0, "Bitcoin": 50000.0, "Europe": 50.0},
    )

    assert plan["total_buy_eur"] == pytest.approx(deposit)
    assert all(val >= 0.0 for val in plan["recommended_buys"].values())
    assert all(val >= 0.0 for val in plan["estimated_shares"].values())


def test_rebalance_calculator_converts_to_estimated_shares():
    calculator = RebalanceCalculator()
    rebalancing_targets = {"VWCE": 0.80, "BTC": 0.20}
    current_values = {"VWCE": 200.0, "BTC": 800.0}
    prices = {"VWCE": 125.0, "BTC": 60000.0}
    deposit = 500.0

    plan = calculator.calculate_deposit_plan(
        deposit_amount=deposit,
        portfolio_value=1000.0,
        rebalancing_targets=rebalancing_targets,
        current_values=current_values,
        prices=prices,
    )

    assert plan["recommended_buys"]["VWCE"] == pytest.approx(500.0)
    assert plan["estimated_shares"]["VWCE"] == pytest.approx(500.0 / 125.0)
    assert plan["estimated_shares"]["BTC"] == pytest.approx(0.0)



def test_portfolio_calculation_engine_generates_daily_history_and_current_holdings():
    transactions = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "time": "09:30",
                "value_date": "2024-01-01",
                "product": "All-World",
                "isin": "IE00BK5BQT80",
                "description": "Koop 10 @ 100",
                "amount": -1000.0,
                "balance": 5000.0,
                "order_id": "order-1",
                "fx": 0.0,
                "price": 100.0,
                "quantity": 10.0,
            },
            {
                "date": "2024-01-02",
                "time": "09:30",
                "value_date": "2024-01-02",
                "product": "All-World",
                "isin": "IE00BK5BQT80",
                "description": "Dividend",
                "amount": 20.0,
                "balance": 5020.0,
                "order_id": "order-2",
                "fx": 0.0,
                "price": 100.0,
                "quantity": 0.0,
            },
        ]
    )

    engine = PortfolioCalculationEngine()
    history = engine.compute_daily_history(transactions, prices={"IE00BK5BQT80": 110.0})
    holdings = engine.compute_current_holdings(transactions, prices={"IE00BK5BQT80": 110.0}, targets={"IE00BK5BQT80": 0.5})

    assert not history.empty
    assert "total_equity_eur" in history.columns
    assert "unrealized_pnl_eur" in history.columns
    assert holdings.iloc[0]["symbol"] == "IE00BK5BQT80"
    assert holdings.iloc[0]["shares_held"] == pytest.approx(10.0)
    assert holdings.iloc[0]["total_value_eur"] == pytest.approx(1100.0)
