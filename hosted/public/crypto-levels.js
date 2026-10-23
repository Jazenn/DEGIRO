const node = (tag, text) => { const value = document.createElement(tag); value.textContent = text; return value; };
const defaults = { purchase: ['35','20','10'], sale: ['75','90','95'] };
export function cryptoLevelsUI(root, request = fetch, clock = Date.now) {
  root.replaceChildren(node('h3', 'Suggested Crypto Levels'), node('p', 'BTC and ETH EUR market references from the preceding 365 completed UTC days. These are historical distribution positions, not predictions or probabilities of profit. Personal gain, drawdown and allocation stay separate.'),
    node('p', 'Percentile templates are unsaved drafts. They change suggestions only; Accepted Crypto Plans remain fixed. Purchases require an explicitly allocated contribution and all execution/cost checks.'));
  const attribution = node('a', 'Daily EUR market data: CoinGecko'); attribution.href = 'https://www.coingecko.com/en/api'; attribution.rel = 'noreferrer'; root.append(attribution);
  const refreshers = [];
  const disposers = [];
  for (const [coin, label] of [['BTC-EUR', 'Bitcoin'], ['ETH-EUR', 'Ethereum']]) {
    const card = document.createElement('article'); card.className = 'crypto-level-card';
    card.append(node('h4', label));
    const form = document.createElement('form');
    for (const kind of ['purchase','sale']) {
      const fields = document.createElement('fieldset'); fields.append(node('legend', `${label} ${kind} percentiles`));
      defaults[kind].forEach((value, index) => {
        const field = node('label', `Level ${index + 1} percentile (%) `);
        const input = document.createElement('input'); input.type = 'number'; input.min = '0'; input.max = '100'; input.step = '0.0001'; input.required = true;
        input.name = `${kind}-${index}`; input.value = value; field.append(input); fields.append(field);
      });
      form.append(fields);
    }
    const submit = node('button', 'Preview percentile draft'); submit.type = 'submit'; form.append(submit);
    const output = document.createElement('div'); output.setAttribute('role', 'status');
    const contribution = node('a', 'Allocate a contribution'); contribution.href = '#contribution';
    card.append(form, contribution, output); root.append(card);
    let epoch = 0, expiry, marketVersion;
    const clear = message => { clearTimeout(expiry); delete output.dataset.marketVersion; output.replaceChildren(node('p', message));
      root.dispatchEvent(new CustomEvent('crypto-levels-invalidated', { bubbles: true, detail: { coin } })); };
    form.addEventListener('input', () => { epoch++; clear('Draft changed. Preview the edited percentiles before reviewing levels.'); });
    async function preview(latest = false) {
      if (document.hidden) { epoch++; clear('Market preview paused while this tab is hidden. Preview again when visible.'); submit.disabled = false; form.querySelectorAll('fieldset').forEach(fields => { fields.disabled = false; }); return; }
      const operation = ++epoch;
      clear('Checking completed daily market history...');
      const templates = Object.fromEntries(['purchase','sale'].map(kind => [kind, [0,1,2].map(index => form.elements.namedItem(`${kind}-${index}`).value)]));
      const controller = new AbortController(); const deadline = setTimeout(() => controller.abort(), 10000);
      submit.disabled = true;
      form.querySelectorAll('fieldset').forEach(fields => { fields.disabled = true; });
      try {
        const response = await request('/api/crypto/levels', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ coin, templates, ...(!latest && marketVersion !== undefined ? { market_version: marketVersion } : {}) }), signal: controller.signal });
        if (operation !== epoch) return;
        if (response.status === 409) { marketVersion = undefined; clear('Market history changed. Preview again to use the latest series.'); return; }
        if (response.status === 400) { clear('Use three percentiles between 0 and 100 for each purchase/sale template.'); return; }
        if (!response.ok) throw Error('unavailable');
        const result = await response.json(); if (operation !== epoch) return;
        marketVersion = result.market_version;
        clear(`${result.state === 'ready' ? 'Ready for review' : result.state === 'review' ? 'Review required: coincident or unordered levels' : 'Suggestions paused: complete history required'}. ${result.available_days}/365 days available. Window ${result.window_start} through ${result.window_end}.`);
        output.append(node('p', `Market series ${marketVersion || 'unavailable'}; last provider attempt ${result.attempted_at || 'unavailable'}. Observation at the following 00:00 UTC closes the preceding day.`));
        if (result.state !== 'paused') for (const kind of ['purchase','sale']) {
          output.append(node('h5', `${label} suggested ${kind} references`));
          for (const level of result[kind]) output.append(node('p', `${level.percentile}th historical percentile: EUR ${level.price_eur}`));
        }
        if (result.missing_days?.length) output.append(node('p', `Missing completed days: ${result.missing_days.join(', ')}`));
        const diagnostics = [...(result.diagnostics || []), ...(result.provider_diagnostics || [])];
        if (diagnostics.length) output.append(node('p', diagnostics.join('; ')));
        const context = document.createElement('details'); context.append(node('summary', `Latest 90 completed days of context (${result.context.length} observations available)`));
        const table = document.createElement('table');
        const head = document.createElement('tr'); ['UTC day','EUR observation','Source / observation time'].forEach(title => head.append(node('th', title))); table.append(head);
        for (const day of result.context) { const row = document.createElement('tr'); row.append(node('td', day.day), node('td', day.price_eur), node('td', `${day.provider} / ${day.observed_at}`)); table.append(row); }
        context.append(table); output.append(context);
        output.dataset.marketVersion = marketVersion || '';
        const remaining = Date.parse(result.valid_until) - clock();
        if (remaining <= 0) clear('UTC day changed. Preview again; the rolling window must be complete.');
        else expiry = setTimeout(() => { epoch++; clear('UTC day changed. Preview again; the rolling window must be complete.'); }, Math.min(remaining, 2147483647));
        root.suggestedPreviews ??= {}; root.suggestedPreviews[coin] = result;
        root.dispatchEvent(new CustomEvent('crypto-levels-preview', { bubbles: true, detail: result }));
      } catch { if (operation === epoch) clear('Suggested levels unavailable. Existing Accepted Crypto Plans are unchanged. Retry the preview.'); }
      finally { clearTimeout(deadline); if (operation === epoch) { submit.disabled = false; form.querySelectorAll('fieldset').forEach(fields => { fields.disabled = false; }); } }
    }
    form.addEventListener('submit', event => { event.preventDefault(); preview(); });
    refreshers.push(() => preview(true));
    disposers.push(() => { epoch++; clearTimeout(expiry); });
    preview(true);
  }
  const accepted = event => {
    root.dataset.portfolioGeneration = event.detail.generation_id;
    refreshers.forEach(refresh => refresh());
  };
  document.addEventListener('accepted-snapshot', accepted);
  return () => { document.removeEventListener('accepted-snapshot', accepted); disposers.forEach(dispose => dispose()); };
}
const root = document.querySelector('#crypto-levels');
if (root) cryptoLevelsUI(root);
