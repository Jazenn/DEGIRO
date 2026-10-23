// @vitest-environment jsdom
import { expect, test, vi } from 'vitest';
// @ts-expect-error deployed browser module
import { cryptoPlanUI } from './public/crypto-plan.js';
import { prepareCryptoPlan } from './crypto-plan';
import { now, snapshot, terms } from './crypto-plan-test-support';

test('owner explicitly previews original quantities then accepts; accepted plan survives new holdings and history loss', async () => {
  document.body.innerHTML='<div id="snapshot"></div><div id="plans"></div>';
  Object.assign(document.querySelector('#snapshot')!, {acceptedSnapshot:structuredClone(snapshot)});
  const root = document.querySelector('#plans')!;
  const acceptedEvent=vi.fn(); document.addEventListener('crypto-plan-accepted',acceptedEvent);
  let saved: any = null, failRead=false;
  const cleanup = cryptoPlanUI(root, async (url: string, init: RequestInit) => {
    if (init.method === 'GET') return Response.json(failRead ? {} : {version:'0',plan:url.includes('BTC-EUR')?saved:null,terms}, {status:failRead?503:200});
    const payload=JSON.parse(String(init.body));
    const plan=prepareCryptoPlan(snapshot,terms,payload,now,{});
    if (!url.endsWith('/preview')) saved=plan;
    return Response.json({state:url.endsWith('/preview')?'preview':'accepted',version:'1',plan});
  },()=>Date.parse(now));
  await vi.waitFor(()=>expect(root.textContent).toContain('Reviewed sale quantity rules'));
  const form=root.querySelector('form')!;
  expect(form.querySelector<HTMLInputElement>('[name=core]')!.value).toBe('');
  expect(form.querySelector<HTMLInputElement>('[name=share-1]')!.value).toBe('');
  document.dispatchEvent(new CustomEvent('crypto-levels-preview',{detail:{coin:'BTC-EUR',state:'ready',market_version:'market1',valid_until:'2026-10-24T00:00:00Z',templates:{purchase:['35','20','10'],sale:['75','90','95']},sale:[{price_eur:'100'},{price_eur:'200'},{price_eur:'300'}]}}));
  const buttons=()=>Array.from(form.querySelectorAll('button'));
  buttons().find(button=>button.textContent==='Copy reviewed suggested sale levels')!.click();
  for(const [name,value] of [['core','0.2'],['share-1','50'],['share-2','30'],['share-3','20']]) {
    const field=form.querySelector<HTMLInputElement>(`[name=${name}]`)!;field.value=value;field.dispatchEvent(new Event('input',{bubbles:true}));
  }
  form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  await vi.waitFor(()=>expect(root.textContent).toContain('Rounding residual retained: 0.11'));
  const accept=buttons().find(button=>button.textContent==='Accept reviewed plan')!;
  expect(accept.disabled).toBe(true);
  const review=form.querySelector<HTMLInputElement>('[name=review]')!;review.checked=true;review.dispatchEvent(new Event('input',{bubbles:true}));
  expect(accept.disabled).toBe(false);accept.click();
  await vi.waitFor(()=>expect(root.textContent).toContain('Plan accepted and saved across devices'));
  expect(acceptedEvent).toHaveBeenCalledOnce();
  document.dispatchEvent(new CustomEvent('accepted-snapshot',{detail:{...snapshot,generation_id:'new-purchase'}}));
  document.dispatchEvent(new CustomEvent('crypto-levels-preview',{detail:{coin:'BTC-EUR',state:'paused',market_version:'missing'}}));
  expect(root.textContent).toContain('Stage 1: 0.4 units');
  expect(root.textContent).toContain('Accepted levels and quantities stay fixed');
  failRead=true;root.querySelector<HTMLButtonElement>('button')!.click();
  await vi.waitFor(()=>expect(root.textContent).toContain('Accepted-plan read failed'));
  expect(root.textContent).toContain('Stage 1: 0.4 units');
  cleanup();
  document.removeEventListener('crypto-plan-accepted',acceptedEvent);
});
