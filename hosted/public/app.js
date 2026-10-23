// This entrypoint consumes persisted JSON only. No ledger, provider or privileged browser storage.
import { renderPerformance } from './performance.js';
const amount = value => value === null || value === undefined ? 'Unavailable' : `EUR ${value}`;
function text(tag, value) {
  const node = document.createElement(tag);
  node.textContent = value;
  return node;
}
export async function loadSnapshot(destination, request = fetch) {
  const target = document.createElement('div');
  const previous = destination.dataset.generation;
  destination.querySelector('[data-read-warning]')?.remove();
  if (!previous) destination.replaceChildren(text('p', 'Loading accepted Snapshot...'));
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await request('/api/snapshot', { credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
    if (response.status === 401) { delete destination.dataset.generation; destination.replaceChildren(text('p', 'Your session has expired. Reload this page to sign in.')); return; }
    if (response.status === 403) { delete destination.dataset.generation; destination.replaceChildren(text('p', 'Access is restricted to the owner.')); return; }
    if (!response.ok) throw Error('read failed');
    const result = await response.json();
    if (result.state === 'empty') { delete destination.dataset.generation; destination.replaceChildren(text('p', 'No accepted Snapshot has been published.')); return; }
    if (result.state !== 'ready' || !result.snapshot?.read_model?.ledger) throw Error('invalid response');
    const snapshot = result.snapshot;
    const model = snapshot.read_model;
    const ledger = model.ledger;
    target.replaceChildren(text('p', snapshot.data_classification === 'synthetic' ? 'Synthetic data · hosting verification only' : 'Private portfolio data'));

    const metrics = document.createElement('section');
    metrics.className = 'shell-summary';
    metrics.setAttribute('aria-label', 'Portfolio summary');
    for (const [label, key] of [['Equity including cash', 'equity_eur'], ['All-time net gain', 'net_gain_eur'], ['Net external contributions', 'net_external_contributions_eur'],
      ['Holdings market value', 'market_value_eur'], ['Available cash', 'cash_balance_eur'], ['Gross income', 'gross_income_eur'], ['Income withholding', 'withholding_eur'], ['Net income', 'net_income_eur'], ['Portfolio-only costs', 'portfolio_costs_eur']]) {
      const card = document.createElement('article');
      card.append(text('span', label), text('strong', amount(ledger[key])));
      metrics.append(card);
    }
    target.append(metrics, text('p', `Current holdings cutoff: ${model.cutoff}. Finalized period results have their own cutoff in Performance.`), text('h3', 'Investment result explanation'));
    target.append(text('p', 'All-time net gain is equity including cash minus net external contributions. Completed-sale results remain included after the Asset is sold. Retained gain uses fee-inclusive FIFO recorded cost; realized gain uses actual completed sales. Net income includes withholding. Trade charges are already included in FIFO costs and sale proceeds; portfolio-only costs are deducted separately. Do not subtract recorded charges again.'));
    target.append(text('p', `Future fee estimates are separate from these recorded charges. ${model.portfolio_history && Object.keys(model.portfolio_history.periods ?? {}).length ? 'Finalized historical coverage is shown separately in Performance.' : 'Finalized historical coverage is unavailable.'} Current holdings are not a historical return series.`));
    for (const [title, closed] of [['Current holdings', false], ['Completed positions', true]]) {
      const section = document.createElement('section');
      section.setAttribute('aria-label', title);
      section.append(text('h3', title));
      const assets = ledger.positions.filter(position => /^-?0(?:\.0+)?$/.test(position.quantity) === closed);
      if (!assets.length) section.append(text('p', closed ? 'No completed positions recorded.' : 'No current holdings recorded.'));
      for (const position of assets) {
        const card = document.createElement('article');
        card.append(text('h4', position.symbol ?? position.broker_asset_id));
        card.append(text('p', `${position.asset_kind} | quantity ${position.quantity} | market value ${amount(position.market_value_eur)}`));
        card.append(text('p', `Retained FIFO cost ${amount(position.retained_cost_eur)} | retained gain ${amount(position.held_gain_eur)} | realized gain ${amount(position.realized_gain_eur)}`));
        card.append(text('p', `Recorded-cost coverage: ${position.cost_coverage}`));
        section.append(card);
      }
      target.append(section);
    }
    const charges = document.createElement('section');
    charges.setAttribute('aria-label', 'Recorded charges');
    charges.id = 'recorded-costs';
    charges.append(text('h3', 'Recorded charges'));
    if (!ledger.charges.length) charges.append(text('p', 'No charges are recorded in this generation. This does not verify complete charge history.'));
    for (const charge of ledger.charges) {
      charges.append(text('p', `${charge.date} | ${charge.category} | ${amount(charge.amount_eur)} | ${charge.allocation === 'portfolio' ? 'Portfolio-only cost' : charge.allocation} | Transaction ${charge.transaction_id}`));
    }
    target.append(charges, text('h3', 'Observed price sources'));
    for (const [symbol, quote] of Object.entries(model.observed_prices ?? {})) {
      target.append(text('p', `${symbol} | ${quote.provider} | ${amount(quote.price_eur)} | observed ${quote.observed_at} | retrieved ${quote.retrieved_at ?? 'time unavailable'} | ${quote.currency} ${quote.adjustment_basis}`));
    }
    if (!Object.keys(model.observed_prices ?? {}).length) target.append(text('p', 'Observed price provenance unavailable.'));
    target.append(text('p', [...new Set([...(model.diagnostics ?? []), ...(ledger.diagnostics ?? [])])].join('; ') || 'No coverage diagnostics reported. This does not independently verify complete source history.'));
    target.append(text('h3', 'Versions and coverage'));
    target.append(text('p', `Ledger ${model.ledger_version} · settings ${model.settings_version} · calculation ${model.calculation_version}`));
    target.append(text('p', model.diagnostics.length ? model.diagnostics.join('; ') : 'No calculation diagnostics reported. Synthetic evidence does not certify private source records.'));
    const details = document.createElement('details');
    details.append(text('summary', 'Read exact values, FIFO lots, charges and observed-price provenance'), text('pre', JSON.stringify(model, null, 2)));
    details.append(text('p', `Generation ${snapshot.generation_id} | published ${snapshot.published_at}`));
    target.append(details);
    destination.replaceChildren(...target.childNodes);
    destination.dataset.generation = snapshot.generation_id;
    const performance = document.querySelector('#performance');
    if (performance) renderPerformance(performance, snapshot);
  } catch {
    if (previous) {
      const warning = text('p', 'Snapshot read failed. Showing the previous accepted generation; values have not been refreshed.');
      warning.setAttribute('role', 'alert');
      warning.dataset.readWarning = 'true';
      destination.prepend(warning);
    } else destination.replaceChildren(text('p', 'Snapshot unavailable. Retry the read. No replacement values have been supplied.'));
  } finally { clearTimeout(deadline); }
}
const target = document.querySelector('#snapshot');
const reload = document.querySelector('#reload');
if (target && reload) {
  reload.addEventListener('click', () => loadSnapshot(target));
  loadSnapshot(target);
}
