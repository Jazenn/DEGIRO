// @vitest-environment jsdom
import { expect, test, vi } from 'vitest';
// @ts-expect-error deployed browser module
import { cryptoExecutionUI } from './public/crypto-execution.js';

test('past sales remain reportable with stale quotes and matching requires an explicit execution choice', async () => {
  document.body.innerHTML='<div id="snapshot"></div><div id="history"></div>';
  Object.assign(document.querySelector('#snapshot')!,{acceptedSnapshot:{generation_id:'g1'}});
  const commands: any[]=[]; let version='0', reports: any[]=[], allocations: any[]=[];
  const source_timezone={name:'Europe/Amsterdam',status:'owner_assumed',evidence:'synthetic owner decision'};
  const request=vi.fn(async (url:string,init:RequestInit)=>{
    if(init.method==='GET') return Response.json({state:'ready',coin:url.includes('BTC')?'BTC-EUR':'ETH-EUR',version,generation_id:'g1',
      plan:{plan_id:'plan1',stages:[{stage_id:'plan1:1',quantity:'0.6'}]},progress:{pending_quantity:reports.length?'0.6':'0',matched_quantity:allocations.length?'0.6':'0'},reports,allocations,
      executions:allocations.length?[]:[{execution_id:'fill-a',quantity:'0.6',available_quantity:'0.6',eligible:true,executed_at:'2026-10-22T12:00:00Z',source_timezone,gross_proceeds_eur:'500',fees_eur:'5',disposed_cost_eur:'480',realized_gain_eur:'15',coverage:'verified_complete'}],diagnostics:[]});
    const body=JSON.parse(String(init.body)); commands.push(body); version=String(Number(version)+1);
    if(body.action==='report') reports=[{report_id:'report1',plan_id:'plan1',stage_id:'plan1:1',quantity:'0.6',pending_quantity:'0.6',matched_quantity:'0',status:'open'}];
    else allocations=[{execution_id:'fill-a',quantity:'0.6',receipt:{state:'verified',executed_at:'2026-10-22T12:00:00Z',source_timezone,display:{gross_proceeds_eur:'500.00',fees_eur:'5.00',disposed_cost_eur:'480.00',realized_gain_eur:'15.00'},rounding_note:'Display rounded; exact receipt retained.'}}];
    return Response.json({state:body.action==='report'?'reported':'matched',version});
  });
  const root=document.querySelector('#history')!, cleanup=cryptoExecutionUI(root,request);
  await vi.waitFor(()=>expect(root.textContent).toContain('fill-a'));
  expect(root.textContent).toContain('Execution time assumes Europe/Amsterdam at your request');
  expect(root.textContent).toContain('DEGIRO has not verified this convention');
  const form=root.querySelector('form')!;
  const field=(name:string)=>form.querySelector<HTMLInputElement|HTMLSelectElement>(`[name=${name}]`)!;
  expect(field('execution').value).toBe('');
  field('stage').value='plan1:1';field('quantity').value='0.6';
  form.dispatchEvent(new Event('submit',{cancelable:true,bubbles:true}));
  await vi.waitFor(()=>expect(root.textContent).toContain('report1'));
  expect(commands[0]).toMatchObject({action:'report',generation_id:'g1',expected_version:'0',quantity:'0.6'});
  expect(root.textContent).toContain('Pending');
  field('quantity').value='0.6';field('report').value='report1';
  Array.from(form.querySelectorAll('button')).find(button=>button.textContent==='Match selected execution')!.click();
  await vi.waitFor(()=>expect(root.textContent).toContain('Choose an actual imported execution'));
  expect(commands).toHaveLength(1);
  field('execution').value='fill-a';
  Array.from(form.querySelectorAll('button')).find(button=>button.textContent==='Match selected execution')!.click();
  await vi.waitFor(()=>expect(commands).toHaveLength(2));
  await vi.waitFor(()=>expect(root.textContent).toContain('15.00'));
  expect(root.textContent).toContain('Matched execution time: 2026-10-22T12:00:00Z');
  expect(root.textContent).toContain('Execution time assumes Europe/Amsterdam at your request');
  expect(commands[1]).toMatchObject({action:'match',execution_id:'fill-a',report_id:'report1',expected_version:'1'});
  cleanup();
});

