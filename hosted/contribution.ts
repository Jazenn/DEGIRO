import Decimal from "decimal.js";
import type { Targets } from "./targets";
import { timestamp } from "./read-model";
const D = Decimal.clone({ precision: 80, rounding: Decimal.ROUND_HALF_EVEN });
export interface ExecutionTerms {
  asset_id: string;
  revision: string;
  quantity_step: string;
  minimum_quantity: string;
  minimum_notional_eur: string;
  fixed_fee_eur: string;
  fee_rate_pct: string;
  minimum_fee_eur: string;
  fee_status: "known" | "estimated";
  evidence: string;
  valid_from: string;
  valid_until: string;
  spread_allowance_pct?: string | null;
  spread_evidence?: string | null;
}
export interface ContributionAsset {
  asset_id: string;
  symbol: string;
  asset_kind: "ETF" | "Cryptocurrency";
  identity_evidence: string;
  verified_at: string;
}
type Model = Record<string, any>;
export interface ContributionPlan {
  state: "complete" | "incomplete";
  budget_eur: string;
  invested_eur: string | null;
  fees_eur: string | null;
  remaining_cash_eur: string;
  spread_allowance_eur: string | null;
  warnings: string[];
  budgets: Record<string, string>;
  diagnostics: string[];
  policy: string;
  purchases: Record<string, string>[];
  allocation: Record<string, string | null>[];
}
const numeric = (value: unknown): value is string =>
  typeof value === "string" && /^\d{1,12}(?:\.\d{1,18})?$/.test(value);
const money = (value: unknown): value is string =>
  typeof value === "string" && /^\d{1,12}(?:\.\d{1,2})?$/.test(value);
