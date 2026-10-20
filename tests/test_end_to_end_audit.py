"""End-to-end audit and ingestion verification tests for raw Account.csv."""

from __future__ import annotations

import io
from pathlib import Path
import pytest
import pandas as pd

from backend.ingestion import load_degiro_csv
from backend.engine.cash import calculate_cash_balance, calculate_net_invested_capital
from backend.engine.portfolio import compute_fifo_holdings, build_daily_equity_history
from backend.cli import cmd_audit


def _resolve_account_csv() -> Path | None:
    """Find Account.csv in current directory or repo root."""
    candidate_paths = [
        Path("Account.csv"),
        Path(__file__).resolve().parent.parent / "Account.csv",
        Path("C:/Users/griff/Projects/DEGIRO/Account.csv"),
    ]
    for p in candidate_paths:
        if p.exists() and p.is_file():
            return p
    return None


@pytest.fixture
def account_csv_path() -> Path:
    p = _resolve_account_csv()
    if not p:
        pytest.skip("Account.csv not found locally.")
    return p


def test_end_to_end_account_csv_ingestion_and_valuation(account_csv_path: Path):
    """Validate full end-to-end pipeline on raw Account.csv."""
    with open(account_csv_path, "rb") as f:
        content = f.read()

    # 1. Ingestion & Grammar Validation
    df = load_degiro_csv(content)
    assert len(df) == 172, f"Expected exactly 172 rows parsed, got {len(df)}"

    # Required forensic schema contract columns
    required_cols = [
        "date", "time", "product", "isin", "description",
        "amount", "balance", "action", "quantity", "price",
        "row_hash", "is_cash_sweep", "type"
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing expected column '{col}' in normalized DataFrame"

    # 2. Cash Accounting & Forensic Invariants
    net_invested = calculate_net_invested_capital(df)
    assert net_invested == 3728.00, f"Expected net invested capital of €3,728.00, got €{net_invested}"

    closing_cash = calculate_cash_balance(df)
    assert closing_cash == 5.96, f"Expected closing cash balance of €5.96, got €{closing_cash}"

    # 3. FIFO Asset Holdings Verification
    holdings = compute_fifo_holdings(df)
    assert not holdings.empty, "FIFO holdings DataFrame should not be empty"

    holdings_by_symbol = {row["symbol"]: row for _, row in holdings.iterrows()}

    # Verify exact holdings: 11 VWCE, 18 EXUS, 4 IMAE, 10 FOD, 0.010844 BTC, 0.062577 ETH
    assert "VWCE.DE" in holdings_by_symbol
    assert holdings_by_symbol["VWCE.DE"]["shares_held"] == 11.0
    assert holdings_by_symbol["VWCE.DE"]["isin"] == "IE00BK5BQT80"

    assert "EXUS.DE" in holdings_by_symbol
    assert holdings_by_symbol["EXUS.DE"]["shares_held"] == 18.0
    assert holdings_by_symbol["EXUS.DE"]["isin"] == "IE0006WW1TQ4"

    assert "IMAE.AS" in holdings_by_symbol
    assert holdings_by_symbol["IMAE.AS"]["shares_held"] == 4.0
    assert holdings_by_symbol["IMAE.AS"]["isin"] == "IE00B4K48X80"

    # ASWC.DE is Future of Defence (FOD) ETF: IE000OJ5TQP4
    assert "ASWC.DE" in holdings_by_symbol
    assert holdings_by_symbol["ASWC.DE"]["shares_held"] == 10.0
    assert holdings_by_symbol["ASWC.DE"]["isin"] == "IE000OJ5TQP4"

    assert "BTC-EUR" in holdings_by_symbol
    assert holdings_by_symbol["BTC-EUR"]["shares_held"] == pytest.approx(0.010844, abs=1e-6)

    assert "ETH-EUR" in holdings_by_symbol
    assert holdings_by_symbol["ETH-EUR"]["shares_held"] == pytest.approx(0.062577, abs=1e-6)

    # Fully liquidated positions (e.g. Aegon) must not appear in active holdings
    assert len(holdings) == 6, f"Expected exactly 6 active holdings, got {len(holdings)}"

    # 4. Daily Equity History Verification
    history = build_daily_equity_history(df)
    assert not history.empty, "Daily equity history should not be empty"
    assert len(history) > 900, f"Expected > 900 daily rows spanning 2024 to present, got {len(history)}"

    expected_history_cols = [
        "date", "total_equity_eur", "invested_capital_eur",
        "cash_balance_eur", "unrealized_pnl_eur", "unrealized_pnl_pct"
    ]
    assert list(history.columns) == expected_history_cols

    # Ensure zero NaN/null values in history records
    assert history.isnull().sum().sum() == 0, "Daily equity history contains null or NaN values"

    # Ensure chronological order and valid boundaries
    assert history["date"].is_monotonic_increasing, "Historical dates must be monotonically increasing"
    assert history["date"].iloc[0] == "2024-04-02", f"First historical date should be 2024-04-02, got {history['date'].iloc[0]}"

    latest_row = history.iloc[-1]
    assert latest_row["cash_balance_eur"] == 5.96, f"Latest cash balance should be €5.96, got €{latest_row['cash_balance_eur']}"


def test_cli_audit_command(account_csv_path: Path, capsys: pytest.CaptureFixture[str]):
    """Verify backend CLI audit command runs successfully against Account.csv."""
    cmd_audit(str(account_csv_path))
    captured = capsys.readouterr()
    assert "Total rows parsed     : 172" in captured.out
    assert "Net external invested : €    3728.00" in captured.out
    assert "Closing cash balance  : €       5.96" in captured.out
    assert "VWCE.DE" in captured.out
    assert "EXUS.DE" in captured.out
    assert "BTC-EUR" in captured.out
    assert "ASWC.DE" in captured.out
