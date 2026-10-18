from __future__ import annotations

import pandas as pd


class PortfolioCalculationEngine:
    """Compute portfolio snapshots and current holdings from DEGIRO transactions."""

    def compute_daily_history(self, transactions: pd.DataFrame, prices: dict | None = None) -> pd.DataFrame:
        if transactions is None or transactions.empty:
            return pd.DataFrame(columns=["date", "total_equity_eur", "invested_capital_eur", "cash_balance_eur", "unrealized_pnl_eur", "unrealized_pnl_pct"])

        df = transactions.copy()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
        if df.empty:
            return pd.DataFrame(columns=["date", "total_equity_eur", "invested_capital_eur", "cash_balance_eur", "unrealized_pnl_eur", "unrealized_pnl_pct"])

        prices = prices or {}
        history_rows = []

        for day, day_rows in df.groupby(df["date"].dt.floor("D")):
            symbol_prices = {}
            for _, row in day_rows.iterrows():
                symbol = str(row.get("isin") or row.get("product") or "").strip()
                if symbol and symbol not in symbol_prices:
                    symbol_prices[symbol] = float(prices.get(symbol, prices.get(row.get("product"), 0.0)))

            market_value = 0.0
            for _, row in day_rows.iterrows():
                qty = float(row.get("quantity", 0.0) or 0.0)
                symbol = str(row.get("isin") or row.get("product") or "").strip()
                price = float(prices.get(symbol, prices.get(row.get("product"), 0.0)) or 0.0)
                market_value += qty * price

            invested_capital = float(day_rows.get("amount", pd.Series([0.0] * len(day_rows))).sum())
            invested_capital = max(invested_capital * -1.0, 0.0)
            cash_balance = float(day_rows.get("balance", pd.Series([0.0] * len(day_rows))).iloc[-1] if "balance" in day_rows.columns else 0.0)
            equity = market_value + cash_balance
            pnl = equity - invested_capital
            pct = (pnl / invested_capital * 100.0) if invested_capital else 0.0
            history_rows.append({
                "date": day,
                "total_equity_eur": equity,
                "invested_capital_eur": invested_capital,
                "cash_balance_eur": cash_balance,
                "unrealized_pnl_eur": pnl,
                "unrealized_pnl_pct": pct,
            })

        return pd.DataFrame(history_rows).sort_values("date").reset_index(drop=True)

    def compute_current_holdings(self, transactions: pd.DataFrame, prices: dict | None = None, targets: dict | None = None) -> pd.DataFrame:
        if transactions is None or transactions.empty:
            return pd.DataFrame(columns=["symbol", "name", "isin", "shares_held", "current_price_eur", "total_value_eur", "actual_pct", "target_pct", "drift_pct", "recommended_action_eur"])

        df = transactions.copy()
        if "quantity" not in df.columns:
            df["quantity"] = 0.0
        if "price" not in df.columns:
            df["price"] = 0.0

        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0)
        df["amount"] = pd.to_numeric(df.get("amount", 0.0), errors="coerce").fillna(0.0)

        grouped = df.groupby([df.get("isin", pd.Series([None] * len(df))).fillna(df.get("product", pd.Series([None] * len(df)))), "product"], dropna=False).agg(
            shares_held=("quantity", "sum"),
            total_cost=("amount", "sum"),
        )
        grouped = grouped.reset_index()
        grouped = grouped.rename(columns={"level_0": "symbol"})
        grouped["symbol"] = grouped["isin"].fillna(grouped["product"])

        prices = prices or {}
        targets = targets or {}
        total_value = 0.0
        values = []
        for _, row in grouped.iterrows():
            symbol = str(row.get("symbol") or row.get("product") or "").strip()
            price = float(prices.get(symbol, prices.get(row.get("product"), 0.0)) or 0.0)
            total_value_row = float(row.get("shares_held", 0.0)) * price
            total_value += total_value_row
            values.append({
                "symbol": symbol,
                "name": row.get("product") or symbol,
                "isin": row.get("isin") or symbol,
                "shares_held": float(row.get("shares_held", 0.0)),
                "current_price_eur": price,
                "total_value_eur": total_value_row,
                "target_pct": float(targets.get(symbol, targets.get(row.get("product"), 0.0))) if symbol and (symbol in targets or row.get("product") in targets) else 0.0,
            })

        if not values:
            return pd.DataFrame(columns=["symbol", "name", "isin", "shares_held", "current_price_eur", "total_value_eur", "actual_pct", "target_pct", "drift_pct", "recommended_action_eur"])

        holdings = pd.DataFrame(values)
        holdings["actual_pct"] = (holdings["total_value_eur"] / total_value * 100.0) if total_value else 0.0
        holdings["drift_pct"] = holdings["actual_pct"] - holdings["target_pct"]
        holdings["recommended_action_eur"] = 0.0
        return holdings[["symbol", "name", "isin", "shares_held", "current_price_eur", "total_value_eur", "actual_pct", "target_pct", "drift_pct", "recommended_action_eur"]].sort_values("total_value_eur", ascending=False).reset_index(drop=True)
