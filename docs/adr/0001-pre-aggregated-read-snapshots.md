# Pre-Aggregated Read Snapshots for Sub-100ms Dashboard Loads

## Context & Decision

Calculating portfolio valuation, historical equity curves, and asset allocation drift requires running FIFO cost-basis math across thousands of historical DEGIRO transactions. Running these calculations dynamically on page request introduces perceptible UI latency and cold-start overhead.

We decided to decouple transaction ingestion and financial calculations from the frontend read model. A background worker recalculates and writes pre-aggregated daily equity curves and asset status records into snapshot tables (`portfolio_daily_history` and `current_asset_holdings`). The frontend dashboard acts strictly as a high-performance read layer querying these pre-computed tables directly, ensuring sub-50ms query responses.

## Considered Options

- **On-the-fly calculation in the frontend/edge**: Rejected because executing full transaction parsing and FIFO cost-basis in serverless edge functions introduces cold starts, compute time limits, and CPU throttling.
- **Materialized views in PostgreSQL**: Evaluated, but dedicated snapshot tables allow granular background worker writes, historical freezing, and zero-lock fast reads on Neon serverless compute.
