// Display immutable, generation-pinned history. Drawing never feeds accounting.
const element = (tag, content) => {
  const node = document.createElement(tag); node.textContent = content; return node;
};
const money = value => value === null || value === undefined ? 'Unavailable' : `EUR ${value}`;
function assumption(target, timezone) {
  if (timezone?.status === 'owner_assumed') target.append(element('p', `Transaction times assume ${timezone.name} at your request. DEGIRO has not verified this convention. Timing-dependent values use this assumption, including summer and winter clock changes.`));
}
function chart(target, period) {
  const points = period.points, values = points.map(point => Number(point.equity_eur));
  if (points.length < 2 || !values.every(Number.isFinite)) return;
  const low = Math.min(...values), high = Math.max(...values);
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 640 200'); svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', `Observed equity from ${period.start} to ${period.end}`);
  const path = document.createElementNS(svg.namespaceURI, 'polyline');
  path.setAttribute('points', values.map((value, index) => `${20 + index / (values.length - 1) * 600},${180 - (value - low) / (high - low || 1) * 160}`).join(' '));
  path.setAttribute('fill', 'none'); path.setAttribute('stroke', '#304d69'); path.setAttribute('stroke-width', '3');
  svg.append(path); target.append(svg);
}
function auditPage(target, payload) {
  target.replaceChildren(element('p', `Observed days ${Number(payload.offset) + 1}–${Number(payload.offset) + payload.points.length}`));
  for (const day of payload.daily) {
    target.append(element('p', `${day.start} to ${day.cutoff} | gain ${money(day.net_gain_eur)} | signed flows ${money(day.external_flows_eur)} | weighted flows ${money(day.weighted_external_flows_eur)} | denominator ${money(day.denominator_eur)} | daily fraction ${day.fraction}`));
    for (const flow of day.flows ?? []) target.append(element('p', `Flow ${flow.transaction_id} | ${flow.at} | signed ${money(flow.amount_eur)} | remaining interval weight ${flow.remaining_interval_weight}`));
  }
  for (const point of payload.points) {
    target.append(element('p', `${point.cutoff} | equity ${money(point.equity_eur)}`));
    for (const [symbol, quote] of Object.entries(point.observed_prices)) target.append(element('p', `${symbol} | ${quote.provider} | price ${money(quote.price_eur)} | observed ${quote.observed_at} | retrieved ${quote.retrieved_at ?? 'unknown'} | ${quote.currency} | ${quote.adjustment_basis}`));
    if (point.diagnostics?.length) target.append(element('p', point.diagnostics.join('; ')));
  }
}
export function renderPerformance(target, snapshot, request = fetch) {
  target.disposeHistory?.();
  const previous = target.querySelector('[data-history-view]');
  const result = previous ?? document.createElement('div'); result.dataset.historyView = 'true';
  const controls = document.createElement('div'); controls.setAttribute('aria-label', 'Performance period');
  const status = element('p', 'Open Performance or load finalized history. Current values are already available.'); status.setAttribute('role', 'status');
  const loadButton = element('button', 'Load finalized history'); loadButton.type = 'button';
  target.replaceChildren(element('h2', 'What changed over time?'), element('p', 'Finalized daily history is separate from current intraday holdings.'));
  assumption(target, snapshot.read_model.source_timezone);
  target.append(loadButton, controls, status, result);
  const buttons = [], state = { serial: 0, disposed: false, active: new Set(), response: result.historyResponse ?? null, period: result.dataset.period ?? 'ALL' };
  const cancel = () => { for (const controller of state.active) controller.abort(); state.active.clear(); };
  const dispose = () => { state.disposed = true; state.serial++; cancel(); window.removeEventListener('hashchange', onHash); };
  target.disposeHistory = dispose;
  async function read(name, offset, generation = snapshot.generation_id) {
    const controller = new AbortController(); state.active.add(controller);
    const deadline = setTimeout(() => controller.abort(), 10000);
    const params = new URLSearchParams({ generation_id: generation, period: name });
    if (offset !== undefined) params.set('offset', offset);
    try {
      const response = await request('/api/history?' + params, { credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
      if (!response.ok) throw Error('history_read_failed');
      const payload = await response.json();
      if (payload.generation_id !== generation || (payload.state === 'ready' && payload.period_name !== name)) throw Error('history_generation_mismatch');
      return payload;
    } finally { clearTimeout(deadline); state.active.delete(controller); }
  }
  function details(payload, name) {
    const details = document.createElement('details'), body = document.createElement('div'), notice = element('p', ''), navigation = document.createElement('div');
    details.append(element('summary', 'Observed equity, dated price sources and daily flow weights'),
      element('p', `Generation ${payload.generation_id} | history settings ${payload.settings_version} | ledger ${payload.ledger_version}`),
      element('p', 'Daily Modified Dietz: (closing equity - opening equity - signed external flows) / (opening equity + remaining-interval weighted external flows). Daily growth factors are multiplied across every supported day. This is an estimate, without annualization.'), notice, body, navigation);
    let loaded = false, loading = false, page = '0';
    async function loadPage(offset) {
      if (loading || state.disposed || state.response !== payload) return;
      loading = true; notice.textContent = 'Loading observed sources and daily weights...';
      try {
        const audit = await read(name, offset, payload.generation_id);
        if (state.disposed || state.response !== payload) return;
        if (audit.state !== 'ready' || audit.offset !== offset || audit.ledger_version !== payload.ledger_version || audit.settings_version !== payload.settings_version) throw Error('invalid_history_details');
        auditPage(body, audit); page = offset; loaded = true; notice.textContent = '';
        navigation.replaceChildren();
        if (Number(page) > 0) {
          const back = element('button', 'Previous observed days'); back.type = 'button'; back.addEventListener('click', () => loadPage(String(Math.max(0, Number(page) - 7)))); navigation.append(back);
        }
        if (audit.next_offset !== null) {
          const next = element('button', 'Next observed days'); next.type = 'button'; next.addEventListener('click', () => loadPage(audit.next_offset)); navigation.append(next);
        }
      } catch { if (!state.disposed && state.response === payload) notice.textContent = 'Detail read failed. The previous displayed audit page is unchanged; try the page again.'; }
      finally { loading = false; }
    }
    details.addEventListener('toggle', () => { if (details.open && !loaded) loadPage(page); });
    return details;
  }
  function display(payload, name) {
    const next = document.createElement('div');
    assumption(next, payload.source_timezone);
    const period = payload.period;
    next.append(element('h3', `${name === 'ALL' ? 'All time' : name} | ${period?.start ?? 'opening unavailable'} to ${period?.end ?? payload.cutoff ?? 'cutoff unavailable'}`));
    if (payload.state !== 'ready') {
      next.append(element('p', `Observed history unavailable. ${(payload.diagnostics ?? [payload.reason ?? 'Verified history has not been supplied.']).join('; ')}`));
    } else {
      if (period.shorter_coverage) next.append(element('p', `Shorter observed coverage: the requested opening is unavailable. Requested opening: ${period.requested_start ?? 'unavailable'}. Observed opening: ${period.start}. Any available chart and EUR results use the displayed observed interval.`));
      const estimate = period.estimated_return;
      if (estimate?.state === 'ready') {
        next.append(element('p', `Estimated cash-flow-adjusted return: ${estimate.percent}%`));
        if (estimate.opening_coverage === 'first_funded_baseline') next.append(element('p', `Percentage opening: ${estimate.start} | first-funded baseline. Verified zero-capital prefunding intervals are excluded from the percentage; EUR results and chart retain their displayed endpoints.`));
        next.append(element('p', `Finalized percentage cutoff: ${estimate.cutoff}. Geometrically linked daily Modified Dietz estimate, without annualization. Current intraday EUR figures have their own cutoff.`));
      } else next.append(element('p', `Estimated cash-flow-adjusted return unavailable. ${(estimate?.diagnostics ?? ['Verified daily return inputs have not been supplied.']).join('; ')}`));
      if (period.state !== 'ready') next.append(element('p', `Period results unavailable. ${(period.diagnostics ?? ['No observed interval supplied.']).join('; ')}`));
      else {
        next.append(element('p', `Net investment gain ${money(period.attribution.net_gain_eur)}. External flows ${money(period.attribution.net_external_flows_eur)}.`));
        chart(next, period);
        const explanation = document.createElement('dl');
        for (const [label, key] of [['Retained unrealized gain change', 'retained_gain_change_eur'], ['Realized gain change, including sold Assets', 'realized_gain_change_eur'], ['Net income after withholding', 'net_income_eur'], ['Portfolio-only costs deducted', 'portfolio_costs_eur']]) explanation.append(element('dt', label), element('dd', money(period.attribution[key])));
        next.append(explanation, element('p', 'Retained gain change + realized gain change + net income - portfolio-only costs = investment gain. Recorded trade fees are already included; dividends are not added again through adjusted prices.'));
        for (const asset of period.assets) next.append(element('p', `${asset.symbol ?? asset.broker_asset_id} | retained gain change ${money(asset.retained_gain_change_eur)} | realized gain change ${money(asset.realized_gain_change_eur)}`));
      }
      next.append(details(payload, name));
    }
    result.replaceChildren(...next.childNodes); result.dataset.period = name; result.dataset.generation = payload.generation_id;
    result.historyResponse = payload;
    for (const button of buttons) button.setAttribute('aria-pressed', String(button.textContent === name));
  }
  async function select(name) {
    cancel(); const serial = ++state.serial;
    status.textContent = 'Loading finalized history; the previous displayed period is retained until this read completes.';
    try {
      const payload = await read(name);
      if (state.disposed || serial !== state.serial) return;
      if (payload.state !== 'ready' && payload.state !== 'unavailable') throw Error('invalid_history');
      display(payload, name); state.response = payload; state.period = name; status.textContent = '';
    } catch {
      if (!state.disposed && serial === state.serial) status.textContent = 'History read failed. Showing the previous displayed period unchanged; load finalized history to retry.';
    }
  }
  for (const name of ['ALL', 'YTD', '1Y', '3M', '1M', '1W']) {
    const button = element('button', name); button.type = 'button'; button.addEventListener('click', () => select(name)); controls.append(button); buttons.push(button);
  }
  function onHash() {
    if (!target.isConnected) { dispose(); return; }
    if (window.location.hash === '#performance') { if (!state.response || state.response.generation_id !== snapshot.generation_id) select(state.period); }
    else { state.serial++; cancel(); }
  }
  window.addEventListener('hashchange', onHash);
  if (state.response) display(state.response, state.period);
  loadButton.addEventListener('click', () => select(state.period));
  if (window.location.hash === '#performance') return select(state.period);
  return Promise.resolve();
}
