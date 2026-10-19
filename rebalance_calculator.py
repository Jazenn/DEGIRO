from __future__ import annotations


class RebalanceCalculator:
    """Create proportional rebalancing purchases for underweight assets."""

    def calculate_deposit_plan(
        self,
        deposit_amount: float,
        portfolio_value: float,
        rebalancing_targets: dict,
        current_values: dict,
        prices: dict | None = None,
    ) -> dict:
        deposit_amount = float(deposit_amount or 0.0)
        if deposit_amount <= 0:
            return {
                "recommended_buys": {asset: 0.0 for asset in current_values},
                "estimated_shares": {asset: 0.0 for asset in current_values},
                "total_buy_eur": 0.0,
                "portfolio_value_after": float(portfolio_value or 0.0),
                "underweight_assets": [],
            }

        normalized = self._normalize_weights(rebalancing_targets)
        total_target = sum(normalized.values())
        if total_target <= 0:
            return {
                "recommended_buys": {asset: 0.0 for asset in current_values},
                "estimated_shares": {asset: 0.0 for asset in current_values},
                "total_buy_eur": 0.0,
                "portfolio_value_after": float(portfolio_value or 0.0),
                "underweight_assets": [],
            }

        projected_total = float(portfolio_value or 0.0) + deposit_amount
        target_values = {
            symbol: projected_total * (weight / total_target)
            for symbol, weight in normalized.items()
        }

        underweight = [
            symbol for symbol in normalized
            if float(current_values.get(symbol, 0.0)) < float(target_values.get(symbol, 0.0))
        ]
        if not underweight:
            return {
                "recommended_buys": {asset: 0.0 for asset in current_values},
                "estimated_shares": {asset: 0.0 for asset in current_values},
                "total_buy_eur": 0.0,
                "portfolio_value_after": projected_total,
                "underweight_assets": [],
            }

        total_gap = sum(max(float(target_values.get(symbol, 0.0)) - float(current_values.get(symbol, 0.0)), 0.0) for symbol in underweight)
        if total_gap <= 0:
            return {
                "recommended_buys": {asset: 0.0 for asset in current_values},
                "estimated_shares": {asset: 0.0 for asset in current_values},
                "total_buy_eur": 0.0,
                "portfolio_value_after": projected_total,
                "underweight_assets": [],
            }

        recommended = {asset: 0.0 for asset in current_values}
        for asset in underweight:
            target_value = float(target_values.get(asset, 0.0))
            current_value = float(current_values.get(asset, 0.0))
            gap = max(target_value - current_value, 0.0)
            recommended[asset] = deposit_amount * (gap / total_gap)

        total_buy_eur = sum(recommended.values())
        estimated_shares = {asset: 0.0 for asset in current_values}
        if prices:
            for asset, buy_eur in recommended.items():
                price = float(prices.get(asset, 0.0) or 0.0)
                estimated_shares[asset] = (buy_eur / price) if price > 0 else 0.0

        return {
            "recommended_buys": recommended,
            "estimated_shares": estimated_shares,
            "total_buy_eur": total_buy_eur,
            "portfolio_value_after": projected_total,
            "underweight_assets": underweight,
        }

    @staticmethod
    def _normalize_weights(weights: dict) -> dict:
        normalized = {}
        for symbol, weight in (weights or {}).items():
            try:
                value = float(weight)
            except (TypeError, ValueError):
                continue
            if value > 0:
                normalized[str(symbol)] = value
        return normalized
