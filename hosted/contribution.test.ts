import { expect, test } from "vitest";
import { planContribution, type ExecutionTerms } from "./contribution";
const terms = (asset_id: string): ExecutionTerms => ({
  asset_id,
  revision: "review-1",
  quantity_step: "1",
  minimum_quantity: "1",
  minimum_notional_eur: "0",
  fixed_fee_eur: "1",
  fee_rate_pct: "0",
  minimum_fee_eur: "0",
  fee_status: "estimated",
  evidence: "Synthetic reviewed all-in EUR purchase tariff",
  valid_from: "2026-01-01T00:00:00Z",
  valid_until: "2027-01-01T00:00:00Z",
});
const model = {
  settings_version: "financial-fixture",
  rebalancing_targets_version: "1",
  ledger: {
    market_value_eur: "200",
    positions: [
      {
        broker_asset_id: "A",
        symbol: "A",
        asset_kind: "ETF",
        market_value_eur: "100",
        quantity: "1",
      },
      {
        broker_asset_id: "B",
        symbol: "B",
        asset_kind: "ETF",
        market_value_eur: "100",
        quantity: "1",
      },
    ],
  },
  observed_prices: {
    A: { price_eur: "100", observed_at: "2026-10-23T10:00:00Z" },
    B: { price_eur: "100", observed_at: "2026-10-23T10:00:00Z" },
  },
};
const settings = {
  version: "1",
  targets: [
    { asset_id: "A", target_pct: "50" },
    { asset_id: "B", target_pct: "50" },
  ],
};

test("ETF budget pays purchase fees and resolves equal shortfalls by Asset identifier with visible cash", () => {
  const plan = planContribution(
    model,
    settings,
    [terms("B"), terms("A")],
    "202",
    "2026-10-23T10:00:00Z",
  );
  expect(plan.state).toBe("complete");
  expect(
    plan.purchases.map((row) => [
      row.asset_id,
      row.quantity,
      row.total_cost_eur,
    ]),
  ).toEqual([
    ["A", "1", "101"],
    ["B", "1", "101"],
  ]);
  expect(plan.fees_eur).toBe("2");
  expect(plan.remaining_cash_eur).toBe("0");
  expect(plan.allocation[0]).toMatchObject({
    before_pct: "50",
    after_pct: "50",
  });
  const tiny = planContribution(
    model,
    settings,
    [terms("A"), terms("B")],
    "100",
    "2026-10-23T10:00:00Z",
  );
  expect(tiny.purchases).toEqual([]);
  expect(tiny.remaining_cash_eur).toBe("100");
});

test("fee rounding and verified fractional steps keep all-in spend within budget without using existing cash", () => {
  const one = {
    ...model,
    ledger: {
      ...model.ledger,
      cash_balance_eur: "100000",
      market_value_eur: "100",
      positions: [{ ...model.ledger.positions[0], quantity: "10" }],
    },
    observed_prices: {
      A: { price_eur: "10", observed_at: "2026-10-23T10:00:00Z" },
    },
  };
  const fractional = {
    ...terms("A"),
    quantity_step: "0.1",
    minimum_quantity: "0.2",
    minimum_notional_eur: "3",
    fixed_fee_eur: "0.11",
  };
  const plan = planContribution(
    one,
    { version: "1", targets: [{ asset_id: "A", target_pct: "100" }] },
    [fractional],
    "5",
    "2026-10-23T10:00:00Z",
  );
  expect(plan.purchases[0]).toMatchObject({
    quantity: "0.4",
    notional_eur: "4",
    fee_eur: "0.11",
    total_cost_eur: "4.11",
    fee_status: "estimated",
  });
  expect(plan.remaining_cash_eur).toBe("0.89");
  const priced = {
    ...one,
    observed_prices: {
      A: { price_eur: "33.33333333", observed_at: "2026-10-23T10:00:00Z" },
    },
  };
  const roundedFee = planContribution(
    priced,
    { version: "1", targets: [{ asset_id: "A", target_pct: "100" }] },
    [{ ...terms("A"), fixed_fee_eur: "0.1", fee_rate_pct: "1" }],
    "100",
    "2026-10-23T10:00:00Z",
  );
  expect(roundedFee.purchases[0]).toMatchObject({
    quantity: "2",
    fee_eur: "0.77",
    total_cost_eur: "67.43666666",
  });
  expect(roundedFee.remaining_cash_eur).toBe("32.56333334");
});

