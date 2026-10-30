# Crypto and mixed contribution planning

The contribution preview now accepts explicit ETF, crypto and mixed destinations. Crypto mode requires the full chosen budget; mixed mode requires a positive crypto amount smaller than the total. Bitcoin, Ethereum or both are explicit choices. Both requires a positive BTC percentage below 100%; BTC's funding rounds down to cents and ETH receives the remaining crypto funding, so their sum exactly matches the chosen amount. No threshold, existing cash balance, accepted sale plan or Long-Term Crypto Core implicitly supplies this money.

ETF shortfalls use their own allocated contribution envelope and valid Rebalancing Targets. Crypto purchases use the owner's explicitly chosen funding regardless of whether the coin is underweight; crypto-only planning does not depend on ETF targets. All holdings, including the full Long-Term Crypto Core, remain in before/after allocation. Increasing aggregate crypto allocation or exceeding an individual configured crypto target produces information, without a hard cap, sales or changes to existing quantities/plans. Unspent ETF/BTC/ETH funding remains cash instead of being silently moved between categories.

The preview's **Unspent cash by contribution choice** table shows the allocated
budget and remaining cash separately for ETFs, Bitcoin and Ethereum. The API
returns these exact decimal amounts in `remaining_cash_by_category`, with
`etf_eur`, `btc_eur` and `eth_eur` keys. Purchases, fees and spread allowances
reduce only their chosen category. For complete estimates, category remainders
are nonnegative and sum to the total remaining cash. Incomplete estimates retain
all category funding and propose no purchases. Changing the split or funding
clears this table with the rest of the previous preview.

A dated synthetic service example allocates EUR101 as EUR50 ETFs and EUR51
crypto, with 33% BTC. BTC funding rounds down to EUR16.83; ETH receives EUR34.17.
At EUR100 reference prices, EUR1 fixed fees, a 1% spread allowance and 0.01-unit
crypto steps, BTC buys 0.15 units for EUR16.15 and ETH 0.32 for EUR33.32.
The ETF envelopes cannot buy a EUR100 whole unit. Cash remains EUR50 ETFs,
EUR0.68 BTC and EUR0.85 ETH, totaling EUR51.53. Existing cash does not expand
these budgets, and repeated previews change no holdings or retained core units.

Crypto estimates require verified broker identity, an EUR quote observed within five minutes, reviewed fee and quantity-step/minimum terms, and a separately evidenced spread allowance. Commission is applied to reference purchase notional plus the conservative spread allowance; commission and spread allowance round upward to cents. Exact Decimal arithmetic and the existing stepped quantity solver keep reference notional + fee + allowance within each category envelope and the overall chosen budget. Market values after purchase use reference prices; fees/spread allowance and remaining cash are separate. These are manual estimates under the reviewed allowance, not guarantees of actual broker fills.

First purchases use reviewed identities in `hosted_contribution_assets`, never invented zero-cost accounting lots. Their quotes join the same bounded refresh batch and accepted generation as held assets, without adding nonexistent holdings to the ledger. Missing, ambiguous or unverified broker identities remain incomplete. The new schema extends reviewed execution terms with nullable spread allowance/evidence; NULL means unknown, not zero. Apply `hosted/mixed-contribution-schema.sql` only on an explicitly approved branch and grant SELECT-only Worker access. No private identity mappings or broker tariffs are seeded.

Official Netherlands evidence checked on 2026-10-23:

- [DEGIRO crypto offering](https://www.degiro.nl/zelf-beleggen/crypto-kopen) lists BTC/ETH and 0.29% commission per purchase/sale, excluding spreads. This does not establish an all-in fee or spread amount.
- [Fractional crypto purchases](https://www.degiro.nl/helpdesk/crypto/kan-ik-fracties-van-cryptovaluta-kopen) are supported, without specifying the exact quantity step.
- [Minimum crypto order](https://www.degiro.nl/helpdesk/crypto/wat-de-minimale-ordergrootte-die-toegestaan-voor-cryptohandel) states a EUR 1 purchase minimum and no minimum sale amount. Exact account/asset execution constraints still need review before configuration.
- The [public crypto asset PDF](https://www.degiro.nl/data/pdf/Overzicht%20Crypto%20Activa.pdf) returned HTTP 503 through both the web reader and an independent direct HTTPS fetch. Broker IDs from search snippets are not treated as verified account identities.

Exact BTC/ETH quantity steps, applicable spread allowances, account-specific broker identities/constraints and durable database configuration remain release gates. No schema mutation, private account access, deployment or trade was performed. The hosted form clears old previews when funding, split, targets or accepted generation changes; late results cannot restore superseded suggestions.
