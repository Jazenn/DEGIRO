// @vitest-environment jsdom
import { expect, test } from 'vitest';
// @ts-expect-error browser module
import { startRefresh } from './public/refresh.js';

test('open renders last generation first, then refreshes and reloads only after successful publication', async () => {
  document.body.innerHTML = '<button id="reload"></button><p id="refresh-status"></p><section id="snapshot"></section>';
  const events: string[] = [];
  const load = async () => { events.push('read'); return true; };
  const request = async () => { events.push('refresh'); return Response.json({ state: 'refreshed', generation_id: 'next' }); };
  await startRefresh(document.querySelector('#snapshot'), document.querySelector('button'), document.querySelector('p'), load, request);
  expect(events).toEqual(['read', 'refresh', 'read']);
  expect(document.querySelector('p')!.textContent).toContain('refreshed together');
});

test('failed refresh retains last view, and hidden page makes no provider request', async () => {
  document.body.innerHTML = '<button></button><p></p><section>Previous generation</section>';
  const section = document.querySelector('section')!;
  await startRefresh(section, document.querySelector('button'), document.querySelector('p'), async () => {}, async () => Response.json({ state: 'retained', reason: 'refresh_timeout' }));
  expect(section.textContent).toBe('Previous generation');
  expect(document.querySelector('p')!.textContent).toContain('refresh_timeout');
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
  let calls = 0;
  await startRefresh(section, document.querySelector('button'), document.querySelector('p'), async () => {}, async () => { calls++; throw Error(); });
  expect(calls).toBe(0);
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
});

test('successful server refresh followed by failed Snapshot read does not claim visible freshness', async () => {
  document.body.innerHTML = '<button></button><p></p><section>Previous generation</section>';
  await startRefresh(document.querySelector('section'), document.querySelector('button'), document.querySelector('p'), async () => false,
    async () => Response.json({ state: 'refreshed', generation_id: 'next' }));
  expect(document.querySelector('p')!.textContent).toContain('updated on the server');
  expect(document.querySelector('p')!.textContent).not.toContain('refreshed together');
});

