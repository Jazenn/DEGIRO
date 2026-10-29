# Guarded synthetic staging crypto market history

`Synthetic staging crypto market history` uses the existing canonical public
CoinGecko producer to update only `hosted_crypto_market_history` in the approved
synthetic staging database. It does not rebuild Portfolio History, publish a
Snapshot, accept plans or enable private imports. Production flags and publisher
secrets are unchanged.

Configure the **synthetic-staging** GitHub environment with the existing
`STAGING_PUBLISHER_DATABASE_URL`, `STAGING_EXPECTED_HOST` and
`STAGING_EXPECTED_DATABASE` secrets, plus the owner's free
`COINGECKO_DEMO_API_KEY`. Never put the key in a command argument, tracked file,
workflow input or log. The entrypoint uses the shared effective-libpq destination
guard before connecting, requires explicit staging approval and a nonempty key,
then verifies that existing Snapshot generations are nonempty and synthetic-only.

The workflow can run manually on `main` or `integration/useful-dashboard`. Daily
scheduling at 00:29 UTC stays disabled unless the distinct repository variable
`STAGING_CRYPTO_HISTORY_ENABLED` is explicitly set to `true`. It shares the
staging verification concurrency group with import/recovery rehearsals. No flags,
secrets, deployment or dispatch were changed by this implementation.

The [CoinGecko Demo contract](https://docs.coingecko.com/demo/reference/coins-id-market-chart)
documents daily midnight observations, last-completed-day availability after
00:10 UTC and a 365-day history limit. Its documented Demo key is required even
though earlier anonymous probes succeeded. This job makes two bounded provider
requests, one per public coin, and requires all 365 following-midnight samples
that close the preceding completed UTC days. Today's live tail is excluded by
the existing adapter. It makes no private broker-identity or executable-quote
claim.

Each coin updates independently. A provider failure or incomplete required window
retains that coin's previous series and records a diagnostic. The job exits with
sanitized failure unless both coins published complete windows; logs include only
coin names, state and observation counts. Frontend window validation still pauses
suggestions if retained observations no longer cover the current window. Missing
history is never replaced by synthetic prices or a shorter window.

`python -m backend.staging_crypto_market` uses the same explicit environment
configuration; `STAGING_CRYPTO_HISTORY_APPROVED=synthetic-staging-only` is the
operator approval marker used by the workflow. Tests at the external HTTP and
publisher boundary cover key forwarding, complete/incomplete independent results
and retention. Guard tests reject missing keys and wrong destinations before a
connection starts. Actual hosted quota, free-tier CPU, durable reads and daily
publication remain live verification checks until the workflow is run.

On 29 October 2026, the owner-provided Demo key was configured only in the
`synthetic-staging` environment. The [authenticated hosted publication](https://github.com/Jazenn/DEGIRO/actions/runs/40876151180)
passed for both coins with 365 completed days. Authenticated deployed Worker reads
then returned `ready`, no missing days and 90 context days for each coin, covering
29 October 2025 through 28 October 2026. The temporary verification session was
removed. Sustained account quota and full-workload resource usage remain unproven.
The schedule remains disabled because the temporary staging branch expires on
30 October 2026 at 10:32 UTC; continuous operation requires a reviewed lifecycle.
