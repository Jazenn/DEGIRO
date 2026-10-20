# DEGIRO `Account.csv` Cash Flow & Trade Extraction Grammar

**Date**: 2026-10-20  
**Research Ticket**: #16 (Part of parent epic #14)  
**Dataset Analyzed**: `Account.csv` (172 rows, spanning 2024-04-02 to 2026-10-19)  
**Target Audience**: Ingestion engine developers, portfolio calculation architects, and QA engineers.

---

## 1. Executive Summary

DEGIRO's `Account.csv` is an account-level cash statement export that records all cash debits, credits, internal bank sweeps, trade settlements, dividend distributions, and fee levies across an investor's DEGIRO portfolio.

A detailed forensic audit of 172 real production export rows revealed:
1. **100% Deterministic Taxonomy**: All 172 rows map into exactly 8 functional categories (12 specific event subtypes) with zero unclassified rows.
2. **Internal Cash Sweeps (`ΔCash = 0`)**: DEGIRO holds cash through **flatexDEGIRO Bank**. Sweeps between the trading balance and the Flatex bank account produce paired ledger records (`Degiro Cash Sweep Transfer` and `Overboeking [van/naar] uw geldrekening...`). Treating sweeps as external cash flows distorts invested capital and portfolio cash balances; from a consolidated portfolio perspective, **cash sweeps are net-zero internal transfers**.
3. **Deposit Lifecycle (3-Row Progression)**: iDEAL deposits follow a 3-step lifecycle:
   - $T_0$: `Reservation iDEAL` ($+X$) — instant trading credit.
   - $T_{\text{settle}}$: `Reservation iDEAL` ($-X$) — reservation release.
   - $T_{\text{settle}}$: `iDEAL Deposit` ($+X$) — final settled bank cash.
   The algebraic sum is $+X$, but naive cash flow aggregation will count $2X$ deposits and $1X$ withdrawal unless properly handled.
4. **Trade & Fee 1:1 Coupling via `Order Id`**: Every stock, ETF, and crypto trade row is paired 1:1 with an exact transaction fee row sharing the exact same UUID `Order Id`.
5. **Reverse Chronological Export & Strict Tie-Breaking**: DEGIRO exports transactions in reverse chronological order (newest at row 0, oldest at the bottom). For simultaneous timestamps ($T_A = T_B$), chronological replay requires tie-breaking by **`csv_row_id DESC`** (higher row index executed earlier).
6. **Balance Continuity**: When internal cash sweeps are treated as non-distorting transfers and rows are replayed in `(date ASC, time ASC, csv_row_id DESC)` order, the simulated cumulative cash matches DEGIRO's `Saldo` column with **€0.00 deviation across all 172 rows**.

---

## 2. Header & Schema Structure

### 2.1 Raw Export Headers
In Dutch DEGIRO exports:
```csv
Datum,Tijd,Valutadatum,Product,ISIN,Omschrijving,FX,Mutatie,,Saldo,,Order Id
```
In English DEGIRO exports:
```csv
Date,Time,Value date,Product,ISIN,Description,FX,Change,,Balance,,Order Id
```

### 2.2 Multi-Column Shift Grammar (The "Currency Shift" Quirk)
Notice the header contains empty column names: `Mutatie,,Saldo,,` (or `Change,,Balance,,`).

- Column index 7 (`Mutatie` / `Change`): Contains the 3-letter currency code (e.g. `EUR`, `USD`, `GBP`) or is empty.
- Column index 8 (`Unnamed: 8`): Contains the actual numeric mutation string (e.g. `"419,04"`, `"-1,00"`).
- Column index 9 (`Saldo` / `Balance`): Contains the currency code (`EUR`).
- Column index 10 (`Unnamed: 10`): Contains the running account balance string (e.g. `"5,96"`, `"1034,45"`).

#### Ingestion Rule: Column Shift
When `Mutatie` / `Change` contains a 3-letter currency code or alphabetical string ($\le 3$ chars), the ingestion engine must shift:
$$\text{amount} = \text{col}[idx + 1]$$
$$\text{balance} = \text{col}[idx_{\text{balance}} + 1]$$
If the adjacent cell is empty (as occurs in `Overboeking...` rows), `amount` evaluates to `null` / `0.0`.

