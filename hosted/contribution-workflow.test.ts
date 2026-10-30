// @vitest-environment jsdom
import { expect, test } from "vitest";
// @ts-expect-error static browser module
import { contributionUI } from "./public/contribution.js";
import { createContribution } from "./contribution-store";

test.each(["missing-fees", "missing-price", "tiny-budget", "zero-budget"])(
  "ETF workflow retains the chosen budget and explains %s without executable purchases",
  async (scenario) => {
    document.body.innerHTML = '<section id="snapshot"></section><section id="contribution"></section>';
    const root = document.querySelector("#contribution")!;
    const snapshot = { generation_id: "etf-synthetic", published_at: "2026-10-23T10:00:00Z",
      data_classification: "synthetic" as const, read_model: {
        settings_version: "financial-fixture", rebalancing_targets_version: "1",
        ledger: { market_value_eur: "100", positions: [
          { broker_asset_id: "ETF", symbol: "ETF", asset_kind: "ETF", quantity: "1", market_value_eur: "100" },
        ] },
        observed_prices: scenario === "missing-price" ? {} : {
          ETF: { price_eur: "100", observed_at: "2026-10-23T10:00:00Z" },
        },
      } };
    const preview = createContribution({ read: async () => ({ snapshot,
      settings: { version: "1", targets: [{ asset_id: "ETF", target_pct: "100" }] },
      terms: scenario === "missing-fees" ? [] : [{ asset_id: "ETF", revision: "synthetic-1",
        quantity_step: "1", minimum_quantity: "1", minimum_notional_eur: "0", fixed_fee_eur: "1",
        fee_rate_pct: "0", minimum_fee_eur: "0", fee_status: "estimated",
        evidence: "Synthetic reviewed terms, not a real broker tariff",
        valid_from: "2026-01-01T00:00:00Z", valid_until: "2027-01-01T00:00:00Z" }],
    }) }, () => Date.parse("2026-10-23T10:00:00Z"));
    contributionUI(root, document.querySelector("#snapshot"), async (_url: string, options: RequestInit) =>
      Response.json(await preview(JSON.parse(String(options.body)))));
    document.dispatchEvent(new CustomEvent("accepted-snapshot", { detail: snapshot }));
    const budget = scenario === "zero-budget" ? "0" : scenario === "tiny-budget" ? "100" : "101";
    root.querySelector("input")!.value = budget;
    root.querySelector("form")!.dispatchEvent(new Event("submit", { cancelable: true }));
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(root.querySelector("thead")?.textContent ?? "").not.toContain("Buy quantity");
    if (scenario.startsWith("missing")) {
      expect(root.textContent).toContain("Estimate incomplete. No purchases proposed");
      expect(root.textContent).toContain("Unallocated contribution EUR 101. Fees unknown.");
      expect(root.textContent).toContain(scenario === "missing-fees"
        ? "Reviewed fees or quantity minimums are missing for ETF"
        : "An eligible source price is missing for ETF");
    } else {
      expect(root.textContent).toContain("produce no purchases");
      expect(root.textContent).toContain(`Remaining cash EUR ${budget}`);
      expect(root.textContent).toContain("Estimated fees EUR 0");
    }
    expect(snapshot.read_model.ledger.positions[0].quantity).toBe("1");
  },
);

test("owner previews a manual ETF contribution and changing generation invalidates the visible plan", async () => {
  document.body.innerHTML =
    '<section id="snapshot"></section><section id="contribution"></section>';
  const root = document.querySelector("#contribution")!;
  let submitted: any;
  contributionUI(
    root,
    document.querySelector("#snapshot"),
    async (_url: string, options: RequestInit) => {
      submitted = JSON.parse(options.body as string);
      return Response.json({
        state: "complete",
        settings_version:"financial-fixture",
        generation_id: "g1",
        rebalancing_targets_version: "1",
        budget_eur: "101",
        invested_eur: "100",
        fees_eur: "1",
        remaining_cash_eur: "0",
        policy:
          "Proportional shortfalls; Asset identifier tie-break; rounding stays cash.",
        purchases: [
          {
            asset_id: "ETF",
            quantity: "1",
            price_eur: "100",
            fee_eur: "1",
            fee_status: "estimated",
            total_cost_eur: "101",
            quote_observed_at: "2026-10-23T10:00:00Z",
            terms_revision: "review-1",
            terms_evidence: "Synthetic all-in fee evidence",
            quantity_step: "1",
            minimum_quantity: "1",
            minimum_notional_eur: "0",
          },
        ],
        allocation: [
          {
            asset_id: "ETF",
            before_pct: "100",
            after_pct: "100",
            target_pct: "100",
            before_deviation_pct: "0",
            after_deviation_pct: "0",
          },
        ],
      });
    },
  );
  document.dispatchEvent(
    new CustomEvent("accepted-snapshot", {
      detail: { generation_id: "g1", read_model: { settings_version:"financial-fixture", rebalancing_targets_version: "1" } },
    }),
  );
  root.querySelector("input")!.value = "101";
  root
    .querySelector("form")!
    .dispatchEvent(new Event("submit", { cancelable: true }));
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(submitted).toEqual({
    budget_eur: "101",
    generation_id: "g1",
    rebalancing_targets_version: "1",
  });
  expect(root.textContent).toContain("Estimated fees EUR 1");
  expect(root.textContent).toContain("Manual");
  expect(root.textContent).toContain("Before deviation (pp)");
  expect(root.textContent).toContain("After deviation (pp)");
  expect(root.textContent).toContain("Quantity step 1; minimum quantity 1; minimum purchase EUR 0");
  document.dispatchEvent(
    new CustomEvent("accepted-snapshot", {
      detail: { generation_id: "g2", read_model: { settings_version:"financial-fixture", rebalancing_targets_version: "1" } },
    }),
  );
  expect(root.textContent).toContain("changed");
  expect(root.textContent).not.toContain("Estimated fees EUR 1");
});

