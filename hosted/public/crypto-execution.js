const node = (tag, value) => { const element = document.createElement(tag); element.textContent = value; return element; };
const reasons = {
  snapshot_or_plan_changed: 'Holdings or the accepted plan changed.',
  operation_id_reused: 'This operation identity was already used for different inputs.',
  stage_quantity_exceeded: 'This quantity exceeds the stage remainder.',
  pending_quantity_exceeds_available_core: 'Existing pending sales and the retained core leave insufficient available quantity.',
  report_not_found: 'The selected report is no longer available.',
  execution_not_found: 'The selected execution is unavailable in the accepted ledger.',
  execution_before_plan: 'This execution predates the accepted plan and cannot consume its stages.',
  execution_capacity_exhausted: 'The execution quantity has already been allocated.',
  execution_facts_changed_review: 'The imported execution changed and requires reconciliation.',
  report_quantity_exceeded: 'This match exceeds the pending report quantity.',
  plan_reconciliation_required: 'The accepted plan needs reconciliation before this operation.',
};
export function cryptoExecutionUI(root, request = fetch) {
  root.replaceChildren(node('h3', 'Report and match actual crypto sales'), node('p', 'A report stays pending until you explicitly match an imported execution. Quotes and daily market history are not required to record past sales. Matching never places a broker order.'));
  const reload = node('button', 'Reload sales and executions'); reload.type = 'button'; root.append(reload);
  const states = new Map(); let disposed = false;
  for (const coin of ['BTC-EUR', 'ETH-EUR']) {
    const section = document.createElement('section'), records = document.createElement('div'), form = document.createElement('form'), status = node('p', 'Reading shared execution history...');
    section.setAttribute('aria-label', `${coin} actual sales`); form.setAttribute('aria-label', `${coin} report and match`); status.setAttribute('role', 'status');
    section.append(node('h4', coin), records, form, status); root.append(section);
    const state = { coin, context: null, pending: null, busy: false, epoch: 0, controller: null, records, status, form };
    states.set(coin, state);
    function field(label, name, tag = 'input') {
      const wrapper = document.createElement('label'), input = document.createElement(tag); input.name = name;
      wrapper.append(node('span', label), input); form.append(wrapper); return input;
    }
    const stage = field('Accepted stage', 'stage', 'select'); stage.required = true;
    const quantity = field('Actual quantity to report or match (units)', 'quantity'); quantity.type = 'text'; quantity.inputMode = 'decimal'; quantity.required = true;
    const report = field('Pending report to match (optional)', 'report', 'select');
    const execution = field('Actual imported execution to match', 'execution', 'select');
    const note = field('Private note (optional)', 'note'); note.type = 'text'; note.maxLength = 1000;
    const reportButton = node('button', 'Report sale as pending'); reportButton.type = 'submit';
    const matchButton = node('button', 'Match selected execution'); matchButton.type = 'button'; form.append(reportButton, matchButton);
    const cancelButton=node('button','Cancel pending remainder');cancelButton.type='button';form.append(cancelButton);
    const controls = () => form.querySelectorAll('input,select,button').forEach(input => { input.disabled = state.busy || !state.context; });
    function options(select, label, rows) {
      const previous = select.value; select.replaceChildren(); const empty = node('option', label); empty.value = ''; select.append(empty);
      for (const [value, label] of rows) { const option = node('option', label); option.value = value; select.append(option); }
      select.value = Array.from(select.options).some(option => option.value === previous) ? previous : '';
    }
    function display(value) {
      records.replaceChildren();
      const progress = value.progress ?? {};
      if (progress.reconciliation_required) records.append(node('p', 'An imported execution changed or disappeared. Recorded matches remain in history; reconcile the correction and review a replacement before acting on this plan.'));
      records.append(node('p', `Shared sales version ${value.version}. Pending ${progress.pending_quantity ?? 'unavailable'} units; matched ${progress.matched_quantity ?? 'unavailable'} units.`));
      for (const row of value.reports ?? []) records.append(node('p', `Report ${row.report_id}; stage ${row.stage_id}; ${row.quantity} units. Pending ${row.pending_quantity}; matched ${row.matched_quantity}; ${row.status}.`));
      for(const event of value.report_events??[])records.append(node('p',`Report ${event.report_id}: ${event.event_type} at ${event.created_at}. Reason: ${event.reason}. Original report and matched executions retained.`));
      const executions = value.executions ?? [];
      records.append(node('h5', 'Imported executions'));
      for (const row of executions) {
        records.append(node('p', `Execution ${row.execution_id}; ${row.executed_at ?? 'observation time unverified'}; ${row.quantity} units; unallocated ${row.available_quantity}.`));
        if (row.coverage === 'verified_complete') records.append(node('p', `Actual gross EUR ${row.gross_proceeds_eur}; actual fees EUR ${row.fees_eur}; disposed FIFO cost EUR ${row.disposed_cost_eur}; actual realized gain EUR ${row.realized_gain_eur}.`));
        else records.append(node('p', 'Actual cost or fee coverage is unverified. Do not infer a gain.'));
      }
      if (!executions.length) records.append(node('p', 'No imported executions available. Reports remain pending until actual records are imported and matched.'));
      for (const allocation of value.allocations ?? []) {
        const receipt = allocation.receipt ?? allocation;
        records.append(node('p', `Matched execution ${allocation.execution_id ?? receipt.execution_id}; ${allocation.quantity ?? receipt.quantity} units.`));
        if (receipt.state === 'verified' && receipt.display) {
          const amount = receipt.display;
          records.append(node('p', `Allocated actual gross EUR ${amount.gross_proceeds_eur}; fees EUR ${amount.fees_eur}; disposed FIFO cost EUR ${amount.disposed_cost_eur}; realized gain EUR ${amount.realized_gain_eur}.`));
          records.append(node('p', receipt.rounding_note ?? 'Displayed amounts are rounded; exact allocation receipts are retained.'));
        } else records.append(node('p', 'Allocation recorded; actual gain remains unverified.'));
      }
      options(stage, 'Choose an accepted stage', (value.plan?.stages ?? []).map(row => [row.stage_id, `${row.stage_id} (${row.quantity} original units)`]));
      options(report, 'Create and match a report together', (value.reports ?? []).filter(row => (!row.plan_id || row.plan_id===value.plan?.plan_id) && ['open','pending'].includes(row.status) && Number(row.pending_quantity)>0).map(row => [row.report_id, `${row.report_id}: pending ${row.pending_quantity}`]));
      options(execution, 'Choose an actual imported execution', executions.filter(row => row.eligible === true).map(row => [row.execution_id, `${row.execution_id}: ${row.available_quantity} available units` ]));
    }
    async function read() {
      const epoch = ++state.epoch; state.controller?.abort(); const controller = new AbortController(); state.controller = controller; state.context = null; controls();
      const deadline = setTimeout(() => controller.abort(), 10000);
      try {
        const response = await request('/api/crypto/executions?coin=' + encodeURIComponent(coin), { method: 'GET', credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
        const value = await response.json(); if (disposed || epoch !== state.epoch) return;
        if (!response.ok || value.state !== 'ready') throw Error('Read failed');
        display(value);
        const generation = document.querySelector('#snapshot')?.acceptedSnapshot?.generation_id;
        if (!generation || generation !== value.generation_id) status.textContent = 'Execution history loaded. Refresh the displayed Snapshot before reporting or matching against these holdings.';
        else if (!value.plan) status.textContent = 'Execution history loaded. Accept a reviewed plan before reporting or matching its stages.';
        else { state.context = value; status.textContent = 'Choose the stage and exact quantity. Match only the execution you reviewed; ambiguous candidates require your explicit choice.'; }
      } catch { if (!disposed && epoch === state.epoch) status.textContent = 'Execution-history read failed. Previously displayed records and your draft remain. Reload shared state before submitting.'; }
      finally { clearTimeout(deadline); if (!disposed && epoch === state.epoch) controls(); }
    }
    async function submit(action) {
      if (state.busy || !state.context || (action!=='cancel'&&!form.reportValidity())) return;
      if(action==='cancel'&&(!report.value||note.value.trim().length<10)){status.textContent='Explain the cancellation in at least ten characters and select the pending report. Matched executions will remain recorded.';return;}
      if (action === 'match' && !execution.value) { status.textContent = 'Choose an actual imported execution before matching. No sale was matched.'; return; }
      const intent = { action, coin, plan_id: state.context.plan?.plan_id, stage_id: stage.value, quantity: quantity.value.trim(),
        ...(note.value.trim() ? { note: note.value.trim() } : {}), ...(action === 'match' ? { execution_id: execution.value, ...(report.value ? { report_id: report.value } : {}) } : {}),
        ...(action==='cancel'?{report_id:report.value}:{}) };
      const fingerprint = JSON.stringify(intent);
      if (state.pending?.fingerprint !== fingerprint) state.pending = { fingerprint, body: { ...intent, operation_id: crypto.randomUUID(), expected_version: state.context.version, generation_id: state.context.generation_id } };
      state.busy = true; controls(); const controller = new AbortController(), deadline = setTimeout(() => controller.abort(), 10000);
      try {
        const response = await request('/api/crypto/executions', { method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: { 'Content-Type': 'application/json' }, signal: controller.signal, body: JSON.stringify(state.pending.body) });
        const result = await response.json(); if (disposed) return;
        if (response.status === 409) { state.pending = null; state.context = null; status.textContent = (reasons[result.reason ?? result.error] ?? 'Shared sales or holdings changed.') + ' Your draft remains. Reload sales and executions before reviewing again.'; return; }
        if (response.status === 400) { state.pending = null; status.textContent = 'The sale request was rejected. Review the selected stage, positive exact quantity and execution. Your draft remains.'; return; }
        if (!response.ok || !['reported', 'matched','cancelled'].includes(result.state)) throw Error('Operation failed');
        state.pending = null; quantity.value = ''; note.value = ''; await read();
        document.dispatchEvent(new CustomEvent('crypto-execution-updated', { detail: { coin } }));
      } catch { if (!disposed) status.textContent = 'Sale operation was not confirmed. Your draft remains; retrying unchanged keeps its operation identity. Reload shared history to check the recorded outcome.'; }
      finally { clearTimeout(deadline); state.busy = false; if (!disposed) controls(); }
    }
    form.addEventListener('submit', event => { event.preventDefault(); submit('report'); }); matchButton.addEventListener('click', () => submit('match'));
    cancelButton.addEventListener('click',()=>submit('cancel'));
    state.read = read; read();
  }
  const load = () => { if (!disposed) for (const state of states.values()) state.read(); };
  reload.addEventListener('click', load); document.addEventListener('accepted-snapshot', load); document.addEventListener('crypto-plan-accepted', load);
  return () => { disposed = true; for (const state of states.values()) { state.epoch++; state.controller?.abort(); }
    reload.removeEventListener('click', load); document.removeEventListener('accepted-snapshot', load); document.removeEventListener('crypto-plan-accepted', load); };
}
const root = document.querySelector('#crypto-execution');
if (root) cryptoExecutionUI(root);

