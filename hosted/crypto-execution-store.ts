import { neon } from '@neondatabase/serverless';
import { validCoin } from './crypto-plan';
export interface ExecutionStore {
  read(coin: string): Promise<Record<string, any>>;
  commit(value: Record<string, unknown>): Promise<Record<string, any>>;
}
export function cryptoExecutions(store: ExecutionStore) {
  return async (method: string, value: unknown) => {
    if (method === 'GET') {
      if (!validCoin(value)) throw Error('invalid_crypto_execution');
      return store.read(value);
    }
    const input = value as Record<string, unknown>;
    const text = (key: string) => typeof input?.[key] === 'string' && (input[key] as string).length > 0 && (input[key] as string).length <= 1000;
    if (!input || !validCoin(input.coin) || !['report','match','cancel'].includes(String(input.action))
        || !text('operation_id') || !/^[\w-]{8,100}$/.test(input.operation_id as string)
        || !text('expected_version') || !/^\d{1,18}$/.test(input.expected_version as string)
        || !['generation_id','plan_id'].every(text)
        || (input.action!=='cancel'&&(!text('stage_id') || !text('quantity') || !/^\d{1,18}(?:\.\d{1,18})?$/.test(input.quantity as string) || !/[1-9]/.test(input.quantity as string)))
        || (input.action==='cancel'&&(!text('report_id')||!text('note')||(input.note as string).trim().length<10))
        || (input.action === 'match' && !text('execution_id'))
        || ('report_id' in input && (!['match','cancel'].includes(String(input.action)) || !text('report_id')))
        || ('note' in input && (typeof input.note !== 'string' || input.note.length > 1000))) throw Error('invalid_crypto_execution');
    const request = Object.fromEntries(['coin','action','operation_id','expected_version','generation_id','plan_id',
      ...(input.action==='cancel'?['report_id']:['stage_id','quantity']),
      ...(input.action === 'match' ? ['execution_id',...('report_id' in input ? ['report_id'] : [])] : []),...('note' in input ? ['note'] : [])].map(key=>[key,input[key]]));
    return store.commit(request);
  };
}
export function neonExecutionStore(url: string): ExecutionStore {
  const sql=neon(url);
  return {
    async read(coin) { return (await sql.query("SELECT hosted_read_crypto_executions($1) || jsonb_build_object('report_events',hosted_read_crypto_report_events($1)) AS result",[coin]))[0].result; },
    async commit(value) { return (await sql.query(value.action==='cancel'?'SELECT hosted_cancel_crypto_report($1::jsonb) AS result':'SELECT hosted_record_crypto_execution($1::jsonb) AS result',[JSON.stringify(value)]))[0].result; },
  };
}
