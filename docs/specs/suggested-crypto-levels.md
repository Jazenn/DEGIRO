# Suggested Crypto Levels

BTC/ETH market history is independent of personal Portfolio History, holdings,
cost eligibility, opening baseline and broker timestamp verification. It is a
public EUR reference series, not proof that a private broker Asset is spot crypto.

`python -m backend.crypto_market` fetches Bitcoin and Ethereum separately through
the existing CoinGecko adapter. The new daily `crypto_market_history.yml` job runs
at 00:23 UTC when explicitly enabled with `HOSTED_CRYPTO_MARKET_ENABLED=true`.
It requires the reviewed `hosted/crypto-market-schema.sql`, server-only publisher
database secret and any required `COINGECKO_DEMO_API_KEY`; no private calculation
settings are consumed. The Worker gets SELECT only. No schemas, secrets, flags or
deployments were changed by this implementation.

The [official CoinGecko Demo market_chart documentation](https://docs.coingecko.com/demo/reference/coins-id-market-chart),
checked 23 October 2026, documents daily 00:00 UTC observations, availability of
the last completed day after 00:10 UTC and a 365-day free history limit. Earlier
read-only probes of both public coins returned the required midnight series;
see [observed history evidence](../research/observed-history-coverage.md). A fresh
read-only probe through the implemented independent adapter returned365 midnight
observations for each coin, from2025-10-24 through2026-10-23, closing the complete
2025-10-23 through2026-10-22 daily window; live tails were excluded. Provider
availability and actual hosted quota/CPU remain live gates. A configured free key
may be required; no account or paid subscription was provisioned. The new job uses
at most two provider calls per run and makes no private history replay calls.

One following-midnight observation closes each of the 365 preceding completed UTC
calendar days. Today's live tail is discarded. Missing days pause new suggestions;
there is no shorter-window fallback. Source/currency/time mismatches pause the
series too. A failed per-coin fetch retains that coin's previous stored series and
adds a diagnostic; the current UTC window is still checked before use. BTC and ETH
are updated independently, with explicit market-series versions and attempt times.
No accepted Snapshot needs to exist to read these series.

The authenticated, same-origin POST `/api/crypto/levels` reads one per-coin durable
series. It accepts three purchase and three sale percentile strings, initially
35/20/10 and 75/90/95. Decimal arithmetic sorts the 365 observations and interpolates
at `(n-1)*p`. A hand example `[10,20,40,100]` produces 21 at the35th percentile,
55 at the75th, and91 at the95th. Levels with coincident or unordered prices require
review. These positions do not predict future prices or the probability of profit.
They never become personal gain, drawdown or allocation scores.

Editable templates are explicitly labelled unsaved per-coin preview drafts, not
accepted plans or personal core/stage allocations. The response includes market
version, complete-window dates, diagnostics and the most recent90 completed days
with observation/source provenance. A supplied stale market version is rejected.
Acceptance, fixed quantities and durable plan history belong to the later plan
lifecycle; missing market history never deletes or rewrites accepted state.

The visible workflow lives under stable `#crypto-scale` / `#crypto-levels`. It
invalidates context on `accepted-snapshot`, suppresses late requests, and expires
displayed suggestions at UTC rollover with a one-shot browser timer. It performs
no continuous polling or hidden-tab requests. It emits `crypto-levels-preview`
with the current response and `crypto-levels-invalidated` with the affected coin;
future plan UIs must check state/version and never treat these events as execution.
Purchases remain choices funded from explicitly allocated contributions.

Local calculation, signed-owner application, public HTTP-adapter and browser
workflow tests cover hand percentiles, rolling expiry, the missing-data pause,
flat/unordered levels, independent edits, preserved accepted-plan content and
timer expiry. They do not prove deployed SQL/CPU, actual multi-device persistence
of future plans, source availability tomorrow or complete private investment history.
