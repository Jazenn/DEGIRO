# Reached Crypto Stage review and bounded cost estimates

The same eligible current EUR quote reviews every reached unfinished accepted
stage, including gaps:118k reaches100k and115k, not125k. It never records a sale,
reserves quantities, rearms a completed identity or changes accepted levels.
Quotes need a verified provider observation time and expire after five minutes;
retrieval time cannot refresh their age. Missing public daily history leaves
accepted plans readable and does not block review of an independently fresh quote.

The canonical Python read model publishes `disposal_cost_projections[asset_id]`.
These immutable cumulative quantity/cost breakpoints describe CURRENT remaining
FIFO inventory after actual imported disposals, including acquisition fees. They
carry broker identity, ledger/calculation/financial-settings versions, source ledger
cutoff, cost coverage and supported quantity range. Generic80-digit interpolation
of C(end)-C(start) consumes this accounting output. The Worker never orders raw
lots, allocates acquisition fees or replays Transactions. Missing coverage or
provenance/range mismatch means profit unverified, never average cost or zero.

## Precision contract and proof scope

This is a bounded estimate for at most three hypothetical accepted-stage disposals,
not a promise of bit-exact arbitrary future partial-fill accounting. Actual sales
continue through Python's40-significant-digit ledger. A6-unit lot costing1 euro
demonstrates a1E-40 difference between the second sequential actual disposal and
independently rounded cumulative endpoints; the interval must include it.

Let N be the number of remaining segments (at most4096), C the sum of their
nonnegative recorded costs, and u40=5e-40, the relative rounding unit of a normal
40-digit half-even operation. Eligibility requires each positive lot quantity
<=1e18 and an exact common quantum1e-18; requested interval endpoints use the same
quantum. Thus every positive quantity sum/residual has fewer than1e40 integer
quantum units (4096*1e36=4.096e39). All canonical quantity additions/subtractions
are exact at40 digits. This restriction is essential: tiny quantity roundoff times
a steep cost slope can otherwise exceed a cost-only rounding bound by many orders.
The discovered tiny-cheap-lot/steep-lot counterexample is explicitly rejected.

Each cost operand is finite/nonnegative, <=1e18, at most40 significant digits and
scale<=40. The authoritative current quantity and retained cost must equal the
80-digit endpoint sums exactly. Endpoint sums have fewer than63 significant
digits; source values and all supported intermediate products/ratios remain far
inside Python Decimal's normal exponent range (no underflow/overflow). Consumers
validate the declared range, common quantum, endpoint identity and minimum bound.

For a partial removal with exact quantity ratio a in[0,1], rounded multiply/divide
introduce at most(2u40+u40²)*current_cost absolute error. Residual subtraction adds
at most u40*current_cost (using the conservative pre-subtraction magnitude), and
the remaining-cost map is nonexpansive in prior absolute cost error. Across at
most three removals, using current_cost<=2*original_cost gives a conservative
40u40*original_cost bound per segment for any one stage's consumed cost. Summing
N nonnegative contributions adds less than2Nu40*C. Guard-digit interpolation and
outward-bound additions at80 digits are dominated by the remaining margin.
The published bound is B=100*(N+1)*u40*max(1,C), rounded outward. Consumers must
not accept a smaller bound, extrapolate, apply more than three hypothetical
disposals or claim verification outside the source ranges. Unsupported precision
only disables the estimate; it does not round or erase canonical source records.

Profit-taking is labelled estimated with verified inputs only when displayed
net-proceeds LOWER bound exceeds displayed cost UPPER bound. Monetary display
bounds are rounded outward to EUR cents; boundary ambiguity stays unverified.
The center estimate and lower/upper ranges are explicit. Mandatory actual
canonical goldens500-5-480=15 and500-5-520=-25 remain covered. Differential tests
compare actual sequential canonical disposals with projected intervals, including
repeating ratios and maximum segment-count/quantity-scale boundaries.

## Quantity, fees and runtime integration

Completed matched quantities have already left imported holdings and are never
subtracted a second time. Outstanding reports reserve quantities against current
holdings/core and stage remainders. Pending unmatched execution ordering withholds
cost verification. A changed ledger requires explicit execution reconciliation;
new purchases never resize accepted stages. The #58 operation layer supplies
coherent durable progress: global and per-stage pending/matched quantities plus
the reconciled ledger version. Unknown/manual reductions suspend suggestions.

`hosted/crypto-stage-schema.sql` adds reviewed ALL-IN SALE charges and spread
allowance evidence, separate from purchase tariffs. Dated sale permission,
quantity-rule revision and fee/spread evidence must match the accepted plan and
current review time. Missing or expired fees/costs stay unverified. No cost facts
or defaults are seeded and no infrastructure was changed by this implementation.

The owner-only same-origin POST `/api/crypto/stages/preview` reads plan, accepted
generation, current sale permission and cost revision in one SQL MVCC statement;
supplied stale generation/plan versions are rejected. Manual net proceeds are
suggested for ETF contribution review; no broker execution or automatic funding
occurs. Deployed SQL/CPU/provider latency and actual broker identity, precision,
tariff and coverage evidence remain explicit delivery gates.
