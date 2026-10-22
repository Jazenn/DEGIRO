> Historical specification: conflicting requirements are superseded by the [approved useful-dashboard implementation handoff](useful-dashboard-implementation-handoff.md) and its linked decisions. In particular, earlier latency promises, direct browser credential access, UI choices and assumed free-data coverage are not current requirements or verified facts.

# Technical Specification: Backend Architecture Overhaul & Clean Codebase Structure

## Problem Statement

The investor's personal portfolio tracking system for DEGIRO account data has suffered from recurring calculation discrepancies and technical debt:

1. **Portfolio & Cash Calculation Discrepancies**: The dashboard reported incorrect numbers that deviated significantly from the official DEGIRO mobile app and web platform:
   - Total portfolio value fluctuated wildly (reporting over €48,000 or falling to €723, when the actual portfolio value was ~€4,110).
   - Free cash reported €0.00 instead of the actual cash fund balance of €5.96.
   - Crypto asset values were inflated or multiplied (reporting over €1,249 in Bitcoin and €198 in Ethereum instead of the real holdings of €787 and €133).
2. **Cluttered, Unorganized Repository Root**: The codebase contained loose, tangled Python scripts at the repository root (`data_processing.py`, `db_utils.py`, `managers.py`, `portfolio_calculation.py`, `snapshot_worker.py`, `transaction_ingestion.py`). These scripts mixed HTTP fetching, data parsing, financial algorithms, and database operations without clear boundaries, making it difficult for automated agents and developers to locate modules and maintain structure.
3. **Flatex Cash Sweep Accounting Error**: DEGIRO uninvested cash is held at flatexDEGIRO Bank, creating twin ledger entries (`Degiro Cash Sweep Transfer` and `Overboeking naar/van uw geldrekening`). Legacy logic misclassified these sweeps as external deposits and withdrawals, severely distorting net invested capital.
4. **Chronological Tie-Breaking & Missing ISIN Bugs**: The CSV export is reverse-chronological; replaying events without a row-index tie-breaker evaluated trades and fees out of order. Additionally, crypto trades lacked ISINs and were dropped by filters expecting traditional 12-character identifiers.

The user requires a clean, organized, structurally sound codebase with a modular backend that mathematically matches DEGIRO account values with €0.00 deviation, loads in < 50ms, and updates live market quotes instantly upon opening the site.

---

## Solution

A decoupled, modular backend package and clean codebase layout:

1. **Forensic `Account.csv` Ingestion Engine**:
   - Classifies 100% of rows into deterministic taxonomies (sweeps, deposits, trades, fees, corporate actions, interest, promotions).
   - Treats Flatex cash sweeps as net-zero internal transfers ($\Delta\text{Cash} = 0$).
   - Models the 3-row iDEAL deposit lifecycle ($T_0$ reservation credit, $T_{\text{settle}}$ reservation release, $T_{\text{settle}}$ bank settlement).
   - Extracts fractional crypto quantities and prices directly from descriptions without requiring ISINs.
   - Replays transactions forward in time using `(date ASC, time ASC, csv_row_id DESC)` tie-breaking, ensuring €0.00 deviation across all 172 production rows and arriving at the exact €5.96 closing balance.
2. **Modular `backend/` Package Hierarchy (ADR-0002)**:
   - `backend/ingestion/`: Canonical CSV parsing and deterministic 32-character MD5 hashing.
   - `backend/engine/`: FIFO lot tracking, asset holdings, cash ledger balance, cumulative equity history, and proportional rebalancing.
   - `backend/providers/`: Direct TradeGate quote scraper (European ETFs/stocks) and CoinGecko/Binance public endpoints (crypto), with Yahoo Finance fallback.
   - `backend/db/`: Pure environment-variable-based Neon PostgreSQL connection pooling, idempotent transaction storage (`ON CONFLICT (row_hash) DO NOTHING`), and pre-aggregated snapshot persistence.
   - `backend/cli.py`: Standalone CLI for local auditing, database ingestion, and snapshot refreshes (`python -m backend.cli audit <file>`, `python -m backend.cli ingest <file>`, `python -m backend.cli snapshot`).
