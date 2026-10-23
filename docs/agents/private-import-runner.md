# Private CSV import runner

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
happen in the same database transaction. A validation/calculation failure rolls
back the new generation and retains the prior accepted pointer. Raw source files
remain private for overlap replay and correction review. Retrying an identical
file retains its durable identity; explicit retries recover failed jobs or a
processing job abandoned for fifteen minutes. A database advisory lock serializes
processors, and the hosted workflow is limited to ten minutes.

Current prices are reused with their original timestamps and diagnostics; import
does not fetch or claim fresh quotes. Background history has its own explicit
`unavailable` status until a history worker is integrated and verified. An import
completing means the canonical ledger Snapshot was published, not that history or
price refresh completed. Do not claim the parent delivery gates are met until
those integrations and browser/live database recovery checks have passed.
