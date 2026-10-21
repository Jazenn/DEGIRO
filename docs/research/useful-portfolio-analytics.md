# Useful portfolio analytics: preliminary research

Research date: 21 October 2026. Scope: a personal, read-only dashboard for long-term ETF investing and a separately defined Bitcoin/Ethereum strategy. These are decision inputs, not an approved feature specification or evidence of a profitable trading strategy.

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

Candidate interaction models to investigate with the user, not endorsed strategies:

- **Crypto Scale:** predefined staged price thresholds for partial sales and purchases, matching the existing glossary term.
- **Allocation bands:** review when crypto exceeds or falls below user-defined portfolio weights; this controls exposure rather than predicting price peaks.
- **Core plus tactical:** keep a defined portion held while another portion follows explicit sell/rebuy rules.

A complete plan needs both sides: what triggers a sale, quantity, reference price, rebuy trigger, cash destination, maximum exposure, and what happens if the price continues rising after a sale or keeps falling after a purchase. It also needs a rule for repeated threshold crossings and a record of completed transactions so a threshold does not repeatedly suggest the same action. These are product requirements inferred from the proposed workflows, not findings that any rule outperforms holding.

Candidate visuals: price with user-defined thresholds and completed transactions, cash reserved for re-entry, distance to the next condition, current versus maximum allocation, drawdown and recovery, and a journal of planned versus actual decisions. A historical drawdown measures decline from a previous peak; it is not a forecast of a bottom.

Net outcomes must include both sale and purchase costs. Coinbase documents variable trading fees and, for Simple Trade, an included spread. This is an example of cost structure, not an assumption about the user's platform or a provider recommendation. [Coinbase pricing disclosures](https://help.coinbase.com/en-au/coinbase/trading-and-funding/pricing-and-fees/fees), [Coinbase Advanced fees](https://help.coinbase.com/en-gb/coinbase/trading-and-funding/advanced-trade/advanced-trade-fees).

If simulation is investigated, compare the explicit strategy with holding the same starting assets under identical cash flows, dates and costs. Show time in cash, asset quantities, turnover and drawdown alongside value. Use chronological evaluation and an untouched evaluation interval; do not optimize thresholds on the same period used to claim success. These are methodological recommendations. FINRA's investment-tool rule supplies a useful presentation principle: disclose methodology, assumptions, limitations and the hypothetical nature of results. It is cited as design guidance, not a legal determination for this Dutch personal project. [FINRA Rule 2214](https://www.finra.org/rules-guidance/rulebooks/finra-rules/2214).

## Questions still needed before specification

Are Bitcoin/Ethereum actual coins on another platform, or exchange-traded crypto assets held through DEGIRO? This determines transaction imports, trading hours, valuations and available cost data. How often does the user want to review crypto? Does tactical mean all crypto or a bounded portion? What loss and cash exposure are acceptable? Which holdings and historical data are actually available? Can complete ETF holdings be obtained and refreshed under the free-data constraint? None of those feasibility or personal-strategy questions is resolved by this research.
