const node = (tag, content) => { const value = document.createElement(tag); value.textContent = content; return value; };
const messages = {
  invalid_crypto_plan: 'Choose a positive retained core, three positive proportions totaling 100%, and three increasing positive levels',
  reviewed_sale_quantity_terms_required: 'Verified sale permissions and quantity rules are missing or expired',
  verified_crypto_holding_required: 'Verified direct crypto holdings and complete quantity history are required',
  positive_tactical_quantity_required: 'The chosen core must leave a positive tactical quantity',
  stage_below_reviewed_minimum: 'A rounded stage is zero or below the verified quantity/notional minimum; review the core and proportions',
  snapshot_changed: 'Holdings changed; reload and preview again',
  snapshot_or_plan_changed: 'Holdings or the accepted plan changed; reload and review',
  market_history_changed: 'Market history changed; preview the latest levels again',
  reviewed_inputs_changed: 'Reviewed broker rules or market context changed; reload and preview again',
  complete_market_history_required: 'Complete recent history is required for a new plan; existing accepted plans remain saved',
};
export function cryptoPlanUI(root, request = fetch, clock = () => Date.now()) {
  root.replaceChildren(node('h3', 'Accepted Crypto Plans'), node('p', 'Choose your own retained core and three sale proportions. Preview exact quantities before explicitly accepting. Acceptance never executes a Transaction.'));
  let snapshot = document.querySelector('#snapshot')?.acceptedSnapshot;
  const states = new Map();
  const load = node('button', 'Reload accepted plans'); load.type = 'button'; root.append(load);
  async function http(url, body) {
    const controller = new AbortController(), deadline = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await request(url, { method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
        ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) });
      const value = await response.json();
      if (!response.ok) { const reason = value.reason ?? value.error; throw Error(messages[reason] ?? (response.status === 409 ? 'Inputs changed. Reload before reviewing again.' : 'Plan operation unavailable.')); }
      return value;
    } finally { clearTimeout(deadline); }
  }
  for (const coin of ['BTC-EUR','ETH-EUR']) {
    const section = document.createElement('section'); section.setAttribute('aria-label', `${coin} Accepted Crypto Plan`);
    const form = document.createElement('form'); form.setAttribute('aria-label', `${coin} plan choices`);
    const output = document.createElement('div'), accepted = document.createElement('div'), comparison = document.createElement('p'), holdings = document.createElement('p');
    const status = node('p', 'Reading accepted plan...'); status.setAttribute('role', 'status');
    const state = { coin, version: null, terms: null, plan: null, market: null, payload: null, epoch: 0, busy: false };
    states.set(coin, state);
    section.append(node('h4', coin), accepted, holdings, comparison, form, output, status); root.append(section);
    function input(label, name) {
      const wrapper = document.createElement('label'); wrapper.append(node('span', label));
      const field = document.createElement('input'); field.name = name; field.type = 'text'; field.inputMode = 'decimal'; field.required = true;
      wrapper.append(field); form.append(wrapper); return field;
    }
    const core = input('Your Long-Term Crypto Core (units, required)', 'core');
    const shares = [1,2,3].map(index => input(`Stage ${index} share of original tactical quantity (%)`, `share-${index}`));
    const levels = [1,2,3].map(index => input(`Reviewed stage ${index} level (EUR)`, `level-${index}`));
    const copy = node('button', 'Copy reviewed suggested sale levels'); copy.type = 'button';
    const preview = node('button', 'Preview quantities'); preview.type = 'submit';
    const reviewLabel = document.createElement('label'), review = document.createElement('input'); review.type = 'checkbox'; review.name = 'review';
    reviewLabel.append(review, node('span', 'I reviewed the core, original stage quantities and rounding residual.'));
    const accept = node('button', 'Accept reviewed plan'); accept.type = 'button'; accept.disabled = true;
    form.append(copy, preview, reviewLabel, accept);
    function invalidate(message) { state.epoch++; state.payload = null; review.checked = false; accept.disabled = true; output.replaceChildren(); if (message) status.textContent = message; }
    function comparisonText() {
      const position = snapshot?.read_model?.ledger?.positions?.find(row => row.broker_asset_id === state.terms?.asset_id);
      holdings.textContent = position ? `Current recorded holding: ${position.quantity} ${coin} units (broker Asset ${position.broker_asset_id}).` : 'Current verified holding is unavailable in the displayed Snapshot.';
      if (!state.plan) { comparison.textContent = 'No personal core or stage allocation has been selected automatically.'; return; }
      comparison.textContent = state.market && state.market.state !== 'paused' && Date.parse(state.market.valid_until) > clock()
        ? state.plan.stages.map((stage, index) => `Stage ${index+1}: accepted EUR ${stage.level_eur}; latest suggested EUR ${state.market.sale[index]?.price_eur ?? 'unavailable'}.`).join(' ') + ' Accepted levels and quantities stay fixed.'
        : 'Latest suggestions unavailable. Accepted levels and quantities stay fixed.';
    }
    function showPlan() {
      accepted.replaceChildren();
      if (state.plan) {
        const plan = state.plan;
        accepted.append(node('p', `Plan ${plan.plan_id} | version ${plan.plan_version ?? state.version} | accepted ${plan.accepted_at}`),
          node('p', `Retained core ${plan.core_quantity}; original tactical quantity ${plan.original_tactical_quantity}; original holdings ${plan.held_quantity_at_acceptance}.`));
        for (const [index, stage] of plan.stages.entries()) accepted.append(node('p', `Stage ${index+1}: ${stage.quantity} units (${stage.proportion_pct}% of original tactical quantity), level EUR ${stage.level_eur}. ${stage.stage_id}`));
        accepted.append(node('p', `Rounding residual retained: ${plan.rounding_residual_quantity} units. New purchases do not resize this plan. An existing plan requires an explicitly reviewed replacement.`),
          node('p', `Accepted ledger ${plan.ledger_version}; financial settings ${plan.financial_settings_version}; market series ${plan.source_market.market_version}.`));
      } else accepted.append(node('p', 'No accepted plan recorded.'));
      form.querySelectorAll('input,button').forEach(control => { control.disabled = !!state.plan; });
      accept.disabled = true; comparisonText();
    }
    async function read() {
      invalidate();
      try {
        const value = await http('/api/crypto/plans?coin=' + encodeURIComponent(coin));
        state.version = value.version; state.terms = value.terms; state.plan = value.plan; showPlan();
        status.textContent = state.plan ? 'Accepted plan loaded. Acceptance is not execution.' : state.terms
          ? `Reviewed sale quantity rules ${state.terms.revision}: step ${state.terms.quantity_step}, minimum ${state.terms.minimum_quantity}, minimum notional EUR ${state.terms.minimum_notional_eur}. ${state.terms.evidence}`
          : 'Reviewed sale permissions and quantity/minimum rules are unavailable. Acceptance requires verified broker evidence.';
      } catch { status.textContent = 'Accepted-plan read failed. Any previously displayed plan is retained. Reload to confirm shared state.'; }
    }
    form.addEventListener('input', event => {
      if (event.target === review) accept.disabled = !review.checked || !state.payload || state.busy;
      else invalidate('Choices changed. Preview quantities again before accepting.');
    });
    copy.addEventListener('click', () => {
      if (!state.market || state.market.state === 'paused' || Date.parse(state.market.valid_until) <= clock()) { invalidate('Preview complete suggested levels above before reviewing a plan.'); return; }
      levels.forEach((field,index) => { field.value = state.market.sale[index].price_eur; });
      invalidate('Suggested levels copied for your review. Choose the core and all three stage proportions explicitly.');
    });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (state.busy || state.plan) return;
      invalidate();
      if (!snapshot || !state.terms || state.version === null || !state.market || state.market.state === 'paused' || Date.parse(state.market.valid_until) <= clock()) { status.textContent = 'Load current holdings, reviewed sale rules and complete suggested levels before previewing.'; return; }
      const epoch = state.epoch;
      const payload = { coin, operation_id: crypto.randomUUID(), expected_version: state.version, generation_id: snapshot.generation_id,
        market_version: state.market.market_version, terms_revision: state.terms.revision, templates: state.market.templates,
        core_quantity: core.value, proportions: shares.map(field=>field.value), levels_eur: levels.map(field=>field.value) };
      state.busy = true; preview.disabled = true;
      try {
        const result = await http('/api/crypto/plans/preview', payload);
        if (epoch !== state.epoch) return;
        if (result.state !== 'preview') throw Error(result.reason ?? 'Preview unavailable');
        const plan = result.plan;
        output.append(node('h5','Review original quantities'), node('p', `Core ${plan.core_quantity}; original tactical quantity ${plan.original_tactical_quantity}.`));
        for (const [index,stage] of plan.stages.entries()) output.append(node('p', `Stage ${index+1}: ${stage.quantity} units at reviewed EUR ${stage.level_eur}, ${stage.proportion_pct}% of original tactical quantity.`));
        output.append(node('p', `Rounding residual retained: ${plan.rounding_residual_quantity} units. Combined stages cannot consume your core.`));
        state.payload = payload; status.textContent = 'Review the preview, check the confirmation, then accept explicitly. No Transaction will be executed.';
      } catch (error) { if (epoch === state.epoch) status.textContent = error.message + '. Correct the inputs or reload shared state.'; }
      finally { state.busy = false; preview.disabled = !!state.plan; }
    });
    accept.addEventListener('click', async () => {
      if (!review.checked || !state.payload || state.busy) return;
      state.busy = true; accept.disabled = true;
      try {
        const result = await http('/api/crypto/plans', state.payload);
        if (result.state !== 'accepted') throw Error(result.reason ?? 'Acceptance unavailable');
        state.plan = result.plan; state.version = result.version; invalidate(); showPlan(); status.textContent = 'Plan accepted and saved across devices. No Transaction was executed.';
      } catch (error) { status.textContent = error.message + '. Reload shared state after a conflict; retrying an unchanged uncertain acceptance keeps its operation identity.'; }
      finally { state.busy = false; accept.disabled = !state.payload || !review.checked || !!state.plan; }
    });
    state.read = read; state.invalidate = invalidate; state.comparisonText = comparisonText;
    read();
  }
  const onSnapshot = event => { snapshot = event.detail; for (const state of states.values()) { state.invalidate('Holdings generation changed. Accepted plans stay fixed; preview drafts again.'); state.comparisonText(); } };
  const onMarket = event => { const state = states.get(event.detail.coin); if (!state) return; state.market = event.detail; state.invalidate('Market context updated. Accepted plans stay fixed; review draft levels and preview again.'); state.comparisonText(); };
  document.addEventListener('accepted-snapshot', onSnapshot);
  document.addEventListener('crypto-levels-preview', onMarket);
  load.addEventListener('click', () => { for (const state of states.values()) state.read(); });
  for (const result of Object.values(document.querySelector('#crypto-levels')?.suggestedPreviews ?? {})) onMarket({detail:result});
  return () => { document.removeEventListener('accepted-snapshot', onSnapshot); document.removeEventListener('crypto-levels-preview', onMarket); };
}
const root = document.querySelector('#crypto-plan');
if (root) cryptoPlanUI(root);