3. **Hybrid Instant Live Sync (< 500ms)**:
   - Dashboard renders instantly (< 50ms) from pre-computed Neon PostgreSQL snapshot tables (`portfolio_daily_history`, `current_asset_holdings`).
   - Browser immediately fetches up-to-the-minute TradeGate and Binance/CoinGecko quotes in parallel (~300ms), dynamically updating live totals and daily P/L without sluggish serverless compute delays.
4. **Market Close Background Cron**:
   - GitHub Actions workflow runs once daily at **22:00 CET on weekdays** (market close) for historical daily closing snapshot archiving, plus on-demand execution on CSV upload or manual refresh click.
5. **Clean Repository Root**:
   - Deprecates and removes loose root Python scripts (`data_processing.py`, `db_utils.py`, `managers.py`, etc.), standardizing the directory tree to `backend/`, `src/`, `tests/`, and `docs/`.

---

## User Stories

### Transaction Ingestion & Cash Accounting
1. As an investor, I want my `Account.csv` export to be ingested without manual data cleanup, so that I can update my portfolio history in one click.
2. As an investor, I want internal Flatex cash sweeps to be excluded from external cash flow calculations, so that my net invested capital is not artificially inflated by thousands of euros.
3. As an investor, I want iDEAL deposit reservation and settlement rows to be correctly consolidated, so that each deposit is counted exactly once.
4. As an investor, I want crypto purchases (Bitcoin, Ethereum) without ISINs to be parsed accurately from transaction descriptions, so that my crypto holdings and cash debits match my broker records.
5. As an investor, I want transactions occurring in the same minute to be sorted chronologically using the export row index, so that fees are never deducted before their corresponding trades execute.
6. As an investor, I want duplicate CSV imports to be skipped idempotently, so that uploading overlapping monthly statements never creates duplicate positions.
7. As an investor, I want to see an exact match between my calculated cash balance and DEGIRO's €5.96 cash balance, so that I have 100% confidence in the numbers.

### Portfolio Valuation & FIFO Accounting
8. As an investor, I want my holdings to be calculated using First-In, First-Out (FIFO) cost-basis accounting, so that realized and unrealized gains reflect tax and accounting standards.
9. As an investor, I want liquidated positions (such as past stock sales) to be excluded from current active holdings while preserving their historical profit contributions.
10. As an investor, I want my total portfolio value to accurately sum all held shares and crypto at current market prices, so that my net worth is never distorted.
11. As an investor, I want my cumulative invested capital to reflect only net external cash deposits minus withdrawals over time, so that my equity performance curve shows true capital appreciation.

### Market Quotes & Live Dashboard Sync
12. As an investor, I want the dashboard to load from pre-aggregated database snapshots in under 50ms, so that I never experience loading spinners or cold starts.
13. As an investor, I want live market prices for European ETFs to fetch directly from TradeGate in parallel when I open the dashboard, so that I see real-time market valuations during European trading hours.
14. As an investor, I want live Bitcoin and Ethereum prices to fetch from public crypto APIs within 300ms, so that my crypto positions reflect immediate market conditions.
15. As an investor, I want an on-demand "Refresh Prices" button in the header, so that I can manually poll the latest market quotes while viewing the dashboard.
16. As an investor, I want the background price fetcher to archive official closing prices at 22:00 CET on weekdays, so that my historical performance chart has complete daily closing records even when I do not visit the site.

### Asset Allocation & Rebalancing Cockpit
17. As an investor, I want to see my actual asset allocation percentages alongside my rebalancing targets on an interactive donut chart, so that I can identify allocation drift.
18. As an investor, I want an interactive rebalancing cockpit where I can enter a planned monthly deposit, so that I receive exact purchase amounts in EUR and estimated share quantities for underweight assets.
19. As an investor, I want the rebalancing calculator to strictly enforce non-negative buys and zero sells, so that my strategy accumulates underweight positions through cash deposits without triggering taxable sales.

