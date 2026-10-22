# Useful dashboard UI prototype

Decision: [Validate a useful ETF and crypto dashboard prototype](https://github.com/Jazenn/DEGIRO/issues/37).

Question: which information hierarchy makes portfolio results, monthly contribution choices and Crypto Scale easiest to understand on a phone, while remaining useful on a laptop?

This is a throwaway rendering experiment on the existing root route. It uses explicitly fictional fixtures and in-memory interactions. It never calls a portfolio endpoint, reads browser financial storage, imports the private Account.csv, or executes/saves a Transaction. The ordinary root route is unchanged. The prototype route and switcher are enabled only in Vite development mode, so use the development command rather than a production preview.

## Run

Latest user direction: **D combines A's layout, B's fixed bottom navigation and C's blue-grey palette**. Open [the combined direction](http://127.0.0.1:5174/?prototype=1&variant=D). The original A/B/C alternatives remain available for comparison. D is also the default when no variant is specified. The combined result still needs visual feedback; no production implementation is implied.

From this branch/worktree:

```sh
npm install
npm run prototype
```

If dependencies are already installed, only the second command is needed. Open:

- [A: quiet overview](http://127.0.0.1:5174/?prototype=1&variant=A): portfolio and gain first; chart and next contribution alongside each other on desktop.
- [B: action first](http://127.0.0.1:5174/?prototype=1&variant=B): monthly choices first, editorial hierarchy and bottom navigation.
- [C: workspace](http://127.0.0.1:5174/?prototype=1&variant=C): holdings-first workspace with a desktop navigation rail and denser working view.
- [D: selected combination](http://127.0.0.1:5174/?prototype=1&variant=D): A hierarchy, B bottom navigation and C palette.

The bottom switcher and keyboard arrows change the URL variant. Arrows inside inputs do not switch layouts. The scenario selector exposes fee/reinvestment examples, stale prices, missing history, a jump across stages and an illustrative partial stage. The state panel exposes the full relevant in-memory state. Reloading resets it.

## Try

1. Change the period. The gain breakdown and chart change together. Current holdings remain current and are labelled as such.
2. Open the gain explanation and load the Bitcoin sale-to-ETF example: EUR 1,350 value and EUR 350 gain. The historical purchase-fee scenario shows EUR 1,100 value, EUR 1,005 cost and EUR 95 gain.
3. Enter a contribution. Choose ETFs, crypto or a mix. Whole-share ETF suggestions, fictional costs, rounding cash and crypto allocation impact update. These are reviewable examples, not broker tariffs or executed purchases.
4. Open Crypto, accept the example plan, and adjust the core slider. Existing stage prices and original quantities stay fixed until explicitly accepting a replacement plan. BTC and ETH retain separate plans and reported-stage state.
5. Report a stage. It becomes unavailable to report again in that plan and is labelled as awaiting imported-Transaction reconciliation. Switch coin and return: the prior report remains.
6. Switch to missing history. Existing accepted levels remain read-only; no new suggested levels appear. Stale prices disable accepting/reporting stages, and simulated refresh failure preserves prior figures.

## Illustrations awaiting decisions

All prices and plotted paths are generated fixtures, not evidence of investing performance. Period examples assume contribution at their start, allowing a simple illustrative percentage. They do not implement the production cash-flow timing/Modified Dietz contract. No actual refresh latency is measured by the 750 ms simulation.

Crypto zone candidates use linear-interpolated empirical quantiles of 365 fictional daily prices: purchase percentiles 35/20/10 and sale percentiles 75/90/95. Last-90-day extrema provide context. The 50% core and three 25%-of-original-tactical sale stages are example settings to react to, not approved personal allocations or established profitable rules. Three stages leave 25% of the original tactical portion without a sale stage. Accepted plans do not follow quote updates automatically.

The partial-execution scenario only illustrates status copy, not a completed import/matching workflow. Provider integration, real data coverage, production formula correctness, timestamps, timezone/DST policy, stage reconciliation, maximum exposure controls, old-plan history, storage/conflicts, authentication and automatic refresh are not implemented. Prototype feedback must not be treated as validating those systems. The final specification decision remains open.

## Review status

UI source builds. Browser review covers all three variants at 390 px and 1440 px, contribution editing, accepted-stage stability, independent BTC/ETH state, duplicate-report prevention, missing-history plan visibility and both approved arithmetic examples. Screenshots are visual review artifacts, not financial correctness tests. No prototype tests are added. User verdict is pending; do not merge or promote this code to production.
