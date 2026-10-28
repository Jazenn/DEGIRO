# Useful dashboard implementation evidence

This records implementation checks for spec #40. It is not production cutover approval. The current dashboard remains available while replacement capabilities are verified.

## Shared targets, overview and imports — 23 October 2026

The integration branch contains authenticated versioned Rebalancing Targets, a canonical-data overview and durable CSV upload processing. Uploads run through the existing Python ingestion/calculation boundary in a hosted Actions job; they do not introduce a second browser ledger.

Local baseline checks passed: 76 Python tests, 155 frontend tests, 19 hosted tests, frontend production build and hosted typecheck. Following the first integration batch, 78 Python tests and 30 hosted tests passed, with hosted typecheck and the pinned Wrangler dry-run build. Hosted tests and typecheck now run in CI.

Hidden Chrome checks used an explicitly synthetic local HTTP fixture at exact 390px and 1440px viewports. Both rendered the canonical EUR1,100 holdings value, EUR1,005 contribution and EUR95 net gain without horizontal overflow. A failed reread kept the last accepted generation and displayed a warning. An edit based on an old targets version was rejected, retained the draft and offered reload; reload displayed the other device's version. The phone header was adjusted after screenshot inspection to keep the brand and sign-out control readable.

These browser checks verify visible behavior against controlled responses. They do not establish deployed database concurrency, authentication, network latency or Cloudflare CPU usage. Previous real Google sign-in and Worker-to-Neon Snapshot evidence remains documented in [hosted deployment](hosted-snapshot-deployment.md).

## Latest local checks

The verified implementation now includes daily history and supported returns, current valuation refresh, ETF exposure availability, fee-aware ETF/crypto contribution previews, rolling crypto market suggestions and durable accepted Crypto Plans. Review corrections preserve exact execution identities, reconcile corroborating AutoFX charges, reduce persisted history payloads and distinguish financial settings from Rebalancing Targets versions. See [prefix review corrections](prefix-review-corrections.md) and [accepted plans](../accepted-crypto-plans.md).

After integrating accepted plans, 124 Python tests and 82 hosted tests passed, with hosted typecheck, the frontend production build and the Worker dry-run build. The latest previously pushed main batch passed remote CI. Repeat synthetic Chrome checks at 390px and 1440px passed navigation bounds, empty personal plan defaults, disabled acceptance before review, target-conflict recovery and retention of the previous accepted Snapshot after a failed read.

An isolated local PostgreSQL engine executed the actual accepted-plan function successfully: identical retries return the original result, operation reuse and stale versions conflict, existing plans require replacement, and BTC acceptance leaves ETH unchanged. The SQL checks reproduced and corrected a valuation-publication operator-precedence defect. Two permanent PostgreSQL regressions now cover publication guards, immutable ledger facts, plan acceptance and restricted Worker permissions, and run in CI using a development-only dependency. These checks use synthetic records and one connection; they do not demonstrate Neon concurrency.

Reached-stage review now consumes canonical bounded cost projections and separately reviewed sale-fee evidence. An independent review found a quantity-rounding counterexample; producer and consumer now reject unsupported precision rather than mislabel profit. The supported range and error bound are documented in [reached stages](reached-crypto-stages.md). Following integration, 132 Python tests, 90 hosted tests and two actual SQL regressions passed, with typecheck and the Worker dry-run build. Synthetic Chrome checks at both viewports displayed the first two stages reached by EUR118,000, current-price proceeds, and a rounding-boundary result labelled profit unverified without horizontal overflow. Earlier fee expiry clears current review prompts without changing accepted plans; this is covered by a controlled-clock workflow test.

Reviewed Crypto Plan replacements retain old plan/stage identities and all report/allocation history. Pending remainders must be resolved first; explicit cancellation records the original report and reason without releasing matched execution capacity. Replacement checks the Snapshot, plan and shared execution versions under the same locking order as matching. A synthetic PostgreSQL regression covers partial execution, reduced holdings, pending rejection, cancellation retry/audit, stale execution conflicts, replacement retries and independent ETH state. Following execution reconciliation integration, 99 hosted tests and five actual PostgreSQL regressions passed, with hosted typecheck and the frontend production build. Browser workflow tests verify explicit replacement review and reason-based cancellation. These are local synthetic checks; live concurrency and private correction/reversal reconciliation remain release gates. See [Crypto Plan replacements](../crypto-plan-replacements.md).

## Final combined local verification — 28 October 2026

