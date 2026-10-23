// @vitest-environment jsdom
import { expect, test } from "vitest";
// @ts-expect-error static browser module
import { contributionUI } from "./public/contribution.js";

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
        generation_id: "g1",
        settings_version: "1",
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
          },
        ],
        allocation: [
          {
            asset_id: "ETF",
            before_pct: "100",
            after_pct: "100",
            target_pct: "100",
          },
        ],
      });
    },
  );
  document.dispatchEvent(
    new CustomEvent("accepted-snapshot", {
      detail: { generation_id: "g1", read_model: { settings_version: "1" } },
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
    settings_version: "1",
  });
  expect(root.textContent).toContain("Estimated fees EUR 1");
  expect(root.textContent).toContain("Manual");
  document.dispatchEvent(
    new CustomEvent("accepted-snapshot", {
      detail: { generation_id: "g2", read_model: { settings_version: "1" } },
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
        detail: { generation_id, read_model: { settings_version: "1" } },
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
      generation_id: "g1",
      settings_version: "1",
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
        generation_id: "g1",
        settings_version: "1",
        budget_eur: "200",
        budgets: { etf_eur: "100", btc_eur: "75", eth_eur: "25" },
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
      detail: { generation_id: "g1", read_model: { settings_version: "1" } },
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
});