test("late preview cannot repopulate old purchases after refresh and missing inputs remain explicit", async () => {
  document.body.innerHTML =
    '<section id="snapshot"></section><section id="contribution"></section>';
  const root = document.querySelector("#contribution")!;
  let release!: (response: Response) => void;
  contributionUI(
    root,
    document.querySelector("#snapshot"),
    () =>
      new Promise((resolve) => {
        release = resolve;
      }),
  );
  const publish = (generation_id: string) =>
    document.dispatchEvent(
      new CustomEvent("accepted-snapshot", {
        detail: { generation_id, read_model: { settings_version:"financial-fixture", rebalancing_targets_version: "1" } },
      }),
    );
  publish("g1");
  root.querySelector("input")!.value = "101";
  root
    .querySelector("form")!
    .dispatchEvent(new Event("submit", { cancelable: true }));
  publish("g2");
  release(
    Response.json({
      state: "complete",
        settings_version:"financial-fixture",
      generation_id: "g1",
      rebalancing_targets_version: "1",
    }),
  );
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(root.textContent).toContain("Valuation changed");
  expect(root.querySelector("button")!.disabled).toBe(false);
  document.dispatchEvent(
    new CustomEvent("targets-saved", { detail: { version: "2" } }),
  );
  expect(root.querySelector("button")!.disabled).toBe(true);
  expect(root.textContent).toContain("Targets changed");
});

test("owner explicitly chooses mixed funding and a BTC/ETH split and sees concentration warnings", async () => {
  document.body.innerHTML =
    '<section id="snapshot"></section><section id="contribution"></section>';
  const root = document.querySelector("#contribution")!;
  let submitted: any;
  contributionUI(
    root,
    document.querySelector("#snapshot"),
    async (_url: string, options: RequestInit) => {
      submitted = JSON.parse(options.body as string);
      return Response.json({
        state: "complete",
        settings_version:"financial-fixture",
        generation_id: "g1",
        rebalancing_targets_version: "1",
        budget_eur: "200",
        budgets: { etf_eur: "100", btc_eur: "75", eth_eur: "25" },
        remaining_cash_by_category: { etf_eur: "0.25", btc_eur: "0.5", eth_eur: "0.25" },
        invested_eur: "196",
        fees_eur: "2",
        spread_allowance_eur: "1",
        remaining_cash_eur: "1",
        policy: "explicit contribution",
        warnings: ["crypto_concentration_increases"],
        purchases: [],
        allocation: [],
      });
    },
  );
  document.dispatchEvent(
    new CustomEvent("accepted-snapshot", {
      detail: { generation_id: "g1", read_model: { settings_version:"financial-fixture", rebalancing_targets_version: "1" } },
    }),
  );
  const inputs = root.querySelectorAll("input");
  inputs[0].value = "200";
  const mode = root.querySelectorAll("select")[0];
  mode.value = "mixed";
  mode.dispatchEvent(new Event("change"));
  inputs[1].value = "100";
  const coin = root.querySelectorAll("select")[1];
  coin.value = "both";
  coin.dispatchEvent(new Event("change"));
  inputs[2].value = "75";
  root
    .querySelector("form")!
    .dispatchEvent(new Event("submit", { cancelable: true }));
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(submitted.choice).toEqual({
    mode: "mixed",
    crypto_budget_eur: "100",
    coin: "both",
    btc_pct: "75",
  });
  expect(root.textContent).toContain("Crypto concentration increases");
  expect(root.textContent).toContain("Spread allowance EUR 1");
  expect(root.textContent).toContain("Unspent cash by contribution choice");
  expect(Array.from(root.querySelectorAll("tbody tr"), row => row.textContent)).toEqual([
    "ETFs1000.25", "Bitcoin750.5", "Ethereum250.25",
  ]);
  inputs[2].value = "60";
  inputs[2].dispatchEvent(new Event("input"));
  expect(root.textContent).toContain("Coin split changed. Preview again.");
  expect(root.textContent).not.toContain("Unspent cash by contribution choice");
});