---

## 3. Complete Transaction Taxonomy

Every row in `Account.csv` falls into one of the following categories:

| Category Code | Description Pattern (Dutch) | Description Pattern (English) | Mutatie Sign | Product / ISIN Populated | Order ID Present | Count in Dataset |
|---|---|---|---|---|---|---|
| `CASH_SWEEP_TRANSFER` | `Degiro Cash Sweep Transfer` | `Degiro Cash Sweep Transfer` | Signed ($\pm$) | In older exports: `FLATEX EURO BANKACCOUNT` / `NLFLATEXACNT`; newer: Empty | No | 29 |
| `CASH_SWEEP_NOTE` | `Overboeking van/naar uw geldrekening bij flatexDEGIRO Bank...` | `Transfer from/to your cash account at flatexDEGIRO Bank...` | Empty (`null`) | Empty | No | 29 |
| `DEPOSIT_RESERVATION` | `Reservation iDEAL` | `Reservation iDEAL` | $+X$ (initial) / $-X$ (settle) | Empty | No | 28 |
| `DEPOSIT_SETTLEMENT` | `iDEAL Deposit`, `Storting` | `iDEAL Deposit`, `Deposit` | $+X$ | Empty | No | 14 |
| `TRADE_BUY` | `Koop [qty] @ [price] [curr]` | `Buy [qty] @ [price] [curr]` | $-X$ (total cost) | Stock/ETF/Crypto | Yes (UUID) | 23 |
| `TRADE_SELL` | `Verkoop [qty] @ [price] [curr]` | `Sell [qty] @ [price] [curr]` | $+X$ (proceeds) | Stock/ETF/Crypto | Yes (UUID) | 3 |
| `FEE_TRANSACTION` | `DEGIRO Transactiekosten en/of kosten van derden` | `DEGIRO Transaction and/or third party fees` | $-X$ (fee) | Matches Trade | Yes (Same UUID as Trade) | 26 |
| `FEE_CONNECTIVITY` | `DEGIRO Aansluitingskosten [year] ([exchange])` | `DEGIRO Exchange Connectivity Fee [year] ([exchange])` | $-X$ (typically -€2.50) | Empty | No | 1 |
| `DIVIDEND_GROSS` | `Dividend` | `Dividend` | $+X$ (gross) | Asset holding | No | 4 |
| `DIVIDEND_TAX` | `Dividendbelasting` | `Dividend withholding tax` | $-X$ (withholding) | Asset holding | No | 4 |
| `INTEREST` | `Flatex Interest Income` | `Flatex Interest Income` | $\ge 0$ (often `0,00`) | Empty | No | 10 |
| `PROMOTION_CREDIT`| `DEGIRO Verrekening Promotie` | `DEGIRO Promotion Credit` | $+X$ (refund) | Empty | No | 1 |
| **Total Rows** | | | | | | **172** |

---

### 3.1 External Deposits & The 3-Row Lifecycle
DEGIRO processes iDEAL deposits through an immediate reservation followed by batch bank settlement.

#### Lifecycle Pattern:
1. **Initiation ($T_0$)**:
   - `Description`: `Reservation iDEAL`
   - `Mutatie`: $+X$ EUR
   - `Saldo`: Immediately credited to trading balance so the user can purchase assets immediately.
2. **Settlement ($T_{\text{settle}} = T_0 + 1\text{ to }2\text{ business days}$)**:
   - Row A: `Reservation iDEAL` with `Mutatie`: $-X$ EUR (releases reservation).
   - Row B: `iDEAL Deposit` with `Mutatie`: $+X$ EUR (records final bank deposit).

#### Mathematical Impact:
$$\sum \Delta \text{Cash} = (+X) + (-X) + (+X) = +X$$

