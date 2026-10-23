"""Unit tests for backend.ingestion package."""

import io
import pandas as pd
import pytest

from backend.ingestion import (
    load_degiro_csv,
    parse_account_csv,
    parse_transactions_csv,
    parse_degiro_number,
    parse_trade_description,
    is_internal_cash_sweep,
    compute_row_hash,
)
from backend.engine.cash import calculate_cash_balance, calculate_net_invested_capital


def test_parse_degiro_number_formats():
    # Dutch format
    assert parse_degiro_number("1.234,56") == 1234.56
    assert parse_degiro_number("-1.000,50 EUR") == -1000.50
    assert parse_degiro_number("0,003472") == 0.003472
    # English format
    assert parse_degiro_number("1,234.56") == 1234.56
    assert parse_degiro_number("-50.25 USD") == -50.25
    # Degenerate values
    assert parse_degiro_number(None) is None
    assert parse_degiro_number("") is None
    assert parse_degiro_number("-") is None


def test_compute_row_hash_deterministic():
    h1 = compute_row_hash("2026-10-15", "09:30", "IE00BK5BQT80", "uuid-1", -170.10, "Koop 1 @ 170,1 EUR")
    h2 = compute_row_hash("2026-10-15", "09:30", "IE00BK5BQT80", "uuid-1", -170.10, "Koop 1 @ 170,1 EUR")
    assert h1 == h2
    assert len(h1) == 32
    assert isinstance(h1, str)


def test_parse_trade_description():
    action, qty, price = parse_trade_description("Koop 1 @ 170,1 EUR")
    assert action == "BUY"
    assert qty == 1.0
    assert price == 170.1

    action, qty, price = parse_trade_description("Koop 0,003472 @ 57.590,21 EUR")
    assert action == "BUY"
    assert qty == 0.003472
    assert price == 57590.21

    action, qty, price = parse_trade_description("Verkoop 4 @ 149,88 EUR")
    assert action == "SELL"
    assert qty == -4.0
    assert price == 149.88


def test_is_internal_cash_sweep():
    assert is_internal_cash_sweep("Degiro Cash Sweep Transfer", "") is True
    assert is_internal_cash_sweep("Overboeking van uw geldrekening bij flatexDEGIRO Bank", "") is True
    assert is_internal_cash_sweep("", "FLATEX EURO BANKACCOUNT") is True
    assert is_internal_cash_sweep("Koop 1 @ 170,1 EUR", "VANGUARD FTSE ALL-WORLD") is False
    assert is_internal_cash_sweep("iDEAL Deposit", "") is False


def test_real_account_csv_audit_exact_continuity():
    try:
        with open("Account.csv", "rb") as f:
            content = f.read()
    except FileNotFoundError:
        pytest.skip("Account.csv not found locally.")

    df = load_degiro_csv(content)
    assert len(df) == 172

    # Verify types
    assert len(df[df["is_cash_sweep"]]) == 58
    assert len(df[df["action"] == "BUY"]) == 23
    assert len(df[df["action"] == "SELL"]) == 3

    # Verify cash continuity: exact €5.96
    closing_cash = calculate_cash_balance(df)
    assert closing_cash == 5.96

    # Verify net deposited capital: exact €3,728.00
    net_invested = calculate_net_invested_capital(df)
    assert net_invested == 3728.00

def test_import_overlap_preserves_identical_fills_and_rejects_uncertain_multiplicity():
    from backend.ingestion import TransactionIngestionService
    header = "Date;Time;Product;ISIN;Quantity;Price;Value;Order ID\n"
    fill = "03-01-2024;09:30;Example ETF;IE00BK5BQT80;2;50;-100;order-1\n"
    service = TransactionIngestionService()
    first = service.ingest_csv((header + fill * 2).encode())
    assert first.new_rows == 2
    assert first.transactions["row_hash"].nunique() == 2
    assert service.ingest_csv((header + fill * 2).encode()).duplicates_skipped == 2
    review = service.ingest_csv((header + fill).encode())
    assert not review.accepted
    assert review.new_rows == 0
    assert "ambiguous_overlap_multiplicity" in review.diagnostics
    assert len(review.audit_transactions) == 1
    assert service.total_rows_seen == 2


def test_account_external_flows_exclude_reservations_and_sweeps():
    source = (
        "Datum;Tijd;Product;ISIN;Omschrijving;Mutatie;Saldo\n"
        "01-01-2024;09:00;DEGIRO;;Reservation iDEAL;500;500\n"
        "01-01-2024;09:01;DEGIRO;;Reservation iDEAL release;-500;0\n"
        "01-01-2024;09:02;FLATEX EURO BANKACCOUNT;;iDEAL Deposit;500;500\n"
        "02-01-2024;09:00;DEGIRO;;Terugstorting;-100;400\n"
        "03-01-2024;09:00;FLATEX EURO BANKACCOUNT;;Cash Sweep Transfer;-400;0\n"
        "03-01-2024;09:01;FLATEX EURO BANKACCOUNT;;Cash Sweep Transfer;400;400\n"
    )
    rows = load_degiro_csv(source.encode())
    assert list(rows["type"]) == ["RESERVATION", "RESERVATION", "DEPOSIT", "WITHDRAWAL", "CASH_SWEEP", "CASH_SWEEP"]
    assert calculate_net_invested_capital(rows) == 400
    assert calculate_cash_balance(rows) == 400