test("unknown fees, expired precision evidence and stale settings are visibly incomplete, while zero buys cost zero", () => {
  const now = "2026-10-23T10:00:00Z";
  const missing = planContribution(model, settings, [], "500", now);
  expect(missing.state).toBe("incomplete");
  expect(missing.fees_eur).toBeNull();
  expect(missing.purchases).toEqual([]);
  expect(missing.diagnostics).toContain("missing_reviewed_execution_terms:A");
  expect(
    planContribution(model, { ...settings, version: "2" }, [], "500", now)
      .diagnostics,
  ).toContain("settings_changed_refresh_required");
  expect(
    planContribution(
      model,
      settings,
      [{ ...terms("A"), valid_until: "2026-01-01T00:00:00Z" }, terms("B")],
      "500",
      now,
    ).state,
  ).toBe("incomplete");
  expect(planContribution(model, settings, [], "0", now)).toMatchObject({
    state: "complete",
    invested_eur: "0",
    fees_eur: "0",
    remaining_cash_eur: "0",
    purchases: [],
  });
  expect(() => planContribution(model, settings, [], "-1", now)).toThrow(
    "invalid_budget",
  );
});

import { createContribution } from "./contribution-store";
import { createApplication } from "./application";
import { databaseTransport, env, login } from "./auth-test-support";

test("authenticated preview requires the displayed coherent generation and settings and cannot mutate holdings", async () => {
  const snapshot = {
    generation_id: "g1",
    published_at: "2026-10-23T10:00:00Z",
    data_classification: "synthetic" as const,
    read_model: {
      ...model,
      ledger_version: "l1",
      calculation_version: "decimal-accounting-v1",
      cutoff: "2026-10-23T10:00:00Z",
    },
  };
  const contribution = createContribution(
    {
      read: async () => ({
        snapshot,
        settings,
        terms: [terms("A"), terms("B")],
      }),
    },
    () => Date.parse("2026-10-23T10:00:00Z"),
  );
  const app = createApplication({
    authQuery: databaseTransport(),
    readAccepted: async () => null,
    contribution: async (value) => contribution(value),
  });
  const cookie = (await login()).session!;
  const call = (
    value: unknown,
    origin = env.APP_ORIGIN,
    authenticated = true,
  ) =>
    app(
      new Request(env.APP_ORIGIN + "/api/contribution", {
        method: "POST",
        headers: { Cookie: authenticated ? cookie : "", Origin: origin },
        body: JSON.stringify(value),
      }),
      env,
    );
  const input = {
    budget_eur: "202",
    generation_id: "g1",
    rebalancing_targets_version: "1",
  };
  expect((await call(input, env.APP_ORIGIN, false)).status).toBe(401);
  expect((await call(input, "https://wrong.test")).status).toBe(403);
  const stale = await call({ ...input, generation_id: "old" });
  expect(stale.status).toBe(409);
  expect((await stale.json()).state).toBe("stale");
  const response = await call(input);
  expect(response.status).toBe(200);
  expect(await response.json()).toMatchObject({
    state: "complete",
    generation_id: "g1",
    settings_version: "financial-fixture",
    rebalancing_targets_version: "1",
    invested_eur: "200",
    fees_eur: "2",
    remaining_cash_eur: "0",
  });
  expect(snapshot.read_model.ledger.market_value_eur).toBe("200");
});

const cryptoModel = {
  ...model,
  ledger: {
    ...model.ledger,
    market_value_eur: "400",
    positions: [
      ...model.ledger.positions,
      {
        broker_asset_id: "BTC-ID",
        symbol: "BTC",
        asset_kind: "Cryptocurrency",
        market_value_eur: "100",
        quantity: "1",
      },
      {
        broker_asset_id: "ETH-ID",
        symbol: "ETH",
        asset_kind: "Cryptocurrency",
        market_value_eur: "100",
        quantity: "1",
      },
    ],
  },
  observed_prices: {
    ...model.observed_prices,
    BTC: { price_eur: "100", observed_at: "2026-10-23T10:00:00Z" },
    ETH: { price_eur: "100", observed_at: "2026-10-23T10:00:00Z" },
  },
};
const cryptoTerms = (id: string) => ({
  ...terms(id),
  quantity_step: "0.01",
  minimum_quantity: "0.01",
  spread_allowance_pct: "1",
  spread_evidence: "Reviewed synthetic upper allowance",
});
const mixedTargets = {
  version: "1",
  targets: [
    { asset_id: "A", target_pct: "25" },
    { asset_id: "B", target_pct: "25" },
    { asset_id: "BTC-ID", target_pct: "25" },
    { asset_id: "ETH-ID", target_pct: "25" },
  ],
};

