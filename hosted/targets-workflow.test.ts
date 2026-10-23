// @vitest-environment jsdom
import { expect, test } from 'vitest';
// @ts-expect-error browser module
import { loadTargets } from './public/targets.js';

test('a stale phone edit remains visible until owner explicitly reloads shared targets', async () => {
  document.body.innerHTML = '<section></section>';
  const root = document.querySelector('section')!;
  let writes = 0;
  await loadTargets(root, async (_url: string, options: RequestInit = {}) => {
    if (options.method === 'PUT') { writes++; return Response.json({ state: 'conflict', current: { version: '2', targets: [{ asset_id: 'ETF', target_pct: '100' }] } }, { status: 409 }); }
    return Response.json({ version: writes ? '2' : '1', targets: [{ asset_id: 'ETF', target_pct: '100' }] });
  });
  const input = root.querySelector('input')!;
  input.value = 'BTC';
  root.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(root.textContent).toContain('Another device changed');
  expect(input.value).toContain('BTC');
  (Array.from(root.querySelectorAll('button')).find(button => button.textContent === 'Reload shared targets')!).click();
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(root.querySelector('input')!.value).toContain('ETF');
  expect(root.textContent).toContain('Rebalancing Targets version 2');
});


test('uncertain save retries preserve operation identity and visible edits', async () => {
  document.body.innerHTML = '<section></section>';
  const root = document.querySelector('section')!;
  const bodies: string[] = [];
  await loadTargets(root, async (_url: string, options: RequestInit = {}) => {
    if (options.method === 'PUT') {
      bodies.push(String(options.body));
      if (bodies.length === 1) throw Error('connection lost after commit');
      return Response.json({ state: 'saved', current: { version: '2', targets: [{ asset_id: 'ETF', target_pct: '100' }] } });
    }
    return Response.json({ version: '1', targets: [{ asset_id: 'ETF', target_pct: '100' }] });
  });
  const submit = async () => { root.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true })); await new Promise(resolve => setTimeout(resolve, 0)); };
  await submit();
  expect(root.textContent).toContain('Save could not be confirmed');
  await submit();
  expect(bodies[1]).toBe(bodies[0]);
  expect(root.textContent).toContain('Rebalancing Targets version 2');
});
