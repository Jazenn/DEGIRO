// @vitest-environment jsdom
import { expect, test, vi } from 'vitest';
// @ts-expect-error deployed browser module
import { cryptoStageUI } from './public/crypto-stage.js';

test('all reached stages use current proceeds and expire without altering the accepted plan', async () => {
  vi.useFakeTimers();
  const now = Date.parse('2026-10-23T12:00:00Z'); vi.setSystemTime(now);
  document.body.innerHTML='<div id="snapshot"></div><div id="crypto-plan">Saved plan remains</div><div id="stages"></div>';
  const request=vi.fn(async (_url: string, init: RequestInit)=>{
    const {coin}=JSON.parse(String(init.body));
    return Response.json(coin==='ETH-EUR' ? {coin,state:'unavailable',reason:'accepted_plan_required',stages:[]} : {
      coin,state:'ready',plan_id:'plan1',quote:{price_eur:'118000',observed_at:'2026-10-23T11:59:00Z',provider:'synthetic'},
      quote_eligible_until:'2026-10-23T12:04:00Z',available_tactical_quantity:'0.3',pending_quantity:'0',
      stages:[{stage_id:'plan1:1',level_eur:'100000',quantity:'0.1',gross_proceeds_eur:'11800',profit_status:'estimated_profit_verified_inputs',estimated_gain_eur:'15.00',gain_lower_eur:'14.99',gain_upper_eur:'15.01',net_proceeds_lower_eur:'11795',net_proceeds_upper_eur:'11795.01',canonical_cost_lower_eur:'11780',canonical_cost_upper_eur:'11780.01'},
        {stage_id:'plan1:2',level_eur:'115000',quantity:'0.1',gross_proceeds_eur:'11800',profit_status:'profit_unverified',estimated_gain_eur:null,diagnostic:'reviewed_all_in_sale_fees_required'}]});
  });
  const root=document.querySelector('#stages')!;
  const cleanup=cryptoStageUI(root,request);
  await vi.advanceTimersByTimeAsync(0);
  expect(root.textContent).toContain('plan1:1'); expect(root.textContent).toContain('plan1:2');
  expect(root.textContent).toContain('11800'); expect(root.textContent).toContain('Profit unverified');
  expect(root.textContent).toContain('15.00'); expect(root.querySelectorAll('a[href="#contribution"]')).toHaveLength(1);
  expect(root.querySelectorAll('button')).toHaveLength(1);
  await vi.advanceTimersByTimeAsync(240001);
  expect(root.textContent).toContain('Reference quote expired'); expect(root.textContent).not.toContain('plan1:1');
  expect(document.querySelector('#crypto-plan')!.textContent).toBe('Saved plan remains');
  expect(request).toHaveBeenCalledTimes(2);
  cleanup(); vi.useRealTimers();
});
