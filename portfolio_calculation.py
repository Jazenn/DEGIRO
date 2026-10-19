from __future__ import annotations

import re

import pandas as pd

from data_processing import classify_row, parse_quantity
from rebalance_calculator import RebalanceCalculator


HISTORY_COLUMNS = [
    "date",
    "total_equity_eur",
    "invested_capital_eur",
    "cash_balance_eur",
    "unrealized_pnl_eur",
    "unrealized_pnl_pct",
]
HOLDING_COLUMNS = [
    "symbol",
    "name",
    "isin",
    "shares_held",
    "current_price_eur",
    "total_value_eur",
    "total_cost_eur",
    "unrealized_pnl_eur",
    "actual_pct",
    "target_pct",
    "drift_pct",
    "recommended_action_eur",
]
_QUANTITY_FROM_DESCRIPTION = re.compile(
    r"(?:Koop|Verkoop|Buy|Sell)\s+([0-9.,eE+-]+)\s+@", re.IGNORECASE
)
_PRICE_FROM_DESCRIPTION = re.compile(r"@\s*([0-9.,eE+-]+)", re.IGNORECASE)


def _number(value, default=0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if pd.notna(number) else default


def _transaction_quantity(row: pd.Series) -> float:
    quantity = _number(row.get("quantity"), default=float("nan"))
    if pd.notna(quantity) and quantity != 0:
        return quantity
    parsed = parse_quantity(str(row.get("description") or ""))
    if parsed:
        return parsed
    match = _QUANTITY_FROM_DESCRIPTION.search(str(row.get("description") or ""))
    if match:
        return abs(_number(match.group(1)))
    return 0.0


def _symbol(row: pd.Series) -> str:
    isin = str(row.get("isin") or "").strip()
    if isin and isin.lower() != "nan":
        return isin
    return str(row.get("product") or "").strip()


def _transaction_price(row: pd.Series, quantity: float) -> float:
    price = _number(row.get("price"))
    if price > 0:
        return price
    price_match = _PRICE_FROM_DESCRIPTION.search(str(row.get("description") or ""))
    if price_match:
        price_text = price_match.group(1)
        if "," in price_text and "." in price_text:
            decimal_separator = "," if price_text.rfind(",") > price_text.rfind(".") else "."
            thousands_separator = "." if decimal_separator == "," else ","
            price_text = price_text.replace(thousands_separator, "")
            price_text = price_text.replace(decimal_separator, ".")
        elif "," in price_text:
            price_text = price_text.replace(",", ".")
        price = _number(price_text)
        if price > 0:
            return price
    amount = abs(_number(row.get("amount")))
    return amount / abs(quantity) if quantity and amount else 0.0


def _contribution_amount(row: pd.Series) -> float:
    description = str(row.get("description") or "")
    transaction_type = str(row.get("type") or classify_row(description))
    amount = _number(row.get("amount"))
    if transaction_type == "Deposit":
        return abs(amount)
    if transaction_type == "Withdrawal":
        return -abs(amount)
    return 0.0


def _apply_quantity(lots: list[list[float]], quantity: float, price: float) -> None:
    if quantity > 0:
        lots.append([quantity, price])
        return
    if quantity >= 0:
        return

    remaining_to_sell = abs(quantity)
    while remaining_to_sell > 1e-12 and lots:
        lot_quantity, lot_price = lots[0]
        used = min(remaining_to_sell, lot_quantity)
        remaining_to_sell -= used
        lot_quantity -= used
        if lot_quantity <= 1e-12:
            lots.pop(0)
        else:
            lots[0][0] = lot_quantity


class PortfolioCalculationEngine:
    """Compute rolling portfolio history and FIFO holdings from transactions."""

    def compute_daily_history(
        self,
        transactions: pd.DataFrame,
        prices: dict | None = None,
        historical_prices: dict | None = None,
    ) -> pd.DataFrame:
        if transactions is None or transactions.empty or "date" not in transactions:
            return pd.DataFrame(columns=HISTORY_COLUMNS)

        df = transactions.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        if df.empty:
            return pd.DataFrame(columns=HISTORY_COLUMNS)
        if "time" not in df:
            df["time"] = ""
        df = df.sort_values(["date", "time"], kind="stable")

        prices = prices or {}
        require_historical = historical_prices is not None
        historical_prices = historical_prices or {}
        cash_is_reported = "balance" in df and pd.to_numeric(
            df["balance"], errors="coerce"
        ).fillna(0).ne(0).any()
        transaction_days = {
            day: day_rows
            for day, day_rows in df.groupby(df["date"].dt.normalize(), sort=True)
        }
        historical_series = {}
        history_days = set()
        for symbol, values in historical_prices.items():
            series = values if isinstance(values, pd.Series) else pd.Series(values)
            series.index = pd.to_datetime(series.index, errors="coerce")
            if series.index.tz is not None:
                series.index = series.index.tz_localize(None)
            series = pd.to_numeric(series, errors="coerce").dropna()
            series = series[series.index.notna() & (series > 0)]
            series.index = series.index.normalize()
            series = series[~series.index.duplicated(keep="last")].sort_index()
            if not series.empty:
                historical_series[symbol] = series
                history_days.update(series.index)
        timeline = sorted(set(transaction_days).union(history_days))
        timeline_index = pd.DatetimeIndex(timeline)
        carried_prices = {
            symbol: series.reindex(timeline_index, method="ffill")
            for symbol, series in historical_series.items()
        }

        cash_balance = 0.0
        invested_capital = 0.0
        lots: dict[str, list[list[float]]] = {}
        products: dict[str, str] = {}
        rows = []

        for day in timeline:
            day_transactions = transaction_days.get(day, df.iloc[0:0])
            reported_balances = pd.to_numeric(
                day_transactions.get("balance", pd.Series(dtype=float)),
                errors="coerce",
            ).dropna()
            if cash_is_reported and not reported_balances.empty:
                cash_balance = float(reported_balances.iloc[-1])
            else:
                cash_balance += sum(_number(row.get("amount")) for _, row in day_transactions.iterrows())

            for _, row in day_transactions.iterrows():
                invested_capital += _contribution_amount(row)
                quantity = _transaction_quantity(row)
                symbol = _symbol(row)
                if not symbol or not quantity:
                    continue
                _apply_quantity(
                    lots.setdefault(symbol, []),
                    quantity,
                    _transaction_price(row, quantity),
                )
                products[symbol] = str(row.get("product") or symbol)

            market_value = sum(
                sum(lot[0] for lot in asset_lots)
                * self._price_for_day(
                    symbol,
                    products.get(symbol),
                    day,
                    prices,
                    carried_prices,
                    require_historical,
                )
                for symbol, asset_lots in lots.items()
            )
            total_cost = sum(
                quantity * cost
                for asset_lots in lots.values()
                for quantity, cost in asset_lots
            )
            equity = market_value + cash_balance
            pnl = market_value - total_cost
            rows.append(
                {
                    "date": day,
                    "total_equity_eur": equity,
                    "invested_capital_eur": invested_capital,
                    "cash_balance_eur": cash_balance,
                    "unrealized_pnl_eur": pnl,
                    "unrealized_pnl_pct": (
                        pnl / invested_capital * 100.0 if invested_capital else 0.0
                    ),
                }
            )

        return pd.DataFrame(rows, columns=HISTORY_COLUMNS)

    @staticmethod
    def _price_for_day(
        symbol, product, day, prices, historical_prices, require_historical
    ) -> float:
        for key in (symbol, product):
            series = historical_prices.get(key)
            if series is not None:
                price = series.get(day)
                if pd.notna(price) and price > 0:
                    return float(price)
        if require_historical:
            raise ValueError(
                f"Missing historical market price for {symbol} on {day:%Y-%m-%d}."
            )
        return _number(prices.get(symbol, prices.get(product, 0.0)))

    def compute_current_holdings(
        self,
        transactions: pd.DataFrame,
        prices: dict | None = None,
        targets: dict | None = None,
        deposit_amount: float | None = None,
    ) -> pd.DataFrame:
        if transactions is None or transactions.empty:
            return pd.DataFrame(columns=HOLDING_COLUMNS)

        prices = prices or {}
        targets = targets or {}
        ordered = transactions.copy()
        if "date" in ordered:
            ordered["date"] = pd.to_datetime(ordered["date"], errors="coerce")
            ordered = ordered.sort_values(["date", "time"] if "time" in ordered else ["date"])

        lots: dict[str, list[list[float]]] = {}
        products: dict[str, str] = {}
        isins: dict[str, str] = {}
        for _, row in ordered.iterrows():
            symbol = _symbol(row)
            quantity = _transaction_quantity(row)
            if not symbol or not quantity:
                continue

            products[symbol] = str(row.get("product") or symbol)
            isins[symbol] = str(row.get("isin") or "")
            asset_lots = lots.setdefault(symbol, [])
            _apply_quantity(
                asset_lots, quantity, _transaction_price(row, quantity)
            )

        values = []
        for symbol, asset_lots in lots.items():
            shares_held = sum(lot[0] for lot in asset_lots)
            if shares_held <= 1e-12:
                continue
            product = products[symbol]
            price = _number(prices.get(symbol, prices.get(product, 0.0)))
            total_cost = sum(quantity * lot_price for quantity, lot_price in asset_lots)
            total_value = shares_held * price
            target_pct = _number(targets.get(symbol, targets.get(product, 0.0)))
            values.append(
                {
                    "symbol": symbol,
                    "name": product,
                    "isin": isins[symbol] or symbol,
                    "shares_held": shares_held,
                    "current_price_eur": price,
                    "total_value_eur": total_value,
                    "total_cost_eur": total_cost,
                    "unrealized_pnl_eur": total_value - total_cost,
                    "target_pct": target_pct,
                }
            )

        if not values:
            return pd.DataFrame(columns=HOLDING_COLUMNS)
        holdings = pd.DataFrame(values)
        total_value = holdings["total_value_eur"].sum()
        holdings["actual_pct"] = (
            holdings["total_value_eur"] / total_value * 100.0 if total_value else 0.0
        )
        holdings["drift_pct"] = holdings["actual_pct"] - holdings["target_pct"]

        holding_targets = dict(zip(holdings["symbol"], holdings["target_pct"]))
        current_values = dict(zip(holdings["symbol"], holdings["total_value_eur"]))
        current_prices = dict(zip(holdings["symbol"], holdings["current_price_eur"]))

        if deposit_amount is not None and float(deposit_amount) > 0:
            effective_deposit = float(deposit_amount)
        else:
            total_target_pct = sum(v for v in holding_targets.values() if v > 0)
            if total_target_pct > 0 and total_value > 0:
                shortfall = sum(
                    max(0.0, total_value * (weight / total_target_pct) - current_values.get(sym, 0.0))
                    for sym, weight in holding_targets.items()
                    if weight > 0
                )
                effective_deposit = shortfall
            else:
                effective_deposit = 0.0

        if effective_deposit > 0:
            calculator = RebalanceCalculator()
            plan = calculator.calculate_deposit_plan(
                deposit_amount=effective_deposit,
                portfolio_value=total_value,
                rebalancing_targets=holding_targets,
                current_values=current_values,
                prices=current_prices,
            )
            buys = plan.get("recommended_buys", {})
            holdings["recommended_action_eur"] = holdings["symbol"].map(
                lambda s: round(float(buys.get(s, 0.0)), 2)
            )
        else:
            holdings["recommended_action_eur"] = 0.0

        return holdings[HOLDING_COLUMNS].sort_values(
            "total_value_eur", ascending=False
        ).reset_index(drop=True)