@pytest.mark.parametrize("bad", ["", "not-money", "NaN", "inf"])
def test_import_rejects_invalid_money_instead_of_inventing_zero(bad):
    from backend.ingestion import TransactionIngestionService
    source = f"Datum;Tijd;Product;ISIN;Omschrijving;Mutatie;Saldo\n01-01-2024;09:00;DEGIRO;;Storting;{bad};100\n"
    with pytest.raises(ValueError, match="Invalid Transaction amount"):
        TransactionIngestionService().ingest_csv(source.encode())


def test_corrections_remain_auditable_without_publishing_financial_changes():
    from backend.ingestion import TransactionIngestionService
    source = b"Date;Time;Product;ISIN;Description;Change;Balance\n01-01-2024;09:00;DEGIRO;;Correction reversal deposit;-500;0\n"
    result = TransactionIngestionService().ingest_csv(source)
    assert not result.accepted
    assert result.new_rows == 0
    assert result.audit_transactions.iloc[0]["amount"] == -500
    assert "correction_requires_review" in result.diagnostics


def test_import_retains_raw_asset_currency_and_unverified_timezone_evidence():
    source = b"Date;Time;Product;ISIN;Description;Change;;Balance;\n27-10-2024;02:30;BITCOIN;DE000A28M8D0;Buy 1 @ 50 USD;USD;-50;USD;100\n"
    rows = load_degiro_csv(source)
    record = rows.iloc[0]
    assert record["broker_asset_id"] == "DE000A28M8D0"
    assert record["raw_product"] == "BITCOIN"
    assert record["amount_currency"] == "USD"
    assert record["quote_currency"] == "USD"
    assert record["asset_kind"] == "unverified"
    assert record["quote_symbol"] is None
    assert record["source_timezone"] is None
    assert "source_timezone_unverified" in record["diagnostics"]

def test_import_validates_cash_continuity_and_retains_review_records():
    from backend.ingestion import TransactionIngestionService
    source = b"Date;Time;Product;ISIN;Description;Change;Balance\n01-01-2024;09:00;DEGIRO;;Deposit;1000;1000\n02-01-2024;09:00;DEGIRO;;Withdrawal;-100;800\n"
    result = TransactionIngestionService().ingest_csv(source)
    assert not result.accepted
    assert "cash_balance_discontinuity" in result.diagnostics
    assert len(result.audit_transactions) == 2


def test_overlapping_imports_retain_same_financial_result_after_service_restart():
    from backend.ingestion import TransactionIngestionService
    from backend.engine.calculation import calculate_portfolio
    source = b"Date;Time;Product;ISIN;Quantity;Price;Value;Order ID\n01-01-2024;09:30;ETF;IE00BK5BQT80;2;50;-100;order-1\n01-01-2024;09:30;ETF;IE00BK5BQT80;2;50;-100;order-1\n"
    first = TransactionIngestionService().ingest_csv(source)
    repeated = TransactionIngestionService(first.transactions).ingest_csv(source)
    assert repeated.new_rows == 0
    assert repeated.duplicates_skipped == 2
    report = calculate_portfolio(first.transactions, observed_prices={}, settings={},
                                 ledger_version="v1", settings_version="s1", cutoff="2024-01-02T00:00:00Z")
    assert report.holdings.iloc[0]["shares_held"] == 4
    assert report.cash_balance_eur == -200

def test_import_iso_dates_keep_calendar_meaning_at_calculation_cutoff():
    from backend.ingestion import TransactionIngestionService
    from backend.engine.calculation import calculate_portfolio
    source = b"Date;Time;Product;ISIN;Quantity;Price;Value;Order ID\n2026-05-10;09:00;ETF;IE00BK5BQT80;2;50;-100;order-1\n2026-10-05;09:00;ETF;IE00BK5BQT80;3;50;-150;order-2\n"
    result = TransactionIngestionService().ingest_csv(source)
    report = calculate_portfolio(result.transactions, observed_prices={}, settings={},
                                 ledger_version="v1", settings_version="s1", cutoff="2026-06-01T00:00:00Z")
    assert report.holdings.iloc[0]["shares_held"] == 2
    assert report.cash_balance_eur == -100

def test_account_blank_informational_mutation_preserves_source_without_cash_posting():
    from backend.ingestion import TransactionIngestionService
    source = b"Date;Time;Product;ISIN;Description;Change;;Balance;\n02-01-2024;09:00;DEGIRO;;Cash Sweep Transfer;EUR;;EUR;100\n01-01-2024;09:00;DEGIRO;;Deposit;EUR;100;EUR;100\n"
    result = TransactionIngestionService().ingest_csv(source)
    assert result.accepted
    assert len(result.transactions) == 2
    assert result.transactions.iloc[0]["type"] == "CASH_SWEEP"
    assert result.transactions.iloc[0]["mutation_present"] == False
    assert result.transactions.iloc[0]["source_record"]["unnamed: 6"] == ""
    assert calculate_cash_balance(result.transactions) == 100
    assert calculate_net_invested_capital(result.transactions) == 100

def test_sweep_notifications_bound_cash_continuity_to_comparable_account_segments():
    from backend.ingestion import TransactionIngestionService
    source = b"Date;Time;Product;ISIN;Description;Change;;Balance;\n04-01-2024;09:00;DEGIRO;;Dividend;EUR;10;EUR;10\n03-01-2024;09:00;DEGIRO;;Cash Sweep Transfer;EUR;;EUR;0\n02-01-2024;09:00;DEGIRO;;Cash Sweep Transfer;EUR;-100;EUR;100\n01-01-2024;09:00;DEGIRO;;Deposit;EUR;100;EUR;100\n"
    result = TransactionIngestionService().ingest_csv(source)
    assert result.accepted
    assert "cash_sweep_continuity_unverified" in result.diagnostics
    assert calculate_cash_balance(result.transactions) == 110