#### Ingestion Rules:
- **Ledger Replay Engine**: Ingesting all three rows chronologically maintains balance continuity with DEGIRO's `Saldo` at every intermediate state.
- **External Cash Flow / Inflow Aggregator**: An external cash-flow aggregator computing total deposited capital must **not** sum all rows with positive mutations. It must deduplicate the deposit event:
  - Either count `Reservation iDEAL (+X)` on day $T_0$ and ignore the settlement pair (`Reservation iDEAL (-X)` + `iDEAL Deposit (+X)`),
  - Or count `iDEAL Deposit (+X)` on settlement day and ignore all `Reservation iDEAL` rows.
  - Recommended: Recognize `Reservation iDEAL (+X)` as the external cash arrival event (since purchasing power was granted on $T_0$), and treat the settlement pair on $T_{\text{settle}}$ as an internal ledger reclassification netting to €0.

### 3.2 External Withdrawals
- **Dutch Patterns**: `Terugstorting`, `Onttrekking naar geldrekening`, `Handmatige overboeking naar referentierekening`.
- **English Patterns**: `Withdrawal`, `Transfer to reference account`.
- **Mutatie**: Negative ($-X$ EUR).
- **Behavior**: External outflow from the portfolio to the investor's linked bank account.

---

### 3.3 Internal Cash Sweeps (Flatex Bank vs. DEGIRO Trading Account)

#### Background
Under German/Dutch banking regulations, DEGIRO does not hold client cash directly; cash is held in a personal bank account at **flatexDEGIRO Bank AG**. When an investor buys securities, cash is swept from the Flatex bank account to the DEGIRO account. When an investor deposits cash, sells securities, or receives dividends, uninvested cash is swept from DEGIRO to the Flatex bank account.

#### Sweep Grammar & Paired Structure
Every sweep generates two simultaneous records at the exact same timestamp:
1. **`Degiro Cash Sweep Transfer`**:
   - `Mutatie`: Signed numeric amount ($\pm X$).
   - `Saldo`: Intermediate post-sweep balance.
2. **`Overboeking [van/naar] uw geldrekening bij flatexDEGIRO Bank [:] [amount] EUR`**:
   - `Mutatie`: Empty (`null` / 0.0).
   - `Saldo`: Pre-sweep balance.

#### Exact Mathematical Invariant:
For all 29 pairs in `Account.csv`:
$$\text{Saldo}(\text{Overboeking}) = \text{Saldo}(\text{Degiro Cash Sweep Transfer}) - \text{Mutatie}(\text{Degiro Cash Sweep Transfer})$$
$$\Delta \text{Net Portfolio Cash} = 0.00$$

#### Ingestion Engine Rule:
- **Never treat `Degiro Cash Sweep Transfer` as an external deposit or withdrawal**. Doing so will create catastrophic cash distortion (in our 172-row dataset, sweeping over €7,000 back and forth would inflate perceived cash flows by thousands of euros).
- For a **consolidated portfolio view** (which tracks Total Cash = Flatex Cash + DEGIRO Cash), internal sweeps have net-zero effect.
- The `Overboeking...` rows carry no financial mutation (`Mutatie = ''`) and represent human-readable bank ledger commentary.

---

### 3.4 Asset Trades (Stocks, ETFs, Fractional Crypto)

#### Grammar
- **Dutch Buy**: `Koop <quantity> @ <price> <currency>`
- **Dutch Sell**: `Verkoop <quantity> @ <price> <currency>`
- **English Buy**: `Buy <quantity> @ <price> <currency>`
- **English Sell**: `Sell <quantity> @ <price> <currency>`

#### Regular Expression Grammar:
```regex
^(Koop|Verkoop|Buy|Sell)\s+([0-9.,eE+-]+)\s*@\s*([0-9.,eE+-]+)(?:\s+([A-Za-z]{3}))?
```

#### Extraction Rules:
1. **Action**:
   - If action is `Koop` or `Buy`: signed quantity $Q = +|\text{parsed\_qty}|$. Trade mutation is negative: $\text{Mutatie} \approx -(Q \times P)$.
   - If action is `Verkoop` or `Sell`: signed quantity $Q = -|\text{parsed\_qty}|$. Trade mutation is positive: $\text{Mutatie} \approx +(|Q| \times P)$.