### Codebase Organization & Developer Ergonomics
20. As a developer or AI assistant, I want all backend code organized into cohesive domain packages under `backend/`, so that I can easily find ingestion, calculation, price provider, and database modules.
21. As a developer, I want a standalone command-line interface (`python -m backend.cli audit <file>`), so that I can audit local CSV exports and verify financial math offline without needing a database connection.
22. As a developer, I want obsolete root-level legacy files removed, so that the repository root remains clean, professional, and easy to maintain.
23. As a developer, I want comprehensive automated unit tests covering domain calculations with zero runtime warnings, so that future modifications cannot introduce regressions.

---

## Implementation Decisions

### Modular Package Hierarchy (`backend/`)
The backend is structured into four distinct domain layers with isolated responsibilities:
- **`backend.ingestion`**: Handles file intake, encoding normalization, dialect sniffing, multi-column shift correction, and deterministic 32-character hexadecimal MD5 row hashing.
- **`backend.engine`**: Pure financial domain logic independent of databases or network I/O. Contains FIFO lot accumulation, cash balance replay, cumulative equity series generation, and deposit rebalancing math.
- **`backend.providers`**: Market data integrations querying primary execution venues (TradeGate exchange quotes for European ETFs/stocks, CoinGecko and Binance for crypto) with Yahoo Finance fallback.
- **`backend.db`**: Neon Serverless PostgreSQL persistence using pure environment variables (`DATABASE_URL`), connection pooling, idempotent upserts (`ON CONFLICT (row_hash) DO NOTHING`), and pre-aggregated read snapshot management.
- **`backend.cli`**: Command-line entrypoint exposing `audit`, `ingest`, and `snapshot` subcommands for manual operations and CI automation.

### Ingestion Grammar Rules
- **Column Shift Detection**: When `Mutatie` / `Change` contains a 3-letter currency code or alphabetical string, the numeric mutation is extracted from the subsequent column.
- **Cash Sweep Exclusion**: Rows matching `Degiro Cash Sweep Transfer`, `Overboeking van/naar uw geldrekening`, or `FLATEX EURO BANKACCOUNT` are flagged as internal cash sweeps and excluded from external cash flow totals.
- **Deposit Lifecycle Netting**: The 3-row iDEAL deposit lifecycle ($+X$ reservation, $-X$ release, $+X$ settled bank deposit) is preserved for chronological balance replay, while external deposit calculation counts net cash additions.
- **Chronological Tie-Breaking**: Forward chronological sorting orders by `(date ASC, time ASC, csv_row_id DESC)`, guaranteeing that trades execute before fees and gross dividends settle before withholding tax deductions.

### Read Model & Live Sync Contract
- **Pre-Aggregated Snapshots**:
  - `portfolio_daily_history`: Stores daily historical records (`date`, `total_equity_eur`, `invested_capital_eur`, `cash_balance_eur`, `unrealized_pnl_eur`, `unrealized_pnl_pct`).
  - `current_asset_holdings`: Stores active holding records (`symbol`, `name`, `isin`, `shares_held`, `current_price_eur`, `total_value_eur`, `total_cost_eur`, `unrealized_pnl_eur`, `actual_pct`, `target_pct`, `drift_pct`, `recommended_action_eur`).
  - `portfolio_asset_settings`: Stores strategy configuration (`symbol`, `display_name`, `target_pct`, `buy_dip_trigger`, `sell_profit_trigger`, `sell_profit_pct`, `is_crypto`, `buy_budget`).
- **Hybrid Performance Model**:
  - Initial load executes in < 50ms from pre-aggregated PostgreSQL tables.
  - Client-side parallel fetcher queries TradeGate and Binance/CoinGecko concurrently via browser HTTP, updating live metrics in ~300ms without server-side compute overhead.
- **Market Close Background Cron**:
  - GitHub Actions runs `python -m backend.cli snapshot` once per weekday at 22:00 CET, archiving official closing values into the historical equity curve table.

### Codebase Cleanliness & Root Deprecation
- Loose root Python scripts (`data_processing.py`, `db_utils.py`, `managers.py`, `portfolio_calculation.py`, `snapshot_worker.py`, `transaction_ingestion.py`) are systematically migrated and deleted once all test imports point directly to `backend.*`.

