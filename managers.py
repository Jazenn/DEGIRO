import json
from pathlib import Path
import pandas as pd
import streamlit as st
import yfinance as yf
import re
import concurrent.futures
import threading

# --- CONFIGURATION MANAGER ---
class ConfigManager:
    """Centralized management for application configuration and persistence (Unified)."""
    
    CONFIG_FILE = "target_config.json"
    # Legacy files for migration
    LEGACY_SETTINGS_FILE = "target_config_settings.json" 
    LEGACY_MAPPING_FILE = "target_config_mapping.json"
    LEGACY_NAMES_FILE = "target_config_names.json"
    
    def __init__(self, drive=None):
        self.drive = drive
        self._config = {
            "assets": {},
            "settings": {
                "stock_fee_eur": 1.0,
                "crypto_fee_pct": 0.29
            },
            "mappings": {}
        }
        self.load_all()

    def load_all(self):
        data = self._load_json(self.CONFIG_FILE)
        
        if data and "assets" in data:
            # New Unified Format Detected
            self._config = data
            # Ensure keys exist if partial file
            if "settings" not in self._config: self._config["settings"] = {}
            if "mappings" not in self._config: self._config["mappings"] = {}
        else:
            # Old Format or Missing -> Migrate
            self._migrate_legacy_config(data)

    def _migrate_legacy_config(self, old_targets_data):
        # 1. Targets (legacy was {"KEY": pct})
        if old_targets_data and isinstance(old_targets_data, dict):
             for k, v in old_targets_data.items():
                 if k not in self._config["assets"]:
                     self._config["assets"][k] = {}
                 self._config["assets"][k]["target_pct"] = float(v)
                 
        # 2. Settings
        old_settings = self._load_json(self.LEGACY_SETTINGS_FILE)
        if old_settings:
            self._config["settings"].update(old_settings)
            
        # 3. Mappings
        old_mappings = self._load_json(self.LEGACY_MAPPING_FILE)
        if old_mappings:
            self._config["mappings"].update(old_mappings)
            
        # 4. Names
        old_names = self._load_json(self.LEGACY_NAMES_FILE)
        if old_names:
            for k, name in old_names.items():
                if k not in self._config["assets"]:
                     self._config["assets"][k] = {"target_pct": 0.0}
                self._config["assets"][k]["display_name"] = name
                
        # Save immediately to complete migration (if we have any data)
        # Only save if we actually loaded something or if it's a fresh init
        self._save_config()

    def _load_json(self, filename):
        if self.drive:
            try:
                data = self.drive.load_json(filename)
                if data: return data
            except: pass
        
        if Path(filename).exists():
            try:
                with open(filename, "r") as f:
                    return json.load(f)
            except: pass
        return None

    def _save_config(self):
        filename = self.CONFIG_FILE
        data = self._config
        
        if self.drive:
            try:
                self.drive.save_json(filename, data)
            except: pass
        else:
            try:
                with open(filename, "w") as f:
                    json.dump(data, f, indent=4)
            except Exception as e:
                st.error(f"Failed to save {filename}: {e}")

    def _save_json(self, filename, data):
        # Helper mainly for legacy or direct calls if needed, 
        # but _save_config handles the main file.
        pass

    # --- Targets ---
    def get_targets(self): 
        return {k: v.get("target_pct", 0.0) for k, v in self._config.get("assets", {}).items()}
    
    def set_target(self, product, percentage):
        if product not in self._config["assets"]: 
            self._config["assets"][product] = {}
        self._config["assets"][product]["target_pct"] = percentage
        self._save_config()
        
    def remove_target(self, product):
        if product in self._config["assets"]:
            del self._config["assets"][product]
            self._save_config()
            
    # --- Settings ---
    def get_settings(self): return self._config.get("settings", {})
    
    def update_settings(self, stock_fee=None, crypto_fee=None):
        changed = False
        settings = self._config.get("settings", {})
        
        if stock_fee is not None and stock_fee != settings.get("stock_fee_eur"):
            settings["stock_fee_eur"] = stock_fee
            changed = True
        if crypto_fee is not None and crypto_fee != settings.get("crypto_fee_pct"):
            settings["crypto_fee_pct"] = crypto_fee
            changed = True
        
        if changed:
            self._config["settings"] = settings
            self._save_config()

    # --- Mappings ---
    def get_mappings(self): return self._config.get("mappings", {})
    
    def get_ticker_for_product(self, product, isin=None):
        mappings = self.get_mappings()
        # 1. Check direct product mapping
        if product in mappings:
            return mappings[product]
        # 2. Check ISIN mapping
        if isin and isin in mappings:
            return mappings[isin]
        return None
        
    def set_mapping(self, key, value):
        if "mappings" not in self._config: self._config["mappings"] = {}
        self._config["mappings"][key] = value
        self._save_config()

    # --- Unified Asset Management (Rich Objects) ---
    def get_assets(self):
        """Return the full dictionary of asset objects."""
        return self._config.get("assets", {})
        
    def set_asset(self, key, target_pct=None, display_name=None):
        """Update an asset's properties. Creates it if missing."""
        if key not in self._config["assets"]:
            self._config["assets"][key] = {}
            
        if target_pct is not None:
             self._config["assets"][key]["target_pct"] = float(target_pct)
        
        if display_name is not None:
             self._config["assets"][key]["display_name"] = str(display_name).strip()
             
        self._save_config()

    # --- Legacy/Helper Wrappers (Maintained for compatibility but redirect to assets) ---
    def get_targets(self): 
        return {k: v.get("target_pct", 0.0) for k, v in self._config.get("assets", {}).items()}
    
    def set_target(self, product, percentage):
        self.set_asset(product, target_pct=percentage)
        
    def remove_target(self, product):
        if product in self._config["assets"]:
            del self._config["assets"][product]
            self._save_config()

    # --- Names (Metadata) ---
    def get_product_name(self, key):
        asset = self._config.get("assets", {}).get(key, {})
        return asset.get("display_name", key) # fallback to key
        
    def set_product_name(self, key, name):
        self.set_asset(key, display_name=name)

