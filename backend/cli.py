"""Command Line Interface (CLI) for DEGIRO backend tasks.

Usage:
    python -m backend.cli audit Account.csv
    python -m backend.cli ingest Account.csv
    python -m backend.cli snapshot
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.config import BackendConfig, get_database_url
from backend.engine.cash import calculate_cash_balance, calculate_net_invested_capital, sort_transactions_chronologically
from backend.engine.portfolio import compute_fifo_holdings, build_daily_equity_history
from backend.ingestion import load_degiro_csv
from backend.providers import PriceService


def cmd_audit(csv_path: str) -> None:
    """Run local audit of an Account.csv or Transactions.csv file."""
    path = Path(csv_path)
    if not path.exists():
        print(f"Error: File not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "rb") as f:
        content = f.read()

    df = load_degiro_csv(content)
    print("=" * 60)
    print(f"DEGIRO CSV AUDIT: {path.name}")
    print("=" * 60)
    print(f"Total rows parsed     : {len(df)}")
    if "type" in df.columns:
        print("\nBreakdown by type:")
        for t, count in df["type"].value_counts().items():
            print(f"  {t:15}: {count:4d}")

    # Cash analysis
    cash = calculate_cash_balance(df)
    net_invested = calculate_net_invested_capital(df)
    print("\nCash Ledger Analysis:")
    print(f"  Net external invested : € {net_invested:10.2f}")
    print(f"  Closing cash balance  : € {cash:10.2f}")

    # Holdings analysis
    config = BackendConfig()
    holdings = compute_fifo_holdings(df, config=config)
    print("\nFIFO Asset Holdings:")
    if holdings.empty:
        print("  No active holdings found.")
    else:
        for _, h in holdings.iterrows():
            sym = h["symbol"]
            qty = h["shares_held"]
            cost = h["total_cost_eur"]
            print(f"  {sym:10}: {qty:12.6f} shares | Total Cost: € {cost:8.2f}")
    print("=" * 60)


def cmd_ingest(csv_path: str) -> None:
    """Ingest CSV into Neon PostgreSQL and refresh snapshots."""
    from backend.db import TransactionRepository, SnapshotRepository

    path = Path(csv_path)
    if not path.exists():
        print(f"Error: File not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    db_url = get_database_url()
    if not db_url:
        print("Error: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    with open(path, "rb") as f:
        content = f.read()

    df = load_degiro_csv(content)
    tx_repo = TransactionRepository(db_url)
    inserted, skipped = tx_repo.save_transactions(df)
    print(f"Ingested {path.name}: {inserted} new records stored, {skipped} duplicates skipped.")

    # Refresh snapshots
    cmd_snapshot()


def cmd_snapshot() -> None:
    """Fetch market quotes and recalculate pre-aggregated snapshot tables."""
    from backend.db import TransactionRepository, SnapshotRepository

    db_url = get_database_url()
    if not db_url:
        print("Error: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    tx_repo = TransactionRepository(db_url)
    df_tx = tx_repo.load_transactions()
    if df_tx.empty:
        print("No transactions found in database.")
        return

    # Ingest format conversion if loaded from raw DB table
    df_norm = load_degiro_csv(df_tx.to_csv(index=False).encode("utf-8")) if "is_cash_sweep" not in df_tx.columns else df_tx

    config = BackendConfig()
    price_service = PriceService(config)

    # Determine unique active tickers
    trades = df_norm[df_norm["action"].isin(["BUY", "SELL"])].copy()
    tickers = set()
    for _, r in trades.iterrows():
        t = config.get_ticker_for_product(r.get("raw_product") or r.get("product"), r.get("isin"))
        if t:
            tickers.add(t)

    live_prices = price_service.get_live_prices_batch(list(tickers))
    holdings = compute_fifo_holdings(df_norm, config=config, live_prices=live_prices)

    # Historical closes for equity curve
    start_date = "2024-01-01"
    hist_prices = price_service.get_historical_prices_batch(list(tickers), start_date=start_date)
    history = build_daily_equity_history(df_norm, config=config, historical_prices=hist_prices)

    snap_repo = SnapshotRepository(db_url)
    snap_repo.save_portfolio_snapshots(history, holdings)
    print(f"Updated snapshots: {len(holdings)} holdings, {len(history)} daily history points.")


def main() -> None:
    parser = argparse.ArgumentParser(description="DEGIRO Backend CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit", help="Audit local DEGIRO CSV")
    audit_parser.add_argument("csv_file", help="Path to Account.csv or Transactions.csv")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest CSV into Neon and refresh snapshots")
    ingest_parser.add_argument("csv_file", help="Path to CSV file to ingest")

    subparsers.add_parser("snapshot", help="Recalculate snapshots and fetch quotes")

    args = parser.parse_args()
    if args.command == "audit":
        cmd_audit(args.csv_file)
    elif args.command == "ingest":
        cmd_ingest(args.csv_file)
    elif args.command == "snapshot":
        cmd_snapshot()


if __name__ == "__main__":
    main()
