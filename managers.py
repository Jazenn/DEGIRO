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
        # Only save if we actually imported old data
        migrated_something = False
        if old_targets_data and isinstance(old_targets_data, dict):
             migrated_something = True

        if old_settings: migrated_something = True
        if old_mappings: migrated_something = True
        if old_names:    migrated_something = True

        if migrated_something:
            self._save_config()

    def _load_json(self, filename):
        if self.drive:
            try:
                data = self.drive.load_json(filename)
                if data is not None: return data
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
    
    def get_asset(self, key):
        """Get the configuration for a specific asset."""
        return self._config.get("assets", {}).get(key, {})

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

    def batch_update_assets(self, updates: list):
        """Update multiple assets and save once to prevent Drive API rate limits."""
        for u in updates:
            key = u.get("key")
            target_pct = u.get("target_pct")
            display_name = u.get("display_name")
            
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

    def batch_remove_assets(self, products: list):
        changed = False
        for product in products:
            if product in self._config["assets"]:
                del self._config["assets"][product]
                changed = True
        if changed:
            self._save_config()

    # --- Names (Metadata) ---
    def get_product_name(self, key):
        asset = self._config.get("assets", {}).get(key, {})
        name = asset.get("display_name", key) # fallback to key
        n = str(name).upper()
        if "VANGUARD" in n: return "All-World"
        if "XTRACKERS" in n: return "Ex-USA"
        if "ISHARES" in n: return "Europe"
        if "FUTURE OF DEFENCE" in n or "HANETF" in n: return "FOD"
        return name
        
    def set_product_name(self, key, name):
        self.set_asset(key, display_name=name)

    # --- Trading Strategy ---
    def get_trading_strategy(self, key):
        """Get the trading strategy for a specific asset."""
        asset = self._config.get("assets", {}).get(key, {})
        return asset.get("trading_strategy", {"sell_levels": [], "buy_levels": []})

    def set_trading_strategy(self, key, strategy):
        """Update the trading strategy for a specific asset."""
        if key not in self._config["assets"]:
            self._config["assets"][key] = {}
        self._config["assets"][key]["trading_strategy"] = strategy
        self._save_config()

