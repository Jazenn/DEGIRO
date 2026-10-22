# Useful dashboard: selected combination and original alternatives

Throwaway prototype for [Validate a useful ETF and crypto dashboard prototype](https://github.com/Jazenn/DEGIRO/issues/37). The user approved D's visual direction, BTC/ETH contribution choices and full tactical sale-stage coverage. Production numeric rules remain a separate decision.

The user's selected direction is **A's layout + B's bottom navigation + C's palette**, now combined as D. Run `npm run prototype` from this prototype branch/worktree, then open <http://127.0.0.1:5174/?prototype=1&variant=D>. Use the floating arrow switcher or the keyboard arrows to compare layouts. All data, price paths, fees and crypto thresholds are explicitly fictional. No login, network portfolio connection, storage or financial execution is implemented.

| Direction | Hierarchy | Phone | Laptop |
|---|---|---|---|
| D — Selected combination | A layout, B bottom navigation, C blue-grey palette | [Phone screenshot](D-mobile.png) | [Laptop screenshot](D-desktop.png) |
| A — Quiet overview | Portfolio/gain first; chart and next contribution | [Phone screenshot](A-mobile.png) | [Laptop screenshot](A-desktop.png) |
| B — Action first | Monthly contribution and crypto choices first | [Phone screenshot](B-mobile.png) | [Laptop screenshot](B-desktop.png) |
| C — Workspace | Holdings table, sidebar and denser working view | [Phone screenshot](C-mobile.png) | [Laptop screenshot](C-desktop.png) |

Use the scenario menu to review the fee and Bitcoin-sale examples, stale/missing prices, multiple reached stages and partial-execution copy. The full scope and limitations are in the [prototype notes](../../src/components/PrototypeDashboard.README.md).

Latest interaction previews: [BTC/ETH contribution split](D-contribution-mobile.png) and [adjustable full-coverage sale stages](D-crypto-mobile.png).

These screenshots and UI interactions do not establish correct production calculations, profitable investment rules, actual data coverage or real refresh latency. The prototype must stay on its throwaway branch. Feedback should identify a preferred hierarchy or elements to combine; it must not be treated as approval of the illustrative allocations or price thresholds.
