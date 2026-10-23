const text = (tag, content) => { const node = document.createElement(tag); node.textContent = content; return node; };
const percent = value => value === null || value === undefined ? 'unknown' : `${Number(value).toLocaleString('en', { maximumFractionDigits: 4 })}%`;
const fraction = value => value === null || value === undefined ? 'unknown' : percent(Number(value) * 100);
function breakdown(title, values) {
  const block = document.createElement('div'); block.append(text('h4', title));
  const list = document.createElement('ul');
  for (const [name, weight] of Object.entries(values || {})) list.append(text('li', `${name}: ${percent(weight)}`));
  block.append(list.children.length ? list : text('p', 'Unavailable for unreported holdings.'));
  return block;
}
export function renderExposure(destination, snapshot) {
  if (!destination) return;
  const content = document.createDocumentFragment();
  content.append(text('h2', 'ETF exposure'));
  const exposure = snapshot.read_model.etf_exposure;
  if (!exposure || exposure.schema_version !== 'etf-exposure-v1') {
    content.append(text('p', 'No dated ETF holdings have been published. Country/region, sector, concentration and overlap remain unavailable.'));
  } else {
    content.append(text('p', exposure.covered_portfolio_fraction === null
      ? 'Portfolio coverage unknown without complete invested-asset market values.'
      : `${fraction(exposure.covered_portfolio_fraction)} of invested asset value has verified fund net-asset look-through coverage. Cash is excluded. Uncovered exposure remains unknown.`));
    for (const limitation of exposure.limitations || []) content.append(text('p', limitation));
    content.append(breakdown('Observed country/region (% of all invested assets)', exposure.countries),
      breakdown('Observed sectors (% of all invested assets)', exposure.sectors));
    for (const fund of exposure.funds) {
      const card = document.createElement('article'); card.className = 'exposure-fund';
      card.append(text('h3', `${fund.fund_id} · ${fund.state}`));
      if (fund.state !== 'unavailable') {
        card.append(text('p', `${fund.provider} · holdings as of ${fund.as_of} · retrieved ${fund.retrieved_at}`));
        const source = document.createElement('a');
        try { const url = new URL(fund.source_url); if (url.protocol === 'https:' && !url.username && !url.password) source.href = url.href; } catch { /* No unsafe source link. */ }
        source.textContent = 'Official source / reviewed provenance'; source.rel = 'noreferrer'; card.append(source);
        card.append(text('p', fund.covered_fund_fraction !== null && fund.covered_fund_fraction !== undefined
          ? `${fraction(fund.covered_fund_fraction)} of fund net assets covered.`
          : `${fraction(fund.covered_reported_fraction)} of provider-reported market-value scope covered; fraction of fund net assets is unknown.`));
        card.append(text('p', `Weight basis: ${fund.weight_basis}. Top ten observed holdings: ${percent(fund.top_ten_weight_pct)} (${fund.concentration_basis === 'exact' ? 'complete dataset' : 'observed lower bound'}).`));
        card.append(text('p', `Country/region classification: ${fund.country_basis || 'unverified provider classification'}. Sector taxonomy: ${fund.sector_taxonomy || 'unverified provider classification'}.`));
        card.append(breakdown('Country/region within reported fund scope', fund.countries), breakdown('Sectors within reported fund scope', fund.sectors));
        const details = document.createElement('details'); details.append(text('summary', 'Reported underlying holdings'));
        const list = document.createElement('ul');
        for (const row of fund.holdings || []) list.append(text('li', `${row.name} · ${percent(row.weight_pct)} · ${row.country || 'country unknown'} · ${row.sector || 'sector unknown'} · ${row.security_id || 'stable identifier unavailable'}`));
        details.append(list); card.append(details);
      }
      for (const limitation of fund.limitations || []) card.append(text('p', limitation));
      content.append(card);
    }
    content.append(text('h3', 'Compatible fund overlap'));
    for (const overlap of exposure.overlap) content.append(text('p', `${overlap.fund_a} / ${overlap.fund_b}: ${overlap.observed_overlap_pct === null
      ? 'Overlap unavailable' : `${percent(overlap.observed_overlap_pct)} ${overlap.state === 'complete' ? 'overlap of fund weights' : 'observed lower bound'}`} · ${overlap.reason}`));
    if (!exposure.overlap.length) content.append(text('p', 'At least two dated compatible holdings datasets are needed to compare overlap.'));
    content.append(text('p', 'These dated disclosures describe holdings, not a forecast or an exact diversification score.'));
  }
  destination.replaceChildren(content);
  destination.dataset.generation = snapshot.generation_id;
}
