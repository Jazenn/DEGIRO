# ETF contribution planning

`POST /api/contribution` is an owner-authenticated, same-origin, read-only preview. The browser sends only its chosen EUR budget and displayed generation/settings identities. One database read observes the accepted immutable generation, shared targets and reviewed execution terms. Any generation or target mismatch rejects the preview until the owner refreshes; saving targets does not silently apply them to older displayed holdings.

The pure `planContribution` seam uses exact Decimal arithmetic. For every ETF with a positive shortfall, desired value is `(all holdings market value + contribution) * target percentage`; shortfall is desired less current value. It divides the budget proportionally across positive ETF shortfalls, capped by each shortfall. Output order is descending shortfall and ascending broker Asset identifier for ties. Every envelope includes the purchase's fixed/rate/minimum fee, conservatively rounded up to cents. Integer bisection finds the largest verified quantity-step multiple fitting that envelope. Minimum quantity/notional requirements may produce no purchase. Rounding remainder stays cash, rather than being redistributed by a hidden tie-breaking rule. Existing cash never expands the budget; no sales or borrowing are suggested.

Before/after allocation includes every holding, including crypto and any Long-Term Crypto Core. Percentages describe holdings market value; unspent contribution cash and purchase fees are stated separately. A preview does not create a Transaction or change shared holdings. All reference quote observation times, fee status, terms revisions and source evidence remain visible. Current broker prices and actual charges still need review when manually acting in DEGIRO.

The preview also shows before/after deviations in percentage points from each
Rebalancing Target. Negative means below target; positive means above target.
Deviations use the unrounded allocation calculation before presentation rounding;
an unavailable allocation or absent target produces an unavailable deviation.
Expand **Quote times and reviewed execution terms** to inspect each suggested
purchase's quantity step, minimum quantity and minimum EUR notional alongside
the dated evidence. These are the same constraints used to size the purchase.

Synthetic workflow checks exercise the preview service through the visible form:
unknown fees or missing prices produce no purchases and retain the contribution
as unallocated cash; zero and too-small budgets produce no purchases and charge
no fees. A hand-checked EUR101 contribution buys one EUR100 unit plus EUR1 fee,
moving a EUR100/EUR100 portfolio toward 75%/25% targets to 66.6667%/33.3333%.
Its deviations move from -25/+25 to about -8.3333/+8.3333 percentage points.

Apply `hosted/contribution-schema.sql` only to an approved branch. Worker access is SELECT-only. A reviewer must populate asset/broker/venue-specific EUR execution terms, quantity precision and minimums with dated all-purchase-charge evidence and explicit validity dates. There are no guessed broker tariffs, free-trade assumptions or fractional-share defaults. Fees can be explicitly known from a reviewed schedule or clearly estimated from reviewed evidence; an unsupported charging model remains unavailable until modeled. Missing price/fee/precision evidence returns an incomplete preview with no purchases and unknown fee totals, rather than a cost-free result. No real tariffs or account-specific terms were verified or installed by this ticket.

The hosted form clears its preview after budget, target or generation changes and while refreshing. Late responses cannot repopulate suggestions from a superseded generation. A stale response from the API prompts refresh. Durable terms deployment, actual broker term verification, private portfolio reconciliation and phone/laptop live checks remain release gates; no schema mutation or deployment was performed.
