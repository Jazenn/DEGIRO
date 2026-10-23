# Estimated cash-flow-adjusted return

The observed-history worker calculates one Modified Dietz estimate for each
consecutive completed UTC day, then multiplies the daily growth factors. It does
not annualize the result. Percentage cutoff and selected interval are displayed
separately from current intraday EUR holdings.

For opening equity B, closing equity E and signed external flows C:

`daily return = (E - B - sum(C)) / (B + sum(weight * C))`

`weight = seconds remaining until 00:00 UTC / 86400`

Deposits increase C and withdrawals decrease it. An endpoint flow has zero
remaining-interval weight; a flow already included in opening equity is excluded
from the following interval. EUR1,000 growing to EUR1,100 followed by a EUR500
endpoint deposit produces EUR100 gain and 10%, with denominator EUR1,000.

External-flow classification is the normalized canonical ledger classification.
Amounts use its preserved exact source decimals and dated FX evidence. Source
identity, date, nonblank time, reviewed broker timezone and unambiguous DST
localization are required. Each interval's flow sum must reconcile with the
canonical net-contribution change. Transaction records are never rewritten.

Missing daily valuations, unverified flows, unknown/DST-ambiguous timing or a
nonpositive denominator withhold the affected selected-period percentage. No
available days are linked across an unknown interval. Intraday first funding
can have positive weighted capital; endpoint first funding cannot. When the
verified zero opening baseline is followed only by known unfunded days and
endpoint deposits, the percentage can explicitly begin at the first funded
daily opening. The UI labels this supported start and the excluded prefunding
intervals, retaining the original EUR chart and attribution endpoints. Missing
observations, invested days and post-withdrawal gaps are never skipped. A fully
withdrawn account can resume with independently eligible intraday funding, but
an intervening day without positive capital remains unavailable. Percentage
unavailability does not erase independently verified EUR results.

The UI calls the figure an estimate: daily cash-flow timing is approximated, so
it is not exact intraday time-weighted return. Exact daily denominators, signed
flows and fractions remain inspectable with the observed-history details.
Historical coverage limits in `docs/research/observed-history-coverage.md` still
apply; no percentage is inferred from current quotes alone.
