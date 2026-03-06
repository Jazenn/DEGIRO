import pandas as pd
import streamlit as st
import datetime

# Compatibility check for st.fragment (Streamlit 1.37+)
if hasattr(st, "fragment"):
    fragment = st.fragment
else:
    # Dummy decorator if getting older version
    def fragment(*args, **kwargs):
        def wrapper(f): return f
        return wrapper

def _shorten_name(name):
    """Verkort de namen van ETFs voor betere leesbaarheid op mobiel."""
    n = str(name).upper()
    if "VANGUARD" in n: return "All-World"
    if "XTRACKERS" in n: return "Ex-USA"
    if "ISHARES" in n: return "Europe"
    if "FUTURE OF DEFENCE" in n or "HANETF" in n: return "FOD"
    return name

def format_eur(value: float) -> str:
    """Format a float as European-style euro string."""
    if pd.isna(value):
        return "€ 0,00"
    # First format with US/UK style, then swap separators
    s = f"{value:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {s}"

def format_pct(value: float) -> str:
    """Format a float as percentage with European decimal separator."""
    if pd.isna(value):
        return ""
    s = f"{value:+.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ",")
    return f"{s}%"

def is_tradegate_open() -> bool:
    """Check if TradeGate is open (07:30-22:00 CET, Mon-Fri)."""
    now = pd.Timestamp.now(tz='Europe/Amsterdam')
    # Only weekdays (Mon=0, Fri=4)
    if now.weekday() > 4:
        return False
    # Trading hours: 07:30 to 22:00
    current_time = now.time()
    start_time = datetime.time(7, 30)
    end_time = datetime.time(22, 0)
    return start_time <= current_time <= end_time
