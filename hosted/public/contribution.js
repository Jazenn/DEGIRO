const node = (tag, value) => { const element = document.createElement(tag); element.textContent = value; return element; };
function table(headers, rows) {
  const wrapper = node('div',''); wrapper.style.overflowX = 'auto';
  const result = document.createElement('table'); const header = document.createElement('tr');
  headers.forEach(value => header.append(node('th',value))); const head = document.createElement('thead'); head.append(header); result.append(head);
  const body = document.createElement('tbody');
  rows.forEach(values => { const row = document.createElement('tr'); values.forEach(value => row.append(node('td',value ?? 'Unavailable'))); body.append(row); });
  result.append(body); wrapper.append(result); return wrapper;
}
export function contributionUI(root, snapshotNode, request = fetch) {
  let snapshot = snapshotNode?.acceptedSnapshot ?? null, epoch = 0, busy = false, requiresRefresh = false;
  root.replaceChildren(node('h2','Plan an ETF contribution'), node('p','Manual buy-only estimates. The chosen contribution covers purchases and fees; other available cash is excluded.'));
  const form = document.createElement('form'), label = node('label','Contribution budget in EUR '), budget = document.createElement('input');
  budget.type = 'text'; budget.inputMode = 'decimal'; budget.value = '0'; budget.required = true; budget.pattern = '\\d{1,12}(\\.\\d{1,2})?'; label.append(budget);
  const submit = node('button','Preview ETF purchases'); submit.type = 'submit'; submit.disabled = !snapshot;
  const status = node('p', snapshot ? 'Enter a contribution to preview.' : 'Load an accepted Snapshot before planning.'); status.setAttribute('role','status');
  const output = node('div',''); form.append(label, submit); root.append(form,status,output);
  const invalidate = message => { epoch++; output.replaceChildren(); status.textContent = message; };
  budget.addEventListener('input', () => invalidate('Budget changed. Preview again.'));
  document.addEventListener('accepted-snapshot', event => {
    snapshot = event.detail; requiresRefresh = false; submit.disabled = busy; invalidate('Valuation changed. Preview again against the displayed generation.');
  });
  document.addEventListener('targets-saved', () => { requiresRefresh = true; submit.disabled = true; invalidate('Targets changed. Refresh current prices before previewing again.'); });
  document.addEventListener('valuation-refresh-started', () => invalidate('Refreshing valuation. Existing preview cleared.'));
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (!snapshot || submit.disabled || busy) return;
    const operation = ++epoch; busy = true; submit.disabled = true; output.replaceChildren(); status.textContent = 'Preparing a coherent contribution preview...';
    const source = snapshot;
    const controller = new AbortController(), deadline = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await request('/api/contribution',{ method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},signal:controller.signal,
        body:JSON.stringify({ budget_eur:budget.value, generation_id:source.generation_id, settings_version:source.read_model.settings_version }) });
      if (operation !== epoch) return;
      if (response.status === 409) { status.textContent = 'Valuation or targets changed on another device. Refresh current prices before previewing again.'; return; }
      if (response.status === 400) { status.textContent = 'Enter a nonnegative EUR budget with up to two decimal places.'; return; }
      if (!response.ok) throw Error();
      const plan = await response.json();
      if (operation !== epoch) return;
      if (plan.generation_id !== snapshot.generation_id || plan.settings_version !== snapshot.read_model.settings_version) throw Error();
      if (plan.state !== 'complete') {
        status.textContent = 'Estimate incomplete. No purchases proposed; missing inputs are not treated as free.';
        output.append(node('p', (plan.diagnostics ?? []).join('; ')),node('p',`Unallocated contribution EUR ${plan.remaining_cash_eur}. Fees unknown.`)); return;
      }
      status.textContent = `Manual estimate from generation ${plan.generation_id}, settings ${plan.settings_version}. Verify current broker prices and charges before acting.`;
      output.append(node('p',`Purchases EUR ${plan.invested_eur} · Estimated fees EUR ${plan.fees_eur} · Remaining cash EUR ${plan.remaining_cash_eur}`));
      output.append(node('p',plan.policy));
      if (!plan.purchases.length) output.append(node('p','This budget and the verified minimums produce no purchases. All unspent cash is retained.'));
      else output.append(table(['Asset','Buy quantity','Reference price EUR','Purchase fee EUR','Fee coverage','All-in EUR'],plan.purchases.map(row => [row.symbol ?? row.asset_id,row.quantity,row.price_eur,row.fee_eur,row.fee_status,row.total_cost_eur])));
      output.append(node('h3','Allocation across all holdings (cash shown separately)'),table(['Asset','Before %','After %','Target %'],plan.allocation.map(row => [row.symbol ?? row.asset_id,row.before_pct,row.after_pct,row.target_pct])));
      const sources = document.createElement('details'); sources.append(node('summary','Quote times and reviewed execution terms'));
      plan.purchases.forEach(row => sources.append(node('p',`${row.asset_id}: source observation ${row.quote_observed_at}; execution terms ${row.terms_revision}; ${row.terms_evidence}; valid until ${row.terms_valid_until ?? 'unavailable'}.`))); output.append(sources);
    } catch { if (operation === epoch) status.textContent = 'Contribution preview unavailable. Previous suggestions cleared. Retry the preview.'; }
    finally { clearTimeout(deadline); busy = false; submit.disabled = requiresRefresh || !snapshot; }
  });
}
const root = document.querySelector('#contribution');
if (root) contributionUI(root,document.querySelector('#snapshot'));

