"""Portfolio valuation, FIFO cost basis, and holding calculations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd

from backend.config import BackendConfig, DEFAULT_DISPLAY_NAMES
from backend.engine.cash import sort_transactions_chronologically, calculate_cash_balance, calculate_net_invested_capital


def compute_fifo_holdings(
    df: pd.DataFrame,
    config: Optional[BackendConfig] = None,
    live_prices: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """Compute current asset holdings using FIFO lot tracking."""
    cfg = config or BackendConfig()
    prices = live_prices or {}
    asset_settings = cfg.get_assets()

    if df.empty:
        return pd.DataFrame()

    df_sorted = sort_transactions_chronologically(df)
    trade_mask = df_sorted["action"].isin(["BUY", "SELL"])
    trades = df_sorted[trade_mask].copy()

    holdings_lots: Dict[str, List[Dict[str, float]]] = {}
    total_qty_map: Dict[str, float] = {}
    ticker_isin_map: Dict[str, str] = {}
    ticker_name_map: Dict[str, str] = {}

    for _, row in trades.iterrows():
        raw_prod = str(row.get("raw_product") or row.get("product") or "")
        isin = str(row.get("isin") or "").strip()
        ticker = cfg.get_ticker_for_product(raw_prod, isin)
        if not ticker:
            continue

        if ticker not in holdings_lots:
            holdings_lots[ticker] = []
            total_qty_map[ticker] = 0.0
            ticker_isin_map[ticker] = isin
            ticker_name_map[ticker] = DEFAULT_DISPLAY_NAMES.get(ticker, raw_prod)

        action = row["action"]
        qty = abs(float(row.get("quantity") or 0.0))
        price = float(row.get("price") or 0.0)

        if action == "BUY":
            holdings_lots[ticker].append({"qty": qty, "price": price})
            total_qty_map[ticker] += qty
        elif action == "SELL":
            sell_qty = qty
            total_qty_map[ticker] = max(0.0, total_qty_map[ticker] - sell_qty)
            while sell_qty > 0 and holdings_lots[ticker]:
                lot = holdings_lots[ticker][0]
                if lot["qty"] <= sell_qty:
                    sell_qty -= lot["qty"]
                    holdings_lots[ticker].pop(0)
                else:
                    lot["qty"] -= sell_qty
                    sell_qty = 0.0

    # Build active holdings records
    records = []
    total_portfolio_value = 0.0

    for ticker, qty in total_qty_map.items():
        if qty <= 1e-6:
            continue  # Exclude liquidated positions

        lots = holdings_lots.get(ticker, [])
        cost = sum(l["qty"] * l["price"] for l in lots)
        current_price = float(prices.get(ticker) or (cost / qty if qty > 0 else 0.0))
        val = round(qty * current_price, 2)
        total_portfolio_value += val

        settings = asset_settings.get(ticker, {})
        target_pct = float(settings.get("target_pct") or 0.0)
        display_name = str(settings.get("display_name") or ticker_name_map.get(ticker) or ticker)

        records.append({
            "symbol": ticker,
            "name": display_name,
            "isin": ticker_isin_map.get(ticker) or "",
            "shares_held": qty,
            "current_price_eur": round(current_price, 4),
            "total_value_eur": val,
            "total_cost_eur": round(cost, 2),
            "unrealized_pnl_eur": round(val - cost, 2),
            "target_pct": target_pct,
        })

    # Compute actual %, drift %, and recommended actions
    for r in records:
        actual_pct = round((r["total_value_eur"] / total_portfolio_value * 100.0), 2) if total_portfolio_value > 0 else 0.0
        drift_pct = round(actual_pct - r["target_pct"], 2)
        # Target value for this asset
        target_val = (total_portfolio_value * (r["target_pct"] / 100.0)) if total_portfolio_value > 0 else 0.0
        shortfall = max(0.0, target_val - r["total_value_eur"])

        r["actual_pct"] = actual_pct
        r["drift_pct"] = drift_pct
        r["recommended_action_eur"] = round(shortfall, 2)

    df_result = pd.DataFrame(records)
    if not df_result.empty:
        df_result = df_result.sort_values(by="total_value_eur", ascending=False).reset_index(drop=True)
    return df_result


def build_daily_equity_history(
    df: pd.DataFrame,
    config: Optional[BackendConfig] = None,
    historical_prices: Optional[Dict[str, Dict[str, float]]] = None,
) -> pd.DataFrame:
    """Build daily historical snapshot records for the portfolio equity curve."""
    cfg = config or BackendConfig()
    hist_prices = historical_prices or {}

    if df.empty:
        return pd.DataFrame()

    df_sorted = sort_transactions_chronologically(df)
    df_sorted["parsed_date"] = pd.to_datetime(df_sorted["date"], dayfirst=True, errors="coerce")
    df_sorted = df_sorted.dropna(subset=["parsed_date"]).copy()

    if df_sorted.empty:
        return pd.DataFrame()

    min_date = df_sorted["parsed_date"].min()
    max_date = pd.Timestamp.now().normalize()
    date_range = pd.date_range(min_date, max_date, freq="D")

    # Group external cash flow mutations by date
    non_sweep = df_sorted[~df_sorted["is_cash_sweep"]].copy()
    daily_cash_mutations = non_sweep.groupby("parsed_date")["amount"].sum().reindex(date_range, fill_value=0.0)
    cumulative_cash = daily_cash_mutations.cumsum()

    # Track net external invested capital
    ext_deposits = non_sweep[non_sweep["type"].isin(["DEPOSIT", "WITHDRAWAL"])]
    daily_ext_mutations = ext_deposits.groupby("parsed_date")["amount"].sum().reindex(date_range, fill_value=0.0)
    cumulative_invested = daily_ext_mutations.cumsum()

    # Track trade quantity accumulation per ticker
    trades = df_sorted[df_sorted["action"].isin(["BUY", "SELL"])].copy()
    trades["ticker"] = trades.apply(
        lambda r: cfg.get_ticker_for_product(r.get("raw_product") or r.get("product"), r.get("isin")),
        axis=1,
    )
    trades = trades.dropna(subset=["ticker"])

    records = []
    # Maintain cumulative share positions
    ticker_positions: Dict[str, float] = {}

    for d in date_range:
        d_str = d.strftime("%Y-%m-%d")
        # Apply trades up to today
        day_trades = trades[trades["parsed_date"] == d]
        for _, tr in day_trades.iterrows():
            t = tr["ticker"]
            q = float(tr.get("quantity") or 0.0)
            ticker_positions[t] = ticker_positions.get(t, 0.0) + q

        # Compute stock portfolio value for this date
        portfolio_stock_value = 0.0
        for t, q in ticker_positions.items():
            if q > 1e-6:
                price_on_date = hist_prices.get(t, {}).get(d_str, 0.0)
                portfolio_stock_value += (q * price_on_date)

        cash = float(cumulative_cash.loc[d])
        invested = float(cumulative_invested.loc[d])
        total_equity = portfolio_stock_value + cash
        unrealized_pnl = total_equity - invested
        unrealized_pnl_pct = (unrealized_pnl / invested * 100.0) if invested > 0 else 0.0

        records.append({
            "date": d_str,
            "total_equity_eur": round(total_equity, 2),
            "invested_capital_eur": round(invested, 2),
            "cash_balance_eur": round(cash, 2),
            "unrealized_pnl_eur": round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
        })

    return pd.DataFrame(records)
