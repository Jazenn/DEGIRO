const node = (tag, value) => {
  const element = document.createElement(tag);
  element.textContent = value;
  return element;
};
function table(headers, rows) {
  const wrapper = node("div", "");
  wrapper.style.overflowX = "auto";
  const result = document.createElement("table");
  const header = document.createElement("tr");
  headers.forEach((value) => header.append(node("th", value)));
  const head = document.createElement("thead");
  head.append(header);
  result.append(head);
  const body = document.createElement("tbody");
  rows.forEach((values) => {
    const row = document.createElement("tr");
    values.forEach((value) => row.append(node("td", value ?? "Unavailable")));
    body.append(row);
  });
  result.append(body);
  wrapper.append(result);
  return wrapper;
}
export function contributionUI(root, snapshotNode, request = fetch) {
  let snapshot = snapshotNode?.acceptedSnapshot ?? null,
    epoch = 0,
    busy = false,
    requiresRefresh = false;
  root.replaceChildren(
    node("h2", "Plan a contribution"),
    node(
      "p",
      "Manual buy-only estimates. The chosen contribution covers purchases and fees; other available cash is excluded.",
    ),
  );
  const form = document.createElement("form"),
    label = node("label", "Contribution budget in EUR "),
    budget = document.createElement("input");
  budget.type = "text";
  budget.inputMode = "decimal";
  budget.value = "0";
  budget.required = true;
  budget.pattern = "[0-9]{1,12}([.][0-9]{1,2})?";
  label.append(budget);
  const destinationLabel = node("label", "Contribution destination "),
    mode = document.createElement("select");
  for (const [value, title] of [
    ["etf", "ETFs"],
    ["crypto", "Crypto"],
    ["mixed", "ETFs and crypto"],
  ]) {
    const option = node("option", title);
    option.value = value;
    mode.append(option);
  }
  destinationLabel.append(mode);
  const cryptoFields = document.createElement("fieldset");
  cryptoFields.append(node("legend", "Explicit crypto contribution"));
  const cryptoLabel = node("label", "Of the total budget, crypto EUR "),
    cryptoBudget = document.createElement("input");
  cryptoBudget.inputMode = "decimal";
  cryptoBudget.required = true;
  cryptoBudget.pattern = "[0-9]{1,12}([.][0-9]{1,2})?";
  cryptoLabel.append(cryptoBudget);
  const coinLabel = node("label", "Cryptocurrency "),
    coin = document.createElement("select");
  for (const [value, title] of [
    ["", "Choose a coin"],
    ["BTC", "Bitcoin"],
    ["ETH", "Ethereum"],
    ["both", "Bitcoin and Ethereum"],
  ]) {
    const option = node("option", title);
    option.value = value;
    coin.append(option);
  }
  coin.required = true;
  coinLabel.append(coin);
  const splitLabel = node(
      "label",
      "Bitcoin percentage of the crypto contribution ",
    ),
    split = document.createElement("input");
  split.type = "number";
  split.min = "0.01";
  split.max = "99.99";
  split.step = "0.01";
  split.required = true;
  splitLabel.append(split);
  cryptoFields.append(
    cryptoLabel,
    coinLabel,
    splitLabel,
    node(
      "p",
      "Ethereum receives the remaining crypto contribution. Unused crypto or ETF money stays cash; it is not transferred automatically.",
    ),
  );
  const controls = () => {
    cryptoFields.hidden = mode.value === "etf";
    cryptoFields.disabled = mode.value === "etf";
    cryptoBudget.readOnly = mode.value === "crypto";
    if (mode.value === "crypto") cryptoBudget.value = budget.value;
    splitLabel.hidden = coin.value !== "both";
    split.disabled = coin.value !== "both";
  };
  controls();
  const submit = node("button", "Preview purchases");
  submit.type = "submit";
  submit.disabled = !snapshot;
  const status = node(
    "p",
    snapshot
      ? "Enter a contribution to preview."
      : "Load an accepted Snapshot before planning.",
  );
  status.setAttribute("role", "status");
  const output = node("div", "");
  form.append(label, destinationLabel, cryptoFields, submit);
  root.append(form, status, output);
  const invalidate = (message) => {
    epoch++;
    output.replaceChildren();
    status.textContent = message;
  };
  budget.addEventListener("input", () => {
    controls();
    invalidate("Budget changed. Preview again.");
  });
  mode.addEventListener("change", () => {
    controls();
    invalidate("Contribution choice changed. Preview again.");
  });
  coin.addEventListener("change", () => {
    controls();
    invalidate("Crypto choice changed. Preview again.");
  });
  cryptoBudget.addEventListener("input", () =>
    invalidate("Crypto contribution changed. Preview again."),
  );
  split.addEventListener("input", () =>
    invalidate("Coin split changed. Preview again."),
  );
  document.addEventListener("accepted-snapshot", (event) => {
    snapshot = event.detail;
    requiresRefresh = false;
    submit.disabled = busy;
    invalidate(
      "Valuation changed. Preview again against the displayed generation.",
    );
  });
  document.addEventListener("targets-saved", () => {
    requiresRefresh = true;
    submit.disabled = true;
    invalidate(
      "Targets changed. Refresh current prices before previewing again.",
    );
  });
  document.addEventListener("valuation-refresh-started", () =>
    invalidate("Refreshing valuation. Existing preview cleared."),
  );
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!snapshot || submit.disabled || busy) return;
    const operation = ++epoch;
    busy = true;
    submit.disabled = true;
    output.replaceChildren();
    status.textContent = "Preparing a coherent contribution preview...";
    const source = snapshot;
    const controller = new AbortController(),
      deadline = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await request("/api/contribution", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          budget_eur: budget.value,
          generation_id: source.generation_id,
          rebalancing_targets_version: source.read_model.rebalancing_targets_version,
          ...(mode.value === "etf"
            ? {}
            : {
                choice: {
                  mode: mode.value,
                  crypto_budget_eur: cryptoBudget.value,
                  coin: coin.value,
                  ...(coin.value === "both" ? { btc_pct: split.value } : {}),
                },
              }),
        }),
      });
      if (operation !== epoch) return;
      if (response.status === 409) {
        status.textContent =
          "Valuation or targets changed on another device. Refresh current prices before previewing again.";
        return;
      }
      if (response.status === 400) {
        status.textContent =
          "Check the total budget, explicit crypto amount and coin split. EUR amounts need up to two decimal places.";
        return;
      }
      if (!response.ok) throw Error();
      const plan = await response.json();
      if (operation !== epoch) return;
      if (
        plan.generation_id !== snapshot.generation_id ||
        plan.rebalancing_targets_version !== snapshot.read_model.rebalancing_targets_version || plan.settings_version !== snapshot.read_model.settings_version
      )
        throw Error();
      if (plan.budgets && plan.remaining_cash_by_category) {
        output.append(
          node("h3", "Unspent cash by contribution choice"),
          table(["Contribution choice", "Allocated budget EUR", "Unspent cash EUR"],
            [["ETFs", "etf_eur"], ["Bitcoin", "btc_eur"], ["Ethereum", "eth_eur"]]
              .map(([label, key]) => [label, plan.budgets[key], plan.remaining_cash_by_category[key]])),
          node("p", "Unspent amounts stay cash. They are not automatically moved to another category or used for future purchases."),
        );
      }
      if (plan.state !== "complete") {
        status.textContent =
          "Estimate incomplete. No purchases proposed; missing inputs are not treated as free.";
        output.append(
          node(
            "p",
            (plan.diagnostics ?? [])
              .map((reason) => {
                const [kind, asset] = reason.split(":");
                const messages = {
                  missing_reviewed_execution_terms:
                    "Reviewed fees or quantity minimums are missing for ",
                  missing_reviewed_spread_allowance:
                    "A reviewed spread allowance is missing for ",
                  missing_eligible_price:
                    "An eligible source price is missing for ",
                  crypto_identity_missing_or_ambiguous:
                    "Broker crypto identity needs review for ",
                  invalid_targets: "ETF targets must be valid and total 100%",
                  unknown_target_asset:
                    "Target Asset identity needs review for ",
                };
                return (messages[kind] ?? kind) + (asset ?? "");
              })
              .join("; "),
          ),
          node(
            "p",
            `Unallocated contribution EUR ${plan.remaining_cash_eur}. Fees unknown.`,
          ),
        );
        return;
      }
      status.textContent = `Manual estimate from generation ${plan.generation_id}, financial settings ${plan.settings_version}, targets ${plan.rebalancing_targets_version}. Verify current broker prices and charges before acting.`;
      output.append(
        node(
          "p",
          `Purchases EUR ${plan.invested_eur} � Estimated fees EUR ${plan.fees_eur} � Spread allowance EUR ${plan.spread_allowance_eur ?? "0"} � Remaining cash EUR ${plan.remaining_cash_eur}`,
        ),
      );
      if (plan.budgets && !plan.remaining_cash_by_category)
        output.append(
          node(
            "p",
            "ETF budget EUR " +
              plan.budgets.etf_eur +
              " / BTC budget EUR " +
              plan.budgets.btc_eur +
              " / ETH budget EUR " +
              plan.budgets.eth_eur,
          ),
        );
      for (const warning of plan.warnings ?? [])
        output.append(
          node(
            "p",
            warning === "crypto_concentration_increases"
              ? "Crypto concentration increases with this contribution. Review the before/after allocation; no hard cap has been applied."
              : "Crypto allocation exceeds its target for " +
                  warning.split(":")[1] +
                  ". Review your chosen contribution.",
          ),
        );
      output.append(node("p", plan.policy));
      if (!plan.purchases.length)
        output.append(
          node(
            "p",
            "This budget and the verified minimums produce no purchases. All unspent cash is retained.",
          ),
        );
      else
        output.append(
          table(
            [
              "Asset",
              "Buy quantity",
              "Reference price EUR",
              "Purchase fee EUR",
              "Fee coverage",
              "Spread allowance EUR",
              "All-in EUR",
            ],
            plan.purchases.map((row) => [
              row.symbol ?? row.asset_id,
              row.quantity,
              row.price_eur,
              row.fee_eur,
              row.fee_status,
              row.spread_allowance_eur ?? "0",
              row.total_cost_eur,
            ]),
          ),
        );
      output.append(
        node(
          "h3",
          "Allocation across all holdings, including the Long-Term Crypto Core (cash shown separately)",
        ),
        table(
          ["Asset", "Before %", "After %", "Target %", "Before deviation (pp)", "After deviation (pp)"],
          plan.allocation.map((row) => [
            row.symbol ?? row.asset_id,
            row.before_pct,
            row.after_pct,
            row.target_pct,
            row.before_deviation_pct,
            row.after_deviation_pct,
          ]),
        ),
      );
      output.append(node("p", "Allocation percentages exclude cash and purchase fees. Deviations are percentage points from the target: negative is below target, positive is above target. Remaining contribution cash is shown separately."));
      const sources = document.createElement("details");
      sources.append(
        node("summary", "Quote times and reviewed execution terms"),
      );
      plan.purchases.forEach((row) =>
        sources.append(
          node(
            "p",
            `${row.asset_id}: source observation ${row.quote_observed_at}; execution terms ${row.terms_revision}; ${row.terms_evidence}; Quantity step ${row.quantity_step ?? "unavailable"}; minimum quantity ${row.minimum_quantity ?? "unavailable"}; minimum purchase EUR ${row.minimum_notional_eur ?? "unavailable"}; spread evidence ${row.spread_evidence ?? "unavailable"}; valid until ${row.terms_valid_until ?? "unavailable"}.`,
          ),
        ),
      );
      output.append(sources);
    } catch {
      if (operation === epoch)
        status.textContent =
          "Contribution preview unavailable. Previous suggestions cleared. Retry the preview.";
    } finally {
      clearTimeout(deadline);
      busy = false;
      submit.disabled = requiresRefresh || !snapshot;
    }
  });
}
const root = document.querySelector("#contribution");
if (root) contributionUI(root, document.querySelector("#snapshot"));
