# Dated ETF exposure: source verification and operation

Read-only public probes on 23 October 2026 verified these primary sources:

- [Vanguard official FTSE All-World accumulating product page](https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating): HTTP 200, machine-readable HTML holdings table. The implemented adapter successfully parsed ten rows dated 30 September 2026. It preserves the provider's reported market-value denominator and does not assume this equals fund net assets. Stable underlying identifiers are absent, so exact cross-provider overlap is unavailable. Per-fund reported country/sector weights and concentration are partial; unreported exposure remains unknown.
- [iShares official Core MSCI Europe page](https://www.ishares.com/uk/individual/en/products/251861/ishares-msci-europe-ucits-etf-acc-fund): official product identity and dated facts are public. A read-only probe of the former `1467271812596.ajax?fileType=csv&fileName=SMEA_holdings&dataType=fund` endpoint returned HTTP 200 **HTML**, not CSV. No working automated holdings adapter is claimed from that response.
- [DWS official World ex USA page](https://etf.dws.com/en-gb/IE0006WW1TQ4-msci-world-ex-usa-ucits-etf-1c/): verifies Xtrackers product/provider identity and dated portfolio sections. It does not establish a usable full holdings download in this implementation. Existing legacy display names are not evidence of provider identity.

These probes required no paid account or API key. They establish one usable partial
public source, not guaranteed perpetual availability, redistribution permission,
complete portfolio coverage, or compatible full holdings for every actual ETF.
Compatible full holdings and stable identifiers across iShares/DWS/hANetf remain an explicit
coverage gate. The application displays unavailable facts rather than substituting
index weights, stale fabricated constituents, or a diversification score.

## iShares source update — 28 October 2026

The [official Core MSCI Europe product page](https://www.ishares.com/uk/individual/en/products/251861/ishares-msci-europe-ucits-etf-acc-fund)
identifies ISIN `IE00B4K48X80` and now links a working
[latest holdings CSV](https://www.ishares.com/uk/individual/en/products/251861/ishares-core-msci-europe-ucits-etf-eur-acc/latest-holdings.csv).
A bounded read-only request returned HTTP 200 `text/plain`, 59,349 bytes and 398
rows dated 27 October 2026. Reported weights total 99.97%; rows include equity,
cash, collateral, money market and futures. These counts do not establish complete
equity coverage, a fund-net-asset denominator or notional derivative exposure.

The `ishares-csv` adapter accepts only that exact public fund/source identity pair
when explicitly configured in a reviewed manifest. It retains reported country,
sector and weight strings without normalizing the 0.03% residual away. Coverage
remains partial and uses the provider-reported market-value scope. No underlying
ISINs are present: ticker/exchange/name never become invented stable identifiers,
so exact cross-provider overlap remains unavailable. The official page's fund
identity does not verify an owner's broker holding; that mapping still needs review.

## Production path

`backend.exposure_sources.load_sources(path)` reads a reviewed manifest mapping
broker fund IDs to `vanguard-page` or the reviewed `ishares-csv` official URL, or `normalized-json`
files. Official source URLs are restricted to Vanguard's HTTPS product pages,
or the exact iShares CSV above, fetched with a twenty-second timeout, a
two-megabyte cap and no redirects. Vanguard pages must identify the requested
ISIN. The iShares adapter checks its fixed, independently reviewed public
fund/URL pairing before any request and rejects unsupported columns, invalid
dates, negative weights and totals above 100%. Reviewed normalized files must identify the same fund.
Nothing is fetched or shown by default without explicit source configuration.

Normalized files contain `fund_id`, `provider`, HTTPS `source_url`, ISO `as_of`,
timezone-aware `retrieved_at`, `identifier_namespace`, `weight_basis`, `complete`,
and `holdings`. Optional documented `country_basis` and `sector_taxonomy` are
required to combine compatible classifications into portfolio totals. Each holding includes `name`, `security_id` (nullable), decimal
`weight_pct`, `country` and `sector` (nullable). Supported weight bases are
`fund_net_assets` and `provider_reported_market_value`. A complete dataset must
total exactly 100%; otherwise it must remain partial with the residual unknown.
Keep provider classifications as reported: matching country/sector labels do not
prove compatible classification methodologies across providers.

Overlap is the sum of minimum weights for matching stable security identifiers.
It requires equal source dates, identifier namespaces and weight bases. Complete
datasets produce a comparison of fund weights, not an investment risk score.
Partial compatible datasets produce only an observed lower bound. Missing IDs,
different dates or incompatible scope disable the comparison. Coverage uses
weights, never the fraction of reported names. Known portfolio coverage excludes
cash and includes only verified fund-net-asset weights; a provider-only denominator
does not establish a percentage of the entire portfolio. Concentration from partial
holdings is an observed lower bound rather than an asserted full top ten.

The operator can enable the weekly hosted workflow only after an approved
synthetic end-to-end verification. Configure repository variable
`HOSTED_EXPOSURE_ENABLED=true`, publisher secret `HOSTED_PUBLISHER_DATABASE_URL`,
and private JSON manifest secret `ETF_EXPOSURE_MANIFEST`, for example:

```json
{
  "REPLACE_WITH_VERIFIED_BROKER_FUND_ISIN": {
    "adapter": "vanguard-page",
    "url": "https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating"
  }
}
```

This is a configuration template, not a production default or a verified mapping
to a private position. The optional iShares source configuration is
`"IE00B4K48X80": {"adapter": "ishares-csv", "url": "https://www.ishares.com/uk/individual/en/products/251861/ishares-core-msci-europe-ucits-etf-eur-acc/latest-holdings.csv"}`,
only after reviewing that broker fund identity. `python -m backend.exposure_publish` uses the same explicit
environment configuration. The hosted entrypoint accepts only official adapters;
normalized files use the explicit local operator command
`python -m backend.exposure_publish --manifest /private/reviewed-sources.json`.
It attaches exposure to a new immutable generation while preserving all canonical
ledger amounts. Pointer comparison rejects concurrent publication conflicts.
Source/validation failure leaves the previous accepted generation intact. No
private positions, source files or credentials are printed. Provisioning, live
database concurrency/recovery and actual free-tier runner usage remain deployment
gates; no infrastructure was changed during this ticket.

The iShares regression fixtures contain invented issuer names and amounts with
the provider's dated CSV schema. Tests exercise the manifest-to-exposure boundary,
including unknown identifiers, residual weights, rejected source identities,
malformed dates/schema, redirects, content types and oversized responses. No
private configuration, deployment, paid source or full production coverage is
claimed by this adapter addition.
