"""Central configuration and default asset settings for the DEGIRO backend."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Default symbol mappings for DEGIRO instruments
DEFAULT_MAPPINGS: Dict[str, str] = {
    # ISIN -> Ticker
    "IE00BK5BQT80": "VWCE.DE",
    "IE0006WW1TQ4": "EXUS.DE",
    "IE00B4K48X80": "IMAE.AS",
    "IE000OJ5TQP4": "ASWC.DE",
    "BMG0112X1056": "AGN.AS",
    # Crypto product names -> Ticker
    "BITCOIN": "BTC-EUR",
    "ETHEREUM": "ETH-EUR",
    "BTC": "BTC-EUR",
    "ETH": "ETH-EUR",
}

# Human-readable names
DEFAULT_DISPLAY_NAMES: Dict[str, str] = {
    "VWCE.DE": "Vanguard FTSE All-World UCITS ETF",
    "EXUS.DE": "iShares MSCI World ex-USA UCITS ETF",
    "IMAE.AS": "iShares Core MSCI Europe UCITS ETF",
    "ASWC.DE": "Future of Defence UCITS ETF",
    "AGN.AS": "Aegon Ltd.",
    "BTC-EUR": "Bitcoin",
    "ETH-EUR": "Ethereum",
}

# Default portfolio rebalancing targets (sums to 100%)
DEFAULT_TARGET_SETTINGS: Dict[str, Dict[str, Any]] = {
    "VWCE.DE": {
        "display_name": "Vanguard FTSE All-World UCITS ETF",
        "target_pct": 55.5,
        "is_crypto": False,
        "buy_dip_trigger": None,
        "sell_profit_trigger": None,
        "buy_budget": None,
    },
    "EXUS.DE": {
        "display_name": "iShares MSCI World ex-USA UCITS ETF",
        "target_pct": 21.0,
        "is_crypto": False,
        "buy_dip_trigger": None,
        "sell_profit_trigger": None,
        "buy_budget": None,
    },
    "BTC-EUR": {
        "display_name": "Bitcoin",
        "target_pct": 8.0,
        "is_crypto": True,
        "buy_dip_trigger": 58500.0,
        "sell_profit_trigger": 75420.0,
        "sell_profit_pct": 15.0,
        "buy_budget": 350.0,
    },
    "IMAE.AS": {
        "display_name": "iShares Core MSCI Europe UCITS ETF",
        "target_pct": 8.5,
        "is_crypto": False,
        "buy_dip_trigger": None,
        "sell_profit_trigger": None,
        "buy_budget": None,
    },
    "ASWC.DE": {
        "display_name": "Future of Defence UCITS ETF",
        "target_pct": 5.0,
        "is_crypto": False,
        "buy_dip_trigger": None,
        "sell_profit_trigger": None,
        "buy_budget": None,
    },
    "ETH-EUR": {
        "display_name": "Ethereum",
        "target_pct": 2.0,
        "is_crypto": True,
        "buy_dip_trigger": 2800.0,
        "sell_profit_trigger": 3800.0,
        "sell_profit_pct": 15.0,
        "buy_budget": 150.0,
    },
}


def get_database_url() -> Optional[str]:
    """Retrieve DATABASE_URL from environment variables."""
    return os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")


class BackendConfig:
    """Manages application configuration, mappings, and settings."""

    CONFIG_FILE = "target_config.json"

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None) -> None:
        self._mappings = dict(DEFAULT_MAPPINGS)
        self._settings = {
            "stock_fee_eur": 1.0,
            "crypto_fee_pct": 0.29,
        }
        self._assets = dict(DEFAULT_TARGET_SETTINGS)

        if config_dict:
            self._apply_dict(config_dict)
        else:
            self._load_local_file()

    def _apply_dict(self, data: Dict[str, Any]) -> None:
        if "mappings" in data and isinstance(data["mappings"], dict):
            self._mappings.update(data["mappings"])
        if "settings" in data and isinstance(data["settings"], dict):
            self._settings.update(data["settings"])
        if "assets" in data and isinstance(data["assets"], dict):
            self._assets.update(data["assets"])

    def _load_local_file(self) -> None:
        if Path(self.CONFIG_FILE).exists():
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._apply_dict(data)
            except Exception:
                pass

    def get_mappings(self) -> Dict[str, str]:
        return dict(self._mappings)

    def get_ticker_for_product(self, product: str, isin: Optional[str] = None) -> Optional[str]:
        if isin and isin in self._mappings:
            return self._mappings[isin]
        if product in self._mappings:
            return self._mappings[product]
        upper_prod = product.upper().strip()
        for k, v in self._mappings.items():
            if k.upper() in upper_prod:
                return v
        return None

    def get_settings(self) -> Dict[str, Any]:
        return dict(self._settings)

    def get_assets(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._assets)
