"""Asset allocation rebalancing and shortfall deposit calculations."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def is_crypto_symbol(symbol: str) -> bool:
    sym = str(symbol).upper()
    return any(k in sym for k in ("BTC", "ETH", "BITCOIN", "ETHEREUM", "CRYPTO"))


class RebalanceCalculator:
    """Create proportional rebalancing purchases for underweight assets."""

    def calculate_deposit_plan(
        self,
        deposit_amount: float,
        portfolio_value: float,
        rebalancing_targets: Dict[str, float],
        current_values: Dict[str, float],
        prices: Optional[Dict[str, float]] = None,
        allow_selling: bool = False,
        round_to_whole_shares: bool = False,
        is_crypto: Optional[Dict[str, bool]] = None,
        current_shares: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        deposit_amount = float(deposit_amount or 0.0)
        prices = prices or {}
        current_shares = current_shares or {}
        is_crypto = is_crypto or {}

        all_symbols = list(set(list(current_values.keys()) + list(rebalancing_targets.keys())))
        recommended = {asset: 0.0 for asset in all_symbols}
        estimated_shares = {asset: 0.0 for asset in all_symbols}
        recommended_sells = {asset: 0.0 for asset in all_symbols}
        estimated_shares_to_sell = {asset: 0.0 for asset in all_symbols}

        if deposit_amount <= 0 and not allow_selling:
            return {
                "recommended_buys": recommended,
                "estimated_shares": estimated_shares,
                "total_buy_eur": 0.0,
                "portfolio_value_after": float(portfolio_value or 0.0),
                "underweight_assets": [],
                "recommended_sells": recommended_sells,
                "estimated_shares_to_sell": estimated_shares_to_sell,
                "total_sell_eur": 0.0,
                "net_cash_flow_eur": 0.0,
                "overweight_assets": [],
                "unallocated_cash_eur": 0.0,
            }

        normalized = self._normalize_weights(rebalancing_targets)
        total_target = sum(normalized.values())
        if total_target <= 0:
            return {
                "recommended_buys": recommended,
                "estimated_shares": estimated_shares,
                "total_buy_eur": 0.0,
                "portfolio_value_after": float(portfolio_value or 0.0),
                "underweight_assets": [],
                "recommended_sells": recommended_sells,
                "estimated_shares_to_sell": estimated_shares_to_sell,
                "total_sell_eur": 0.0,
                "net_cash_flow_eur": 0.0,
                "overweight_assets": [],
                "unallocated_cash_eur": 0.0,
            }

        projected_total = float(portfolio_value or 0.0) + deposit_amount
        target_values = {
            symbol: projected_total * (weight / total_target)
            for symbol, weight in normalized.items()
        }

        overweight_assets: List[str] = []
        total_sell_eur = 0.0

        if allow_selling:
            for symbol, target_val in target_values.items():
                curr_val = float(current_values.get(symbol, 0.0))
                if curr_val > target_val + 0.01:
                    excess = curr_val - target_val
                    price = float(prices.get(symbol, 0.0) or 0.0)
                    is_sym_crypto = is_crypto.get(symbol, is_crypto_symbol(symbol))
                    shares_held = float(current_shares.get(symbol, (curr_val / price) if price > 0 else 0.0))

                    if is_sym_crypto:
                        sell_amt = min(excess, curr_val)
                        recommended_sells[symbol] = sell_amt
                        estimated_shares_to_sell[symbol] = (sell_amt / price) if price > 0 else 0.0
                        total_sell_eur += sell_amt
                        overweight_assets.append(symbol)
                    elif round_to_whole_shares:
                        if price > 0:
                            ideal_shares = excess / price
                            shares_to_sell = round(ideal_shares)
                            shares_to_sell = min(shares_to_sell, math.floor(shares_held))
                            shares_to_sell = max(0, shares_to_sell)
                            if shares_to_sell > 0:
                                sell_amt = shares_to_sell * price
                                recommended_sells[symbol] = sell_amt
                                estimated_shares_to_sell[symbol] = float(shares_to_sell)
                                total_sell_eur += sell_amt
                                overweight_assets.append(symbol)
                    else:
                        sell_amt = min(excess, curr_val)
                        recommended_sells[symbol] = sell_amt
                        estimated_shares_to_sell[symbol] = (sell_amt / price) if price > 0 else 0.0
                        total_sell_eur += sell_amt
                        overweight_assets.append(symbol)

        available_cash = deposit_amount + total_sell_eur

        underweight = []
        gaps = {}
        for symbol, target_val in target_values.items():
            curr_val_after_sell = float(current_values.get(symbol, 0.0)) - recommended_sells.get(symbol, 0.0)
            if curr_val_after_sell < target_val - 0.01:
                underweight.append(symbol)
                gaps[symbol] = target_val - curr_val_after_sell

        total_gap = sum(gaps.values())

        if available_cash <= 0 or not underweight or total_gap <= 0:
            return {
                "recommended_buys": recommended,
                "estimated_shares": estimated_shares,
                "total_buy_eur": 0.0,
                "portfolio_value_after": projected_total,
                "underweight_assets": [],
                "recommended_sells": recommended_sells,
                "estimated_shares_to_sell": estimated_shares_to_sell,
                "total_sell_eur": total_sell_eur,
                "net_cash_flow_eur": -total_sell_eur,
                "overweight_assets": overweight_assets,
                "unallocated_cash_eur": max(0.0, available_cash),
            }

        if not round_to_whole_shares:
            for asset in underweight:
                recommended[asset] = available_cash * (gaps[asset] / total_gap)
                price = float(prices.get(asset, 0.0) or 0.0)
                estimated_shares[asset] = (recommended[asset] / price) if price > 0 else 0.0

            total_buy_eur = sum(recommended.values())
            return {
                "recommended_buys": recommended,
                "estimated_shares": estimated_shares,
                "total_buy_eur": total_buy_eur,
                "portfolio_value_after": projected_total,
                "underweight_assets": underweight,
                "recommended_sells": recommended_sells,
                "estimated_shares_to_sell": estimated_shares_to_sell,
                "total_sell_eur": total_sell_eur,
                "net_cash_flow_eur": total_buy_eur - total_sell_eur,
                "overweight_assets": overweight_assets,
                "unallocated_cash_eur": 0.0,
            }

        # Whole shares for stocks, exact for crypto
        stock_symbols = [s for s in underweight if not is_crypto.get(s, is_crypto_symbol(s))]
        crypto_symbols = [s for s in underweight if is_crypto.get(s, is_crypto_symbol(s))]

        remaining_cash = available_cash

        for s in stock_symbols:
            price = float(prices.get(s, 0.0) or 0.0)
            if price <= 0:
                continue
            ideal_buy = available_cash * (gaps[s] / total_gap)
            whole_shares = math.floor(ideal_buy / price)
            recommended[s] = whole_shares * price
            estimated_shares[s] = float(whole_shares)
            remaining_cash -= recommended[s]

        total_stock_shares = sum(estimated_shares[s] for s in stock_symbols)
        if stock_symbols and total_stock_shares == 0:
            sorted_stocks = sorted(stock_symbols, key=lambda s: gaps.get(s, 0.0), reverse=True)
            top_stock = sorted_stocks[0]
            price = float(prices.get(top_stock, 0.0) or 0.0)
            if price > 0:
                ideal_shares = (available_cash * (gaps[top_stock] / total_gap)) / price
                if ideal_shares >= 0.5:
                    estimated_shares[top_stock] = 1.0
                    recommended[top_stock] = price
                    remaining_cash -= price

        progress = True
        while progress and remaining_cash > 0:
            progress = False
            best_stock = None
            max_rem_gap = 0.0
            for s in stock_symbols:
                p = float(prices.get(s, 0.0) or 0.0)
                if 0 < p <= remaining_cash:
                    curr_val = float(current_values.get(s, 0.0)) + recommended.get(s, 0.0)
                    rem_gap = float(target_values.get(s, 0.0)) - curr_val
                    if rem_gap > max_rem_gap:
                        max_rem_gap = rem_gap
                        best_stock = s
            if best_stock and max_rem_gap > 0:
                p = float(prices.get(best_stock, 0.0) or 0.0)
                estimated_shares[best_stock] += 1.0
                recommended[best_stock] += p
                remaining_cash -= p
                progress = True

        if crypto_symbols and remaining_cash > 0:
            total_crypto_gap = sum(gaps.get(s, 0.0) for s in crypto_symbols)
            for s in crypto_symbols:
                price = float(prices.get(s, 0.0) or 0.0)
                share_of_crypto = (
                    remaining_cash * (gaps.get(s, 0.0) / total_crypto_gap)
                    if total_crypto_gap > 0
                    else remaining_cash / len(crypto_symbols)
                )
                recommended[s] = recommended.get(s, 0.0) + share_of_crypto
                estimated_shares[s] = (recommended[s] / price) if price > 0 else 0.0
            remaining_cash = 0.0
        elif crypto_symbols and total_stock_shares == 0 and available_cash > 0:
            total_crypto_gap = sum(gaps.get(s, 0.0) for s in crypto_symbols)
            for s in crypto_symbols:
                price = float(prices.get(s, 0.0) or 0.0)
                share_of_crypto = (
                    available_cash * (gaps.get(s, 0.0) / total_crypto_gap)
                    if total_crypto_gap > 0
                    else available_cash / len(crypto_symbols)
                )
                recommended[s] = share_of_crypto
                estimated_shares[s] = (recommended[s] / price) if price > 0 else 0.0
            remaining_cash = 0.0

        total_buy_eur = sum(recommended.values())
        return {
            "recommended_buys": recommended,
            "estimated_shares": estimated_shares,
            "total_buy_eur": total_buy_eur,
            "portfolio_value_after": projected_total,
            "underweight_assets": underweight,
            "recommended_sells": recommended_sells,
            "estimated_shares_to_sell": estimated_shares_to_sell,
            "total_sell_eur": total_sell_eur,
            "net_cash_flow_eur": total_buy_eur - total_sell_eur,
            "overweight_assets": overweight_assets,
            "unallocated_cash_eur": max(0.0, remaining_cash),
        }

    @staticmethod
    def _normalize_weights(weights: Dict[str, Any]) -> Dict[str, float]:
        normalized = {}
        for symbol, weight in (weights or {}).items():
            try:
                value = float(weight)
            except (TypeError, ValueError):
                continue
            if value > 0:
                normalized[str(symbol)] = value
        return normalized
