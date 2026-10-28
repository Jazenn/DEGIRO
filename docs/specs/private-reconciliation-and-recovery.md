# Private reconciliation and recovery rehearsal

Ticket #60 remains a release gate. This procedure prepares evidence; it does not authorize migration, infrastructure provisioning or deployment. Keep the current dashboard and its data intact until every gate in spec #40 passes.

## Reconcile independently reviewed source records

Run `python -m backend.reconciliation SNAPSHOT REFERENCE --report NEW_REPORT` with all three paths in an access-restricted directory **outside every repository checkout**. The tool has no network or database writes and prints only its status. Reports include private values; never attach them to GitHub, CI logs or screenshots. It creates a new report exclusively and refuses overwrites. Exit codes are 0 for matched, 1 for mismatch/unavailable, and 2 for invalid files or paths.

`SNAPSHOT` is the canonical read model itself (the `read_model` member of an authenticated Snapshot response), not the surrounding response envelope. Preserve its generation ID, publication time and response privately beside the report. `REFERENCE` is a separately source-reviewed JSON object:

```json
{
  "schema_version": "private-reconciliation-v1",
  "source_evidence": "Private source document/date and review notes",
  "cutoff": "2026-01-11T00:00:00Z",
  "ledger_cutoff": "2026-01-11T00:00:00Z",
  "ledger": {
    "cash_balance_eur": "0",
    "market_value_eur": "1100",
    "equity_eur": "1100",
    "net_external_contributions_eur": "1005",
    "net_gain_eur": "95",
    "attributed_gain_eur": "95",
    "gross_income_eur": "0",
    "withholding_eur": "0",
    "net_income_eur": "0",
    "portfolio_costs_eur": "0",
    "positions": [{
      "broker_asset_id": "SYNTHETIC-A",
      "quantity": "1",
      "retained_cost_eur": "1005",
      "market_value_eur": "1100",
      "held_gain_eur": "95",
      "realized_gain_eur": "0"
    }],
    "charges": [{
      "transaction_id": "replace-with-reviewed-source-identity",
      "date": "2026-01-03",
      "category": "replace-with-reviewed-source-category",
      "amount_eur": "5",
      "allocation": "replace-with-reviewed-source-allocation"
    }]
  }
}
```

The example is synthetic and intentionally needs actual reviewed charge identity/category/allocation before use. Do not copy the calculated ledger into the reference and call that source reconciliation. Map independently reviewed source records to canonical identities, include closed Assets with realized results, and explain each difference privately. Review purchase/sale/FX fees and attribution, dividends/withholding, deposits/withdrawals and internal sweeps. Repeat at representative matching valuation **and ledger** cutoffs, including partial sales/reinvestment/corrections. Different cutoffs are mismatches, even if totals coincide. Decimal values compare exactly without rounding tolerances. Missing/null/nonfinite values remain unavailable; identity sets must match without duplicates. A passed report proves agreement with supplied evidence, not source completeness, price provenance, authentication or migration readiness.

## Export and restore an isolated copy

Use a PostgreSQL client compatible with the source server and a **direct**, non-pooled connection. Store connection details in a private PostgreSQL service/passfile configuration with restricted permissions; names below are placeholders. Keep archives, listings and logs outside this repository with owner-only access. Archives can contain raw CSV uploads, normalized Transactions, settings, plan/report/execution histories and sessions. Restrict access to the restored destination before loading it. Store required application secrets separately from this database archive.

1. Identify the source, its immutable accepted generation and the exact application revision. Pause application writes and background publishers for the final rehearsal/cutover capture; an earlier parallel comparison need not stop the old dashboard. Inventory all application schemas/tables, sequences, functions, triggers, version/conflict operations and grants. Capture expected counts and private row digests through the same consistent database snapshot as the export when concurrent writers exist. Record external configuration and roles separately: a single-database dump does not export cluster roles.
2. Export the **whole application database**, not only the current Snapshot tables, using a custom archive. In PowerShell, first choose a new absolute private `$archivePath` outside the repo, verify it does not exist, then run `pg_dump --dbname=service=approved_source --format=custom --file=$archivePath`. Check the exit code and all private warnings. Record a SHA-256 digest with `Get-FileHash -LiteralPath $archivePath -Algorithm SHA256`. Keep an independently retained copy. A hash proves archive integrity, not restorability.
3. Obtain explicit authorization for the named **empty isolated restore destination**. Verify its resolved database identity differs from the source and contains no application data. Inspect the private archive listing with `pg_restore --list --file=PRIVATE_LISTING_PATH PRIVATE_ARCHIVE_PATH`. Review any untrusted functions before executing them.
4. Restore into that destination using `pg_restore --dbname=service=approved_empty_restore --single-transaction --exit-on-error --no-owner --no-privileges PRIVATE_ARCHIVE_PATH`. Check success. Do not use `--clean`, `--create`, or the current live database as a shortcut. Recreate and independently review least-privilege application/publisher grants; `--no-privileges` deliberately does not restore them. Do not grant PUBLIC access to privileged functions. Restored login sessions must not make an otherwise isolated copy publicly accessible; revoke them before any new deployment.
5. Compare the accepted generation and full read model exactly, verify raw source hashes and every durable table's counts/private row digests, and compare settings/plan/execution histories and operation identities. Exercise synthetic read/write conflict and retry scenarios using the restored application's authorized interface. Reconcile financial totals again from private source evidence. Record restore duration, archive digest, application revision, source/destination identities, grant checks and reviewer outcome privately.

PostgreSQL documents consistent single-database archives and the omission of cluster-wide roles in [pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html). The transactional restore/error options are documented in [pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html). A successful local synthetic rehearsal does not demonstrate a deployed Neon restore or concurrent behavior.

