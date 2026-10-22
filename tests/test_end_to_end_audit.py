"""End-to-end audit and ingestion verification tests for raw Account.csv and checked-in fixtures."""

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
    """Find real Account.csv in current directory or repo root."""
    candidate_paths = [
        Path("Account.csv"),
        Path(__file__).resolve().parent.parent / "Account.csv",
    ]
    for p in candidate_paths:
        if p.exists() and p.is_file():
            return p
    return None


def _resolve_synthetic_fixture_csv() -> Path:
    """Resolve checked-in synthetic test fixture for CI and testing."""
    return Path(__file__).resolve().parent / "fixtures" / "synthetic_account.csv"


@pytest.fixture
def account_csv_path() -> Path:
    p = _resolve_account_csv()
    if not p:
        pytest.skip("Account.csv not found locally.")
    return p


def test_end_to_end_synthetic_fixture_pipeline():
    """Verify end-to-end ingestion, cash continuity, and holdings on synthetic fixture in CI."""
    fixture_path = _resolve_synthetic_fixture_csv()
    assert fixture_path.exists(), f"Synthetic fixture missing at {fixture_path}"
    with open(fixture_path, "rb") as f:
        content = f.read()

    df = load_degiro_csv(content)
    assert len(df) == 7, f"Expected 7 rows parsed, got {len(df)}"

    # Invariants
    net_invested = calculate_net_invested_capital(df)
    assert net_invested == 2000.00, f"Expected net invested €2000.00, got €{net_invested}"

    cash_balance = calculate_cash_balance(df)
    assert cash_balance == 939.00, f"Expected cash balance €939.00, got €{cash_balance}"

    holdings = compute_fifo_holdings(df)
    holdings_by_symbol = {row["symbol"]: row for _, row in holdings.iterrows()}
    assert "VWCE.DE" in holdings_by_symbol
    assert holdings_by_symbol["VWCE.DE"]["shares_held"] == 8.0

    assert "BTC-EUR" in holdings_by_symbol
    assert holdings_by_symbol["BTC-EUR"]["shares_held"] == pytest.approx(0.005, abs=1e-6)

    history = build_daily_equity_history(df)
    assert not history.empty
    assert history["cash_balance_eur"].iloc[-1] == 939.00


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


def test_cli_audit_command(capsys: pytest.CaptureFixture[str]):
    """Verify backend CLI audit command runs successfully against Account.csv or synthetic fixture."""
    real_csv = _resolve_account_csv()
    target_csv = real_csv if real_csv else _resolve_synthetic_fixture_csv()
    cmd_audit(str(target_csv))
    captured = capsys.readouterr()
    if real_csv:
        assert "Total rows parsed     : 172" in captured.out
        assert "Net external invested : €    3728.00" in captured.out
        assert "Closing cash balance  : €       5.96" in captured.out
        assert "EXUS.DE" in captured.out
        assert "ASWC.DE" in captured.out
    else:
        assert "Total rows parsed     : 7" in captured.out
        assert "Net external invested : €    2000.00" in captured.out
        assert "Closing cash balance  : €     939.00" in captured.out
    assert "VWCE.DE" in captured.out
    assert "BTC-EUR" in captured.out

def test_audit_calculation_contract_preserves_synthetic_holdings_and_versions():
    from backend.engine.calculation import calculate_portfolio, ObservedPrice

    transactions = load_degiro_csv(_resolve_synthetic_fixture_csv().read_bytes())
    before = transactions.copy(deep=True)
    report = calculate_portfolio(
        transactions,
        observed_prices={
            "VWCE.DE": ObservedPrice(125, "2026-10-22T12:00:00Z", "synthetic"),
            "BTC-EUR": ObservedPrice(62000, "2026-10-22T12:00:00Z", "synthetic"),
        },
        settings={}, ledger_version="ledger-7", settings_version="settings-2",
        cutoff="2026-10-22T12:00:00Z",
    )
    assert report.ledger_version == "ledger-7"
    assert report.settings_version == "settings-2"
    assert report.calculation_version == "canonical-v1"
    assert report.cutoff == "2026-10-22T12:00:00+00:00"
    assert report.cash_balance_eur == 939
    assert report.net_external_contributions_eur == 2000
    holdings = report.holdings.set_index("symbol")
    assert holdings.loc["VWCE.DE", "shares_held"] == 8
    assert holdings.loc["VWCE.DE", "total_value_eur"] == 1000
    assert holdings.loc["BTC-EUR", "total_value_eur"] == 310
    assert report.observed_prices["VWCE.DE"].provider == "synthetic"
    assert "source_timezone_unverified:cutoff_eligibility_unavailable:legacy_wall_time_filter" in report.diagnostics
    pd.testing.assert_frame_equal(transactions, before)

def test_audit_reports_missing_prices_and_honors_cutoff(capsys):
    cmd_audit(str(_resolve_synthetic_fixture_csv()), cutoff="2026-10-09T23:59:59Z")
    output = capsys.readouterr().out
    assert "canonical-v1" in output
    assert "10.000000 shares" in output
    assert "999.00" in output
    assert "missing_observed_price:VWCE.DE" in output
    assert "BTC-EUR" not in output

@pytest.mark.parametrize("price,observed_at,currency", [
    (float("nan"), "2026-10-22T12:00:00Z", "EUR"),
    (0, "2026-10-22T12:00:00Z", "EUR"),
    (125, "2026-10-23T12:00:00Z", "EUR"),
    (125, "2026-10-22T12:00:00Z", "USD"),
])
def test_audit_calculation_rejects_unusable_observed_prices(price, observed_at, currency):
    from backend.engine.calculation import calculate_portfolio, ObservedPrice
    with pytest.raises(ValueError, match="Observed price"):
        calculate_portfolio(
            load_degiro_csv(_resolve_synthetic_fixture_csv().read_bytes()),
            observed_prices={"VWCE.DE": ObservedPrice(price, observed_at, "synthetic", currency)},
            settings={}, ledger_version="ledger-7", settings_version="settings-2",
            cutoff="2026-10-22T12:00:00Z",
        )

def test_audit_calculation_never_reads_local_settings(monkeypatch):
    from backend.engine.calculation import calculate_portfolio
    transactions = load_degiro_csv(_resolve_synthetic_fixture_csv().read_bytes())

    def forbidden_read(*args, **kwargs):
        raise AssertionError("Calculation attempted filesystem access")

    monkeypatch.setattr(Path, "exists", forbidden_read)
    report = calculate_portfolio(
        transactions, observed_prices={}, settings={}, ledger_version="ledger-7",
        settings_version="settings-2", cutoff="2026-10-22T12:00:00Z",
    )
    assert report.cash_balance_eur == 939
    assert "missing_observed_price:BTC-EUR:legacy_cost_valuation" in report.diagnostics
