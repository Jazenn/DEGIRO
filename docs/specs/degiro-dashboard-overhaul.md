> Historical specification: conflicting requirements are superseded by the [approved useful-dashboard implementation handoff](useful-dashboard-implementation-handoff.md) and its linked decisions. In particular, earlier latency promises, direct browser credential access, UI choices and assumed free-data coverage are not current requirements or verified facts.

# Technical Specification: Modernized DEGIRO Dashboard Overhaul

## Problem Statement

The user's personal investment tracking system for DEGIRO portfolio data has fallen into disrepair. The legacy codebase—developed by early automated coding assistants—suffers from significant architectural fragility, sluggish performance, and visual decay:

1. **Unreliable Uptime & Cold Sleeps:** Hosted on Streamlit Community Cloud, the app frequently enters hibernation, requiring a fragile GitHub Actions workflow running headless Playwright browsers to artificially ping and wake it up.
2. **Slow, Monolithic Computation:** The application recalculates rolling portfolio histories, FIFO cost-basis, and allocation math on every page visit, creating sluggish load times and interface latency.
3. **Outdated, Desktop-Biased Interface:** Built with procedural Streamlit script reruns and ad-hoc HTML/CSS injections, the UI looks like an internal data science prototype rather than a modern consumer application. It is difficult to navigate and use on mobile devices.
4. **Brittle Ingestion:** Synchronizing transactions depends on Google Cloud Service Accounts and Google Drive folder syncing, creating credential maintenance hurdles and failure modes.

The user requires a modern, fast, minimalist dashboard that is 100% free forever, accessible 24/7 across any network, tailored to phones and laptops, and built to help them maintain their desired asset allocation without tedious manual math.

---

## Solution

A ground-up modern overhaul decoupling presentation from computation:

1. **Zero-Sleep Serverless SPA:** A modern web application deployed on Cloudflare Pages Anycast Edge CDN. It boots in 0ms, never enters hibernation, consumes unmetered free bandwidth, and requires zero artificial keep-alive bots.
2. **Sub-50ms Pre-Aggregated Read Architecture (ADR-0001):** Decoupled data engine backed by Neon Serverless PostgreSQL. A background worker computes daily equity curves, cash balances, and asset drift into pre-calculated snapshot tables so the user interface loads instantly without calculating math in the browser.
3. **Minimalist Modern FinTech Aesthetic:** A clean, card-based responsive design (inspired by Apple Card / Revolut) prioritizing quick at-a-glance comprehension.
4. **Interactive Monthly Rebalancing Cockpit:** An intuitive deposit calculator where the user enters a planned investment (e.g., €500 or €800) and immediately receives exact purchase quantities to keep target allocations (e.g., 60% All-World, 10% Bitcoin) balanced without selling.
5. **Visual Crypto Scale Ladder:** An explicit tier-based indicator displaying current crypto prices relative to dip accumulation zones and structured profit-taking targets.
6. **Direct Web CSV Ingestion:** A drag-and-drop / native file upload interface accepting full historical DEGIRO exports, featuring automatic Dutch/English column detection and idempotent MD5 row deduplication.
7. **Quota-Safe Background Price Fetcher:** Scheduled hourly during active European market hours (Mon–Fri 08:00–22:00 CET) plus on-demand triggers, staying well within GitHub Actions' 2,000 free monthly minutes.

---

## User Stories

### Portfolio Overview & Performance
1. As an investor, I want to see my total portfolio valuation, net invested capital, and total unrealized profit/loss within 500ms of opening the app, so that I can immediately understand my net worth.
2. As an investor, I want to view my available cash balance (Flatex/DEGIRO cash fund) at a glance, so that I know how much dry powder is ready to deploy.
3. As an investor, I want to view an interactive portfolio growth curve showing valuation over time compared to my invested capital, so that I can see the compounding effect of my contributions.
4. As an investor, I want to toggle the performance chart across timeframes (1M, 3M, 1Y, ALL), so that I can evaluate both short-term market fluctuations and long-term trajectory.
5. As an investor, I want the dashboard to load instantly with zero cold-start delay, so that I am never greeted by a "Zzzz" sleeping container screen.

### Asset Allocation & Strategy Rebalancing
6. As an investor, I want to view an asset allocation donut chart showing the actual percentage breakdown of my portfolio, so that I can visualize my asset distribution at a glance.
7. As an investor, I want each asset to clearly display its target percentage versus actual percentage, so that I can spot portfolio drift.
8. As an investor, I want to see an allocation drift indicator (e.g. "+1.8% Overweight" or "-1.3% Underweight") for each holding, so that I know which positions require attention.
9. As an investor, I want an interactive monthly deposit slider/input where I can specify an amount to invest (e.g. €800), so that the system calculates the optimal purchase distribution for me.
10. As an investor, I want the rebalancing calculator to recommend purchases exclusively for underweight assets, so that I can balance my portfolio using new capital without triggering taxable sales or trading fees.
11. As an investor, I want the rebalancing recommendations to include estimated share quantities based on latest market prices, so that I can place orders directly on DEGIRO without manual division.
12. As an investor, I want to edit my target allocation percentages (e.g. 60% All-World, 10% Bitcoin) through the settings interface, so that I can update my long-term strategy as my goals change.