## Demonstrate rollback before switching

On an authorized synthetic staging destination, preserve two complete validated generations and the prior application revision. Freeze writes/publishers, record their settings/ledger versions and accepted plan/report/execution state, switch one complete generation through the reviewed publisher, then restore the previous compatible application/data state. Verify the authenticated read returns that exact generation, dependent figures agree and histories/retry identities remain intact. Resume writers only after checks pass.

Do not move only the Snapshot pointer backward across later imports or plan executions: that leaves settings/plans and financial state inconsistent and can replay quantities. If those have changed, recover the full consistent capture into an isolated destination and reconcile post-capture activity before an approved connection/deployment switch. Retain the original database, dashboard and deployment configuration through acceptance. A rollback that loses new reports or executions has failed the rehearsal. No production switch or removal is performed by the reconciliation CLI.

## Required evidence before ticket closure

Keep a dated private release record with pass/fail, reviewed artifact pointers and unresolved decisions for each spec #40 delivery gate:

- Matched-cutoff source reconciliation of holdings, cash, external flows, fee-inclusive costs, gains and attributions; explained differences from the old dashboard.
- Successful full export, isolated restore and rollback, with histories, grants, raw source records and post-capture activity accounted for.
- Actual owner and nonowner access checks across APIs/assets/alternate routes, session expiry/revocation and server-only secrets; real cross-device stale edits/retries.
- Phone/laptop workflows for imports, periods, contributions, accepted plans, reporting, partial fills, corrections and replacements; readable stale/missing/failure states.
- Actual source identity/timezone/quantity/fee/history coverage and free-tier account resource evidence. Record unavailable exposure honestly.
- Separate measured cold/warm authenticated load, provider request, coherent refresh and mobile-network latency, including environment/sample count and errors. Clock tests and bundle sizes do not establish these results.
- Backend/frontend suites, hosted tests and typecheck, actual SQL regressions, frontend build and Worker dry-run build for the candidate revision.

Stop cutover on failed technical checks and fix them. Return a specific infeasible approved product/data/free-service constraint for a decision. Publish only sanitized outcomes. Retire duplicate calculations and privileged browser access after acceptance and a retained recovery path; their continued presence before cutover is intentional.

## Evidence in this implementation

The manual **Synthetic staging full recovery rehearsal** Actions workflow runs
`python -m backend.staging_recovery` using only the distinct
`STAGING_PUBLISHER_DATABASE_URL`, `STAGING_EXPECTED_HOST` and
`STAGING_EXPECTED_DATABASE` secrets in the `synthetic-staging` environment. It does not
enable scheduled import/history jobs or reuse production secrets. The independently
configured host must match a direct TLS connection to the checkpointed synthetic
branch's `neondb`; PostgreSQL server/client major 17 is required. Private source
generations, nonempty legacy tables or retained raw uploads stop the rehearsal.
It also rejects non-extension application relations/routines outside `public`,
views/materialized views/foreign tables and unlogged/temporary application
relations before export, rather than silently omitting them from comparison.
Both staging CLIs validate libpq's effective host/database as well as the URL
authority/path. Query options are limited to `sslmode`, `channel_binding`,
`connect_timeout` and `application_name`; destination/service overrides and
ambient `PGHOSTADDR`/`PGSERVICE`/`PGSERVICEFILE` defaults are rejected before any
connection or archive command.
The root coordinator supplies only the already authorized staging credentials.

The module exports a consistent database snapshot and captures each public table's
row count/private digest plus functions, schema/table/column/function grants,
constraints, triggers, indexes and sequences from that same snapshot. `pg_dump`
writes a full custom archive into a restricted temporary directory. It creates a
uniquely named empty database on the same approved staging branch, revokes PUBLIC
CONNECT there, and restores with `--single-transaction --exit-on-error --no-owner`.
This trusted same-cluster rehearsal deliberately restores existing-role ACLs from
the archive and compares them exactly, including PUBLIC revocations. It does not
create cluster roles or demonstrate independently reviewed grants on a new cluster;
the private production procedure above still requires that review.

After exact data/schema/grant comparison, the module exercises publication CAS,
rollback and immutable-generation rejection **only on the restored database**,
then confirms all captured histories remain unchanged. Only the uniquely named
database successfully created by that invocation can be dropped; no source writes,
existing-destination overwrite, forced disconnect, `--clean` or `--create` restore
is allowed. The archive and private command diagnostics are never uploaded as an
artifact or printed. Only sanitized counts, timings, an archive hash and pass/fail
leave the runner. Successful execution proves that capture's full restore round
trip; its temporary archive is **not an independently retained durable backup**,
and it does not prove private source reconciliation, application cutover, restored
hosted access or recovery of later activity. The job shares the
`synthetic-staging-verification` concurrency group with other staging rehearsals.

Local CLI regressions exercise early rejection before any database connection:
an unapproved endpoint cannot expose credential text, and missing PostgreSQL
clients cannot silently pass. Driver/process-boundary regressions verify that
both restored connections close before database cleanup and an unexpected
application relation prevents every archive/restore command. Live export/restore execution remains separate
evidence until the coordinator runs the manual workflow.

Eight local synthetic regressions cover the read-only comparator/CLI: the EUR1000+EUR5/EUR1100 example, holdings/charge differences, missing gains/costs, cutoff/evidence validation, duplicate identities, nonfinite decimals, exclusive private reports and repository path rejection. No private reconciliation, new database export/restore, staging schema application, benchmark, live resource check, deployment or production cutover is claimed.
