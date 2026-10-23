# Accepted Crypto Plans

The hosted Crypto Scale view keeps BTC and ETH independently versioned. A draft
requires an explicit positive retained core, three positive proportions totaling
100% and three increasing reviewed sale levels. No personal allocation is
preselected. A server preview shows original tactical quantities and the retained
rounding residual before a separate checked acceptance. Nothing executes in DEGIRO.

Stage quantities are rounded down to reviewed broker steps against the original
tactical denominator. A zero/minimum-violating stage is rejected rather than
silently consuming residual or core. Acceptance records immutable plan/stage IDs,
holdings generation, ledger/financial settings, broker-rule revisions and market
series/window/template provenance. Changed suggestions and new purchases never
resize the accepted plan. Missing history does not prevent reading accepted plans.

`GET /api/crypto/plans?coin=BTC-EUR` reads shared state. Authenticated same-origin
`POST /api/crypto/plans/preview` validates without writing; `POST /api/crypto/plans`
accepts the reviewed payload with operation ID, expected coin version and Snapshot
generation. Identical successful retries return the original durable result;
changed payloads, stale versions/generations and changed reviewed inputs conflict.
An existing plan requires an explicit reviewed replacement rather than overwrite.

The separately reviewed `hosted/crypto-plan-schema.sql` is not automatically
applied. It builds on Snapshot, execution-terms and crypto-market tables. A dated
`hosted_crypto_sale_permissions` record must confirm direct coin/broker identity,
sale permission and that the referenced execution quantity/minimum rules apply to
sales. No broker assumptions or allocations are seeded. Purchase fee facts do not
establish sale fees; this feature makes no fee-aware profit claim.

Only the documented SELECT and acceptance-function EXECUTE privileges are needed
by the Worker; it receives no direct plan/history mutation grants. Operation,
history and event records are retained. Tests exercise calculation, authenticated
operations with a SQL transport fixture, and the real browser module over HTTP.
Live SQL execution, cross-device recovery and private broker evidence remain
deployment verification gates; no schema or production state was changed here.
