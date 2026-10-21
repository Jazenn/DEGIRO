# Useful portfolio analytics and free-data feasibility

Research date: 21 October 2026. Scope: a personal, read-only dashboard for long-term ETF investing and a separately defined Bitcoin/Ethereum strategy. These are decision inputs, not an approved feature specification or evidence of a profitable trading strategy. Resolution asset for [Research useful investor analytics and free data feasibility](https://github.com/Jazenn/DEGIRO/issues/31).

## Evidence and useful questions

### What have my investments earned?

Portfolio value growth combines investment outcomes and money added or withdrawn. Present net contributions separately from euro investment gain. Time-weighted return removes the effect of external cash-flow timing; money-weighted return reflects the timing and size of the investor's cash flows. Both answer useful but different questions. Reliable valuations and dated cash flows are prerequisites; missing history must be visible rather than fabricated. GIPS is used here for calculation concepts, not as a claim that this personal dashboard needs institutional reporting compliance. [GIPS handbook](https://www.gipsstandards.org/standards/gips-standards-for-firms/gips-standards-handbook-for-firms/), [GIPS investor reporting clarification](https://www.gipsstandards.org/qadatabase/4805/).

### What caused my gains or losses?

Product hypothesis: begin with a reconcilable euro bridge: opening value + net contributions + investment result = closing value. Then break investment result into asset contributions, income and explicit costs. Example using fictional numbers: ETF +€300, Bitcoin −€150, dividends +€20, fees −€10 gives €160 investment gain. A €1,000 deposit explains additional value growth but is not gain. Currency effects can become a separate explanation if suitable exchange-rate data exist; avoid counting them twice within asset gains.

This is accounting attribution: it explains where a result came from, not the economic reason prices moved. Realized versus unrealized results describe whether gains have been crystallized through sales, not an additional layer of gain to add again. Advanced benchmark attribution is a later decision, not a prerequisite for this useful explanation. Classification of portfolio boundaries matters: a sale into cash within the portfolio is not an external withdrawal. GIPS distinguishes external flows from investment income in its calculation guidance. [GIPS calculation explanation](https://www.gipsstandards.org/wp-content/uploads/2021/03/gips-handbook-3rd-edition.pdf).

### How concentrated am I, including overlap?

Counting ETFs does not measure diversification. Several funds can own the same companies. The SEC explicitly recommends checking funds' top holdings and explains sector and asset-class diversification. [Investor.gov allocation and diversification](https://www.investor.gov/introduction-investing/getting-started/asset-allocation).

Product hypothesis: show allocation across assets, sectors, regions and underlying companies, with separate levels clearly labelled. If 50% of a portfolio is in Fund A with 6% Apple and 30% is in Fund B with 8% Apple, the indirect Apple exposure is 3% + 2.4% = 5.4%, before any direct holdings. These are invented weights for illustration. Show holdings dates, coverage and unknown exposure. Top-ten holdings alone cannot establish complete overlap. Fund domicile and trading currency should not be silently treated as geographical company exposure or economic currency exposure.

### Where would my next contribution go?

Allocation drift changes portfolio risk. Rebalancing can use sales or additional contributions, with calendar or threshold approaches. [Investor.gov allocation and diversification](https://www.investor.gov/introduction-investing/getting-started/asset-allocation).

Product hypothesis: a contribution planner previews allocation before and after a user-entered contribution against their Rebalancing Targets, including cash and whole-share constraints. User-defined targets must remain distinct from an algorithm prescribing the right allocation. A long-term projection can explore contribution and return assumptions, explicitly as scenarios rather than forecasts.

### What am I paying?

Fees reduce amounts left invested; ETF prospectuses contain standardized fee information. [SEC fee bulletin](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/updated).

Product hypothesis: distinguish actual recorded transaction/currency/account fees from estimated ongoing fund expenses. Embedded expenses already affect fund valuation; subtracting an estimate again from recorded performance would double-count them. Show fee coverage and estimation assumptions.

## Crypto: support a complete plan before choosing charts

Crypto volatility does not establish predictability. AFM describes strong price fluctuations and the possibility of losing the full investment. [AFM crypto overview](https://www.afm.nl/nl-nl/consumenten/themas/crypto).

User clarification: BTC and ETH are held through DEGIRO. The desired workflow is price-based partial sales and rebuys, rather than a calendar schedule. The previous approach used annual minimum/maximum prices and staged 25% sales. Treat that as a design starting point, not a validated strategy: historical yearly extrema do not predict future tops or bottoms, and an unfinished year's final extrema are unknowable. Any simulation must use only extrema observable at its decision date. Also define whether 25% means the starting holding or the remaining holding.

Candidate interaction models to investigate with the user, not endorsed strategies:

- **Crypto Scale:** predefined staged price thresholds for partial sales and purchases, matching the existing glossary term.
- **Allocation bands:** review when crypto exceeds or falls below user-defined portfolio weights; this controls exposure rather than predicting price peaks.
- **Core plus tactical:** keep a defined portion held while another portion follows explicit sell/rebuy rules.

A complete plan needs both sides: what triggers a sale, quantity, reference price, rebuy trigger, cash destination, maximum exposure, and what happens if the price continues rising after a sale or keeps falling after a purchase. It also needs a rule for repeated threshold crossings and a record of completed transactions so a threshold does not repeatedly suggest the same action. These are product requirements inferred from the proposed workflows, not findings that any rule outperforms holding.

Candidate visuals: price with user-defined thresholds and completed transactions, cash reserved for re-entry, distance to the next condition, current versus maximum allocation, drawdown and recovery, and a journal of planned versus actual decisions. A historical drawdown measures decline from a previous peak; it is not a forecast of a bottom.

Net outcomes must include both sale and purchase costs. DEGIRO's Dutch direct-crypto page advertises 0.29% commission for each purchase and sale, excluding spreads; this is an observed public rate, not a permanent assumption for calculations. The page returned HTTP 503 when opened directly during this update, so the rate was verified through the search engine's indexed first-party page and should be checked against actual transaction records/current tariffs before implementation. DEGIRO's separate ETP page advertises €2 commission plus €1 handling, with possible additional costs. Do not apply ETP pricing to direct coins. [DEGIRO direct crypto](https://www.degiro.nl/zelf-beleggen/crypto-kopen), [DEGIRO crypto ETPs](https://www.degiro.nl/zelf-beleggen/crypto-etps).

If simulation is investigated, compare the explicit strategy with holding the same starting assets under identical cash flows, dates and costs. Show time in cash, asset quantities, turnover and drawdown alongside value. Use chronological evaluation and an untouched evaluation interval; do not optimize thresholds on the same period used to claim success. These are methodological recommendations. FINRA's investment-tool rule supplies a useful presentation principle: disclose methodology, assumptions, limitations and the hypothetical nature of results. It is cited as design guidance, not a legal determination for this Dutch personal project. [FINRA Rule 2214](https://www.finra.org/rules-guidance/rulebooks/finra-rules/2214).

## Questions still needed before specification

Platform is settled: DEGIRO. DEGIRO offers both direct crypto and crypto ETPs; holding crypto through this broker does not by itself establish which type the imported assets represent. Its official crypto-asset list dated 5 October 2026 identifies Bitcoin as BTC / XFC000A2YY6Q and Ethereum as ETH / XFC000A2YY6X. Match the actual imported identifiers and metadata before deciding trading hours, price sources and cost rules. [DEGIRO crypto-asset list](https://www.degiro.nl/data/pdf/Overzicht%20Crypto%20Activa.pdf), [DEGIRO direct and ETP distinction](https://www.degiro.nl/zelf-beleggen/crypto-etps).

Price conditions rather than a fixed schedule are settled; the remaining questions concern the rule itself. Does tactical mean all crypto or a bounded portion? What loss and cash exposure are acceptable? How are annual reference prices defined and reset, what defines a rebuy, and what happens when price moves beyond the historical range? Which holdings and historical data are actually available? Can complete ETF holdings be obtained and refreshed under the free-data constraint? These feasibility and personal-strategy decisions remain open.

## Bounded feasibility investigation

The following is a source-availability assessment, not an end-to-end integration test. The private account export was inspected locally only for asset identity and column availability; no account amounts, balances, transaction dates or records are reproduced. ETF identities were matched to the first-party pages below. BTC/ETH records have blank ISIN fields in this export, so the published XFC identifiers must not be presented as identifiers already verified from these imported rows. Current holdings cannot be inferred merely from an asset appearing in an account history.

### Public issuer data actually observed

| Issuer example | Verified first-party availability | Remaining uncertainty |
| --- | --- | --- |
| Vanguard FTSE All-World Accumulating, IE00BK5BQT80 | Dated holdings with company, sector, region and weights; geographical exposure; historical NAV/market-price table and download control. | Full download/parser not exercised. NAV currency and selected exchange listing must match the calculation purpose. No historical holdings archive or redistribution permission established. |
| iShares Core MSCI Europe EUR Acc, IE00B4K48X80 | Dated holdings section, Download Holdings control and schema including ISIN, weights, sector, currency; geographical and sector breakdowns. | Download attempted through browser tool but failed, so a usable CSV response is not verified. Historical date selector is not proof of full archival coverage. |
| Xtrackers MSCI World ex USA 1C, IE0006WW1TQ4 | Product page, current fee and documents. KID expressly says composition and latest share prices are available free. | An automated holdings export, historical holdings coverage and permission to republish were not verified. Fund launched in 2024; earlier index history is not actual fund performance. |
| HANetf Future of Defence, IE000OJ5TQP4 | Product page with ISIN, dated facts, accumulating treatment and NAV-history link; issuer factsheets disclose holdings/exposure. | Complete machine-readable holdings/history retrieval and reuse rights remain unverified. Do not substitute the similarly named Screened fund. |

Sources: [Vanguard exact accumulating share class](https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating), [iShares exact share class](https://www.ishares.com/ch/individual/en/products/251861/ishares-msci-europe-ucits-etf-acc-fund?tab=portfolio), [DWS product](https://etf.dws.com/en-lu/IE0006WW1TQ4-msci-world-ex-usa-ucits-etf-1c/), [DWS KID](https://etf.dws.com/en/AssetDownload/Index/73f2266f-b86c-4ec6-a80f-8ee675d176e5/DWS-PRIIPSKID-IE0006WW1TQ4-IE-en-2026-03-06.pdf), [HANetf exact fund](https://hanetf.com/fund/nato-future-of-defence-etf/), [issuer holdings factsheet example, historical rather than current](https://hanetf.com/wp-content/assets/upload/02-25-Factsheet-NATO-IE000OJ5TQP4-en.pdf).

Public viewing and downloads are not equivalent to an open data licence or a stable API. For these four issuers, permission for unattended retrieval, persistent redistribution and public hosting remains unverified. A private dashboard with manually refreshed dated snapshots is a plausible low-cost prototype; this investigation does not approve a production scraping pipeline. Store source, retrieval time, effective holdings date, coverage and parser version. Match securities by identifiers, handle cash and multiple share classes explicitly, and show unknown coverage instead of renormalizing a partial top-ten list into 100%.

### Per-feature decision inputs

These feasibility judgments and visual proposals are product hypotheses grounded in the earlier cited calculation/diversification/fee evidence. They do not select the user's priorities.

| User question / candidate visual | Minimum inputs | Free-data feasibility and limits |
| --- | --- | --- |
| What did I contribute versus earn? Value/contributions/result bridge | Complete external flows, opening and closing valuations, transfers and cash | High potential from private imports plus verified valuation snapshots. Reconcile totals first; an incomplete account period is not inception. |
| How did the investments perform? TWR plus personal MWR | Dated flows and sufficiently frequent valuations for TWR; final value for MWR | Conditional on historical prices and corporate-action correctness. Display method, period and annualization; IRR may lack a unique meaningful solution. |
| Which assets produced the result? Euro contribution bars | Quantities, prices, distributions, costs, cash and FX consistently tracked | Conditional. Reconcile asset contributions with portfolio result. Do not promise precise FX decomposition without a defined method and rates. |
| How much gain was sold versus still held? Realized/unrealized breakdown | Complete purchase/sale lots, fees, transfers, corporate actions and current prices | High potential without extra paid data for transaction arithmetic. FIFO is an accounting convention, not proof of tax liability; missing acquisition lots invalidate profit figures. |
| Where am I exposed twice? Underlying-company/sector/region bars and pair overlap | Full dated holdings with weights and identifiers; current asset weights | Current snapshots appear feasible at zero data purchase cost; complete automated coverage and historical overlap are unverified. Pair overlap can be defined as sum of minimum shared weights; portfolio exposure needs portfolio-weighted sums. Report which measure is used. |
| What does a contribution change? Before/after allocation preview | User Rebalancing Targets, current prices/cash, permitted increments and fee assumptions | High potential; no historical feed required. Whole ETF shares and fractional crypto differ. No automatic target-allocation recommendation follows from this. |
| What costs do I bear? Recorded costs plus labelled expense estimate | Import fee records; dated issuer ongoing charges; invested values over time | High potential for explicit fees; estimated embedded expenses only. Today's TER is not evidence of the rate in every previous year. |
| What income did I receive? Actual distributions and withholding timeline | Actual cash distribution/tax records, security classification | High potential for actual payments. Accumulating ETF internal dividends are reinvested inside the fund, not additional personal cash income; forecasting distributions is separate and uncertain. |
| How far have I fallen from a peak? Drawdown/recovery chart | Cash-flow-adjusted return series and reliable prices | Conditional on the performance series. Raw wallet-value drawdown is distorted by deposits/withdrawals. Historical maximum loss is not a worst-case future bound. |
| What could contributions mean over 30 years? Scenario fan/range | User horizon/contribution assumptions, explicit return/inflation/fee assumptions | High potential without a paid feed for deterministic scenarios. Scenario ranges are not probability intervals; calibrated probabilistic projections need a separate modelling decision. |

### Price history, FX and licensing constraints

The repository already uses yfinance for historical prices (`backend/providers/yahoo.py` and `backend/providers/__init__.py`). The maintainers state it is unaffiliated with Yahoo, intended for research/education and personal use, and direct users to Yahoo's data terms. Its software licence does not grant market-data redistribution rights. Therefore it is a candidate for this personal project, not a verified licensed public data service or complete-history guarantee. Correct exchange/currency mapping, split/dividend adjustments and missing-day handling require validation per asset. Adjusted prices plus separately credited distributions can double-count returns. [yfinance primary README](https://github.com/ranaroussi/yfinance).

ECB provides downloadable historical euro reference rates and daily publication on working days. Its reuse policy permits free reuse with attribution and conditions; these indicative rates are not actual execution prices. Use imported actual FX for transaction accounting where available and an explicit reference-rate convention for valuation, including weekends. [ECB reference downloads](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html), [ECB statistics reuse policy](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.es.html).

CoinGecko's first-party documentation states that free Demo historical access is limited to the past 365 days. That suffices for some recent views but does not establish multi-cycle BTC/ETH strategy evaluation. A separate source and its history/reuse terms must be verified before promising such a simulator. No free historical API was executed in this investigation; issuer download controls likewise establish availability signals, not successful whole-pipeline operation. [CoinGecko history limits](https://www.coingecko.com/learn/download-bitcoin-historical-data).

### Decision-ready conclusion

There is enough evidence to discuss contribution/result separation, euro attribution, explicit fees, contribution previews and cautiously labelled current exposure as useful candidates. Historical analytics depend on reconcilable data; complete historical ETF overlap, reliable multi-cycle crypto history and all-provider automated redistribution remain unverified. This resolves the bounded research question by identifying feasible candidates and constraints, not by selecting a feature list or claiming all free-data integrations are solved. The next product decision belongs to the user; any selected data-dependent feature needs a small end-to-end sample retrieval/reconciliation before implementation scope is committed.
