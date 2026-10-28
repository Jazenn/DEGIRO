# Current crypto reference quotes

The staged Worker returned HTTP 403 for Binance during the actual synthetic
holdings refresh rehearsal. That source failure retained the prior coherent
generation. Diagnostics now disclose only provider name and HTTP status, never
response bodies, request URLs, private symbols or raw exception text. One provider
failure also aborts remaining in-flight quote requests; the ten-second request
budget remains unchanged.

Kraken is an additional explicitly configured public reference source, with no
automatic fallback, default mapping or broker execution. Apply
`hosted/kraken-quotes-schema.sql` only to an approved database before configuring
it. This migration extends allowed provider names and preserves existing rows;
the initial valuation schema also supports the new name. Existing restricted
Worker SELECT and valuation-function grants are unchanged.

Only these reviewed public identities are supported:

| Dashboard symbol | Kraken provider symbol | Base | Quote |
| --- | --- | --- | --- |
| BTC-EUR | XXBTZEUR | XXBT | ZEUR |
| ETH-EUR | XETHZEUR | XETH | ZEUR |

The [official pair metadata API](https://docs.kraken.com/api-reference/market-data/get-tradable-asset-pairs)
and a bounded public response verified these base/quote identities on 28 October
2026. The [recent trades API](https://docs.kraken.com/api-reference/market-data/get-recent-trades)
is requested with `count=1`. The adapter preserves its string price and the actual
trade timestamp, separately from retrieval time; the pagination cursor is never
used as an observation time. Errors, mismatched pair keys, multiple/absent trades,
invalid prices and unknown observation times are rejected. Downstream eligibility
still checks quote age before current stage suggestions.

Kraken documents that [public market data needs no account](https://support.kraken.com/articles/360000919986-public-endpoint-examples-you-can-try-them-directly-in-a-web-browser-?mode=consumerapp).
Local probes returned one timestamped EUR trade per coin, about 5–11 seconds old.
These probes are not proof of Worker reachability, sustained free-source service,
private broker identity, executable DEGIRO prices or account-specific fee/quantity
rules. Actual deployed refresh, canonical equality and resource fit remain staged
checks until the coordinator runs them with explicit synthetic mappings. The
existing Binance/Yahoo mappings are never silently rewritten.
