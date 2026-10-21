# Research: Zero-Cost Benchmark Feeds for VWCE & Global Market Comparison

**Ticket:** [#27](https://github.com/Jazenn/DEGIRO/issues/27)  
**Parent Map:** [#25 (Wayfinder Map: Tabbed Dashboard Overhaul)](https://github.com/Jazenn/DEGIRO/issues/25)  
**Date:** October 2026  
**Status:** Complete  

---

## Executive Summary

To deliver a lightweight, high-performance benchmark comparison overlay on the DEGIRO portfolio chart (comparing portfolio equity performance against **VWCE** and **S&P 500** across `24H`, `1W`, `1M`, `3M`, `1Y`, and `ALL` timeframes) under the strict constraint of **100% zero hosting and data costs forever**, we evaluated all candidate data providers and architectural delivery models.

### Key Findings

1. **TradeGate Exchange Public JSON API** (`refresh.php`):
   - **Excellent for 24H Real-Time Intraday**: Offers live bid/ask, current execution price (`last`), previous day close (`close`), open, high, low, and delta for European ETFs including VWCE (`IE00BK5BQT80`) and S&P 500 UCITS ETFs (`IE00BFMXXD54` VUAA, `IE00B5BMR087` CSPX/SXR8).
   - **Full Browser CORS Support**: Sends `Access-Control-Allow-Origin: *`, allowing sub-150ms client-side browser fetch with zero proxy servers.
   - **Strict Limitation**: Provides **no historical numerical timeseries API**. Historical charts on TradeGate's web portal are server-rendered static `.png` images (`/images/charts/jahr/IE00BK5BQT80.png`). TradeGate cannot power `1W`, `1M`, `3M`, `1Y`, or `ALL` historical curves.

2. **Yahoo Finance v8 Chart API** (`query1.finance.yahoo.com/v8/finance/chart/...`):
   - **Rich Multi-Timeframe Historical Data**: Accurately provides historical daily closes, adjusted closes, timestamps, and intraday candles for `VWCE.DE` (XETRA EUR), `VUAA.DE` / `SXR8.DE` (S&P 500 EUR UCITS), and `^GSPC` (S&P 500 USD index).
   - **Critical Browser Blocker (No CORS)**: Yahoo Finance does **not** return `Access-Control-Allow-Origin` headers. Direct browser `fetch()` is unconditionally blocked by modern browser CORS security policies.
   - **Datacenter Rate Limits**: Datacenter IP addresses (e.g., Cloudflare Workers, AWS Lambda) frequently trigger HTTP 429/403 blocks from Yahoo's edge Envoy proxies. However, scheduled batch runs via GitHub Actions runners using Python's `yfinance` execute with near 100% reliability.

3. **Alternative Providers Evaluated**:
   - **Stooq** (`stooq.com`): Enforces Cloudflare-style JavaScript browser verification challenges (`This site requires JavaScript to verify your browser`), breaking headless and automated requests.
   - **Finnhub / Alpha Vantage / TwelveData**: Either require paid keys for historical ETF candles or enforce strict daily rate limits (e.g. Alpha Vantage 25 calls/day) that violate long-term reliability and zero-key requirements.

### Core Recommendation: The Hybrid Snapshot Architecture

We recommend a **Dual-Layer Hybrid Architecture**:

```
+-------------------------------------------------------------------------------------------------+
|                                     HYBRID BENCHMARK ARCHITECTURE                               |
+-------------------------------------------------------------------------------------------------+
|                                                                                                 |
|   1. HISTORICAL TIMEFRAMES (1W, 1M, 3M, 1Y, ALL)                                                |
|   +-----------------------+     Daily 22:00 CET      +------------------+                       |
|   |   GitHub Actions      | -----------------------> | Neon PostgreSQL  |                       |
|   |   Price Fetcher       |   yfinance batch fetch   | benchmark_daily_ |                       |
|   |  (price_fetcher.yml)  |   VWCE.DE & SXR8.DE      | history table    |                       |
|   +-----------------------+                          +------------------+                       |
|                                                               |                                 |
|                                                               | Parallel HTTP SQL (<50ms)       |
|                                                               v                                 |
|   2. REAL-TIME 24H INTRADAY                          +------------------+                       |
|   +-----------------------+    Direct Client Fetch   | React SPA Client |                       |
|   |  TradeGate Exchange   | -----------------------> | (Cloudflare      |                       |
|   |  refresh.php (CORS *) |      Sub-150ms CORS      |  Pages)          |                       |
|   +-----------------------+                          +------------------+                       |
|                                                                                                 |
+-------------------------------------------------------------------------------------------------+
```

- **Historical Daily Curves (`1W`, `1M`, `3M`, `1Y`, `ALL`)**: Pre-fetched during the existing scheduled GitHub Actions job (`python -m backend.cli snapshot`) using `backend/providers/yahoo.py` (`yfinance`), persisted to a dedicated `benchmark_daily_history` table in Neon Serverless PostgreSQL. Fetched in the frontend in parallel with `portfolio_daily_history` via `@neondatabase/serverless` (0ms third-party API latency, 0 CORS issues, 100% resilient).
- **Intraday (`24H`)**: Live quotes fetched directly in the browser from TradeGate BSX (`https://www.tradegatebsx.com/refresh.php?isin=...`) using the existing CORS-enabled pattern in `src/services/livePrices.ts`.

---

## Detailed Evaluation of Benchmark Assets

### 1. VWCE (Global All-World Benchmark)
- **ISIN:** `IE00BK5BQT80`
- **Product Name:** Vanguard FTSE All-World UCITS ETF USD Accumulating
- **Yahoo Finance Ticker:** `VWCE.DE` (Deutsche Börse Xetra, EUR)
- **TradeGate ISIN:** `IE00BK5BQT80`
- **Characteristics:**
  - Denominated in EUR.
  - Automatically reinvests dividends into fund NAV (Accumulating).
  - Matches DEGIRO's primary global index holding exactly (1:1 apples-to-apples performance comparison).

### 2. S&P 500 (US Large-Cap Benchmark)
When comparing a EUR DEGIRO portfolio against the S&P 500, three candidate tickers exist:

| Candidate | Identifier | Currency | Type | Pros | Cons / Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`VUAA.DE`** | ISIN `IE00BFMXXD54` | EUR | UCITS ETF (Acc) | True investor return (dividends reinvested + EUR currency effect). Traded on TradeGate. | Shorter listing history on XETRA (starts late 2024 on some feeds). |
| **`SXR8.DE` / `CSPX`** | ISIN `IE00B5BMR087` | EUR | UCITS ETF (Acc) | Europe's largest S&P 500 ETF (>€80B AUM). Over 15 years of daily history on XETRA (`SXR8.DE`). Traded on TradeGate. | High share price (€740+), but percentage return is identical to index total return in EUR. **(Recommended primary S&P 500 proxy)** |
| **`^GSPC`** | S&P 500 Index | USD | Price Index | Universally recognized benchmark index. | **Distorted comparison:** Excludes dividend yields (~1.5%/yr drag) and ignores EUR/USD exchange rate fluctuations. A European investor cannot buy raw index points. |

> [!IMPORTANT]
> **Financial Correctness Decision:**  
> For the benchmark comparison overlay, we should use **`VWCE.DE`** for FTSE All-World and **`SXR8.DE`** (or `VUAA.DE`) for S&P 500. This guarantees an **apples-to-apples, EUR-denominated, total-return comparison** against the user's actual DEGIRO portfolio equity.

---

## Provider Feasibility & Technical Tests

### 1. TradeGate Exchange Public JSON Endpoint

We verified the live endpoints:
- `https://www.tradegatebsx.com/refresh.php?isin=IE00BK5BQT80` (VWCE)
- `https://www.tradegatebsx.com/refresh.php?isin=IE00B5BMR087` (SXR8 / S&P 500)
- `https://www.tradegatebsx.com/refresh.php?isin=IE00BFMXXD54` (VUAA / S&P 500)

**Sample Response (`IE00BK5BQT80`):**
```json
{
  "bid": 170.66,
  "ask": 170.68,
  "bidsize": 2000,
  "asksize": 2000,
  "delta": 0.21,
  "stueck": 49559,
  "umsatz": 8465809,
  "avg": 170.8228,
  "executions": 4413,
  "last": 170.66,
  "high": 171.02,
  "low": 170.56,
  "close": 170.30
}
```

**CORS Verification:**
Both `tradegatebsx.com` and `tradegate.de` return:
```http
Access-Control-Allow-Origin: *
```
This allows direct in-browser `fetch()` without serverless proxies or CORS relays.

**Intraday 24H Return Calculation:**
$$\text{Return}_{24H} = \frac{\text{last} - \text{close}}{\text{close}} \times 100\% = \frac{170.66 - 170.30}{170.30} \times 100\% = +0.211\%$$

**Historical Timeseries Capability:**
We inspected the TradeGate website order book and DOM (`orderbuch.php?isin=IE00BK5BQT80`). TradeGate generates server-side static PNG graphics:
- `/images/charts/intraday/IE00BK5BQT80.png`
- `/images/charts/woche/IE00BK5BQT80.png`
- `/images/charts/monat/IE00BK5BQT80.png`
- `/images/charts/jahr/IE00BK5BQT80.png`

There is **no JSON API for historical daily ticks or closing prices** on TradeGate.

---

### 2. Yahoo Finance v8 Chart API

We tested the v8 chart endpoint across all required timeframes:
`https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range}&interval={interval}`

**Verified Parameter Matrix:**

| Timeframe | Yahoo `range` | Yahoo `interval` | Data Points Returned | Sample Latency |
| :--- | :--- | :--- | :--- | :--- |
| **24H** | `1d` | `5m` | ~37 – 79 points | 180 ms |
| **1W** | `5d` | `15m` | ~150 points | 210 ms |
| **1M** | `1mo` | `1d` | ~23 trading days | 140 ms |
| **3M** | `3mo` | `1d` | ~67 trading days | 150 ms |
| **1Y** | `1y` | `1d` | ~254 trading days | 160 ms |
| **ALL** | `max` | `1d` (or `1wk`) | ~711+ points (since 2024) | 220 ms |

**CORS Header Inspection:**
```http
HTTP/1.1 200 OK
content-type: application/json;charset=utf-8
cache-control: public, max-age=10, stale-while-revalidate=20
server: ATS
x-envoy-upstream-service-time: 3
Strict-Transport-Security: max-age=31536000
```
> [!WARNING]
> Notice the complete absence of `Access-Control-Allow-Origin`. A browser running on `https://<project>.pages.dev` calling `query1.finance.yahoo.com` directly will fail with a fatal CORS exception.

---

## Architectural Comparison: Client-Side vs Edge Proxy vs Backend Snapshot

We evaluated three structural architectures to deliver the benchmark feed:

| Evaluation Criteria | Option 1: Direct Client-Side Fetch | Option 2: Cloudflare Edge Proxy (Worker / Pages Functions) | Option 3: Backend Snapshot in Neon DB (Recommended) |
| :--- | :--- | :--- | :--- |
| **Initial Chart Load Latency** | High / Fails on CORS (blocked) | Moderate (150–350ms per ticker proxy hop) | **Instant (< 50ms)** — bundled in the same Neon SQL response as portfolio history |
| **CORS Compliance** | Fails for historical Yahoo; works only for TradeGate 24H | Resolved via custom response headers in Worker | **100% Native** — `@neondatabase/serverless` uses standard HTTPS POST |
| **Rate Limit / IP Block Risk** | High risk of browser fingerprinting | **Severe risk** — Yahoo regularly returns HTTP 429/403 to Cloudflare datacenter IP ranges | **Zero risk** — Single daily batch executed by GitHub Actions runner |
| **Hosting Cost & Limits** | Free | Free tier (100k req/day), but adds edge compute complexity | **100% Free Forever** — Fits within Neon 0.5 GB free storage (< 300 KB needed) |
| **Offline / Local CSV Mode** | Breaks without internet / proxy | Requires Cloudflare dev runtime (`wrangler pages dev`) | Supported natively with bundled fallback fixtures |
| **Maintenance Burden** | Unusable | High — fragile proxy needing cookie/crumb rotation if Yahoo updates auth | **Very Low** — Uses existing, proven `yfinance` in `backend/` |

---

## Recommended Implementation Blueprint

### 1. Database Schema (`setup_db.sql`)

Add a dedicated table for historical daily benchmark closing prices:

```sql
CREATE TABLE IF NOT EXISTS benchmark_daily_history (
    benchmark_id    TEXT NOT NULL,          -- e.g. 'VWCE', 'SP500'
    ticker          TEXT NOT NULL,          -- e.g. 'VWCE.DE', 'SXR8.DE'
    date            DATE NOT NULL,          -- YYYY-MM-DD
    close_price_eur DOUBLE PRECISION NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (benchmark_id, date)
);

CREATE INDEX IF NOT EXISTS idx_benchmark_history_date 
    ON benchmark_daily_history (benchmark_id, date ASC);
```

### 2. Backend Snapshot Extension (`backend/cli.py` & `backend/db/snapshots.py`)

In `backend/cli.py`, inside `cmd_snapshot()`:

```python
BENCHMARK_CONFIG = {
    "VWCE": "VWCE.DE",
    "SP500": "SXR8.DE",  # or VUAA.DE
}

# Fetch historical benchmark prices alongside portfolio holdings
benchmark_tickers = list(BENCHMARK_CONFIG.values())
benchmark_hist = price_service.get_historical_prices_batch(
    benchmark_tickers, start_date="2024-01-01"
)

# Persist to Neon benchmark_daily_history
snap_repo.save_benchmark_history(benchmark_hist, BENCHMARK_CONFIG)
```

### 3. Frontend Data Flow (`src/services/portfolioData.ts`)

In `fetchDashboardData()`, query `benchmark_daily_history` in parallel with `portfolio_daily_history`:

```typescript
const [historyRows, holdingsRows, benchmarkRows] = await Promise.all([
  sql`SELECT date::text as date, total_equity_eur, invested_capital_eur FROM portfolio_daily_history ORDER BY date ASC`,
  sql`SELECT * FROM current_asset_holdings ORDER BY total_value_eur DESC`,
  sql`SELECT benchmark_id, date::text as date, close_price_eur FROM benchmark_daily_history ORDER BY date ASC`
]);
```

### 4. Chart Normalization & Mathematical Alignment

For any selected timeframe $[t_0, t_n]$:

1. **Portfolio Percentage Return Series**:
   $$R_{\text{portfolio}}(t) = \frac{\text{Equity}(t) - \text{Equity}(t_0)}{\text{Equity}(t_0)} \times 100\%$$

2. **Benchmark Percentage Return Series**:
   $$R_{\text{benchmark}}(t) = \frac{\text{Price}(t) - \text{Price}(t_0)}{\text{Price}(t_0)} \times 100\%$$

3. **Holiday & Weekend Forward-Fill**:
   If the portfolio records a valuation on a market holiday or weekend where the exchange was closed, forward-fill the benchmark price from the previous active trading day:
   $$\text{Price}(t) = \text{Price}(t-1) \quad \text{if } \text{Price}(t) \text{ is missing}$$

4. **24H Intraday Comparison**:
   The frontend queries TradeGate BSX (`fetchTradeGatePrice`):
   $$R_{\text{VWCE, 24H}} = \frac{\text{last} - \text{close}}{\text{close}} \times 100\%$$
   The chart displays this as an immediate at-a-glance delta pill or overlay baseline.

---

## Actionable Takeaways for Ticket #28

Ticket [#28](https://github.com/Jazenn/DEGIRO/issues/28) ("Design Timeframe-Aware Dynamic Y-Axis Scaling & Performance Return Modes") is currently blocked by #27. With this research completed:

1. **Overlay Mode Selection**:
   - In **Portfolio Value (€)** mode, plotting benchmark lines on the same Y-axis is disorienting because raw prices (€170 vs €45,000) are incompatible.
   - When a benchmark overlay is activated, the chart should automatically switch (or offer a one-click toggle) to **Relative Return (%)** mode, anchoring both curves at $0.00\%$ at $t_0$.
2. **Y-Axis Dynamic Bounds in Relative Return (%) Mode**:
   - Min Bound: $\min(\min(R_{\text{portfolio}}), \min(R_{\text{benchmark}})) - \text{padding}$
   - Max Bound: $\max(\max(R_{\text{portfolio}}), \max(R_{\text{benchmark}})) + \text{padding}$
   - For `24H` and `1W`, clamp padding to at least $\pm 0.5\%$ to prevent flatlining during low-volatility sessions without exaggerating micro-noise.
3. **Primary Benchmarks to Expose in UI**:
   - Toggle button 1: **VWCE** (Global FTSE All-World)
   - Toggle button 2: **S&P 500** (via EUR UCITS ETF `SXR8` / `VUAA`)

---

## References

- TradeGate Exchange Refresh API: [backend/providers/tradegate.py](file:///C:/Users/griff/Projects/DEGIRO/backend/providers/tradegate.py)
- Yahoo Finance Provider: [backend/providers/yahoo.py](file:///C:/Users/griff/Projects/DEGIRO/backend/providers/yahoo.py)
- Snapshot Repository: [backend/db/snapshots.py](file:///C:/Users/griff/Projects/DEGIRO/backend/db/snapshots.py)
- Scheduled GitHub Action: [.github/workflows/price_fetcher.yml](file:///C:/Users/griff/Projects/DEGIRO/.github/workflows/price_fetcher.yml)
- Database Setup: [setup_db.sql](file:///C:/Users/griff/Projects/DEGIRO/setup_db.sql)
- Frontend Chart Component: [src/components/PortfolioChart.tsx](file:///C:/Users/griff/Projects/DEGIRO/src/components/PortfolioChart.tsx)
- Frontend Live Price Service: [src/services/livePrices.ts](file:///C:/Users/griff/Projects/DEGIRO/src/services/livePrices.ts)
