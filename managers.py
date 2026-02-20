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
    """Centralized management for application configuration and persistence."""
    
    CONFIG_FILE = "target_config.json"
    SETTINGS_FILE = "target_config_settings.json" 
    MAPPING_FILE = "target_config_mapping.json"
    NAMES_FILE = "target_config_names.json"
    
    def __init__(self, drive=None):
        self.drive = drive
        self._targets = {}
        self._settings = {
            "stock_fee_eur": 1.0,
            "crypto_fee_pct": 0.29
        }
        self._mappings = {}
        self._names = {}
        self.load_all()

    def load_all(self):
        self._targets = self._load_json(self.CONFIG_FILE) or {}
        loaded_settings = self._load_json(self.SETTINGS_FILE) or {}
        self._settings.update(loaded_settings)
        self._mappings = self._load_json(self.MAPPING_FILE) or {}
        self._names = self._load_json(self.NAMES_FILE) or {}

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

    def _save_json(self, filename, data):
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

    # --- Targets ---
    def get_targets(self): return self._targets
    
    def set_target(self, product, percentage):
        self._targets[product] = percentage
        self._save_json(self.CONFIG_FILE, self._targets)
        
    def remove_target(self, product):
        if product in self._targets:
            del self._targets[product]
            self._save_json(self.CONFIG_FILE, self._targets)
            
    # --- Settings ---
    def get_settings(self): return self._settings
    
    def update_settings(self, stock_fee=None, crypto_fee=None):
        changed = False
        if stock_fee is not None and stock_fee != self._settings.get("stock_fee_eur"):
            self._settings["stock_fee_eur"] = stock_fee
            changed = True
        if crypto_fee is not None and crypto_fee != self._settings.get("crypto_fee_pct"):
            self._settings["crypto_fee_pct"] = crypto_fee
            changed = True
        
        if changed:
            self._save_json(self.SETTINGS_FILE, self._settings)

    # --- Mappings ---
    def get_mappings(self): return self._mappings
    
    def get_ticker_for_product(self, product, isin=None):
        # 1. Check direct product mapping
        if product in self._mappings:
            return self._mappings[product]
            
        # 2. Check ISIN mapping
        if isin and isin in self._mappings:
            return self._mappings[isin]
            
        return None
        
    def set_mapping(self, key, value):
        self._mappings[key] = value
        self._save_json(self.MAPPING_FILE, self._mappings)

    # --- Names (Metadata) ---
    def get_product_name(self, key):
        return self._names.get(key, key) # fallback to key if no name
        
    def set_product_name(self, key, name):
        if name:
            self._names[key] = name
            self._save_json(self.NAMES_FILE, self._names)

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
            return self._resolve_input_string(mapped)
            
        # 2. Check if product_str itself is a valid ticker input
        resolved = self._resolve_input_string(product_str)
        if resolved: return resolved
        
        # 3. Fallback for legacy hardcoded items (migrate these to JSON ideally)
        if product_str and isinstance(product_str, str):
            upper = product_str.upper()
            if "VANGUARD FTSE ALL-WORLD" in upper: return "VWCE.DE"
            if upper.startswith("BITCOIN"): return "BTC-EUR"
            if upper.startswith("ETHEREUM"): return "ETH-EUR"
            
        return None

    def _resolve_input_string(self, s: str) -> str | None:
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