---

## Testing Decisions

### What Makes a Good Test
Tests must assert observable domain behavior, mathematical invariants, and schema contracts, avoiding internal private implementation details:
- **Exact Accounting Continuity**: Replaying the 172 rows of `Account.csv` must yield an exact closing cash balance of **€5.96** and net invested capital of **€3,728.00** with €0.00 deviation.
- **FIFO Cost-Basis Invariant**: Selling shares must deplete oldest lots first; total cost of remaining shares must equal the sum of remaining unliquidated lots.
- **Rebalancing Invariant**: Deposit allocation must never recommend negative purchases (buys $\ge 0$) and must never recommend selling assets.
- **Idempotency Invariant**: Ingesting the same CSV multiple times must result in 0 new rows inserted and 0 duplicate rows stored.
- **Read Latency**: Snapshot queries against Neon must complete in sub-50ms.

### Modules Under Test
1. **`backend.ingestion`**:
   - Number format parsing (Dutch comma-decimal vs. English dot-decimal).
   - 32-character MD5 hash determinism and stability.
   - Trade description parsing for buys, sells, and fractional crypto.
   - Internal cash sweep detection.
   - Full 172-row `Account.csv` audit verification.
2. **`backend.engine`**:
   - Chronological sorting with timestamp tie-breakers.
   - FIFO lot accounting across multi-buy and partial-sell sequences.
   - Cumulative invested capital and daily cash series generation.
   - Proportional shortfall deposit rebalancing plan calculation.
3. **`backend.providers`**:
   - TradeGate quote parsing and network timeout resilience.
   - CoinGecko and Binance crypto quote fetching with fallback.
   - Yahoo Finance batch quote and historical time series downloads.
4. **`backend.db`**:
   - Neon PostgreSQL connection lifecycle and transaction rollback.
   - Idempotent transaction saving with hash conflict resolution.
   - Snapshot table persistence and retrieval.

### Prior Art
Tests build upon the existing test suites in `tests/test_portfolio_calculation.py` and `tests/test_spec_ticket_modules.py`, expanding coverage with dedicated suites in `tests/test_backend_ingestion.py` and `tests/test_backend_engine.py` using `pytest`.

---

## Out of Scope

1. **Paid Financial API Subscriptions**: Real-time websocket feeds requiring paid subscriptions (e.g. Bloomberg, Refinitiv) are out of scope. Public TradeGate, Binance, CoinGecko, and Yahoo Finance endpoints provide accurate, free data.
2. **Intraday High-Frequency Scraping**: Continuous 5-minute background polling when no user is viewing the dashboard is out of scope. Live quotes are fetched on-demand by the browser.
3. **Legacy Streamlit UI**: Re-implementing or maintaining the deprecated Streamlit dashboard is out of scope. The React + Vite SPA is the permanent frontend.
4. **Direct Broker API Scraping**: Automated browser scraping of DEGIRO user credentials is out of scope. Manual CSV export ingestion is secure, stable, and free from account suspension risk.

---

## Further Notes

- **Architecture Decisions**:
  - [ADR-0001: Pre-Aggregated Read Snapshots](file:///C:/Users/griff/Projects/DEGIRO/docs/adr/0001-pre-aggregated-read-snapshots.md)
  - [ADR-0002: Modular Backend Package Hierarchy](file:///C:/Users/griff/Projects/DEGIRO/docs/adr/0002-backend-modular-package-hierarchy.md)
- **Research Findings**:
  - [`docs/research/account-csv-grammar.md`](file:///C:/Users/griff/Projects/DEGIRO/docs/research/account-csv-grammar.md) on branch `research/account-csv-grammar`.
- **Domain Vocabulary**:
  - Follows [`GLOSSARY.md`](file:///C:/Users/griff/Projects/DEGIRO/GLOSSARY.md) (*Transaction*, *Asset*, *Portfolio History*, *Snapshot*, *Rebalancing Target*, *Crypto Scale*).
