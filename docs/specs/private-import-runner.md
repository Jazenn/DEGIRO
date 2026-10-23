# Private CSV import runner (operator deployment guide)

The authenticated Worker stages private UTF-8 CSV bytes in `hosted_import_jobs`.
The Python Actions workflow processes the durable queue hourly while the owner's
PC is off; a manually dispatched workflow can process it earlier. GitHub schedules
can be delayed and do not provide an immediate-processing guarantee. No browser
GitHub token or database credential is needed. Upload status checks are explicit,
without continuous background polling.

Provisioning is a separate authorized operation. Before enabling uploads:

1. Apply `hosted/import-schema.sql` to the approved database containing the hosted
   Snapshot tables. Give the Worker only the column privileges documented there,
   preserving its existing authentication and Snapshot read privileges. Do not
   grant it access to private CSV contents after insertion.
2. Add GitHub Actions secrets `HOSTED_PUBLISHER_DATABASE_URL` (the private publisher
   role) and `IMPORT_CALCULATION_SETTINGS` (JSON containing reviewed mapping,
   source-timezone, opening-baseline and cost-history evidence). Never invent
   evidence or paste private CSV records into issues or Actions logs.
3. Enable repository variable `HOSTED_IMPORTS_ENABLED=true` and Worker environment
   variable `IMPORTS_ENABLED=true` only after a synthetic end-to-end run verifies
   upload, processing, rejected import recovery and pointer preservation.
4. Verify actual runner usage and free quota. The hourly schedule has roughly
   720 invocations/month, each processing at most ten jobs and limited to ten
   minutes; this is a cap, not evidence that actual usage fits the free tier.

`python -m backend.import_jobs` is also the same entrypoint for a separately
approved hosted runner. It requires explicit environment configuration and does
not read legacy credential files. Publishing and marking the import complete
happen in the same database transaction. Import staging captures the accepted
generation and shared Rebalancing Targets version in one read. Publication locks
the pointer and targets in the same order as current valuation, rejects either
version changing, and never replaces another writer's first pointer insertion.
Conflicts leave a failed, safely retryable job with `publication_conflict_retry`.
The `import_provenance` object records the separate calculation-settings hash and
shared targets version used during that import; it never relabels one as the other.
A validation/calculation failure rolls
back the new generation and retains the prior accepted pointer. Raw source files
remain private for overlap replay and correction review. Retrying an identical
file retains its durable identity; explicit retries recover failed jobs or a
processing job abandoned for fifteen minutes. A database advisory lock serializes
processors, and the hosted workflow is limited to ten minutes.

Current prices are reused with their original timestamps and diagnostics; import
does not fetch or claim fresh quotes. Background history has its own explicit cutoff and coverage state; missing reviewed observations leave affected periods unavailable. An import
completing means the canonical ledger Snapshot was published, not that history or
price refresh completed. Do not claim the parent delivery gates are met until
those integrations and browser/live database recovery checks have passed.


## Daily observed history

The separate `observed_history.yml` workflow runs seven days at 00:23 UTC, after
CoinGecko's documented 00:10 UTC completed-day release. It is disabled until an
explicitly authorized operator sets `HOSTED_HISTORY_ENABLED=true`. It uses the
same private publisher/settings secrets and optional `COINGECKO_DEMO_API_KEY`.
No private records belong in the public repository or job logs.

Reviewed `IMPORT_CALCULATION_SETTINGS.history_sources` maps canonical symbols to
objects with `provider: "coingecko"`, `coin_id: "bitcoin"` or `"ethereum"`,
`verified: true` and nonempty `evidence` for the mapping. Never manufacture
verification. At most two requests fetch 365 daily EUR days with ten-second
request timeouts. The adapter keeps exact observed 00:00 UTC samples only;
missing days and older-than-window records remain unavailable. Provider failure
retains the previous accepted generation. At roughly 60 calls/month the request
count is bounded, but actual free account usage still requires verification.

`python -m backend.import_jobs --history-only` replays completed private sources,
uses canonical calculation at each completed UTC cutoff, and publishes history
and ledger coherently with an accepted-generation compare-and-swap. It operates
without waiting for new uploads and without the owner's PC. Background rebuilds
are separate from bounded current-price refresh. GitHub schedules can be delayed.

For separately approved runners, optional `IMPORT_HISTORY_FILE` points to a
private JSON observation file containing `daily_prices` (UTC cutoff -> symbol ->
ObservedPrice fields), `asset_coverage` (symbol -> reviewed
`corporate_actions_reconciled: true`, `official_close_verified: true` plus `evidence`), and `market_closures`
(cutoff -> symbol -> explicit exchange-calendar evidence). It is an operator
input path, not the hosted worker's sole source. Never commit private files or
unverified prices. Preserve original observation and retrieval timestamps.

See `docs/research/observed-history-coverage.md` for verified public limitations.
ETF provider coverage and older crypto history remain explicit delivery gates.
