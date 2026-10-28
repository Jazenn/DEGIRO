// @vitest-environment jsdom
import { expect,test,vi } from 'vitest';
// @ts-expect-error browser module
import { cryptoPlanUI } from './public/crypto-plan.js';
// @ts-expect-error browser module
import { cryptoExecutionUI } from './public/crypto-execution.js';
import {prepareCryptoPlan} from './crypto-plan';
import {now,snapshot,terms,request} from './crypto-plan-test-support';

test('replacement keeps accepted quantities visible and requires a reviewed preview with execution version',async()=>{
  document.body.innerHTML='<div id="snapshot"></div><div id="plans"></div>';
  Object.assign(document.querySelector('#snapshot')!,{acceptedSnapshot:snapshot});
  const old=prepareCryptoPlan(snapshot,terms,request,now,{}),commands:any[]=[];
  const root=document.querySelector('#plans')!;
  const cleanup=cryptoPlanUI(root,async(url:string,init:RequestInit)=>{
    if(url.includes('/executions'))return Response.json({state:'ready',version:'7',plan:old});
    if(init.method==='GET')return Response.json({version:'1',terms,plan:url.includes('BTC')?old:null,history:[old]});
    const body=JSON.parse(String(init.body));commands.push(body);
    return Response.json({state:'preview',plan:prepareCryptoPlan(snapshot,terms,body,now,{})});
  },()=>Date.parse(now));
  await vi.waitFor(()=>expect(root.textContent).toContain(old.plan_id));
  Array.from(root.querySelectorAll('button')).find(button=>button.textContent==='Review replacement')!.click();
  await vi.waitFor(()=>expect(root.textContent).toContain('Shared sales version 7'));
  document.dispatchEvent(new CustomEvent('crypto-levels-preview',{detail:{coin:'BTC-EUR',state:'ready',market_version:'market1',valid_until:'2026-10-24T00:00:00Z',templates:request.templates,sale:[]}}));
  const form=root.querySelector('form')!;
  const reason=form.querySelector<HTMLInputElement>('[name=replacement-reason]')!;
  reason.value='Reviewed holdings after partial sale';
  form.dispatchEvent(new Event('submit',{cancelable:true,bubbles:true}));
  await vi.waitFor(()=>expect(commands).toHaveLength(1));
  expect(commands[0]).toMatchObject({replace_plan_id:old.plan_id,expected_execution_version:'7',replacement_reason:reason.value,expected_version:'1'});
  expect(root.textContent).toContain('Stage 1: 0.4 units');
  cleanup();
});

test('cancelling pending remainder requires a reason and preserves historical sale records',async()=>{
  document.body.innerHTML='<div id="snapshot"></div><div id="sales"></div>';
  Object.assign(document.querySelector('#snapshot')!,{acceptedSnapshot:{generation_id:'g1'}});
  const commands:any[]=[];const root=document.querySelector('#sales')!;
  const cleanup=cryptoExecutionUI(root,async(_url:string,init:RequestInit)=>{
    if(init.method==='GET')return Response.json({state:'ready',version:'2',generation_id:'g1',plan:{plan_id:'p',stages:[]},reports:[{report_id:'r',plan_id:'p',stage_id:'p:1',quantity:'1',pending_quantity:'0.4',matched_quantity:'0.6',status:'open'}],allocations:[],executions:[]});
    commands.push(JSON.parse(String(init.body)));return Response.json({state:'cancelled',version:'3'});
  });
  await vi.waitFor(()=>expect(root.textContent).toContain('Report r'));
  const form=root.querySelector('form')!;
  form.querySelector<HTMLSelectElement>('[name=report]')!.value='r';
  const cancel=Array.from(form.querySelectorAll('button')).find(button=>button.textContent==='Cancel pending remainder')!;
  cancel.click();await vi.waitFor(()=>expect(root.textContent).toContain('Explain the cancellation'));
  expect(commands).toHaveLength(0);
  form.querySelector<HTMLInputElement>('[name=note]')!.value='Duplicate manual report; preserve matched fill';cancel.click();
  await vi.waitFor(()=>expect(commands).toHaveLength(1));
  expect(commands[0]).toMatchObject({action:'cancel',report_id:'r',expected_version:'2',plan_id:'p'});
  cleanup();
});
