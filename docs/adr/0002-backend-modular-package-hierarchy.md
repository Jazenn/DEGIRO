# 0002: Modular Backend Package Hierarchy & Migration Seams

## Context & Decision

The legacy backend codebase consisted of loose Python scripts at the repository root (`data_processing.py`, `db_utils.py`, `managers.py`, `portfolio_calculation.py`, `rebalance_calculator.py`, `snapshot_worker.py`, `transaction_ingestion.py`). These scripts mixed HTTP fetching, data parsing, financial algorithms, and database operations without clear boundaries.

We decided to reorganize the entire headless Python backend into a cohesive package under `backend/` with four distinct domain seams:

1. **`backend/ingestion/`**:
   - `account_parser.py`: Canonical parser for DEGIRO `Account.csv` exports using the grammar and tie-breaking rules proven in Ticket #16.
   - `transaction_parser.py`: Backward-compatible parser for legacy `Transactions.csv` exports.
   - `normalizer.py`: Deterministic 32-character MD5 hashing and deduplication.
2. **`backend/engine/`**:
   - `portfolio.py`: FIFO cost-basis math, asset quantity accumulation, and historical valuation series.
   - `cash.py`: Running cash balance calculation (excluding internal Flatex sweeps) and external deposit tracking.
   - `rebalancer.py`: Target allocation drift detection and non-negative deposit rebalancing calculator.
3. **`backend/providers/`**:
   - `tradegate.py`: TradeGate exchange quote fetcher for European stocks and ETFs.
   - `coingecko.py`: Public CoinGecko / Binance API client for live and midnight crypto valuations.
   - `yahoo.py`: Yahoo Finance fallback for historical closes and unlisted instruments.
4. **`backend/db/`**:
   - `connection.py`: Neon PostgreSQL connection management via environment variables.
   - `repository.py`: CRUD operations for `degiro_transactions` with `ON CONFLICT (row_hash) DO NOTHING`.
   - `snapshots.py`: Read/write operations for pre-aggregated `portfolio_daily_history`, `current_asset_holdings`, and `degiro_price_snapshots`.
5. **`backend/cli.py`**:
   - Standalone CLI interface for scheduled GitHub Actions runs and local debugging (`python -m backend.cli snapshot`, `python -m backend.cli ingest <file>`).

### Migration Seams & Backwards Compatibility
During initial migration, root-level modules (`data_processing.py`, `db_utils.py`, `managers.py`, `portfolio_calculation.py`, `rebalance_calculator.py`, `snapshot_worker.py`, `transaction_ingestion.py`) temporarily acted as thin forwarders/shims importing from `backend.*`. Following the migration of all test suites and consumers directly to `backend.*`, these root-level legacy files have been purged in Ticket #22 to maintain a clean repository structure.

## Consequences

- Direct imports across domain layers are cleanly isolated (e.g. `engine` has zero knowledge of `db` or `providers`).
- Full decoupling from Streamlit and Google Drive ensures fast startup, zero CLI warnings, and straightforward testing with `pytest`.
- The frontend read layer queries pre-computed snapshot tables populated deterministically by `backend.db.snapshots`.
