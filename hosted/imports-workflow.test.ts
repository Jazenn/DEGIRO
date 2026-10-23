// @vitest-environment jsdom
import { expect, test, vi } from 'vitest';

test('owner sees failed import independently from accepted Snapshot and retries it safely', async () => {
  document.body.innerHTML = '<main id="snapshot">Accepted EUR 1100</main><section id="imports"></section>';
  let state = 'failed';
  vi.stubGlobal('fetch', async (url: string, options?: RequestInit) => {
    if (options?.method === 'POST') {
      expect(url).toBe('/api/imports/synthetic-job/retry');
      state = 'pending';
      return Response.json({ jobs: [{ state }] }, { status: 202 });
    }
    return Response.json({ jobs: [{ job_id: 'synthetic-job', state, history_state: 'unavailable', diagnostics: ['validation_requires_review'] }] });
  });
  // @ts-expect-error static browser JS has no bundled financial dependencies
  await import('./public/imports.js');
  await vi.waitFor(() => expect(document.querySelector('#import-jobs')?.textContent).toContain('failed'));
  expect(document.querySelector('#import-jobs')?.textContent).toContain('Background history: unavailable');
  const retry = Array.from(document.querySelectorAll('button')).find(button => button.textContent === 'Retry safely');
  retry!.click();
  await vi.waitFor(() => expect(document.querySelector('#import-jobs')?.textContent).toContain('pending'));
  expect(document.querySelector('#snapshot')?.textContent).toBe('Accepted EUR 1100');
  vi.unstubAllGlobals();
});