# --- PRICE MANAGER ---
class PriceManager:
    """Centralized price fetching (Live, History, Metadata)."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self._cache = {}
        self._watchlist = set()
        self._lock = threading.Lock()
        self._snapshot_live = {}
        self._snapshot_prev = {}
        self._snapshot_mid = {}
        self._snapshot_open = {}
        
    def load_snapshots(self, snapshot_prices: dict):
        """Pre-populate caches with background fetched data."""
        if not snapshot_prices: return
        self._snapshot_live = snapshot_prices.get("batch_live", {})
        self._snapshot_prev = snapshot_prices.get("batch_prev", {})
        self._snapshot_mid = snapshot_prices.get("batch_mid", {})
        self._snapshot_open = snapshot_prices.get("batch_open", {})
        
    def _should_use_snapshot(self):
        # Use snapshot if the seamless background fetch hasn't completed yet
        return not st.session_state.get("live_fetch_done", False)
        
    def resolve_ticker(self, product_str: str, isin: str = None) -> str | None:
        """Resolve a product to a yfinance ticker using Config and logic."""
        # 1. Check Config Mappings
        mapped = self.config.get_ticker_for_product(product_str, isin)
        if mapped:
            # If it's a legacy format "TICKER | ISIN", grab the ticker
            if "|" in mapped:
                return mapped.split("|")[0].strip()
            return mapped
            
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
        # Always prioritize ISIN search over generic string search to avoid penny stock name collisions.
        if isin:
            quotes = self._get_yf_search_quotes(isin)
            discovered_ticker = self._select_best_quote(quotes) if quotes else None
            if discovered_ticker:
                self.config.set_mapping(isin, discovered_ticker)
                if product_str: 
                    self.config.set_mapping(product_str, discovered_ticker)
                return discovered_ticker
                
        # 5. Fallback to product name auto-discovery if ISIN fails or is missing
        if product_str:
            quotes = self._get_yf_search_quotes(product_str)
            discovered_ticker = self._select_best_quote(quotes) if quotes else None
            
            if discovered_ticker:
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
        if st.session_state.get("live_fetch_done") and st.session_state.get("mem_live_prices"):
            return float(st.session_state["mem_live_prices"].get(ticker, 0.0))
        if self._snapshot_live and self._should_use_snapshot():
            return float(self._snapshot_live.get(ticker, 0.0))
        return self._fetch_live_price_cached(ticker)

    @st.cache_data(ttl=60)
    def _fetch_live_price_cached(_self, ticker):
        import requests
        # 1. Try TradeGate API first for any valid ISINs
        isin = None
        for k, v in _self.config.get_mappings().items():
            if v == ticker and len(k) == 12 and not k.startswith("XFC"):
                isin = k
                break
                
        if isin:
            try:
                url = f"https://www.tradegate.de/refresh.php?isin={isin}"
                headers = {'User-agent': 'Mozilla/5.0'}
                r = requests.get(url, headers=headers, timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    if "last" in data and data["last"]:
                        return float(data["last"])
            except:
                pass

        try:
            # Fallback to YF
            t = yf.Ticker(ticker)
            # Try fast_info first
            price = t.fast_info.last_price
            if price: return float(price)
            # Fallback to history
            hist = t.history(period="1d", prepost=True)
            if not hist.empty: return float(hist["Close"].iloc[-1])
        except: pass
        return 0.0

    def get_live_prices_batch(self, tickers: list[str]) -> dict:
        """Fetch live prices for multiple tickers in one optimized batch."""
        valid_tickers = [t for t in tickers if t]
        if not valid_tickers: return {}
        if st.session_state.get("live_fetch_done") and st.session_state.get("mem_live_prices"):
            return {t: st.session_state["mem_live_prices"].get(t, 0.0) for t in valid_tickers}
        if self._snapshot_live and self._should_use_snapshot():
            return {t: self._snapshot_live.get(t, 0.0) for t in valid_tickers}
        return self._fetch_live_prices_batch_cached(tuple(set(valid_tickers)))

    @st.cache_data(ttl=60)
    def _fetch_live_prices_batch_cached(_self, tickers_tuple: tuple) -> dict:
        results = {t: 0.0 for t in tickers_tuple}
        yf_tickers = []
        
        import requests
        
        # 1. Try TradeGate API first for any valid ISINs
        # Map tickers to ISINs using config mappings (reverse lookup)
        ticker_to_isin = {}
        for k, v in _self.config.get_mappings().items():
            if v in tickers_tuple and (len(k) == 12 and not k.startswith("XFC")): # simple ISIN check
                ticker_to_isin[v] = k
                
        for t in tickers_tuple:
            isin = ticker_to_isin.get(t)
            if isin:
                try:
                    url = f"https://www.tradegate.de/refresh.php?isin={isin}"
                    headers = {'User-agent': 'Mozilla/5.0'}
                    r = requests.get(url, headers=headers, timeout=3)
                    if r.status_code == 200:
                        data = r.json()
                        if "last" in data and data["last"]:
                            results[t] = float(data["last"])
                            continue
                except:
                    pass
            # If no ISIN, TradeGate fail, or no 'last' price, fallback to YF
            yf_tickers.append(t)
            
        if not yf_tickers:
            return results

        try:
            tickers_str = " ".join(yf_tickers)
            # Fetch all at once
            data = yf.download(tickers_str, period="1d", group_by="ticker", progress=False, threads=True)
            
            for t in yf_tickers:
                try:
                    if len(yf_tickers) == 1:
                        if not data.empty and "Close" in data:
                            results[t] = float(data["Close"].dropna().iloc[-1])
                    else:
                        if t in data and "Close" in data[t]:
                            results[t] = float(data[t]["Close"].dropna().iloc[-1])
                except:
                    pass
        except:
            pass
            
        # Fallback to fast_info for tickers that failed in batch download
        for t in yf_tickers:
            if not results.get(t):
                try:
                    price = yf.Ticker(t).fast_info.last_price
                    if price: results[t] = float(price)
                except: pass
                
        return results

    def get_history(self, ticker, period="1y"):
        return self._fetch_history_cached(ticker, period)

    @st.cache_data(ttl=3600)
    def _fetch_history_cached(_self, ticker, period):
        try:
            return yf.Ticker(ticker).history(period=period, prepost=True)
        except: return pd.DataFrame()

    def get_prev_closes_batch(self, tickers: list[str]) -> dict:
        valid = [t for t in tickers if t]
        if not valid: return {}
        if st.session_state.get("live_fetch_done") and st.session_state.get("mem_prev_prices"):
            return {t: st.session_state["mem_prev_prices"].get(t, 0.0) for t in valid}
        if self._snapshot_prev and self._should_use_snapshot():
            return {t: self._snapshot_prev.get(t, 0.0) for t in valid}
        current_date_str = pd.Timestamp.now(tz="Europe/Amsterdam").strftime("%Y-%m-%d")
        return self._fetch_prev_closes_batch_cached(tuple(set(valid)), current_date_str)

    @st.cache_data(ttl=21600)
    def _fetch_prev_closes_batch_cached(_self, tickers_tuple: tuple, current_date_str: str) -> dict:
        results = {t: 0.0 for t in tickers_tuple}
        yf_tickers = []
        import requests
        
        # 1. Try TradeGate API first for any valid ISINs
        ticker_to_isin = {}
        for k, v in _self.config.get_mappings().items():
             if v in tickers_tuple and (len(k) == 12 and not k.startswith("XFC")):
                 ticker_to_isin[v] = k
                 
        for t in tickers_tuple:
            isin = ticker_to_isin.get(t)
            if isin:
                try:
                    url = f"https://www.tradegate.de/refresh.php?isin={isin}"
                    headers = {'User-agent': 'Mozilla/5.0'}
                    r = requests.get(url, headers=headers, timeout=3)
                    if r.status_code == 200:
                        data = r.json()
                        if "close" in data and data["close"]:
                            results[t] = float(data["close"])
                            continue
                except:
                    pass
            yf_tickers.append(t)
            
        if not yf_tickers:
             return results
             
        try:
            tickers_str = " ".join(yf_tickers)
            data = yf.download(tickers_str, period="5d", interval="1d", group_by="ticker", progress=False, threads=True)
            for t in yf_tickers:
                try:
                    if len(yf_tickers) == 1:
                        df_t = data.dropna(subset=["Close"])
                    else:
                        df_t = data[t].dropna(subset=["Close"]) if t in data else pd.DataFrame()
                        
                    if len(df_t) >= 2:
                        results[t] = float(df_t["Close"].iloc[-2])
                    elif len(df_t) == 1:
                        results[t] = float(df_t["Close"].iloc[0])
                except: pass
        except: pass
        return results

    def get_prev_close(self, ticker):
        """Return previous trading day close."""
        if not ticker: return 0.0
        if st.session_state.get("live_fetch_done") and st.session_state.get("mem_prev_prices"):
            return float(st.session_state["mem_prev_prices"].get(ticker, 0.0))
        if self._snapshot_prev and self._should_use_snapshot():
            return float(self._snapshot_prev.get(ticker, 0.0))
        current_date_str = pd.Timestamp.now(tz="Europe/Amsterdam").strftime("%Y-%m-%d")
        return self._fetch_prev_close_cached(ticker, current_date_str)

    @st.cache_data(ttl=21600) # Cache for 6 hours
    def _fetch_prev_close_cached(_self, ticker, current_date_str):
        import requests
        # 1. Try TradeGate API first for any valid ISINs
        isin = None
        for k, v in _self.config.get_mappings().items():
            if v == ticker and len(k) == 12 and not k.startswith("XFC"):
                isin = k
                break

        if isin:
            try:
                url = f"https://www.tradegate.de/refresh.php?isin={isin}"
                headers = {'User-agent': 'Mozilla/5.0'}
                r = requests.get(url, headers=headers, timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    if "close" in data and data["close"]:
                        return float(data["close"])
            except:
                pass

        try:
            hist = yf.Ticker(ticker).history(period="5d", interval="1d", prepost=True) # 5d to be safe regarding weekends
            if len(hist) >= 2:
                return float(hist["Close"].iloc[-2])
            elif len(hist) == 1:
                return float(hist["Close"].iloc[0])
        except: pass
        return 0.0

    def get_market_open_prices_batch(self, tickers: list[str]) -> dict:
        valid = [t for t in tickers if t]
        if not valid: return {}
        if st.session_state.get("live_fetch_done") and st.session_state.get("mem_open_prices"):
            return {t: st.session_state["mem_open_prices"].get(t, 0.0) for t in valid}
        if self._snapshot_open and self._should_use_snapshot():
            return {t: self._snapshot_open.get(t, 0.0) for t in valid}
        return self._fetch_market_open_prices_batch_cached(tuple(set(valid)))

    @st.cache_data(ttl=3600)
    def _fetch_market_open_prices_batch_cached(_self, tickers_tuple: tuple) -> dict:
        results = {t: 0.0 for t in tickers_tuple}
        try:
            tickers_str = " ".join(tickers_tuple)
            data = yf.download(tickers_str, period="1d", group_by="ticker", progress=False, threads=True)
            for t in tickers_tuple:
                try:
                    if len(tickers_tuple) == 1:
                        if not data.empty and "Open" in data:
                            open_vals = data["Open"].dropna()
                            if not open_vals.empty:
                                results[t] = float(open_vals.iloc[-1])
                    else:
                        if t in data and "Open" in data[t]:
                            open_vals = data[t]["Open"].dropna()
                            if not open_vals.empty:
                                results[t] = float(open_vals.iloc[-1])
                except: pass
        except: pass
        return results

    def get_market_open_price(self, ticker):
        """Return opening price of the most recent trading day."""
        if not ticker: return 0.0
        if st.session_state.get("live_fetch_done") and st.session_state.get("mem_open_prices"):
            return float(st.session_state["mem_open_prices"].get(ticker, 0.0))
        if self._snapshot_open and self._should_use_snapshot():
            return float(self._snapshot_open.get(ticker, 0.0))
        return self._fetch_market_open_price_cached(ticker)

    @st.cache_data(ttl=3600)
    def _fetch_market_open_price_cached(_self, ticker):
        try:
            hist = yf.Ticker(ticker).history(period="1d")
            if not hist.empty and "Open" in hist.columns:
                return float(hist["Open"].iloc[-1])
        except: pass
        return 0.0

    def get_midnight_prices_batch(self, tickers: list[str]) -> dict:
        valid = [t for t in tickers if t]
        if not valid: return {}
        if st.session_state.get("live_fetch_done") and st.session_state.get("mem_mid_prices"):
            return {t: st.session_state["mem_mid_prices"].get(t, 0.0) for t in valid}
        if self._snapshot_mid and self._should_use_snapshot():
            return {t: self._snapshot_mid.get(t, 0.0) for t in valid}
        # Use Amsterdam midnight for the cache key, but normalized to UTC base for YF logic
        amsterdam_now = pd.Timestamp.now(tz="Europe/Amsterdam")
        midnight_ams = amsterdam_now.normalize()
        date_str = midnight_ams.strftime("%Y-%m-%d %H:%M:%S %Z")
        return self._fetch_midnight_prices_batch_cached(tuple(set(valid)), date_str)

    @st.cache_data(ttl=3600)
    def _fetch_midnight_prices_batch_cached(_self, tickers_tuple: tuple, date_str: str) -> dict:
        results = {t: 0.0 for t in tickers_tuple}
        try:
            tickers_str = " ".join(tickers_tuple)
            
            # Amsterdam today 00:00 local time
            ams_midnight = pd.Timestamp.now(tz="Europe/Amsterdam").normalize()
            # The point we want is usually the last point of "yesterday" or first of "today"
            # To be safe, we fetch 3 days and find the exact hour that matches AMS midnight.
            
            # Handle single ticker cleanly using Ticker().history()
            if len(tickers_tuple) == 1:
                t = tickers_tuple[0]
                hist = yf.Ticker(t).history(period="3d", interval="1h", prepost=True)
                if not hist.empty and "Close" in hist.columns:
                    hist = hist.reset_index()
                    col_dt = hist.columns[0]
                    if hist[col_dt].dt.tz is None:
                         hist[col_dt] = hist[col_dt].dt.tz_localize("UTC")
                    
                    # Convert history to Amsterdam time
                    hist[col_dt] = hist[col_dt].dt.tz_convert("Europe/Amsterdam")
                    
                    # Find the row where the time is 00:00 on the current day
                    mask = (hist[col_dt].dt.normalize() == ams_midnight) & (hist[col_dt].dt.hour == 0)
                    if mask.any():
                         results[t] = float(hist.loc[mask, "Close"].iloc[0])
                    else:
                        # Fallback to the very latest point before midnight
                        before_midnight = hist[hist[col_dt] < ams_midnight]
                        if not before_midnight.empty:
                            results[t] = float(before_midnight["Close"].iloc[-1])
                return results
                
            # Handle multi-ticker downloaded batch
            data = yf.download(tickers_str, period="3d", interval="1h", group_by="ticker", prepost=True, progress=False, threads=True)
            
            for t in tickers_tuple:
                try:
                    df_t = pd.DataFrame()
                    if isinstance(data.columns, pd.MultiIndex):
                        if t in data.columns.levels[0]:
                            try:
                                sub_df = data.xs(t, axis=1, level=0)
                                if "Close" in sub_df.columns:
                                    df_t = sub_df.dropna(subset=["Close"])
                            except: pass
                    else:
                        df_t = data.dropna(subset=["Close"]) if "Close" in data.columns else pd.DataFrame()
                        
                    if not df_t.empty:
                        hist = df_t.reset_index()
                        col_dt = hist.columns[0]
                        if hist[col_dt].dt.tz is None:
                             hist[col_dt] = hist[col_dt].dt.tz_localize("UTC")
                        
                        hist[col_dt] = hist[col_dt].dt.tz_convert("Europe/Amsterdam")
                        mask = (hist[col_dt].dt.normalize() == ams_midnight) & (hist[col_dt].dt.hour == 0)
                        if mask.any():
                             results[t] = float(hist.loc[mask, "Close"].iloc[0])
                        else:
                            before_midnight = hist[hist[col_dt] < ams_midnight]
                            if not before_midnight.empty:
                                results[t] = float(before_midnight["Close"].iloc[-1])
                except: pass
        except: pass
        return results

    def get_midnight_price(self, ticker):
        """Return price at start of today (midnight Amsterdam time) for daily P/L."""
        if not ticker: return 0.0
        if st.session_state.get("live_fetch_done") and st.session_state.get("mem_mid_prices"):
            return float(st.session_state["mem_mid_prices"].get(ticker, 0.0))
        if self._snapshot_mid and self._should_use_snapshot():
            return float(self._snapshot_mid.get(ticker, 0.0))
        ams_midnight = pd.Timestamp.now(tz="Europe/Amsterdam").normalize()
        date_str = ams_midnight.strftime("%Y-%m-%d %H:%M:%S %Z")
        return self._fetch_midnight_price_cached(ticker, date_str)

    @st.cache_data(ttl=3600)
    def _fetch_midnight_price_cached(_self, ticker, date_str):
        try:
            # Fetch 3d of hourly data
            hist = yf.Ticker(ticker).history(period="3d", interval="1h", prepost=True)
            if hist.empty: return 0.0
            
            # Amsterdam today 00:00 local time
            ams_midnight = pd.Timestamp.now(tz="Europe/Amsterdam").normalize()
            hist = hist.reset_index()
            
            # Convert to Amsterdam time correctly
            if hist["Datetime"].dt.tz is None:
                hist["Datetime"] = hist["Datetime"].dt.tz_localize("UTC")
                
            hist["Datetime"] = hist["Datetime"].dt.tz_convert("Europe/Amsterdam")
            mask = (hist["Datetime"].dt.normalize() == ams_midnight) & (hist["Datetime"].dt.hour == 0)
            if mask.any():
                 return float(hist.loc[mask, "Close"].iloc[0])
            else:
                before_midnight = hist[hist["Datetime"] < ams_midnight]
                if not before_midnight.empty:
                    return float(before_midnight["Close"].iloc[-1])
        except: pass
        return 0.0

