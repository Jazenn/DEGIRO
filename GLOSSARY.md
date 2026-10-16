# DEGIRO Portfolio

A personal investment tracking dashboard for monitoring DEGIRO portfolio performance, asset allocation, rebalancing targets, and crypto scaling strategies.

## Language

**Transaction**:
A single executed record of an asset purchase, sale, dividend, or fee from DEGIRO.
_Avoid_: Order, trade, entry

**Asset**:
A financial holding in the portfolio (Stock, ETF, or Cryptocurrency) identified by an ISIN or ticker symbol.
_Avoid_: Product, instrument, item

**Portfolio History**:
The daily time-series of total portfolio valuation, invested capital, and cash balances computed from transactions and closing prices.
_Avoid_: Performance log, equity curve

**Snapshot**:
A point-in-time pre-computed record of market prices, asset values, and portfolio metrics stored in the database for instant retrieval.
_Avoid_: Cache dump, raw state

**Rebalancing Target**:
The configured target percentage allocation of an asset in the portfolio used to calculate rebalancing buy/sell actions.
_Avoid_: Goal, quota, target weight

**Crypto Scale**:
A tiered price-threshold strategy for taking profits or accumulating crypto allocations based on predefined price bands.
_Avoid_: Ladder, scaling diagram
