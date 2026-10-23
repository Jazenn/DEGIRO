// @vitest-environment jsdom
import { expect, test, vi } from 'vitest';
// @ts-expect-error plain browser JS
import { cryptoLevelsUI } from './public/crypto-levels.js';

function preview(coin: string, templates: { purchase: string[]; sale: string[] }, missing = false) {
  return { coin, state: missing ? 'paused' : 'ready', templates, market_version: coin + '-v1',
    attempted_at: '2026-10-23T00:23:00Z', valid_until: '2026-10-24T00:00:00Z',
    available_days: missing ? '364' : '365', window_start: '2025-10-23', window_end: '2026-10-22',
    purchase: missing ? [] : templates.purchase.map(p => ({ percentile: p, price_eur: '100' })),
    sale: missing ? [] : templates.sale.map(p => ({ percentile: p, price_eur: '200' })),
    context: [{ day: '2026-10-22', price_eur: '150', provider: 'Synthetic daily', observed_at: '2026-10-23T00:00:00Z' }],
    missing_days: missing ? ['2026-10-22'] : [], diagnostics: [], provider_diagnostics: [] };
}

test('independent coin drafts edit suggestions and missing history preserves accepted plan content', async () => {
  document.body.innerHTML = '<section id="crypto-scale"><div id="crypto-levels"></div><div id="accepted-plan">Previously accepted fixed quantities</div></section>';
  let missing = false;
  const transport = async (_url: string, options: RequestInit) => {
    const input = JSON.parse(String(options.body));
    return Response.json(preview(input.coin, input.templates, missing && input.coin === 'BTC-EUR'));
  };
  const dispose = cryptoLevelsUI(document.querySelector('#crypto-levels'), transport, () => Date.parse('2026-10-23T12:00:00Z'));
  await vi.waitFor(() => expect(document.querySelectorAll('[data-market-version]')).toHaveLength(2));
  const cards = document.querySelectorAll('.crypto-level-card');
  const input = cards[0].querySelector('input')!;
  input.value = '30'; input.dispatchEvent(new Event('input', { bubbles: true }));
  cards[0].querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
  await vi.waitFor(() => expect(cards[0].textContent).toContain('30th historical percentile'));
  expect(cards[1].textContent).toContain('35th historical percentile');
  missing = true;
  document.dispatchEvent(new CustomEvent('accepted-snapshot', { detail: { generation_id: 'new-generation' } }));
  await vi.waitFor(() => expect(cards[0].textContent).toContain('Suggestions paused'));
  expect(cards[0].textContent).not.toContain('EUR 100');
  expect(cards[1].textContent).toContain('Ready for review');
  expect(document.querySelector('#accepted-plan')?.textContent).toBe('Previously accepted fixed quantities');
  expect(document.querySelector('#crypto-levels')?.getAttribute('data-portfolio-generation')).toBe('new-generation');
  dispose();
});

test('UTC rollover expires displayed levels without continuous provider or browser polling', async () => {
  vi.useFakeTimers();
  document.body.innerHTML = '<div></div>';
  const transport = vi.fn(async (_url: string, options: RequestInit) => {
    const input = JSON.parse(String(options.body)); return Response.json(preview(input.coin, input.templates));
  });
  const dispose = cryptoLevelsUI(document.querySelector('div'), transport, () => Date.parse('2026-10-23T12:00:00Z'));
  await vi.advanceTimersByTimeAsync(1);
  expect(transport).toHaveBeenCalledTimes(2);
  await vi.advanceTimersByTimeAsync(12 * 60 * 60 * 1000);
  expect(document.body.textContent).toContain('UTC day changed');
  expect(document.body.textContent).not.toContain('EUR 100');
  expect(transport).toHaveBeenCalledTimes(2);
  dispose(); vi.useRealTimers();
});