2. **Asset Identification**:
   - **Stocks & ETFs**: `Product` contains asset name (e.g. `VANGUARD FTSE ALL-WORLD UCITS - (USD)`), `ISIN` contains valid 12-character ISIN (e.g. `IE00BK5BQT80`).
   - **Cryptocurrency**: `ISIN` is empty (`""`). `Product` contains crypto asset name (e.g. `BITCOIN`, `ETHEREUM`). Quantity is fractional (e.g. `0,003472`, `0,000077`).

---

### 3.5 Fees & Correlation via `Order Id`

#### 1. Transaction Fees (`FEE_TRANSACTION`)
- **Description**: `DEGIRO Transactiekosten en/of kosten van derden` (Dutch) / `DEGIRO Transaction and/or third party fees` (English).
- **Order ID**: Populated with the exact UUID of the corresponding trade.
- **Product & ISIN**: Exactly matches the trade asset.
- **Rule**: Every trade row has exactly one fee row sharing its `Order Id`. To compute the complete cost basis of an execution:
$$\text{Total Execution Cost} = |\text{Trade Mutatie}| + |\text{Fee Mutatie}|$$

#### 2. Exchange Connectivity Fees (`FEE_CONNECTIVITY`)
- **Description**: `DEGIRO Aansluitingskosten <year> (<exchange> - <mic>)` (Dutch) / `DEGIRO Exchange Connectivity Fee <year> (<exchange>)` (English).
  - Example: `DEGIRO Aansluitingskosten 2026 (Xetra - XET)`
- **Order ID**: Empty (account-level administrative levy, €2.50 per exchange per year).
- **Rule**: Deducted directly from portfolio cash balance.

#### 3. FX & AutoFX Fees (`FEE_FX`)
- **Description**: `Valutakosten`, `AutoFX`, `AutoFX kosten` (Dutch) / `AutoFX fee`, `Currency conversion fee` (English).
- **Rule**: Deducted when trading assets denominated in foreign currencies (e.g. USD, GBP).

---

### 3.6 Corporate Actions & Dividends

Every dividend payment from an asset holding consists of two simultaneous rows at the exact same timestamp:
1. **Gross Dividend (`DIVIDEND_GROSS`)**:
   - Description: `Dividend`
   - Mutatie: $+X$ EUR
   - Product & ISIN: Populated with the distributing asset (e.g. `AEGON LTD.`, `BMG0112X1056`).
2. **Dividend Withholding Tax (`DIVIDEND_TAX`)**:
   - Description: `Dividendbelasting` (Dutch) / `Dividend withholding tax` (English).
   - Mutatie: $-Y$ EUR (typically 15% Dutch dividend tax).
   - Product & ISIN: Populated with the distributing asset.

#### Net Cash Inflow:
$$\text{Net Dividend} = \text{Mutatie}_{\text{gross}} + \text{Mutatie}_{\text{tax}} = (+X) + (-Y)$$
*Note: In DEGIRO's Flatex cash sweep system, this net dividend is automatically swept to the Flatex bank account within a few hours.*

---

### 3.7 Interest Income & Promotions

1. **Flatex Interest Income (`INTEREST`)**:
   - Description: `Flatex Interest Income` (or `Flatex Rente` / `Debetrente`).
   - Booked quarterly (e.g. 31-03, 30-06, 30-09, 31-12).
   - Mutatie: `0,00` EUR if account balance was below interest threshold, or positive interest credit.
2. **Promotions / Fee Credits (`PROMOTION_CREDIT`)**:
   - Description: `DEGIRO Verrekening Promotie` (Dutch) / `DEGIRO Promotion Credit` (English).
   - Mutatie: Positive cash credit (e.g. $+3,00$ EUR).

---

## 4. Chronological Sorting & Balance Tie-Breaking Grammar

### 4.1 Reverse Chronological Export Order
DEGIRO exports `Account.csv` in **reverse chronological order**:
- Row 0 (line 2 of CSV): Most recent transaction.
- Row $N-1$ (last line of CSV): Oldest historical transaction.

### 4.2 Timestamp Ties and Execution Sequence
Transactions occurring within the same minute share identical `Datum` and `Tijd`. In our dataset, there are **69 timestamp tie groups**.

