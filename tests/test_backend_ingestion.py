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