# --- PRICE MANAGER ---
class PriceManager:
    """Centralized price fetching (Live, History, Metadata)."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self._cache = {}
        self._watchlist = set()
        self._lock = threading.Lock()
        
    def resolve_ticker(self, product_str: str, isin: str = None) -> str | None:
        """Resolve a product to a yfinance ticker using Config and logic."""
        # 1. Check Config Mappings
        mapped = self.config.get_ticker_for_product(product_str, isin)
        # st.write(f"DEBUG: Resolving '{product_str}' / '{isin}' -> Mapped: {mapped}")
        if mapped:
            resolved_mapped = self._resolve_input_string(mapped, strict=False)
            if resolved_mapped:
                return resolved_mapped
            
        # 2. Check if product_str itself is a valid ticker input
        resolved = self._resolve_input_string(product_str, strict=True)
        if resolved: 
            # Auto-save direct ticker string if valid
            mapping_key = isin if isin else product_str
            if mapping_key:
                self.config.set_mapping(mapping_key, resolved)
            return resolved
        
        # 3. Fallback for legacy hardcoded items (migrate these to JSON ideally)
        if product_str and isinstance(product_str, str):
            upper = product_str.upper()
            resolved_legacy = None
            if "VANGUARD FTSE ALL-WORLD" in upper: resolved_legacy = "VWCE.DE"
            elif upper.startswith("BITCOIN"): resolved_legacy = "BTC-EUR"
            elif upper.startswith("ETHEREUM"): resolved_legacy = "ETH-EUR"
            
            if resolved_legacy:
                mapping_key = isin if isin else product_str
                if mapping_key:
                    self.config.set_mapping(mapping_key, resolved_legacy)
                return resolved_legacy

        # 4. Auto-discover using Yahoo Finance Search API
        quotes = []
        if isin:
            quotes.extend(self._get_yf_search_quotes(isin))
        if product_str:
            quotes.extend(self._get_yf_search_quotes(product_str))
             
        discovered_ticker = self._select_best_quote(quotes) if quotes else None
        
        if discovered_ticker:
            # Auto-save discovered ticker
            mapping_key = isin if isin else product_str
            if mapping_key:
                self.config.set_mapping(mapping_key, discovered_ticker)
            return discovered_ticker
            
        return None

    def _get_yf_search_quotes(self, query: str) -> list:
        """Helper to get raw search quotes from YF."""
        import requests
        import urllib.parse
        if not query or not isinstance(query, str):
             return []
        try:
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}"
            headers = {'User-agent': 'Mozilla/5.0'}
            r = requests.get(url, headers=headers, timeout=5)
            r.raise_for_status()
            return r.json().get('quotes', [])
        except Exception:
            return []

    def _select_best_quote(self, quotes: list) -> str | None:
        """Select the best ticker, prioritizing TradeGate/Stuttgart and EUR exchanges."""
        valid_types = ['EQUITY', 'ETF', 'MUTUALFUND']
        # User specified they use TradeGate for almost everything: STU is the Stuttgart exchange (proxies TradeGate on YF)
        preferred_exchanges = ['STU', 'GER', 'AMS', 'PAR', 'MIL', 'BRU', 'DUB']
        
        valid_quotes = []
        for q in quotes:
            ticker = q.get('symbol')
            q_type = q.get('quoteType')
            exchange = q.get('exchange', '')
            if ticker and q_type in valid_types:
                valid_quotes.append((ticker, exchange))
                
        # First pass: try to find a valid ticker on a preferred exchange
        for ticker, exchange in valid_quotes:
            if exchange in preferred_exchanges:
                if self._validate_ticker(ticker):
                    return ticker
                    
        # Second pass: fallback to any valid ticker
        for ticker, _ in valid_quotes:
            if self._validate_ticker(ticker):
                 return ticker
                 
        return None

    def _resolve_input_string(self, s: str, strict: bool = False) -> str | None:
        """Handle 'TICKER | ISIN' and validation."""
        if not s or not isinstance(s, str): return None
        s = s.strip()
        
        # Split "TICKER | ISIN"
        candidates = []
        if "|" in s:
            parts = [p.strip() for p in s.split("|")]
            # Try ticker first (part 0), then ISIN (part 1)
            candidates.extend(parts)
        else:
            candidates.append(s)
            
        # Validation Loop
        suffixes = ["", ".DE", ".F", ".AS"]
        for cand in candidates:
            for suf in suffixes:
                ticker = f"{cand}{suf}"
                if self._validate_ticker(ticker):
                    return ticker
        
        if strict:
            return None
            
        # Fallback: Just return the first candidate if it looks reasonable
        return candidates[0] if candidates else None

    def _validate_ticker(self, ticker):
        """Quick check if ticker exists."""
        try:
            # Check cache first to avoid spamming YF
            if ticker in self._cache: return True
            
            t = yf.Ticker(ticker)
            # Fast check: info or 1d history
            hist = t.history(period="1d", interval="1d")
            return not hist.empty
        except:
            return False

    def get_live_price(self, ticker):
        if not ticker: return 0.0
        # Check cache logic or fetch
        # For simplicity in this refactor step, we'll do a direct fetch with st.cache_data wrapper 
        # or implement the background worker. 
        # Let's keep the background worker concept if possible, or simplify to cached fetch.
        # User wants "clean and robust".
        return self._fetch_live_price_cached(ticker)

    @st.cache_data(ttl=60)
    def _fetch_live_price_cached(_self, ticker):
        try:
            # Special case for Tradegate scraping if needed, but YF is preferred standard
            t = yf.Ticker(ticker)
            # Try fast_info first
            price = t.fast_info.last_price
            if price: return price
            # Fallback to history
            hist = t.history(period="1d")
            if not hist.empty: return hist["Close"].iloc[-1]
        except: pass
        return 0.0

    def get_history(self, ticker, period="1y"):
        return self._fetch_history_cached(ticker, period)

    @st.cache_data(ttl=3600)
    def _fetch_history_cached(_self, ticker, period):
        try:
            return yf.Ticker(ticker).history(period=period)
        except: return pd.DataFrame()

    def get_prev_close(self, ticker):
        """Return previous trading day close."""
        if not ticker: return 0.0
        return self._fetch_prev_close_cached(ticker)

    @st.cache_data(ttl=21600) # Cache for 6 hours
    def _fetch_prev_close_cached(_self, ticker):
        try:
            hist = yf.Ticker(ticker).history(period="5d", interval="1d") # 5d to be safe regarding weekends
            if len(hist) >= 2:
                return float(hist["Close"].iloc[-2])
            elif len(hist) == 1:
                return float(hist["Close"].iloc[0])
        except: pass
        return 0.0

    def get_midnight_price(self, ticker):
        """Return price at start of today (midnight) for daily P/L."""
        if not ticker: return 0.0
        return self._fetch_midnight_price_cached(ticker)

    @st.cache_data(ttl=3600)
    def _fetch_midnight_price_cached(_self, ticker):
        try:
            # Fetch 1d of hourly data
            hist = yf.Ticker(ticker).history(period="1d", interval="1h")
            if hist.empty: return 0.0
            
            # Find first datapoint of "today"
            today = pd.Timestamp.now().normalize()
            hist = hist.reset_index()
            # Ensure Datetime is timezone naive or compatible
            if hist["Datetime"].dt.tz is not None:
                hist["Datetime"] = hist["Datetime"].dt.tz_localize(None)
                
            mask = hist["Datetime"].dt.normalize() == today
            if mask.any():
                 return float(hist.loc[mask, "Close"].iloc[0])
        except: pass
        return 0.0

