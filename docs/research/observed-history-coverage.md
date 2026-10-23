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
