// Display persisted period attribution only. Pixel coordinates never feed accounting.
const element = (tag, content) => {
  const node = document.createElement(tag);
  node.textContent = content;
  return node;
};
const money = value => value === null || value === undefined ? 'Unavailable' : `EUR ${value}`;
export function renderPerformance(target, snapshot) {
  const history = snapshot.read_model.portfolio_history;
  target.replaceChildren(element('h2', 'What changed over time?'));
  target.append(element('p', 'Finalized daily history is separate from current intraday holdings.'));
  if (!history || !Object.keys(history.periods ?? {}).length) {
    target.append(element('p', `Observed history unavailable. ${(history?.diagnostics ?? ['Verified historical prices and coverage have not been supplied.']).join('; ')}`));
    return;
  }
  const controls = document.createElement('div');
  controls.setAttribute('aria-label', 'Performance period');
  const result = document.createElement('div');
  const buttons = [];
  const select = name => {
    for (const button of buttons) button.setAttribute('aria-pressed', String(button.textContent === name));
    const period = history.periods[name];
    result.replaceChildren(element('h3', `${name === 'ALL' ? 'All time' : name} | ${period?.start ?? 'opening unavailable'} to ${period?.end ?? history.cutoff}`));
    if (period?.shorter_coverage) result.append(element('p', 'Shorter observed coverage: the requested opening is unavailable. Results use the displayed observed start.'));
    const estimate = period?.estimated_return;
    if (estimate?.state === 'ready') {
      result.append(element('p', `Estimated cash-flow-adjusted return: ${estimate.percent}%`));
      if (estimate.opening_coverage === 'first_funded_baseline') {
        result.append(element('p', `Percentage opening: ${estimate.start} | first-funded baseline. Verified zero-capital prefunding intervals are excluded from the percentage; EUR results and chart retain their displayed endpoints.`));
      }
      result.append(element('p', `Finalized percentage cutoff: ${estimate.cutoff}. Geometrically linked daily Modified Dietz estimate, without annualization. Current intraday EUR figures have their own cutoff.`));
    } else {
      result.append(element('p', `Estimated cash-flow-adjusted return unavailable. ${(estimate?.diagnostics ?? ['Verified daily return inputs have not been supplied.']).join('; ')}`));
    }
    if (!period || period.state !== 'ready') {
      result.append(element('p', `Period results unavailable. ${(period?.diagnostics ?? ['No observed interval supplied.']).join('; ')}`));
      return;
    }
    result.append(element('p', `Net investment gain ${money(period.attribution.net_gain_eur)}. External flows ${money(period.attribution.net_external_flows_eur)}.`));
    const points = period.points;
    const values = points.map(point => Number(point.equity_eur));
    // Accounting is exact persisted decimal text; Number is used for drawing only.
    if (points.length >= 2 && values.every(Number.isFinite)) {
      const low = Math.min(...values), high = Math.max(...values);
      const chart = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      chart.setAttribute('viewBox', '0 0 640 200');
      chart.setAttribute('role', 'img');
      chart.setAttribute('aria-label', `Observed equity from ${period.start} to ${period.end}`);
      const path = document.createElementNS(chart.namespaceURI, 'polyline');
      path.setAttribute('points', values.map((value, index) => `${20 + index / (values.length - 1) * 600},${180 - (value - low) / (high - low || 1) * 160}`).join(' '));
      path.setAttribute('fill', 'none'); path.setAttribute('stroke', '#304d69'); path.setAttribute('stroke-width', '3');
      chart.append(path); result.append(chart);
    }
    const explanation = document.createElement('dl');
    for (const [label, key] of [['Retained unrealized gain change', 'retained_gain_change_eur'], ['Realized gain change, including sold Assets', 'realized_gain_change_eur'], ['Net income after withholding', 'net_income_eur'], ['Portfolio-only costs deducted', 'portfolio_costs_eur']]) {
      explanation.append(element('dt', label), element('dd', money(period.attribution[key])));
    }
    result.append(explanation, element('p', 'Retained gain change + realized gain change + net income - portfolio-only costs = investment gain. Recorded trade fees are already included; dividends are not added again through adjusted prices.'));
    for (const asset of period.assets) result.append(element('p', `${asset.symbol ?? asset.broker_asset_id} | retained gain change ${money(asset.retained_gain_change_eur)} | realized gain change ${money(asset.realized_gain_change_eur)}`));
    const details = document.createElement('details');
    details.append(element('summary', 'Observed equity and dated price sources'));
    details.append(element('p', `Generation ${snapshot.generation_id} | history settings ${history.settings_version} | ledger ${history.ledger_version}`));
    if (estimate?.state === 'ready') {
      details.append(element('p', 'Daily Modified Dietz: (closing equity - opening equity - signed external flows) / (opening equity + remaining-interval weighted external flows). Daily growth factors are multiplied across every observed day. This approximates flow timing rather than exact intraday time-weighted performance.'));
      for (const day of estimate.daily) {
        details.append(element('p', `${day.start} to ${day.cutoff} | gain ${money(day.net_gain_eur)} | signed flows ${money(day.external_flows_eur)} | weighted flows ${money(day.weighted_external_flows_eur)} | denominator ${money(day.denominator_eur)} | daily fraction ${day.fraction}`));
      }
    }
    for (const point of points) {
      details.append(element('p', `${point.cutoff} | equity ${money(point.equity_eur)}`));
      for (const [symbol, quote] of Object.entries(point.observed_prices)) details.append(element('p', `${symbol} | ${quote.provider} | observed ${quote.observed_at} | retrieved ${quote.retrieved_at ?? 'unknown'} | ${quote.currency} | ${quote.adjustment_basis}`));
    }
    result.append(details);
  };
  for (const name of ['ALL', 'YTD', '1Y', '3M', '1M', '1W']) {
    const button = element('button', name); button.type = 'button';
    button.addEventListener('click', () => select(name)); controls.append(button); buttons.push(button);
  }
  target.append(controls, result); select('ALL');
}