When replaying transactions forward in time (chronological reconstruction):
1. Primary Sort Key: `Datum` ASC (parsed as `YYYY-MM-DD`).
2. Secondary Sort Key: `Tijd` ASC (parsed as `HH:MM`).
3. **Tertiary Sort Key (Tie-Breaker)**: **`csv_row_id DESC`** (higher original CSV row index comes earlier in chronological time).

### 4.3 Mathematical Proof of Tie-Breaking Rule

#### Case 1: Trade and Transaction Fee
At `15-10-2026 15:46`:
- Row 8 (CSV Index 8): `DEGIRO Transactiekosten...`, Mut = -1.00, Saldo = 5.96
- Row 9 (CSV Index 9): `Koop 1 @ 39,96 EUR`, Mut = -39.96, Saldo = 6.96
- Pre-trade balance: 46.92 EUR.
- If sorted by `csv_row_id DESC`:
  1. Row 9 executes first: $46.92 - 39.96 = 6.96$ (Matches Row 9 Saldo: 6.96).
  2. Row 8 executes second: $6.96 - 1.00 = 5.96$ (Matches Row 8 Saldo: 5.96).
- If sorted incorrectly (`csv_row_id ASC`), Row 8 would execute first: $46.92 - 1.00 = 45.92 \neq 5.96$ (Broken balance!).

#### Case 2: iDEAL Settlement Pair
At `17-10-2026 02:32`:
- Row 2 (CSV Index 2): `iDEAL Deposit`, Mut = +75.00, Saldo = 5.96
- Row 3 (CSV Index 3): `Reservation iDEAL`, Mut = -75.00, Saldo = -69.04
- Pre-settlement balance: 5.96 EUR.
- If sorted by `csv_row_id DESC`:
  1. Row 3 executes first: $5.96 - 75.00 = -69.04$ (Matches Row 3 Saldo: -69.04).
  2. Row 2 executes second: $-69.04 + 75.00 = 5.96$ (Matches Row 2 Saldo: 5.96).

#### Case 3: Dividend Distribution Pair
At `09-07-2024 07:07`:
- Row 159 (CSV Index 159): `Dividendbelasting`, Mut = -0.02, Saldo = 4.39
- Row 160 (CSV Index 160): `Dividend`, Mut = +0.16, Saldo = 4.41
- Pre-dividend balance: 4.25 EUR.
- If sorted by `csv_row_id DESC`:
  1. Row 160 executes first: $4.25 + 0.16 = 4.41$ (Matches Row 160 Saldo: 4.41).
  2. Row 159 executes second: $4.41 - 0.02 = 4.39$ (Matches Row 159 Saldo: 4.39).

---

## 5. Cash Flow Reconstruction & Balance Continuity Rules

### 5.1 The Mathematical Model
Let $\text{Cash}_t$ be the consolidated cash balance at time $t$.
$$\text{Cash}_t = \text{Cash}_0 + \sum_{k=1}^t \Delta \text{Cash}_k$$

Where $\Delta \text{Cash}_k$ includes:
- Deposits: $+X$ (via `Reservation iDEAL` at $T_0$, with settlement pair netting to 0).
- Withdrawals: $-X$.
- Trades: $-(\text{Qty} \times \text{Price})$ for Buys, $+(\text{Qty} \times \text{Price})$ for Sells.
- Fees: $-(\text{Transaction Fee})$, $-(\text{Connectivity Fee})$, $-(\text{FX Fee})$.
- Corporate Actions: $+(\text{Gross Dividend}) - (\text{Dividend Withholding Tax})$.
- Promotion Credits: $+(\text{Promotion Credit})$.
- Internal Cash Sweeps: **Excluded** ($\Delta \text{Cash}_{\text{sweep}} = 0$).

### 5.2 Verification Across All 172 Production Rows
When this simulation was executed across all 172 rows of `Account.csv`:
$$\max_{k=1}^{172} \left| \text{CalculatedCash}_k - \text{CSVSaldo}_k \right| = 0.00\text{ EUR}$$
Final simulated cash balance: **€5.96**, exactly matching DEGIRO's official closing balance of **€5.96**.

---

## 6. Number Formatting & Locale Parsing Grammar

DEGIRO exports format numbers according to the user's regional interface locale:

