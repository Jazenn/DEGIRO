// This entrypoint consumes persisted JSON only. No ledger, provider or privileged browser storage.
const amount = value => value === null || value === undefined ? 'Unavailable' : `EUR ${value}`;
function text(tag, value) {
  const node = document.createElement(tag);
  node.textContent = value;
  return node;
}
export async function loadSnapshot(target, request = fetch) {
  target.replaceChildren(text('p', 'Loading accepted Snapshot…'));
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await request('/api/snapshot', { credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
    if (response.status === 401) { target.replaceChildren(text('p', 'Your session has expired. Reload this page to sign in.')); return; }
    if (response.status === 403) { target.replaceChildren(text('p', 'Access is restricted to the owner.')); return; }
    if (!response.ok) throw Error('read failed');
    const result = await response.json();
    if (result.state === 'empty') { target.replaceChildren(text('p', 'No accepted Snapshot has been published.')); return; }
    if (result.state !== 'ready' || !result.snapshot?.read_model?.ledger) throw Error('invalid response');
    const snapshot = result.snapshot;
    const model = snapshot.read_model;
    const ledger = model.ledger;
    target.replaceChildren(text('h2', snapshot.data_classification === 'synthetic' ? 'Synthetic data · hosting verification only' : 'Private portfolio data'));
    target.append(text('p', `Generation ${snapshot.generation_id} · published ${snapshot.published_at}`));
    target.append(text('p', `Current holdings cutoff: ${model.cutoff}. No finalized percentage history is supplied by this view.`));
    const metrics = document.createElement('dl');
    for (const [label, key] of [['Holdings market value', 'market_value_eur'], ['Available cash', 'cash_balance_eur'],
      ['Equity including cash', 'equity_eur'], ['Net external contributions', 'net_external_contributions_eur'],
      ['All-time net gain', 'net_gain_eur'], ['Net income', 'net_income_eur'], ['Portfolio costs', 'portfolio_costs_eur']]) {
      metrics.append(text('dt', label), text('dd', amount(ledger[key])));
    }
    target.append(metrics, text('h3', 'Assets, including completed positions'));
    const list = document.createElement('ul');
    for (const position of ledger.positions) {
      list.append(text('li', `${position.symbol ?? position.broker_asset_id} · quantity ${position.quantity} · market value ${amount(position.market_value_eur)} · held gain ${amount(position.held_gain_eur)} · realized gain ${amount(position.realized_gain_eur)} · cost coverage ${position.cost_coverage}`));
    }
    target.append(list, text('h3', 'Versions and coverage'));
    target.append(text('p', `Ledger ${model.ledger_version} · settings ${model.settings_version} · calculation ${model.calculation_version}`));
    target.append(text('p', model.diagnostics.length ? model.diagnostics.join('; ') : 'No calculation diagnostics reported. Synthetic evidence does not certify private source records.'));
    const details = document.createElement('details');
    details.append(text('summary', 'Read exact values, FIFO lots, charges and observed-price provenance'), text('pre', JSON.stringify(model, null, 2)));
    target.append(details);
  } catch {
    target.replaceChildren(text('p', 'Snapshot unavailable. Retry the read. No replacement values have been supplied.'));
  } finally { clearTimeout(deadline); }
}
const target = document.querySelector('#snapshot');
const reload = document.querySelector('#reload');
if (target && reload) {
  reload.addEventListener('click', () => loadSnapshot(target));
  loadSnapshot(target);
}
