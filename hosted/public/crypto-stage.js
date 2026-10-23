const text = (tag, value) => { const element = document.createElement(tag); element.textContent = value; return element; };
const reasons = {
  accepted_plan_required: 'Accept a reviewed plan to see its reached unfinished stages.',
  current_reference_quote_unavailable_or_expired: 'A reference quote with a verified observation time within five minutes is required.',
  manual_quantity_change_requires_reconciliation: 'Recorded holdings changed. Reconcile sales and the retained core before acting.',
  holdings_or_plan_reconciliation_required: 'Holdings and the accepted plan need reconciliation.',
  stage_quantity_reconciliation_required: 'Stage quantities need reconciliation before acting.',
  core_protection_or_pending_quantity_limit: 'Pending sales and the retained core leave insufficient available tactical quantity.',
  snapshot_or_plan_changed: 'Holdings or the accepted plan changed. Review the latest shared state.',
  pending_execution_order_requires_canonical_reconciliation: 'A pending sale needs matching to imported executions before FIFO cost can be verified.',
  canonical_cost_projection_unverified: 'Verified FIFO cost is unavailable for these units.',
  reviewed_all_in_sale_fees_required: 'Reviewed all-in sale fees and spread allowance are required.',
};
export function cryptoStageUI(root, request = fetch, clock = () => Date.now()) {
  root.replaceChildren(text('h3', 'Reached unfinished stages'), text('p', 'Review all reached stages together at the current reference price. Reaching a level never records or executes a sale.'));
  const reload = text('button', 'Review reached stages'); reload.type = 'button'; root.append(reload);
  const destination = text('a', 'Review actual net sale proceeds in ETF contribution planning'); destination.href = '#contribution'; root.append(destination);
  const states = new Map(); let disposed = false;
  for (const coin of ['BTC-EUR', 'ETH-EUR']) {
    const section = document.createElement('section'), output = document.createElement('div'), status = text('p', 'Reading current stage review...');
    section.setAttribute('aria-label', `${coin} reached stages`); status.setAttribute('role', 'status');
    section.append(text('h4', coin), output, status); root.append(section);
    states.set(coin, { output, status, epoch: 0, timer: null, controller: null });
  }
  function clear(state, message) {
    state.epoch++; clearTimeout(state.timer); state.controller?.abort(); state.output.replaceChildren(); state.status.textContent = message;
  }
  async function read(coin, state) {
    clear(state, 'Reading current stage review...');
    if (document.hidden) { state.status.textContent = 'Return to this tab and review current quotes before acting.'; return; }
    const epoch = state.epoch, controller = new AbortController(); state.controller = controller;
    const deadline = setTimeout(() => controller.abort(), 10000);
    try {
      const generation = document.querySelector('#snapshot')?.acceptedSnapshot?.generation_id;
      const response = await request('/api/crypto/stages/preview', { method: 'POST', credentials: 'same-origin', cache: 'no-store',
        signal: controller.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ coin, ...(generation ? { generation_id: generation } : {}) }) });
      const value = await response.json();
      if (disposed || epoch !== state.epoch) return;
      if (!response.ok) throw Error('Stage review unavailable.');
      if (value.state !== 'ready') { state.status.textContent = reasons[value.reason] ?? 'Current stage review is unavailable. Accepted plans remain saved.'; return; }
      const until = Date.parse(value.quote_eligible_until), remaining = until - clock();
      if (!Number.isFinite(until) || remaining <= 0 || remaining > 300000 || !Array.isArray(value.stages)) {
        state.status.textContent = 'Reference quote expired. Review again for current reached-stage prompts.'; return;
      }
      state.output.append(text('p', `Reference EUR ${value.quote.price_eur}; observed ${value.quote.observed_at}; source ${value.quote.provider}. Available tactical quantity ${value.available_tactical_quantity}; pending ${value.pending_quantity}.`));
      for (const stage of value.stages) {
        const article = document.createElement('article');
        article.append(text('h5', `Stage ${stage.stage_id}`), text('p', `${stage.quantity} units; accepted level EUR ${stage.level_eur}; estimated gross proceeds at the current reference price EUR ${stage.gross_proceeds_eur}.`));
        if (stage.estimated_gain_eur != null && ['estimated_profit_verified_inputs','estimated_loss'].includes(stage.profit_status)) {
          article.append(text('p', `${stage.profit_status === 'estimated_loss' ? 'Estimated loss' : 'Estimated profit with verified inputs'}: EUR ${stage.estimated_gain_eur}. Gain range EUR ${stage.gain_lower_eur} to ${stage.gain_upper_eur}.`));
        } else {
          article.append(text('p', 'Profit unverified. ' + (reasons[stage.diagnostic] ?? 'The cost and fee bounds do not establish a positive net gain.')));
          if (stage.estimated_gain_eur != null) article.append(text('p', `Center estimate EUR ${stage.estimated_gain_eur}; uncertainty range EUR ${stage.gain_lower_eur} to ${stage.gain_upper_eur}.`));
        }
        if (stage.net_proceeds_lower_eur != null) article.append(text('p', `Estimated net proceeds EUR ${stage.net_proceeds_lower_eur} to ${stage.net_proceeds_upper_eur}; FIFO cost EUR ${stage.canonical_cost_lower_eur} to ${stage.canonical_cost_upper_eur}.`));
        if (stage.fee_evidence) article.append(text('p', `Sale fees ${stage.fee_status}: ${stage.fee_evidence}. Spread allowance: ${stage.spread_evidence}.`));
        state.output.append(article);
      }
      state.status.textContent = value.stages.length ? 'Reference estimates only. Execute manually and report actual sales for reconciliation.' : 'No currently reached unfinished stages.';
      state.timer = setTimeout(() => clear(state, 'Reference quote expired. Review again for current reached-stage prompts.'), remaining);
    } catch {
      if (!disposed && epoch === state.epoch) { state.output.replaceChildren(); state.status.textContent = 'Stage review failed. Accepted plans remain saved. Review again before acting.'; }
    } finally { clearTimeout(deadline); }
  }
  const load = () => { if (!disposed) for (const [coin, state] of states) read(coin, state); };
  const hidden = () => { if (document.hidden) for (const state of states.values()) clear(state, 'Return to this tab and review current quotes before acting.'); };
  reload.addEventListener('click', load); document.addEventListener('accepted-snapshot', load);
  document.addEventListener('crypto-plan-accepted', load); document.addEventListener('visibilitychange', hidden);
  load();
  return () => { disposed = true; for (const state of states.values()) clear(state, ''); reload.removeEventListener('click', load);
    document.removeEventListener('accepted-snapshot', load); document.removeEventListener('crypto-plan-accepted', load); document.removeEventListener('visibilitychange', hidden); };
}
const root = document.querySelector('#crypto-stage');
if (root) cryptoStageUI(root);