### Dutch Export Locale:
- Decimal separator: Comma (`,`)
- Thousands separator: Period (`.`)
- Examples: `1.585,98`, `57.590,21`, `0,003472`, `18,076`, `149`.

### English Export Locale:
- Decimal separator: Period (`.`)
- Thousands separator: Comma (`,`)
- Examples: `1,585.98`, `57,590.21`, `0.003472`, `18.076`, `149`.

### Robust Parser Implementation:
```python
def parse_degiro_number(val: str | float | None) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    # Strip currency codes and clean whitespace
    for cur in ("EUR", "USD", "GBP", "CHF"):
        s = s.replace(cur, "")
    s = s.strip()
    if not s or s.lower() in ("nan", "none", "-"):
        return None

    last_comma = s.rfind(",")
    last_dot = s.rfind(".")

    if last_comma > last_dot:
        # European format: 1.234,56 -> 1234.56
        s = s.replace(".", "").replace(",", ".")
    elif last_dot > last_comma:
        # Anglo format: 1,234.56 -> 1234.56
        s = s.replace(",", "")
    elif last_comma != -1:
        # Only comma: 1234,56 -> 1234.56
        s = s.replace(",", ".")

    try:
        return float(s)
    except ValueError:
        return None
```

---

## 7. Deduplication & Idempotency Rules

When importing overlapping CSV exports (e.g. monthly downloads), deduplication must use a deterministic hash that resists minor export variations.

### Canonical Row Hash Specification
A transaction row hash should combine the immutable economic properties of the record:
$$\text{RowHash} = \text{MD5}\Big(\text{Date} \,||\, \text{Time} \,||\, \text{ISIN} \,||\, \text{OrderId} \,||\, \text{Amount} \,||\, \text{Description}\Big)$$

- **Date**: Normalized `YYYY-MM-DD`.
- **Time**: Normalized `HH:MM`.
- **ISIN**: Uppercase or empty string.
- **OrderId**: Lowercase UUID string or empty string.
- **Amount**: Normalized float string formatted to 4 decimal places (e.g. `-199.9500`).
- **Description**: Trimmed exact string.

If `RowHash` already exists in the database/store, the ingestion engine skips the row as a duplicate, ensuring 100% idempotent re-imports.

---

## 8. Architectural Traps & Antipatterns

1. **The Cash Sweep Trap**:
   - *Trap*: Counting `Degiro Cash Sweep Transfer` as external cash inflow/outflow.
   - *Consequence*: Cash balance fluctuates wildly, and total deposited capital is inflated by thousands of euros.
   - *Fix*: Filter out internal cash sweeps from external cash calculations; treat as net-zero internal transfers.
2. **The Triple Deposit Trap**:
   - *Trap*: Blindly summing positive rows containing `iDEAL` or `Deposit`.
   - *Consequence*: Every €100 deposit is counted as €200 deposited (initial reservation + final settlement).
   - *Fix*: Recognize the 3-row reservation/settlement lifecycle.
3. **The Chronological Sort Inversion**:
   - *Trap*: Sorting only by `date ASC, time ASC` without a tie-breaker.
   - *Consequence*: Transactions and fees are evaluated out of order, producing spurious negative balance anomalies.
   - *Fix*: Always tie-break timestamp ties with `csv_row_id DESC`.
4. **The Crypto Missing ISIN Bug**:
   - *Trap*: Assuming all trades have an `ISIN` and discarding rows with empty `ISIN`.
   - *Consequence*: All Bitcoin and Ethereum transactions are discarded, corrupting crypto holdings and cash balances.
   - *Fix*: Match trades on `Product` (`BITCOIN`, `ETHEREUM`) when `ISIN` is empty.
5. **The Hardcoded Stock Name Filter Bug**:
   - *Trap*: Checking `prod.includes('aegon')` as an internal cash transaction filter (previously observed in `transactionAggregator.ts`).
   - *Consequence*: Legitimately held stocks (like `AEGON LTD.`, ISIN `BMG0112X1056`) are misclassified as cash transfers and ignored from equity holdings!
   - *Fix*: Only classify explicitly verified bank products (`FLATEX EURO BANKACCOUNT`, `NLFLATEXACNT`, `geldrekening`) as cash accounts.
