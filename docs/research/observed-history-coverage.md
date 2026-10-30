# Observed history coverage, checked 2026-10-23

Full private all-time coverage is **not verified**. Public symbols below do not
establish verified mappings to the owner's broker Assets. No private records or
credentials were used in these probes.

[CoinGecko Demo documentation](https://docs.coingecko.com/demo/reference/coins-id-market-chart)
limits history to 365 days and documents daily 00:00 UTC observations, with the
latest completed day available after 00:10 UTC. The adapter discards the live
tail and consumes only exact midnight samples. The following midnight closes
the preceding day.

[Yahoo historical download help](https://in.help.yahoo.com/kb/finance/download-historical-data-yahoo-finance-sln2311.html)
requires Gold for CSV downloads and describes licensing restrictions. A public
chart response does not guarantee a supported free historical API.
[Yahoo adjustment documentation](https://help.yahoo.com/kb/SLN28256.html)
describes split and dividend adjustments. Adjusted prices cannot be combined
with separately recorded dividends as if they were unadjusted observations.

## Safe live probes

Bounded public HTTPS requests used no keys or cookies; logs contain only counts,
dates, currency and statuses. These are observations, not a service guarantee.

| Public request | Observed result |
| --- | --- |
| CoinGecko bitcoin market_chart, EUR, 365 days, daily | HTTP 200, 366 samples including live tail |
| CoinGecko ethereum market_chart, EUR, 365 days, daily | HTTP 200, 366 samples; 365 exact-midnight observations, 2025-10-24 through 2026-10-23 |
| CoinGecko ethereum market_chart, EUR, 366 days, daily | HTTP 401; consistent with documented limit, not proof of exact failure cause |
| Yahoo chart VWCE.DE, one month, daily, events requested | HTTP 200, EUR, 23 timestamps, no event types returned |
| Yahoo chart VWCE.DE, five years, daily, events requested | HTTP 200, EUR, 1,275 timestamps, 2021-10-25 through 2026-10-23, no event types returned |

VWCE timestamps included 07:00 UTC; they do not verify official close times.
Empty events do not prove complete corporate-action history. EUR quotes do not
repair missing dated transaction FX; the canonical ledger still requires reviewed
`fx_evidence` for historical non-EUR cash Transactions.

## Remaining delivery gate

The PC-independent daily worker fetches reviewed BTC/ETH mappings with at most
two provider calls per run. The free Demo window cannot recover older all-time
crypto history. ETFs require a verified unadjusted source, exchange-calendar
closures and corporate-action reconciliation. Paying for sources or reducing
coverage requires a specific decision; neither has been authorized here.

The calculation and Performance UI support observed and unavailable intervals.
Missing observations are never replaced by zeros, cost valuations, adjusted
prices or inferred movements. Private source reconciliation and source coverage
remain parent delivery gates; public probes and synthetic tests do not satisfy them.

## Rechecked 2026-10-30 for selected-period history (#49)

Three bounded public read-only probes used no keys, cookies or private mappings:

| Public request | Observed result |
| --- | --- |
| CoinGecko bitcoin market_chart, EUR, 365 days, daily | HTTP 200; 365 exact-midnight samples, 2025-10-31 through 2026-10-30 |
| CoinGecko ethereum market_chart, EUR, 365 days, daily | HTTP 200; 365 exact-midnight samples, 2025-10-31 through 2026-10-30 |
| Yahoo chart VWCE.DE, one month, daily, events requested | HTTP 200; EUR; 23 timestamps, 2026-09-30 07:00 UTC through 2026-10-30 08:00 UTC; no event types returned |

The [CoinGecko Demo documentation](https://docs.coingecko.com/demo/reference/coins-id-market-chart)
still states a 365-day limit, daily 00:00 UTC granularity and availability of the
last completed day after 00:10 UTC. A request without a key succeeding today
does not supersede the documented key requirement or guarantee future access.
The Yahoo timestamp/event response still does not verify official unadjusted
closes, complete corporate actions or an owner's Asset mapping. The prior Yahoo
adjustment help URL returned HTTP 429 to the web reader during this recheck;
no new adjustment guarantee is inferred. Full private all-time coverage remains
unverified, and missing FX, source or corporate-action evidence still withholds
dependent results.

For an intraday verified opening baseline, daily history starts at the next UTC
midnight. **All time** now marks that interval as shorter than the requested
opening day, rather than silently implying complete opening coverage. The UI
names requested and observed openings; chart and EUR attribution both retain
the observed endpoints. A synthetic 2026-01-01 08:00 UTC baseline produces an
observed 2026-01-02 through 2026-01-05 interval with EUR29 gain, excluding the
unobserved opening-day result. Additional calculation checks withhold adjusted
prices in the presence of recorded distributions, accept independently dated
transaction FX, and reject FX evidence for a different date.