test("explicit mixed contribution preserves category budgets, both coin split, fees, spread and all holdings", () => {
  const plan = planContribution(
    cryptoModel,
    mixedTargets,
    [terms("A"), terms("B"), cryptoTerms("BTC-ID"), cryptoTerms("ETH-ID")],
    "404",
    "2026-10-23T10:00:00Z",
    { mode: "mixed", crypto_budget_eur: "202", coin: "both", btc_pct: "50" },
  );
  expect(plan.state).toBe("complete");
  expect(
    plan.purchases.map((row) => [row.symbol, row.quantity, row.total_cost_eur]),
  ).toEqual([
    ["A", "1", "101"],
    ["B", "1", "101"],
    ["BTC", "0.99", "100.99"],
    ["ETH", "0.99", "100.99"],
  ]);
  expect(plan.invested_eur).toBe("398");
  expect(plan.fees_eur).toBe("4");
  expect(plan.spread_allowance_eur).toBe("1.98");
  expect(plan.remaining_cash_eur).toBe("0.02");
  expect(plan.allocation).toHaveLength(4);
  expect(plan.warnings).not.toContain("crypto_concentration_increases");
});

test("BTC-only contribution can exceed targets with a warning and never consumes existing crypto/core quantities", () => {
  const plan = planContribution(
    cryptoModel,
    mixedTargets,
    [cryptoTerms("BTC-ID")],
    "202",
    "2026-10-23T10:00:00Z",
    { mode: "crypto", crypto_budget_eur: "202", coin: "BTC" },
  );
  expect(plan.state).toBe("complete");
  expect(plan.purchases.map((row) => [row.symbol, row.quantity])).toEqual([
    ["BTC", "1.99"],
  ]);
  expect(plan.warnings).toContain("crypto_concentration_increases");
  expect(plan.warnings).toContain("crypto_above_target:BTC-ID");
  expect(plan.allocation.find((row) => row.symbol === "ETH")).toMatchObject({
    before_value_eur: "100",
    after_value_eur: "100",
  });
  expect(
    cryptoModel.ledger.positions.find((row) => row.symbol === "BTC")!.quantity,
  ).toBe("1");
});

test("contradictory category/coin choices and missing spread evidence never create crypto purchases", () => {
  const now = "2026-10-23T10:00:00Z",
    all = [cryptoTerms("BTC-ID"), cryptoTerms("ETH-ID")];
  for (const choice of [
    { mode: "mixed", crypto_budget_eur: "202", coin: "BTC" },
    { mode: "crypto", crypto_budget_eur: "100", coin: "BTC" },
    { mode: "crypto", crypto_budget_eur: "202", coin: "both", btc_pct: "100" },
    { mode: "crypto", crypto_budget_eur: "202", coin: "ETH", btc_pct: "50" },
    { mode: "etf", crypto_budget_eur: "1" },
  ])
    expect(() =>
      planContribution(cryptoModel, mixedTargets, all, "202", now, choice),
    ).toThrow("invalid_choice");
  const unknown = planContribution(
    cryptoModel,
    mixedTargets,
    [{ ...cryptoTerms("BTC-ID"), spread_allowance_pct: null }],
    "202",
    now,
    { mode: "crypto", crypto_budget_eur: "202", coin: "BTC" },
  );
  expect(unknown.state).toBe("incomplete");
  expect(unknown.purchases).toEqual([]);
  expect(unknown.diagnostics).toContain(
    "missing_reviewed_spread_allowance:BTC-ID",
  );
  const stale = structuredClone(cryptoModel);
  stale.observed_prices.BTC.observed_at = "2026-10-23T09:54:59Z";
  expect(
    planContribution(stale, mixedTargets, all, "202", now, {
      mode: "crypto",
      crypto_budget_eur: "202",
      coin: "BTC",
    }).diagnostics,
  ).toContain("missing_eligible_price:BTC-ID");
});

test("first crypto purchase requires reviewed broker identity and a quote from the accepted generation", () => {
  const first = {
    ...model,
    contribution_assets: [
      {
        asset_id: "BTC-ID",
        symbol: "BTC",
        asset_kind: "Cryptocurrency",
        identity_evidence: "Synthetic reviewed broker identity",
        verified_at: "2026-01-01T00:00:00Z",
      },
    ],
    observed_prices: {
      ...model.observed_prices,
      BTC: { price_eur: "100", observed_at: "2026-10-23T10:00:00Z" },
    },
  };
  const plan = planContribution(
    first,
    settings,
    [cryptoTerms("BTC-ID")],
    "202",
    "2026-10-23T10:00:00Z",
    { mode: "crypto", crypto_budget_eur: "202", coin: "BTC" },
  );
  expect(plan.state).toBe("complete");
  expect(plan.purchases[0].symbol).toBe("BTC");
  expect(
    plan.allocation.find((row) => row.symbol === "BTC")!.before_value_eur,
  ).toBe("0");
  const noQuote = { ...first, observed_prices: model.observed_prices };
  expect(
    planContribution(
      noQuote,
      settings,
      [cryptoTerms("BTC-ID")],
      "202",
      "2026-10-23T10:00:00Z",
      { mode: "crypto", crypto_budget_eur: "202", coin: "BTC" },
    ).state,
  ).toBe("incomplete");
});

