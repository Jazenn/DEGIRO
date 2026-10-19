from dataclasses import dataclass

import pandas as pd

from portfolio_calculation import PortfolioCalculationEngine


@dataclass(frozen=True)
class SnapshotRefreshResult:
    history_rows: int
    holding_rows: int
    quotes_requested: int


def refresh_portfolio_snapshots(
    storage,
    price_provider,
    config_manager,
    as_of_date: str | None = None,
) -> SnapshotRefreshResult:
    """Fetch mapped quotes, calculate snapshots, and persist the read model."""
    transactions = storage.load_transactions()
    if transactions.empty:
        return SnapshotRefreshResult(0, 0, 0)

    asset_tickers = {}
    tickers = set()
    for _, row in transactions.iterrows():
        product = str(row.get("product") or "").strip()
        isin = str(row.get("isin") or "").strip()
        if not product and not isin:
            continue
        ticker = price_provider.resolve_ticker(product, isin or None)
        if ticker:
            asset_tickers[(product, isin)] = ticker
            tickers.add(ticker)

    ticker_prices = price_provider.get_live_prices_batch(sorted(tickers))
    snapshot_date = as_of_date or pd.Timestamp.now(
        tz="Europe/Amsterdam"
    ).strftime("%Y-%m-%d")
    dates = (
        pd.to_datetime(transactions["date"], errors="coerce").dropna()
        if "date" in transactions
        else pd.Series(dtype="datetime64[ns]")
    )
    historical_ticker_prices = (
        price_provider.get_historical_prices_batch(
            sorted(tickers),
            (dates.min() - pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
        )
        if len(dates) and tickers
        else {}
    )
    prices = {}
    historical_prices = {}
    for (product, isin), ticker in asset_tickers.items():
        price = ticker_prices.get(ticker, 0.0)
        history = dict(historical_ticker_prices.get(ticker, {}))
        if price and price > 0:
            history[snapshot_date] = price
        if isin:
            prices[isin] = price
            historical_prices[isin] = history
        if product:
            prices[product] = price
            historical_prices[product] = history
        prices[ticker] = price

    targets = {
        key: float(settings.get("target_pct") or 0.0)
        for key, settings in config_manager.get_assets().items()
    }
    engine = PortfolioCalculationEngine()
    history = engine.compute_daily_history(
        transactions,
        prices=prices,
        historical_prices=historical_prices,
    )
    holdings = engine.compute_current_holdings(
        transactions,
        prices=prices,
        targets=targets,
    )
    storage.save_portfolio_snapshots(history, holdings)

    return SnapshotRefreshResult(
        history_rows=len(history),
        holding_rows=len(holdings),
        quotes_requested=len(tickers),
    )
