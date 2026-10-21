# Useful dashboard: three UI directions

Throwaway prototype for [Validate a useful ETF and crypto dashboard prototype](https://github.com/Jazenn/DEGIRO/issues/37). User review is pending.

Run `npm run prototype` from this prototype branch/worktree, then open <http://127.0.0.1:5174/?prototype=1&variant=A>. Use the floating arrow switcher or the keyboard arrows to compare layouts. All data, price paths, fees and crypto thresholds are explicitly fictional. No login, network portfolio connection, storage or financial execution is implemented.

| Direction | Hierarchy | Phone | Laptop |
|---|---|---|---|
| A — Quiet overview | Portfolio/gain first; chart and next contribution | [Phone screenshot](A-mobile.png) | [Laptop screenshot](A-desktop.png) |
| B — Action first | Monthly contribution and crypto choices first | [Phone screenshot](B-mobile.png) | [Laptop screenshot](B-desktop.png) |
| C — Workspace | Holdings table, sidebar and denser working view | [Phone screenshot](C-mobile.png) | [Laptop screenshot](C-desktop.png) |

Use the scenario menu to review the fee and Bitcoin-sale examples, stale/missing prices, multiple reached stages and partial-execution copy. The full scope and limitations are in the [prototype notes](../../src/components/PrototypeDashboard.README.md).

These screenshots and UI interactions do not establish correct production calculations, profitable investment rules, actual data coverage or real refresh latency. The prototype must stay on its throwaway branch. Feedback should identify a preferred hierarchy or elements to combine; it must not be treated as approval of the illustrative allocations or price thresholds.