### Crypto Scaling Strategy
13. As a crypto investor, I want to see current crypto prices alongside my predefined dip accumulation target, so that I know when market drops present a scheduled buying opportunity.
14. As a crypto investor, I want to see my next profit-taking target price and the percentage of holdings to sell at that tier, so that I follow a disciplined exit plan rather than emotional trading.
15. As a crypto investor, I want to customize my crypto buy and sell price bands directly in the settings, so that my scaling strategy reflects current market cycles.

### Transaction Ingestion & Data Integrity
16. As an investor, I want to drag and drop or upload my DEGIRO CSV exports directly in the web browser, so that updating my portfolio is simple and fast.
17. As an investor, I want the system to accept both `Account.csv` and `Transactions.csv` export types, so that I can upload whichever report I pull from DEGIRO.
18. As an investor, I want the parser to automatically detect Dutch and English header formats, so that language setting changes on DEGIRO do not break my ingestion.
19. As an investor, I want duplicate transaction rows to be automatically identified and skipped using deterministic MD5 hashing, so that I can upload overlapping or multi-year historical files with zero risk of duplicated trades.
20. As an investor, I want the dashboard snapshots to automatically recalculate immediately after a CSV upload, so that my new transactions are visible right away.

### Cross-Device & Mobile Usability
21. As a mobile user, I want the dashboard layout to adapt cleanly to my phone's screen with touch-friendly controls, so that I can check my investments and enter deposits on the go.
22. As a mobile user, I want to upload DEGIRO CSV files directly from my phone's files/downloads folder, so that I don't need a desktop computer to update my portfolio.
23. As an investor, I want the web app to be accessible 24/7 over secure HTTPS from any network, so that I can access my data anywhere in the world.

### System Upkeep & Automation
24. As an investor, I want stock and ETF prices to refresh automatically every hour during European market hours, so that my portfolio valuations remain accurate throughout the trading day.
25. As an investor, I want an on-demand "Refresh Prices" button, so that I can force a live market update whenever I want.
26. As an investor, I want all hosting and compute infrastructure to remain 100% free with generous headroom, so that I never incur unexpected subscription costs.

---

## Implementation Decisions

### Architecture & Hosting
- **Serverless SPA on Cloudflare Pages:** Static assets compiled with Vite, React, and Tailwind CSS globally distributed across Cloudflare's Anycast Edge CDN. Delivers 0ms cold start, never sleeps, and operates on an unmetered free bandwidth tier.
- **Neon Serverless PostgreSQL:** Database engine utilizing `@neondatabase/serverless` over HTTP/WebSockets. Automatically scales compute to zero after 5 minutes of inactivity (conserving free hours) and transparently auto-wakes on incoming queries in ~300ms without user-facing sleep screens.
- **Decommissioning Keep-Alive Bot:** The GitHub Actions Playwright workflow (`keep_alive.yml`) is completely decommissioned.

### Data Model & Pre-Aggregated Snapshots (ADR-0001)
- **Decoupled Read Model:** Raw `transactions` are normalized on ingestion. The calculation worker pre-computes two read-optimized tables:
  1. `portfolio_daily_history`: `(date, total_equity_eur, invested_capital_eur, cash_balance_eur, unrealized_pnl_eur, unrealized_pnl_pct)`
  2. `current_asset_holdings`: `(symbol, name, isin, shares_held, current_price_eur, total_value_eur, actual_pct, target_pct, drift_pct, recommended_action_eur)`
- **Dynamic Configuration Table:** Strategy weights and crypto price triggers are stored in `portfolio_asset_settings` `(symbol, display_name, target_pct, buy_dip_trigger, sell_profit_trigger, is_crypto)`.

### Transaction Ingestion Seam
- **Module Interface:** `TransactionIngestionService` exposes a single entrypoint: `ingest_csv(file_content: bytes) -> IngestionResult`.
- **Language & Format Detection:** Normalizes bilingual headers (`Datum` $\to$ `date`, `Aantal` $\to$ `quantity`, `Koers` $\to$ `price`, `Waarde` $\to$ `value`, `Product` $\to$ `product`, `ISIN` $\to$ `isin`).
- **Deterministic Row Hashing:** Calculates MD5 hash across `(date, time, isin, order_id, amount, value)` for each row. The database enforces a `UNIQUE(row_hash)` constraint, making all inserts idempotent (`ON CONFLICT (row_hash) DO NOTHING`).

