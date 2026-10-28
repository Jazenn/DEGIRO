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

## Outstanding release gates

Ticket #58 now connects the sale reporting UI to owner-only durable operations,
canonical actual-disposal receipts and reached-stage progress. Local checks passed
131 Python tests (two environment-dependent skips), 95 hosted tests and four actual
PostgreSQL regressions, including the new execution scenarios. See
[execution reconciliation](crypto-execution-reconciliation.md) for the contract and
remaining staged verification gates. No real deployment or private import is claimed.

- Apply reviewed new schemas and least-privilege grants to the authorized staging destination; demonstrate real durable target conflicts and upload retry/publication behavior.
- Configure and verify the hosted Python job with server-only publisher credentials and reviewed calculation settings. Keep import feature gates disabled until this passes. No private CSV or settings belong in repository files, Actions logs or public issue comments.
- Verify exact broker Asset identities, source timezone, quantity precision/minimums, historical coverage and fee assumptions before dependent recommendations are complete.
- Verify current/historical provider integration, coherent publication, recovery and free-tier resource usage using actual staged requests. Local clocks and dry-run builds are not latency or quota evidence.
- Complete private matched-cutoff source reconciliation and demonstrate backup, export/restore and rollback before switching production or retiring legacy calculations/access paths.

Tickets remain open where their required live checks have not passed. Missing source coverage must remain an explicit unavailable state, never a generated history, zero value or fee-free recommendation.
