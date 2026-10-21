# Crypto Scale: staged sales and re-entry research

Date: 2026-10-21. Decision ticket: [Research staged crypto sales and re-entry strategies on DEGIRO](https://github.com/Jazenn/DEGIRO/issues/33).

## Research conclusion

Research supports an explainable, explicit plan and honest evaluation, not a claim that any indicator identifies profitable tops or bottoms. Compare fixed stages, the existing yearly-range idea, drawdown/trend context and allocation bands. Compare each on a tactical portion plus an untouched long-term core and on the entire holding. The user has approved investigating both structures, not any split, threshold or rule. ETF buy-and-hold remains a separate 30+ year policy.

The requirements and recommendations below are design deductions, not established profitable trading strategies. No historical simulation was performed; no app-generated Portfolio History was used as evidence.

## DEGIRO asset identity and execution

DEGIRO's official crypto-assets list dated 2026-10-05 identifies direct Bitcoin as BTC / XFC000A2YY6Q and Ethereum as ETH / XFC000A2YY6X. A DEGIRO identifier in an ISIN-shaped field does not establish that the asset is an exchange-listed tracker. Verify the user's records and category rather than relying on the phrase "listed product". [Official crypto-assets list](https://www.degiro.nl/data/pdf/Overzicht%20Crypto%20Activa.pdf).

DEGIRO separately describes direct crypto and crypto ETP exposure. Its ETP page distinguishes owning crypto from holding a listed asset that follows its price. ETP transactions follow exchange opening hours, unlike the underlying market. Hence the plan must attach to the actual holding's price, currency and executable venue, rather than substituting generic BTC/USD prices. [DEGIRO crypto ETPs](https://www.degiro.nl/zelf-beleggen/crypto-etps).

The Dutch direct-crypto and tariffs pages returned HTTP 503 during this investigation. Do not infer Dutch direct-crypto costs from ETP tariffs or another country's offering. Remaining verification before implementation: current commission, spread and any minimum fee; transaction minimum and fractional precision; available transaction instructions and execution hours; settlement/available-cash rules; export treatment and reliable quotes. Read the current account terms and tariff documents for the actual asset. [Direct crypto page](https://www.degiro.nl/zelf-beleggen/crypto-kopen), [Dutch tariffs](https://www.degiro.nl/tarieven). These links are verification entry points, not evidence that an exact fee has been confirmed.

## Candidate rule families

| Candidate | Explicit rule shape to evaluate | Main weakness or unresolved choice |
|---|---|---|
| Fixed price stages | Freeze named EUR sale and purchase levels at plan creation; attach quantities to each | Anchors can become obsolete; cost basis measures personal gain rather than market cheapness |
| Trailing yearly range | Compute low/high from preceding observed prices and place stages within that range | Range position is historical context, not valuation; levels move when old extremes expire |
| Drawdown and trend context | Track decline from an observed peak and/or price relative to a trailing moving average; optionally require recovery before purchases | A large decline can continue; waiting for recovery can mean buying higher; averages lag |
| Allocation bands | Review crypto exposure when outside a chosen band around a Rebalancing Target | Controls exposure, not price timing; other assets' moves and deposits can trigger it |

These are candidate specifications proposed here. Do not combine them into an opaque confidence score. For every candidate, describe the measurable condition, action, reason, and failure scenario in plain language.

The user's previous yearly-low/high and 25% stages are an understandable baseline. Specify daily close versus intraday extremes, EUR versus USD, observation timestamp, calendar days versus samples, and minimum history. A range score could be `(price - trailingLow) / (trailingHigh - trailingLow)`; if the denominator is zero or history is inadequate, report unavailable. Define whether the current observation enters the window. Freeze that convention before evaluation. A level can move across the price because an old extreme expires even when today's price barely changes; decide explicitly whether that triggers a review. None of this formula proves expected return.

A simple moving average is an average over a chosen past window; smoothing introduces lag. That makes it explainable trend context, not proof of a turning point. [Fidelity SMA definition](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/sma).

RSI is a momentum measure. Fidelity explicitly observes that it can remain overbought or oversold during strong trends. Its conventional levels should therefore be optional research candidates, not imported as proven BTC/ETH buy/sell thresholds. [Fidelity RSI definition](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/RSI).

Rebalancing returns exposure toward a chosen allocation. Investor.gov describes changing purchases or using contributions as alternatives to selling and notes costs and tax implications. This supports distinguishing an exposure-control goal from a price-timing goal; it does not establish which crypto allocation is appropriate for this user. [Investor.gov allocation and rebalancing](https://www.investor.gov/additional-resources/general-resources/publications-research/info-sheets/beginners-guide-asset).

## Core plus tactical versus entire holding

Core plus tactical means quantities are attributed to two policies even if held in the same DEGIRO account. Sales under Crypto Scale cannot consume the protected core. This preserves some participation if price rises after tactical sales, while leaving that core exposed to declines. It can reduce both upside and downside differences relative to holding, depending on the price path. Entire-holding rules can release more cash but can also leave the user wholly uninvested if all stages sell and re-entry never occurs. These are mechanical consequences, not forecasts.

Keep BTC and ETH quantities and cash attribution explicit. Decide whether reserved proceeds can buy the other asset, whether new deposits feed the core or tactical portion, and how manual transactions change each portion. Portfolio-wide exposure must include both portions. A protected core is not protected from market loss.

## A complete cycle requires persistent state

The following proposed requirements make the alternatives implementable and auditable:

1. **Plan version:** asset identity, price source/currency/timestamp, starting quantities, protected core, tactical quantity, stage rules and reference date. Changes create a version; they do not rewrite prior decisions.
2. **Stage sizing:** label whether a fraction refers to original tactical quantity, currently remaining tactical quantity, or a EUR budget. For 1 unit, four sales of 25% of the original sell the whole unit; four sales of 25% of the remainder leave `0.75^4 = 31.640625%`. Neither means selling "25% of profit". Show both units and estimated proceeds.
3. **Stage lifecycle:** armed, condition reached, awaiting user action, partially executed, executed, skipped, cancelled. Price reaching a level is not an executed Transaction. Reconcile imported transactions to user-confirmed actions without counting a duplicate import twice.
4. **Repeat crossings:** each stage fires at most once per defined cycle. Reopening the page or oscillating around a threshold cannot sell repeatedly. Rearming needs an explicit rule: a distinct recovery/reset level, a completed re-entry stage, or user confirmation. A cooldown alone does not define a new cycle.
5. **Gaps:** decide whether a price jumping across multiple levels suggests all crossed stages or only the next stage. A read-only dashboard presents a combined review; it never assumes fills at crossed prices.
6. **Cash:** reserve net sale proceeds for named re-entry stages; separate that cash from funds available for ETF contributions and other spending. A hypothetical reservation cannot exceed actual available cash. Do not fund a purchase with proceeds that have not become available.
7. **Re-entry:** specify price anchor (sale fill, frozen plan level, or trailing peak), budget, allowed quantity precision, and maximum total crypto exposure. Decide what happens if price never returns, or keeps falling after all budgets are spent. Waiting in cash is a possible outcome; borrowing and unlimited averaging down are not implied.
8. **Continued rises:** after each sale, show remaining participation and the alternative holding value. Define whether a deliberate new plan is required above the last stage; do not silently chase the market by rewriting targets.
9. **Data quality:** stale/missing quotes, uncertain asset identity, incomplete history, unmatched transactions or unknown execution constraints produce an explicit unavailable state rather than a confident action.

These are design proposals to take to the human decision ticket. They do not approve actual sale quantities or automatic execution.

## Profit, cash and total wealth are different

Illustrative arithmetic, ignoring costs: buy 1 unit for EUR 100 and sell 0.25 at EUR 200. Cash received is EUR 50, but realized gain under proportional cost allocation is EUR 25; EUR 25 is returned cost. Remaining value is EUR 150, so total wealth is EUR 200 immediately after the sale, exactly as before it. If price then reaches EUR 300 without re-entry, wealth is EUR 275 versus EUR 300 from holding. If instead it reaches EUR 100, wealth is EUR 125 versus EUR 100 from holding. Locking in a realized gain does not itself increase total wealth relative to holding.

For a sold quantity `q`, gross sale price `Ps`, and actual sale costs `Cs`, cash is `q*Ps-Cs`. Rebuying the same quantity at `Pb` costs `q*Pb+Cb`. The round trip releases excess cash only if `q*(Ps-Pb) > Cs+Cb`. Include spreads in execution prices or as costs, never both. Fixed fees penalize small stages; commissions, spreads, slippage, FX and any asset-specific ongoing charges belong in evaluation. Record tax treatment separately if applicable; this note does not assume a tax rule.

## Honest evaluation requirements

This is a proposed evaluation protocol, not reported results:

- Compare holding, whole-holding Crypto Scale, and core plus tactical using identical starting wealth, assets, contribution dates/amounts and withdrawal assumptions. Value all remaining holdings plus cash at the same timestamp. Model interest on cash consistently or show sensitivity.
- Use actual executable-asset history where available. Generic crypto spot history may illustrate a rule but cannot establish ETP fills or platform spreads. Distinguish theoretical signal price from attainable execution price and delayed human action.
- On each historical date, compute range, peaks, moving averages and allocation only from information available then. Never use the completed year's future high/low. Require a warm-up window; use a later executable observation after the signal when the signal depends on that close. Daily high/low data cannot reveal which of two crossed levels happened first.
- Lock candidate parameters before an untouched chronological evaluation period. Use multiple start dates and rising, falling and sideways periods. Keep a record of every tried configuration; a parameter sweep followed by displaying only the winner is misleading. Walk-forward evaluation is useful, but does not guarantee generalization.
- Report final wealth relative to holding in EUR and percent, maximum drawdown, time invested, cash balance, quantities retained, fees, turnover, number of actions, worst missed rally, and periods waiting for re-entry. Show combined total profit alongside realized/unrealized components.
- Include higher-cost and delayed-action scenarios, missing-data periods, gap handling and a continuous-rise scenario with no re-entry. Evaluate whole portfolios as well as the tactical portion so a small successful sleeve cannot hide an unsuccessful total outcome.

Bailey and coauthors document how selecting strategies from many historical trials creates backtest overfitting and discuss why ordinary hold-out methods alone can be unreliable for investment backtests. This supports treating historical evaluation as evidence with limitations, not certification of future profitability. [Original research: The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

## Next decisions and evidence gaps

Human decisions: whether the primary aim is reducing exposure, securing spendable cash, increasing crypto quantity, or outperforming holding; protected-core policy; stage denominator; cash destination; missed-re-entry policy; acceptable action frequency; candidate rules to prototype. Percentages and thresholds remain open.

Data prerequisites: reconcile actual DEGIRO BTC/ETH holdings, quantities and costs; verify current execution constraints and fee schedule; establish trustworthy historical prices and accounting. Only then estimate which comparisons are feasible. Research does not justify replacing these prerequisites with synthetic Portfolio History.