test('a conflict preserves the draft and explicit reload rebases a new operation', async () => {
  document.body.innerHTML='<div id="snapshot"></div><div id="history"></div>';
  Object.assign(document.querySelector('#snapshot')!,{acceptedSnapshot:{generation_id:'g1'}});
  const commands:any[]=[];let version='0';
  const cleanup=cryptoExecutionUI(document.querySelector('#history')!,async (_url:string,init:RequestInit)=>{
    if(init.method==='GET') return Response.json({state:'ready',version,generation_id:'g1',plan:{plan_id:'p',stages:[{stage_id:'p:1',quantity:'1'}]},reports:[],executions:[],allocations:[]});
    const body=JSON.parse(String(init.body));commands.push(body);version='1';
    return commands.length===1?Response.json({state:'conflict'},{status:409}):Response.json({state:'reported',version:'2'});
  });
  const root=document.querySelector('#history')!;
  await vi.waitFor(()=>expect(root.textContent).toContain('Shared sales version 0'));
  const form=root.querySelector('form')!, quantity=form.querySelector<HTMLInputElement>('[name=quantity]')!;
  form.querySelector<HTMLSelectElement>('[name=stage]')!.value='p:1';quantity.value='0.6';
  form.dispatchEvent(new Event('submit',{cancelable:true,bubbles:true}));
  await vi.waitFor(()=>expect(root.textContent).toContain('Your draft remains'));
  expect(quantity.value).toBe('0.6');expect(quantity.disabled).toBe(true);
  root.querySelector<HTMLButtonElement>('button')!.click();
  await vi.waitFor(()=>expect(quantity.disabled).toBe(false));
  form.dispatchEvent(new Event('submit',{cancelable:true,bubbles:true}));
  await vi.waitFor(()=>expect(commands).toHaveLength(2));
  expect(commands[1].expected_version).toBe('1');expect(commands[1].operation_id).not.toBe(commands[0].operation_id);
  cleanup();
});

test('an uncertain result retains the original operation after reloading a newer shared version', async () => {
  document.body.innerHTML='<div id="snapshot"></div><div id="history"></div>';
  Object.assign(document.querySelector('#snapshot')!,{acceptedSnapshot:{generation_id:'g1'}});
  const commands:any[]=[];let version='0';
  const cleanup=cryptoExecutionUI(document.querySelector('#history')!,async (_url:string,init:RequestInit)=>{
    if(init.method==='GET') return Response.json({state:'ready',version,generation_id:'g1',plan:{plan_id:'p',stages:[{stage_id:'p:1',quantity:'1'}]},reports:[],executions:[],allocations:[]});
    commands.push(JSON.parse(String(init.body)));version='1';
    if(commands.length===1) throw Error('response lost after commit');
    return Response.json({state:'reported',version:'1'});
  });
  const root=document.querySelector('#history')!;
  await vi.waitFor(()=>expect(root.textContent).toContain('Shared sales version 0'));
  const form=root.querySelector('form')!;
  form.querySelector<HTMLSelectElement>('[name=stage]')!.value='p:1';form.querySelector<HTMLInputElement>('[name=quantity]')!.value='0.6';
  form.dispatchEvent(new Event('submit',{cancelable:true,bubbles:true}));
  await vi.waitFor(()=>expect(root.textContent).toContain('not confirmed'));
  root.querySelector<HTMLButtonElement>('button')!.click();
  await vi.waitFor(()=>expect(root.textContent).toContain('Shared sales version 1'));
  form.dispatchEvent(new Event('submit',{cancelable:true,bubbles:true}));
  await vi.waitFor(()=>expect(commands).toHaveLength(2));
  expect(commands[1]).toEqual(commands[0]);
  cleanup();
});