import { createRefresh } from "./refresh";
test("bounded refresh includes reviewed first-purchase quote symbols in its coherent accepted batch", async () => {
  const snapshot = {
    generation_id: "g",
    published_at: "2026-10-23T10:00:00Z",
    data_classification: "synthetic" as const,
    read_model: JSON.parse(
      await (
        await import("node:fs/promises")
      ).readFile("hosted/synthetic.fixture", "utf8"),
    ),
  };
  let published: any;
  const requested: string[] = [];
  const refresh = createRefresh(
    {
      read: async () => ({
        snapshot,
        settings: { version: "1", targets: [] },
        planning_symbols: ["BTC"],
        mappings: [
          {
            symbol: "SYNTHETIC",
            provider: "yahoo",
            provider_symbol: "SYNTHETIC",
            evidence: "fixture",
          },
          {
            symbol: "BTC",
            provider: "binance",
            provider_symbol: "BTCEUR",
            evidence: "fixture",
          },
        ],
      }),
      publish: async (_input, model) => {
        published = model;
        return true;
      },
    },
    async (mapping) => {
      requested.push(mapping.symbol);
      return {
        price_eur: "1200",
        observed_at: "2026-10-23T10:00:00Z",
        retrieved_at: "2026-10-23T10:00:01Z",
        provider: "synthetic",
        currency: "EUR",
        adjustment_basis: "unadjusted",
      };
    },
    () => Date.parse("2026-10-23T10:00:01Z"),
  );
  expect((await refresh()).state).toBe("refreshed");
  expect(requested.sort()).toEqual(["BTC", "SYNTHETIC"]);
  expect(published.observed_prices.BTC.price_eur).toBe("1200");
  expect(published.ledger.positions).toHaveLength(1);
});

test("crypto-only ETH allocation works without ETF targets and never silently substitutes BTC", () => {
  const plan = planContribution(
    cryptoModel,
    { version: "1", targets: [] },
    [cryptoTerms("ETH-ID")],
    "202",
    "2026-10-23T10:00:00Z",
    { mode: "crypto", crypto_budget_eur: "202", coin: "ETH" },
  );
  expect(plan.state).toBe("complete");
  expect(plan.budgets).toEqual({ etf_eur: "0", btc_eur: "0", eth_eur: "202" });
  expect(plan.purchases.map((row) => row.symbol)).toEqual(["ETH"]);
  expect(
    planContribution(
      cryptoModel,
      { version: "1", targets: [] },
      [cryptoTerms("ETH-ID")],
      "202",
      "2026-10-23T10:00:00Z",
      { mode: "mixed", crypto_budget_eur: "100", coin: "ETH" },
    ).diagnostics,
  ).toContain("invalid_targets");
});

test("authenticated API rejects contradictory allocations and returns an explicit crypto preview", async () => {
  const contribution = createContribution(
    {
      read: async () => ({
        snapshot: {
          generation_id: "crypto-g",
          published_at: "2026-10-23T10:00:00Z",
          data_classification: "synthetic",
          read_model: cryptoModel,
        },
        settings: mixedTargets,
        terms: [cryptoTerms("BTC-ID")],
      }),
    },
    () => Date.parse("2026-10-23T10:00:00Z"),
  );
  const app = createApplication({
    authQuery: databaseTransport(),
    readAccepted: async () => null,
    contribution: async (value) => contribution(value),
  });
  const cookie = (await login()).session!;
  const call = (choice: unknown) =>
    app(
      new Request(env.APP_ORIGIN + "/api/contribution", {
        method: "POST",
        headers: { Cookie: cookie, Origin: env.APP_ORIGIN },
        body: JSON.stringify({
          generation_id: "crypto-g",
          rebalancing_targets_version: "1",
          budget_eur: "202",
          choice,
        }),
      }),
      env,
    );
  expect(
    (await call({ mode: "crypto", crypto_budget_eur: "100", coin: "BTC" }))
      .status,
  ).toBe(400);
  const response = await call({
    mode: "crypto",
    crypto_budget_eur: "202",
    coin: "BTC",
  });
  expect(response.status).toBe(200);
  expect(await response.json()).toMatchObject({
    state: "complete",
    budgets: { etf_eur: "0", btc_eur: "202", eth_eur: "0" },
    warnings: ["crypto_concentration_increases", "crypto_above_target:BTC-ID"],
  });
});