### Rebalance Calculation Algorithm
- **Proportional Inflow Allocation:** Given a planned deposit $D$ and current portfolio value $V$, the target value for each asset $i$ is $(V + D) \times \text{target\_pct}_i$.
- If current value $V_i < \text{target\_value}_i$, the shortfall is $\Delta_i = \text{target\_value}_i - V_i$.
- Deposit $D$ is distributed proportionally across all underweight assets ($\Delta_i > 0$). No assets are sold.

### Visual Design System
- **Minimalist FinTech Aesthetic:** Derived from prototype Variant B ([`prototypes/dashboard-ui-prototype.html`](file:///C:/Users/griff/Projects/DEGIRO/prototypes/dashboard-ui-prototype.html)): slate-950 dark background, subtle slate-800 borders, JetBrains Mono for financial figures, clean KPI cards, donut allocation visualization, and interactive deposit slider.

### Price Fetcher Optimization
- **Scheduled Cron:** GitHub Actions workflow running hourly Mon–Fri 08:00–22:00 CET (~300 minutes/month out of 2,000 free minutes).
- **On-Demand Dispatch:** Supports GitHub Actions `workflow_dispatch` / repository dispatch triggered directly by the web dashboard upon CSV upload or manual refresh click.

---

## Testing Decisions

### What Makes a Good Test
Tests must assert observable domain behavior and business invariants, never implementation internals or private functions. A test should verify:
- Ingestion of real CSV fixtures produces exact expected database transactions without data corruption.
- Re-importing identical files produces zero duplicate records.
- Rebalance calculation never recommends selling or outputs negative purchases.
- Read queries return correctly formatted data structures in under 50ms.

### Modules Under Test
1. **`TransactionIngestionService`:**
   - Test Dutch `Account.csv` sample import.
   - Test English `Transactions.csv` sample import.
   - Test duplicate ingestion idempotency.
   - Test invalid/corrupt CSV handling with descriptive errors.
2. **`PortfolioCalculationEngine`:**
   - Test FIFO cost-basis and realized/unrealized profit calculation against known hand-calculated transaction sequences.
   - Test cash balance calculation across dividends, deposits, and fees.
   - Test pre-aggregated daily snapshot generation.
3. **`RebalanceCalculator`:**
   - Test deposit distribution with multiple underweight assets.
   - Test deposit distribution when all assets are balanced.
   - Test zero-deposit edge case.

### Prior Art
The legacy codebase contained zero automated unit or integration tests (`tests/` did not exist). This spec introduces the first standardized test suite using `pytest` for backend domain logic and component/unit tests for frontend calculation utilities.

---

## Out of Scope

1. **Legacy Database Migration:** Preserving or migrating corrupted rows from the old database schema is out of scope. The user will export full historical CSVs from DEGIRO and perform a clean initial import.
2. **Automated Scraping / Reverse-Engineered Broker APIs:** Direct scraping of DEGIRO credentials with headless browsers is out of scope. Official CSV exports are reliable, safe, and free from account suspension risk.
3. **Playwright Keep-Alive Maintenance:** The `keep_alive.yml` workflow will be deleted, not maintained.
4. **Paid Financial Feeds:** Real-time millisecond market streaming feeds requiring paid subscriptions (e.g. Bloomberg, Refinitiv) are out of scope. Free public Yahoo Finance and crypto APIs meet all requirements.

---

## Further Notes

- **Context Paper Trail:**
  - Architecture decisions recorded on Map Issue: [#1 Wayfinder Map: Modernized DEGIRO Dashboard Overhaul](https://github.com/Jazenn/DEGIRO/issues/1).
  - Hosting evaluation: [`docs/research/free-24-7-frontend-hosting.md`](file:///C:/Users/griff/Projects/DEGIRO/docs/research/free-24-7-frontend-hosting.md) on branch `research/frontend-hosting-evaluation`.
  - Visual prototype: [`prototypes/dashboard-ui-prototype.html`](file:///C:/Users/griff/Projects/DEGIRO/prototypes/dashboard-ui-prototype.html) on branch `prototype/portfolio-ui-variants`.
  - Architectural Decision Record: [ADR-0001: Pre-Aggregated Read Snapshots](file:///C:/Users/griff/Projects/DEGIRO/docs/adr/0001-pre-aggregated-read-snapshots.md).
  - Domain glossary: [`GLOSSARY.md`](file:///C:/Users/griff/Projects/DEGIRO/GLOSSARY.md).