The combined integration passed 141 Python tests, 99 hosted tests, 156 frontend tests and five actual PostgreSQL regressions, plus typechecks, the frontend production build and the pinned Worker dry-run build. Synthetic hidden Chrome checks at 390px and 1440px verified sale reports, partial execution matching and the actual allocation receipt without horizontal overflow. Standards review reported zero findings through `eb86fc5`; specification review reported zero findings through `fa84eb3`.

These results establish local behavior with synthetic records. They do not establish live integration, measured production concurrency/latency, private financial reconciliation, deployment or cutover. Follow the [private reconciliation and recovery runbook](private-reconciliation-and-recovery.md) before satisfying the remaining release gates.

## Authorized synthetic staging verification — 28 October 2026

Following explicit owner authorization, the reviewed schemas and least-privilege Worker grants were applied atomically to the existing isolated synthetic staging database. A new canonical synthetic generation was published and the current Worker deployed. The previous generation, original Google owner binding/session and empty legacy tables were preserved. Preview URLs remain disabled. No private production records or existing Pages deployment were changed.

Live authenticated Worker-to-Neon checks verified exact generation/decimal/null reads, protected assets, expired/unknown session rejection and logout revocation. Two independent temporary owner sessions raced shared target writes: one succeeded, the stale write conflicted, and an identical retry returned its original result. Cross-origin writes were rejected. The Worker cannot directly mutate protected Snapshot/plan/allocation records or read raw CSV bytes. Missing quote mappings retained the previous complete generation; contribution requests with stale target versions conflicted. Snapshot request samples took 198–407ms end to end; these are ordinary reads, not isolated cold-start or mobile-network measurements.

An explicitly invented 365-day crypto series and canonical synthetic CSV records exercised the deployed acceptance, pending reporting, partial matching, cancellation and replacement interfaces across both sessions. The partial match produced EUR18.50 actual gain for 0.2 units against independently checked fee-inclusive cost; retries did not consume more quantity. Cancellation retained matched capacity and its audit reason. Replacement preserved the old plan and global consumed units while ETH remained unchanged. Probe configuration, plans and sessions were removed afterward and the original accepted synthetic generation restored. Immutable synthetic probe generations remain retained. This verifies staged application behavior; it does not validate real broker rules, historical provider coverage or private execution reconciliation.

The four pre-migration hosted tables were exported privately outside the repository, restored exactly into a disposable schema in the same approved database, and compared before rolling back the rehearsal schema. The accepted generation remained unchanged. This proves that export's round trip, not full post-migration database recovery.

The rehearsal reproduced a canonical calculation defect when valid imports mixed minute, second and fractional-second timestamps. A regression first failed at the public import-to-calculation boundary; cutoff filtering, chronological sorting and baseline checks now parse each timestamp's precision consistently. All 142 backend tests passed after the fix. The deployed Worker has no Python ledger runtime to redeploy for this correction.

Cloudflare's sampled aggregate metrics recorded 92 invocations with zero runtime errors. This small rehearsal does not establish sustained free-tier CPU/resource fit; retain the [resource limits](https://developers.cloudflare.com/workers/platform/limits/) and [CPU rollover](https://developers.cloudflare.com/workers/observability/metrics-and-analytics/#cpu-time-per-execution) caveats when assessing the complete workload. Private imports remain disabled until the publisher job and its configuration are verified. No production cutover is claimed.

## Outstanding release gates

Ticket #58 now connects the sale reporting UI to owner-only durable operations,
canonical actual-disposal receipts and reached-stage progress. Its interim checks passed
131 Python tests (two environment-dependent skips), 95 hosted tests and four actual
PostgreSQL regressions, including the new execution scenarios. See
[execution reconciliation](crypto-execution-reconciliation.md) for the contract and
remaining staged verification gates. The final combined counts above supersede these interim counts and skips. The dated staging section records subsequent live checks; no private import or production cutover is claimed.

- Reviewed staging schemas, restricted grants and real durable target conflicts are verified. Demonstrate upload retry/publication behavior after configuring the publisher job.
- Configure and verify the hosted Python job with server-only publisher credentials and reviewed calculation settings. Keep import feature gates disabled until this passes. No private CSV or settings belong in repository files, Actions logs or public issue comments.
- Verify exact broker Asset identities, source timezone, quantity precision/minimums, historical coverage and fee assumptions before dependent recommendations are complete.
- Verify current/historical provider integration, coherent publication, recovery and free-tier resource usage using actual staged requests. Local clocks and dry-run builds are not latency or quota evidence.
- Complete private matched-cutoff source reconciliation and demonstrate backup, export/restore and rollback before switching production or retiring legacy calculations/access paths.

Tickets remain open where their required live checks have not passed. Missing source coverage must remain an explicit unavailable state, never a generated history, zero value or fee-free recommendation.