function validTerms(terms: ExecutionTerms, now: string) {
  return (
    terms &&
    typeof terms.revision === "string" &&
    terms.revision.length > 0 &&
    typeof terms.evidence === "string" &&
    terms.evidence.length > 0 &&
    ["known", "estimated"].includes(terms.fee_status) &&
    timestamp(terms.valid_from) &&
    timestamp(terms.valid_until) &&
    Date.parse(terms.valid_from) <= Date.parse(now) &&
    Date.parse(terms.valid_until) >= Date.parse(now) &&
    [
      "quantity_step",
      "minimum_quantity",
      "minimum_notional_eur",
      "fixed_fee_eur",
      "fee_rate_pct",
      "minimum_fee_eur",
    ].every((key) => numeric(terms[key as keyof ExecutionTerms])) &&
    new D(terms.quantity_step).gt(0) &&
    new D(terms.minimum_quantity).gte(terms.quantity_step) &&
    new D(terms.fee_rate_pct).lte(100)
  );
}
function budgetsFor(budget: Decimal, choice: unknown) {
  const selected =
    choice === undefined
      ? { mode: "etf" }
      : (choice as Record<string, unknown>);
  if (!selected || !["etf", "crypto", "mixed"].includes(String(selected.mode)))
    throw Error("invalid_choice");
  if (selected.mode === "etf") {
    if (
      (selected.crypto_budget_eur !== undefined &&
        (!money(selected.crypto_budget_eur) ||
          !new D(selected.crypto_budget_eur).isZero())) ||
      selected.coin !== undefined ||
      selected.btc_pct !== undefined
    )
      throw Error("invalid_choice");
    return { etf: budget, BTC: new D(0), ETH: new D(0) };
  }
  if (
    !money(selected.crypto_budget_eur) ||
    !["BTC", "ETH", "both"].includes(String(selected.coin))
  )
    throw Error("invalid_choice");
  const crypto = new D(selected.crypto_budget_eur);
  if (
    (selected.mode === "crypto" && !crypto.eq(budget)) ||
    (selected.mode === "mixed" && (!crypto.gt(0) || !crypto.lt(budget)))
  )
    throw Error("invalid_choice");
  const pct =
    selected.coin === "BTC"
      ? "100"
      : selected.coin === "ETH"
        ? "0"
        : selected.btc_pct;
  if (
    !numeric(pct) ||
    new D(pct).gt(100) ||
    (selected.coin === "both" && (!new D(pct).gt(0) || !new D(pct).lt(100))) ||
    (selected.coin !== "both" &&
      selected.btc_pct !== undefined &&
      (!numeric(selected.btc_pct) || !new D(selected.btc_pct).eq(pct)))
  )
    throw Error("invalid_choice");
  // Currency split rounded down to cents for BTC; ETH receives the exact remainder.
  const btc = crypto.mul(pct).div(100).toDecimalPlaces(2, Decimal.ROUND_FLOOR);
  return { etf: budget.minus(crypto), BTC: btc, ETH: crypto.minus(btc) };
}
export function planContribution(
  model: Model,
  settings: Targets,
  terms: ExecutionTerms[],
  budgetInput: unknown,
  now: string,
  choice?: unknown,
): ContributionPlan {
  if (!money(budgetInput)) throw Error("invalid_budget");
  const budget = new D(budgetInput),
    pools = budgetsFor(budget, choice);
  const result: ContributionPlan = {
    state: "incomplete",
    budget_eur: budget.toFixed(),
    invested_eur: null,
    fees_eur: null,
    spread_allowance_eur: null,
    remaining_cash_eur: budget.toFixed(),
    warnings: [],
    budgets: {
      etf_eur: pools.etf.toFixed(),
      btc_eur: pools.BTC.toFixed(),
      eth_eur: pools.ETH.toFixed(),
    },
    diagnostics: [],
    purchases: [],
    allocation: [],
    policy:
      "ETF budget is proportional to positive target shortfalls against all holdings plus the total contribution, sorted descending shortfall then Asset identifier. Crypto uses only the explicitly chosen BTC/ETH contribution split. BTC split rounds down to cents; ETH receives the remainder. Fees and reviewed spread allowances fit each envelope. Quantities round down to verified steps. All unused category budgets stay cash; no automatic transfers, sales or threshold purchases.",
  };
  const diagnostics = result.diagnostics;
  const positions: Model[] = [...(model.ledger?.positions ?? [])];
  for (const asset of (model.contribution_assets ??
    []) as ContributionAsset[]) {
    if (
      !positions.some((row) => row.broker_asset_id === asset.asset_id) &&
      asset.identity_evidence &&
      timestamp(asset.verified_at) &&
      Date.parse(asset.verified_at) <= Date.parse(now) &&
      ["ETF", "Cryptocurrency"].includes(asset.asset_kind)
    )
      positions.push({
        broker_asset_id: asset.asset_id,
        symbol: asset.symbol,
        asset_kind: asset.asset_kind,
        quantity: "0",
        market_value_eur: "0",
      });
  }
  if (settings.version !== model.settings_version)
    diagnostics.push("settings_changed_refresh_required");
  if (
    pools.etf.gt(0) &&
    (!settings.targets.length ||
      new Set(settings.targets.map((row) => row.asset_id)).size !==
        settings.targets.length ||
      settings.targets.some(
        (row) => !numeric(row.target_pct) || new D(row.target_pct).gt(100),
      ) ||
      !settings.targets
        .reduce(
          (sum, row) =>
            sum.plus(numeric(row.target_pct) ? row.target_pct : "0"),
          new D(0),
        )
        .eq(100))
  )
    diagnostics.push("invalid_targets");
  if (
    model.ledger?.market_value_eur === null ||
    !positions.length ||
    positions.some((row) => row.market_value_eur === null)
  )
    diagnostics.push("incomplete_current_valuation");
  if (diagnostics.length) return result;
  const market = new D(model.ledger.market_value_eur);
  if (
    !positions
      .reduce((sum, row) => sum.plus(row.market_value_eur), new D(0))
      .eq(market)
  ) {
    diagnostics.push("inconsistent_current_valuation");
    return result;
  }
  type Candidate = {
    position: Model;
    shortfall: Decimal;
    terms: ExecutionTerms;
    price: Decimal;
    observed: string;
    pool: "etf" | "BTC" | "ETH";
  };
  const candidates: Candidate[] = [];
  const prepare = (
    position: Model,
    shortfall: Decimal,
    pool: Candidate["pool"],
  ) => {
    const quote = model.observed_prices?.[position.symbol],
      rule = terms.find((row) => row.asset_id === position.broker_asset_id);
    const age = quote?.observed_at
      ? Date.parse(now) - Date.parse(quote.observed_at)
      : NaN;
    if (
      !quote ||
      !numeric(quote.price_eur) ||
      !new D(quote.price_eur).gt(0) ||
      !timestamp(quote.observed_at) ||
      age < 0 ||
      (pool !== "etf" && age > 300000)
    ) {
      diagnostics.push("missing_eligible_price:" + position.broker_asset_id);
      return;
    }
    if (!rule || !validTerms(rule, now)) {
      diagnostics.push(
        "missing_reviewed_execution_terms:" + position.broker_asset_id,
      );
      return;
    }
    if (
      pool !== "etf" &&
      (!numeric(rule.spread_allowance_pct) ||
        new D(rule.spread_allowance_pct).gt(100) ||
        !rule.spread_evidence)
    ) {
      diagnostics.push(
        "missing_reviewed_spread_allowance:" + position.broker_asset_id,
      );
      return;
    }
    candidates.push({
      position,
      shortfall,
      terms: rule,
      price: new D(quote.price_eur),
      observed: quote.observed_at,
      pool,
    });
  };
  if (pools.etf.gt(0))
    for (const target of settings.targets) {
      const position = positions.find(
        (row) => row.broker_asset_id === target.asset_id,
      );
      if (!position) {
        diagnostics.push("unknown_target_asset:" + target.asset_id);
        continue;
      }
      if (position.asset_kind !== "ETF") continue;
      const shortfall = D.max(
        0,
        market
          .plus(budget)
          .mul(target.target_pct)
          .div(100)
          .minus(position.market_value_eur),
      );
      if (shortfall.gt(0)) prepare(position, shortfall, "etf");
    }
  for (const coin of ["BTC", "ETH"] as const)
    if (pools[coin].gt(0)) {
      const matches = positions.filter(
        (row) => row.asset_kind === "Cryptocurrency" && row.symbol === coin,
      );
      if (matches.length !== 1)
        diagnostics.push("crypto_identity_missing_or_ambiguous:" + coin);
      else prepare(matches[0], pools[coin], coin);
    }
  if (diagnostics.length) return result;
  candidates.sort(
    (a, b) =>
      (a.pool === "etf" ? 0 : 1) - (b.pool === "etf" ? 0 : 1) ||
      b.shortfall.comparedTo(a.shortfall) ||
      (a.position.broker_asset_id < b.position.broker_asset_id ? -1 : 1),
  );
  const totalShortfall = candidates
    .filter((row) => row.pool === "etf")
    .reduce((sum, row) => sum.plus(row.shortfall), new D(0));
  let invested = new D(0),
    fees = new D(0),
    spreads = new D(0);
  for (const {
    position,
    shortfall,
    terms: rule,
    price,
    observed,
    pool,
  } of candidates) {
    const envelope =
      pool === "etf"
        ? D.min(shortfall, pools.etf.mul(shortfall).div(totalShortfall))
        : pools[pool];
    const step = new D(rule.quantity_step);
    const spread = (notional: Decimal) =>
      notional
        .mul(pool === "etf" ? "0" : rule.spread_allowance_pct!)
        .div(100)
        .toDecimalPlaces(2, Decimal.ROUND_CEIL);
    const fee = (notional: Decimal) =>
      D.max(
        rule.minimum_fee_eur,
        new D(rule.fixed_fee_eur).plus(
          notional.plus(spread(notional)).mul(rule.fee_rate_pct).div(100),
        ),
      ).toDecimalPlaces(2, Decimal.ROUND_CEIL);
    let low = new D(0),
      high = envelope.div(price).div(step).floor();
    while (low.lt(high)) {
      const middle = low.plus(high).plus(1).div(2).floor(),
        notional = middle.mul(step).mul(price);
      if (notional.plus(spread(notional)).plus(fee(notional)).lte(envelope))
        low = middle;
      else high = middle.minus(1);
    }
    const quantity = low.mul(step),
      notional = quantity.mul(price);
    if (
      quantity.isZero() ||
      quantity.lt(rule.minimum_quantity) ||
      notional.lt(rule.minimum_notional_eur)
    )
      continue;
    const charge = fee(notional),
      allowance = spread(notional);
    invested = invested.plus(notional);
    fees = fees.plus(charge);
    spreads = spreads.plus(allowance);
    result.purchases.push({
      asset_id: position.broker_asset_id,
      symbol: position.symbol,
      category: pool,
      quantity: quantity.toFixed(),
      price_eur: price.toFixed(),
      notional_eur: notional.toFixed(),
      fee_eur: charge.toFixed(),
      spread_allowance_eur: allowance.toFixed(),
      spread_evidence:
        rule.spread_evidence ?? "Not configured for ETF estimate",
      total_cost_eur: notional.plus(charge).plus(allowance).toFixed(),
      fee_status: rule.fee_status,
      terms_revision: rule.revision,
      terms_evidence: rule.evidence,
      terms_valid_until: rule.valid_until,
      quote_observed_at: observed,
      quantity_step: rule.quantity_step,
    });
  }
  if (invested.plus(fees).plus(spreads).gt(budget))
    throw Error("budget_invariant");
  const afterMarket = market.plus(invested);
  result.state = "complete";
  result.invested_eur = invested.toFixed();
  result.fees_eur = fees.toFixed();
  result.spread_allowance_eur = spreads.toFixed();
  result.remaining_cash_eur = budget
    .minus(invested)
    .minus(fees)
    .minus(spreads)
    .toFixed();
  result.allocation = positions.map((position) => {
    const purchase = result.purchases.find(
        (row) => row.asset_id === position.broker_asset_id,
      ),
      after = new D(position.market_value_eur).plus(
        purchase?.notional_eur ?? "0",
      );
    return {
      asset_id: position.broker_asset_id,
      symbol: position.symbol,
      before_value_eur: position.market_value_eur,
      after_value_eur: after.toFixed(),
      before_pct: market.isZero()
        ? null
        : new D(position.market_value_eur)
            .div(market)
            .mul(100)
            .toDecimalPlaces(12)
            .toFixed(),
      after_pct: afterMarket.isZero()
        ? null
        : after.div(afterMarket).mul(100).toDecimalPlaces(12).toFixed(),
      target_pct:
        settings.targets.find(
          (row) => row.asset_id === position.broker_asset_id,
        )?.target_pct ?? null,
    };
  });
  const cryptoIds = new Set(
    positions
      .filter((row) => row.asset_kind === "Cryptocurrency")
      .map((row) => row.broker_asset_id),
  );
  const beforeCrypto = positions
    .filter((row) => cryptoIds.has(row.broker_asset_id))
    .reduce((sum, row) => sum.plus(row.market_value_eur), new D(0));
  const afterCrypto = result.allocation
    .filter((row) => cryptoIds.has(row.asset_id))
    .reduce((sum, row) => sum.plus(row.after_value_eur!), new D(0));
  if (
    afterMarket.gt(0) &&
    (market.isZero()
      ? afterCrypto.gt(0)
      : afterCrypto.div(afterMarket).gt(beforeCrypto.div(market)))
  )
    result.warnings.push("crypto_concentration_increases");
  for (const row of result.allocation)
    if (
      cryptoIds.has(row.asset_id) &&
      row.target_pct !== null &&
      row.after_pct !== null &&
      new D(row.after_pct).gt(row.target_pct)
    )
      result.warnings.push("crypto_above_target:" + row.asset_id);
  return result;
}
