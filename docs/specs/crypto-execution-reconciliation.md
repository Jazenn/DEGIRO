# Reported and imported Crypto Stage executions

Ticket #58 keeps manually reported sales pending until an owner explicitly chooses
an imported Transaction. Neither a reached target nor an ambiguous candidate records
an execution. The authenticated `/api/crypto/executions` interface reads and writes
durable shared state independently of quote/history availability.

Apply `hosted/crypto-execution-schema.sql` only to an approved destination, after
the Snapshot, contribution and Crypto Plan schemas. Grant the Worker EXECUTE on
`hosted_read_crypto_executions(text)` and `hosted_record_crypto_execution(jsonb)`;
no direct report, allocation, capacity or operation table mutation grants are needed.
Stage review uses the read function in its existing coherent SQL statement. The
read function is STABLE so every nested read uses that statement's MVCC snapshot.

Commands carry the accepted generation, current plan identity, independent shared
execution version and a stable operation identity. Pointer, plan and per-coin
execution locks serialize publication/replacement conflicts. Identical retries
return their original result; changed inputs using the same identity conflict.
Unchanged uncertain browser retries preserve that identity even after a reload.
An existing report can be partially matched. Matching without a report creates and
matches one atomically. Stage remainder includes both matched and pending quantity;
pending reports reserve held tactical units above the core. Matching an imported
sale does not subtract already sold units from current holdings a second time.

The Python ledger publishes actual disposal identities, observed execution times,
actual proceeds/fees, consumed FIFO lots and cumulative cost breakpoints. The SQL
operation interpolates that canonical execution projection rather than replaying
accounting. Allocations consume consecutive ranges of a globally protected execution
capacity, so nonuniform FIFO costs follow their actual units. Exact rational
receipts retain fee/proceeds fractions and explicitly allocate the canonical
execution's final arithmetic rounding residual. Their exact totals telescope to the
recorded execution result; separately rounded EUR display amounts can differ by a
cent from the sum of displayed components. Missing verified fees/costs produce an
unverified receipt rather than a gain claim.

Reports and allocations retain their plan identities across replacements. Current
progress only counts the current plan. Reimporting unchanged facts leaves global
execution capacity intact; ledger/cutoff publication metadata is not a new fill.
Changed or missing matched facts preserve receipts and matched quantities, flag
reconciliation, and suspend stage suggestions even when the ledger version itself
did not change. Unmatched post-acceptance sales and holdings deficits also prevent
claiming that a changed ledger has been reconciled. Completed identities are never
automatically released or rearmed.

Local evidence: the approved application boundary checks owner access, same-origin
writes, invalid quantities and conflict responses. Real isolated PostgreSQL checks
cover partial fills, retry/overlap capacity, independent coins, actual nonuniform
costs, corrections, reversals, unrelated manual reductions and restricted Worker
permissions. The SQL tests run in `npm run hosted:sql-test` and therefore CI. Browser
module workflow tests cover explicit candidate choice, draft retention, stale
quotes, conflicts and uncertain retries. These are synthetic local checks; schema
application, Neon concurrency, real imports and browser/device checks against the
approved staged service remain release gates.
