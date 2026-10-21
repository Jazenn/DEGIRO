# Portfolio data foundation audit

Research for [Audit trustworthy valuations and the dashboard data foundation](https://github.com/Jazenn/DEGIRO/issues/32), 2026-10-21. Inspected revision: `23d0b8d`. No implementation changes.

## Decision

Retain the ledger, ingestion/domain seams, configurable allocation model and background snapshot/read-model architecture. A blanket rewrite is not justified. Correct price coverage, financial semantics, freshness and deployment boundaries before adding performance charts or evaluating Crypto Scale strategies.

## Verified correctness and provenance matrix

| Area | Evidence | Required improvement |
|---|---|---|
| Invented history | Browser `transactionAggregator.ts` interpolates execution/latest prices and adds deterministic sine waves in `getAssetPriceOnDate`. Local-import and raw-transaction fallbacks can expose it with `isDemo: false`. | Synthetic movements belong only in explicit demos. Use observed history, documented carry-forward or unavailable states. Never backtest this history. |
| Active missing prices | Actions runs `backend.cli snapshot`, which uses `engine/portfolio.py`. Its calendar-date lookup defaults to zero when a historical close is absent. | Weekend ETF closes/provider gaps must not zero holdings. Distinguish market closure, stale prices and failures. |
| Duplicate engines | TypeScript, Python `portfolio.py`, and Python `portfolio_engine.py` overlap. The latter has forward-fill/strict missing-price behavior but is not the CLI path. | Establish canonical runtime engine and versioned read model; shared reconciliation fixtures if local calculation remains. |
| Period return | `PortfolioChart` divides ending minus starting equity by starting equity. | Deposits count as return. Separate equity change, flows, investment profit and cash-flow-adjusted return. |
| Profit naming | Active Python history calls equity minus net contributions `unrealized_pnl`; alternative engine uses remaining-lot market value minus cost. Metrics consumes the field as total gain/loss. | Define realized, unrealized, income, costs and total result separately. They differ after sales and dividends. |
| Mixed timestamps | Snapshot branch updates holding prices/value, retains snapshot allocation/drift/actions, derives headline metrics from historical equity and sets `lastUpdated` to request time. | Provide quote-as-of, ledger-through, calculation time, source and freshness; align dependent metrics. |
| Fallback selection | Snapshot completeness partly compares holding row counts with local calculation; failures can fall back to local/demo data. | Use ledger/import generations and reconciliation state; make stale/demo/unavailable visible. Row count is not completeness. |
| Browser boundary | Browser accepts/stores DB URL, executes reads/writes, supports `VITE_DATABASE_URL`; refresh supports `VITE_GITHUB_TOKEN`. | Choose local-only or authenticated remote architecture. Actual deployed configuration was not inspected; do not bundle privileged credentials. |
| Refresh | Missing GitHub credentials can simulate refresh; dispatch success means accepted workflow, not completed data. Schedule is weekdays 21:00 UTC. | Expose actual job/data state and choose separate crypto monitoring cadence. Daily weekday snapshots are not continuous crypto signals. |

Sources at inspected revision: [aggregator](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/src/utils/transactionAggregator.ts), [data orchestration](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/src/services/portfolioData.ts), [chart](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/src/components/PortfolioChart.tsx), [metrics](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/src/utils/metrics.ts), [CLI](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/backend/cli.py), [active history engine](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/backend/engine/portfolio.py), [alternative engine](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/backend/engine/portfolio_engine.py), [refresh](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/src/services/priceRefresh.ts), [workflow](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/.github/workflows/price_fetcher.yml).

[Vite documentation](https://vite.dev/guide/env-and-mode) confirms `VITE_` variables are exposed in client source. This establishes an architectural risk, not evidence that a deployed secret leaked.

## Direct crypto identity

A private local CSV check inspected headers and unique crypto names/identifier presence only; no financial records are published. Bitcoin/Ethereum entries have empty ISIN fields. Therefore that export does not verify an XFC code, execution venue, or ETP wrapper. The user's direct-crypto confirmation is consistent with DEGIRO's offering.

DEGIRO distinguishes [direct crypto](https://www.degiro.nl/zelf-beleggen/crypto-kopen) from [crypto ETPs](https://www.degiro.nl/zelf-beleggen/crypto-etps). The [official crypto asset list](https://www.degiro.nl/data/pdf/Overzicht%20Crypto%20Activa.pdf) maps Bitcoin to `BTC` / `XFC000A2YY6Q` and Ethereum to `ETH` / `XFC000A2YY6X`. These are public reference identifiers, not identifiers verified in the private CSV. Demo data uses a different Ethereum XFC code and must not serve as asset master data.

Separate broker identity, asset kind, quote-provider symbol and currency. CoinGecko aggregate/Binance prices are reference valuations, not verified executable DEGIRO prices. Venue, spread, account fees and available order types remain unverified in this bounded audit.

## Free history feasibility

The [historical provider](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/backend/providers/yahoo.py) downloads daily Yahoo `Close` with `auto_adjust=False`. CLI history starts at a hard-coded date rather than ledger coverage. The [provider service](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/backend/providers/__init__.py) and [browser live service](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/src/services/livePrices.ts) use TradeGate and CoinGecko/Binance fallbacks. Coverage, CORS stability and reliability have not been measured.

A no-subscription personal dashboard is plausible; guaranteed free multi-decade coverage is not established. [yfinance's own documentation](https://ranaroussi.github.io/yfinance/) says it is unaffiliated with Yahoo, intended for research/education, and data usage remains subject to Yahoo terms/personal-use limits. Treat it as replaceable, not a contracted provider.

[CoinGecko Demo documentation](https://docs.coingecko.com/demo/reference/coins-id-market-chart-range) restricts history to the past 365 days. This alone cannot cover multiple full crypto cycles; daily points use 00:00 UTC. Persist permitted observations with source, currency, timestamp, adjustment basis, retrieval time and quality flags. Persistence cannot reconstruct missing past prices. Validate actual-asset coverage before selecting providers.

Raw/adjusted prices, dividends, splits and FX need compatible treatment. Do not combine adjusted total-return prices with separately counted distributions. Currency and corporate-action correctness were not certified here.

## Retained foundations and remaining decisions

[ADR 0001](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/docs/adr/0001-pre-aggregated-read-snapshots.md) supports snapshot/read separation; its latency claims were not measured. [ADR 0002](https://github.com/Jazenn/DEGIRO/blob/23d0b8d/docs/adr/0002-backend-modular-package-hierarchy.md) provides useful ingestion, engine, provider and persistence seams. Preserve normalized imports, deterministic deduplication, chronological ordering, external-flow/internal-sweep distinction and FIFO foundations, subject to reconciliation rather than assuming all edge cases work.

Decide canonical ledger/engine, local-only versus authenticated remote deployment, metric definitions, daily/live snapshot contracts, missing-data rules, asset mapping and crypto evaluation cadence. Later verification should reconcile repeated imports, same-time records, fees, partial sales, withdrawals, dividends, fractional crypto, missing quotes and market holidays.

## Verification limits

Source tracing, primary-document checks and a private non-financial schema/identity check completed. No production DB, deployed credentials or live portfolio reconciliation was accessed. No workflow dispatched, code changed, application tests/build run, or latency measured. Findings establish reachable source behavior; frequency and impact in the deployed portfolio remain unknown.
