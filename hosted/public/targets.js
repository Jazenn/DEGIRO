const node = (tag, value) => { const element = document.createElement(tag); element.textContent = value; return element; };
export async function loadTargets(root, request = fetch) {
  const status = node('p', 'Loading shared Rebalancing Targets...');
  root.replaceChildren(node('h2', 'Rebalancing Targets'), status);
  let settings;
  try {
    const response = await request('/api/targets', { credentials: 'same-origin', cache: 'no-store' });
    if (!response.ok) throw Error();
    settings = await response.json();
  } catch { status.textContent = 'Targets unavailable. Reload this page to retry.'; return; }
  status.textContent = `Rebalancing Targets version ${settings.version}. The Snapshot records its Rebalancing Target version separately. Saving targets does not refresh valuation or change financial settings.`;
  const form = document.createElement('form');
  const rows = node('div', '');
  function addRow(target = { asset_id: '', target_pct: '' }) {
    const row = node('div', '');
    const asset = document.createElement('input'); asset.value = target.asset_id; asset.required = true; asset.maxLength = 100;
    const pct = document.createElement('input'); pct.value = target.target_pct; pct.required = true; pct.type = 'number'; pct.min = '0'; pct.max = '100'; pct.step = '0.01';
    const assetLabel = node('label', 'Asset identifier '); assetLabel.append(asset);
    const pctLabel = node('label', 'Target percentage '); pctLabel.append(pct);
    const remove = node('button', 'Remove'); remove.type = 'button'; remove.onclick = () => { row.remove(); pending = null; };
    row.append(assetLabel, pctLabel, remove); rows.append(row);
  }
  const message = node('p', 'Targets must total 100%. Use the same Asset identifiers as your holdings.'); message.setAttribute('role', 'status');
  let pending = null;
  settings.targets.forEach(addRow);
  const add = node('button', 'Add Asset'); add.type = 'button'; add.onclick = () => addRow();
  const save = node('button', 'Save targets'); save.type = 'submit';
  const reload = node('button', 'Reload shared targets'); reload.type = 'button';
  reload.onclick = () => loadTargets(root, request);
  form.append(rows, add, save, reload, message); root.append(form);
  form.addEventListener('input', () => { pending = null; });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (save.disabled) return;
    const targets = Array.from(rows.children).map(row => {
      const inputs = row.querySelectorAll('input'); return { asset_id: inputs[0].value.trim(), target_pct: inputs[1].value };
    });
    pending ||= { operation_id: crypto.randomUUID(), expected_version: settings.version, targets };
    save.disabled = true; reload.disabled = true; add.disabled = true;
    rows.querySelectorAll('input, button').forEach(control => { control.disabled = true; });
    try {
      const response = await request('/api/targets', { method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pending) });
      if (response.status === 409) {
        message.textContent = 'Another device changed these targets. Your edits remain here. Review them, then Reload shared targets before editing and saving again.';
        save.disabled = true; return;
      }
      if (response.status === 400) { message.textContent = 'Targets are invalid. Use unique Asset identifiers and nonnegative percentages totaling 100% (up to two decimal places).'; pending = null; return; }
      if (!response.ok) throw Error();
      const result = await response.json(); settings = result.current; pending = null;
      status.textContent = `Rebalancing Targets version ${settings.version}. Saved across devices. Valuations keep their recorded Rebalancing Target version until refreshed. Financial settings stay unchanged.`;
      message.textContent = 'Targets saved.';
      document.dispatchEvent(new CustomEvent('targets-saved',{detail:settings}));
    } catch { message.textContent = 'Save could not be confirmed. Retry Save targets unchanged to safely confirm the same change.'; }
    finally { rows.querySelectorAll('input, button').forEach(control => { control.disabled = false; }); if (!message.textContent.startsWith('Another device')) save.disabled = false; reload.disabled = false; add.disabled = false; }
  });
}
const root = document.querySelector('#targets');
if (root) loadTargets(root);


