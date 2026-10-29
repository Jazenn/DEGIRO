# Useful DEGIRO dashboard: implementation handoff

Status: approved ready-to-build specification, 22 October 2026. No production code or infrastructure changed. This is a delivery plan and contract index, not proof that integrations pass.

Decision owner: [Agree the overhaul specification and implementation sequence](https://github.com/Jazenn/DEGIRO/issues/38). Map: [Useful DEGIRO Dashboard and ETF/Crypto Overhaul](https://github.com/Jazenn/DEGIRO/issues/25).

## Authoritative product decisions

Read each ticket's resolution, not historical proposals in isolation. Later explicit corrections supersede earlier proposals.

| Concern | Authoritative decision |
| --- | --- |
| First-version workflows and exclusions | [Choose the dashboard questions and first-release priorities](https://github.com/Jazenn/DEGIRO/issues/34) |
| Gain presentation, periods and sale/reinvestment examples | [Choose asset performance calculations and explanations](https://github.com/Jazenn/DEGIRO/issues/29) |
| Historical fees versus market value | [Choose fee insights and long-term projection scope](https://github.com/Jazenn/DEGIRO/issues/30) |
| Private access, shared state and coherent fast refresh | [Choose the frontend and backend overhaul boundaries](https://github.com/Jazenn/DEGIRO/issues/36), including its fast-refresh correction |
| Selected visual direction and interactions | [Validate a useful ETF and crypto dashboard prototype](https://github.com/Jazenn/DEGIRO/issues/37) |
| Crypto intent, proceeds and contribution funding | [Choose Crypto Scale rules and the long-term core boundary](https://github.com/Jazenn/DEGIRO/issues/35) |
| Exact crypto-level convention and plan safeguards | [Set adaptive crypto price rules and plan safeguards](https://github.com/Jazenn/DEGIRO/issues/39) |

The prototype branch is a visual/interaction reference with synthetic data, not production code to merge. Its example fees, core split, stage quantities and percentage returns do not override the decisions above.

This approved handoff and its linked decisions supersede conflicting instructions in `docs/specs/degiro-dashboard-overhaul.md` and `docs/specs/backend-architecture-overhaul.md`. Retain those documents as historical context with prominent supersession notices. No guaranteed zero-latency, sub-50ms refresh, permanently free service or verified complete free-data coverage is established.

## Delivery sequence approved in live discussion

1. Canonical accounting, normalized imports, historical fee handling and explicit price/calculation contracts.
2. Private hosted access and durable, versioned settings and plans shared across devices.
3. The selected responsive dashboard, real-data overview, performance explanations and costs; coherent fast current revaluation and separately dated history. Develop the visual shell alongside steps 1–2.
4. Monthly contribution planning and trustworthy ETF exposure/overlap where source data supports it.
5. Crypto suggestions, explicit Accepted Crypto Plans and execution reconciliation over the established accounting/shared-state modules.

Implement in independently reviewable increments. Keep the current dashboard available until the replacement passes reconciliation and access checks. A phase is not complete merely because its UI renders.

## Calculation contract

Retain React/Vite, Neon and modular Python ingestion/provider/persistence foundations. One canonical Python ledger owns Transaction interpretation, cash, FIFO purchase lots, fee allocation and historical accounting. It accepts normalized records, observed prices/provenance, settings versions and a valuation cutoff; returns validated read models and coverage diagnostics. Provider/network/persistence work stays outside its calculation interface.

A bounded server-side current revaluation may consume its versioned positions/cost/income/realized-result output and a quote batch. It does not replay Transactions or implement competing fee/FIFO rules. Reconcile its output against the canonical engine with common examples.

- Market value is quantity times price. Future selling costs do not reduce today's market value.
- External net contributions are deposits minus withdrawals, excluding sales, purchases, reinvestment, dividends and internal account sweeps.
- For a fully covered interval, net investment gain is `end equity - start equity - net external contributions`. Equity includes cash and holdings. For all-time results require a verified opening baseline; do not assume missing opening capital is zero.
- Remaining FIFO lots include allocated purchase fees. Realized sale gain uses net sale proceeds less disposed fee-inclusive lot cost. Held gain uses current market value less retained fee-inclusive lot cost. Income and portfolio-only charges are separately attributed.
- Include income/withholding/FX/account charges through one consistent ledger treatment; label gross/net income and attributed expenses so the sum reconciles to the equity bridge. Never subtract a fee twice because it appears inline and as a separate record, or is already reflected in cash. Embedded fund expenses are not charged again.
- Period gain is a change over the selected interval, not the all-time held/sold totals merely relabelled. Changes in retained unrealized gain, realized gain, income and expenses must reconcile across both endpoints. Closed Assets remain visible in period attribution.
- Use decimal money/quantity arithmetic internally and explicit display/execution rounding. Broker precision/minimums are verified before presenting executable quantities. Missing purchase cost withholds affected gain, not the observed market value.

### Percentage estimate — approved convention

For completed daily intervals ending 00:00 UTC, use the approved Modified Dietz estimate:

`r = (V_end - V_start - sum(CF)) / (V_start + sum(w * CF))`

`CF` is a signed external cash flow and `w` the fraction of the interval remaining after its verified timestamp. Link consecutive supported intervals with `product(1 + r) - 1`; do not annualize by default. Label the percentage as estimated cash-flow-adjusted return, not exact intraday TWR or a tax calculation. Display finalized percentage cutoff separately from newer current EUR figures; first version does not improvise a partial-day percentage.

Source timezone/DST must be verified before converting imported timestamps to UTC. Unknown or ambiguous timing, missing opening/closing values, unresolved flows, missing required valuations or a nonpositive denominator makes the affected percentage unavailable. Do not invent flow times or compound across an unknown interval. Establish a verified first-funded baseline; split valid sequences after a complete withdrawal/refunding rather than linking an undefined return through zero capital. Any fallback timing convention needs an explicit reviewed decision.

On 29 October 2026 the owner explicitly chose the fallback convention `Europe/Amsterdam` after confirming independent timezone evidence was unavailable. This supersedes the verification requirement for that configured assumption only. Preserve `verified=false`, record explicit approval and dated evidence, display that Transaction times and dependent results use an owner assumption, and continue rejecting missing/ambiguous/nonexistent times. Other source coverage and reconciliation gates remain mandatory. See the [accounting timing contract](decimal-accounting-contract.md).

Supported views: all time by default; YTD, 1Y, 3M, 1M and 1W. For rolling calendar periods use UTC calendar boundaries ending at the most recent completed daily cutoff; YTD starts at 1 January UTC, calendar month/year subtraction clamps to the last valid day. Indicate shorter verified coverage explicitly; do not claim a full period when its opening valuation is absent. Chart and selected-period EUR attribution share the same endpoints. Current holdings remain separately labelled current.

### Historical and current price quality

Record Asset identity, kind, currency, source timestamp, provider, retrieval timestamp, adjustment basis and coverage. An aggregate crypto reference price is not a promised executable DEGIRO price.

Use observed unadjusted prices with explicitly reconciled splits/quantity changes and actual cash distributions; do not combine dividend-adjusted total-return prices with separately counted dividends. FX conversion must be dated and source-labelled; missing FX makes the dependent EUR valuation unavailable. Verify broker/source corporate-action conventions before publishing affected intervals.

For a normal ETF market closure, the last observed official close can carry forward with its original date and a market-closed label. Unexpected provider gaps are not closures, zero prices or invented chart movements. Crypto history follows its approved seven-day window convention. Incomplete historical coverage blocks the affected calculation and shows the reason.

### Coherent valuation and quote freshness

Publish one generation atomically, recording ledger-through, ledger/settings/calculation versions, valuation time, calculation time and per-Asset quote-as-of/provenance/quality. Browser fetch time is never the price timestamp. Current holdings, held/total gain, allocation and contribution previews update together. Different source timestamps remain visible; a coherent batch does not imply every market supplied a simultaneous observation.

Approved first-version crypto prompt eligibility: a valid timestamped reference quote no more than five minutes old. Older/unknown timestamps preserve the view with a stale label but disable current target-reached prompts. This is an operational guard, not an investment horizon or a continuous monitoring promise. Existing executed/pending reports remain readable and actual Transaction imports remain available when quotes are stale.

Refresh current quotes on open/manual request, with a short server cache and bounded concurrent provider calls. Polling/background notifications are not required for the first version. Stop abandoned requests and avoid keeping free-tier compute active for hidden tabs. Full imports/history repairs run independently in the background, including crypto daily history on weekends.

Use a ten-second interactive request budget as the approved initial failure-handling default: show a timeout/partial-source diagnostic and keep the previous coherent generation, rather than silently waiting minutes. Normal current refresh aims for seconds; benchmark cold/warm authenticated reads, provider calls, computation and mobile end-to-end separately. Do not claim the budget is an achieved speed.

## Contribution and exposure acceptance

User chooses ETF/crypto/mixed contribution and BTC/ETH/both. Respect the chosen budget, recorded/clearly estimated fees, verified precision and no negative quantities. Display unspent remainder; never silently sell an Asset or increase budget to fund purchases. An unknown fee means an estimate is incomplete, not zero. Allocation consequences include the retained crypto core.

ETF allocation uses the user's Rebalancing Targets with buy-only shortfalls; order-size rounding must preserve budget. Any tie-breaking or leftover allocation is deterministic and visible, not described as optimal returns. Require target configuration to be valid before a recommendation.

ETF look-through uses dated fund/provider facts and coverage labels. Overlap comparisons require compatible underlying holdings and report the covered fraction/date. Do not infer precise current exposure from incomplete or incompatible datasets. Advanced risk statistics, projections and a strategy simulator remain outside the first release.

## Durable state, security and migration

Candidate hosting remains Cloudflare Workers Static Assets plus Neon; prove fit before deploying private data. On 23 October 2026 the owner replaced the email-code/Cloudflare Access preference with Google sign-in and authorized choosing the simplest genuinely free implementation, without payment details or a purchased domain. Direct Google OpenID Connect is the selected approach; retain owner-only server authorization and remembered sessions capped at one month. Clerk was considered but its production custom-domain requirement does not fit the owner's `pages.dev` hosting. This supersedes the identity-provider and email-code details of the earlier decision, not the shared-state or server-only credential requirements. Account provisioning and deployment are not performed by this planning artifact.

Authorize every read/write, verify identity tokens, protect alternate preview/version routes and keep database/GitHub credentials server-side. Use version-checked writes; reject stale edits rather than losing another device's plan/settings changes. Snapshot/plan generations must reference the reconciled ledger they use.

Crypto stage status is not inferred from price alone. Imported executions and user reports match explicitly; ambiguous matches require review. Duplicate reports/imports cannot consume quantity twice. Partial fills retain remaining stage quantity. Cancellation or corrected/reversed records preserve audit history and trigger recalculation/review, not automatic rearming. Manual sales that violate expected quantities suspend actionable suggestions until reconciled. Replacements preserve previous plan/execution identities. Follow the authoritative crypto decision for sizing, core protection and crossed-level review.

Before cutover: private export/backup, sanitized verification examples, new versioned storage alongside the current generation, matched-cutoff comparisons and demonstrated restore/rollback. Reconcile holdings, cash, costs and flows against source records; differences from old calculations require an explained reconciliation, not blind preservation of old bugs. Switch one complete validated generation, retain rollback, and retire duplicate financial runtimes only after acceptance. Never publish private financial fixtures or secrets to the public repository/issues.

## Delivery gates and evidence

| Gate | Evidence required before dependent functionality is complete |
| --- | --- |
| Accounting | Hand-calculated examples plus representative private source reconciliation: purchase/sale/partial-sale fees, income, FX, deposits/withdrawals, same-time ordering, repeat/overlapping imports, corrected records and cash sweeps. No lost legitimate duplicate-looking fills. |
| Gain examples | EUR1000 purchase + EUR5 fee, value EUR1100 => EUR95 gain. Approved BTC-to-ETF example => EUR1350 value/EUR350 total gain. EUR100 growth + EUR20 income - EUR5 costs => EUR115 gain. |
| Percentage | EUR1000 to EUR1100, then EUR500 endpoint deposit => EUR100 gain/10% return; verify intraday weights, DST, first funding, full withdrawal, unknown intervals and nonpositive denominator unavailable states. |
| Historical data | Actual ETF/crypto EUR coverage, timestamps, calendars, distribution/split/FX handling and required rolling-year crypto window. An infeasible provider contract returns for decision. |
| Current valuation | Canonical/projected reconciliation, atomic values/gain/allocation updates, truthful stale/timeout behavior, separate history job state and measured warm/cold/mobile latency. |
| Hosted access | Valid owner login, unauthenticated/unauthorized read/write rejection, alternate-route checks, no privileged client secrets, Worker-to-Neon connectivity, actual free-tier usage and recovery/export. |
| Shared plans | Cross-device edits and conflicts, independent BTC/ETH settings, retained core, original quantities, all-stage coverage, gaps, partial/manual/reversed executions, idempotent matching and explicit replacement history. |
| Contribution/exposure | Budget/fees/precision/remainder invariants, no forced sales, BTC/ETH/mix choice, before/after allocation and honest look-through coverage. |
| Migration/mobile | Phone and laptop workflows, old dashboard retained until cutover, explained reconciliation differences and demonstrated rollback/restore. |

No live integration, deployment, benchmark or financial reconciliation has been performed for this handoff. A failing check that only needs a technical fix stays implementation work. A failure that requires changing an approved contract, cost constraint or product behavior returns for an explicit decision; it must not be silently waived.

## Final agreement

The user approved the build order, migration approach and observable completion checks, followed by finalized daily percentage cutoffs/unavailable states, five-minute crypto quote eligibility, a ten-second interactive request timeout and the ready-to-build distinction. Delivery gates are mandatory implementation acceptance checks. They are not evidence of completed integration, measured performance or authorization to provision accounts, enter payment details or deploy.

The planning destination is reached. Start with canonical accounting and data contracts while developing the visual shell; revisit an approved requirement only if implementation evidence exposes a new decision.
