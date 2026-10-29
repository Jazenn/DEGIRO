import { neon } from '@neondatabase/serverless';
import { timestamp } from './read-model.ts';

type Row = Record<string, any>;
type Query = (sql: string, params: unknown[], signal?: AbortSignal) => Promise<Row[]>;
export interface HistoryRequest { generation_id: string; period: string; offset?: string }
export interface HistoryReader { read(value: HistoryRequest, signal?: AbortSignal): Promise<Row> }
const periods = ['ALL', 'YTD', '1Y', '3M', '1M', '1W'];
const object = (value: unknown): value is Row => !!value && typeof value === 'object' && !Array.isArray(value);
const strings = (value: unknown) => Array.isArray(value) && value.every(item => typeof item === 'string');
const decimal = (value: unknown) => typeof value === 'string' && /^-?\d+(?:\.\d+)?(?:E[+-]?\d+)?$/i.test(value);
const exact = (value: unknown): boolean => typeof value !== 'number' &&
  (!value || typeof value !== 'object' || Object.values(value).every(exact));
const midnight = (value: unknown) => timestamp(value) && /T00:00:00Z$/.test(String(value));
export function historyRequest(value: unknown): HistoryRequest {
  if (!object(value) || Object.keys(value).some(key => !['generation_id', 'period', 'offset'].includes(key))
      || typeof value.generation_id !== 'string' || !/^[A-Za-z0-9_.:-]{1,160}$/.test(value.generation_id)
      || !periods.includes(value.period) || (value.offset !== undefined && (typeof value.offset !== 'string' || !/^(?:0|[1-9]\d{0,5})$/.test(value.offset)))) throw Error('invalid_history_request');
  return { generation_id: value.generation_id, period: value.period, ...(value.offset === undefined ? {} : { offset: value.offset }) };
}

// The immutable generation is the history reference. Projection happens inside
// Postgres so the current Worker never parses the full six-period document.
const context = `WITH source AS (
  SELECT generation_id,read_model->>'ledger_version' AS current_ledger,
    read_model->>'cutoff' AS valuation_cutoff,read_model->'portfolio_history' AS history
  FROM hosted_snapshot_generations WHERE generation_id=$1
), selected AS (
  SELECT *,history->'periods'->$2 AS period FROM source
) `;
const envelope = `'generation_id',generation_id,'period_name',$2::text,
  'ledger_version',history->>'ledger_version','settings_version',history->>'settings_version',
  'cutoff',history->>'cutoff','source_timezone',history->'source_timezone'`;
const summarySql = context + `SELECT CASE
  WHEN history IS NULL OR history->'periods'->$2 IS NULL THEN
    jsonb_build_object('state','unavailable','generation_id',generation_id,'reason','history_not_supplied',
      'diagnostics',coalesce(history->'diagnostics','["observed_daily_history_not_supplied"]'::jsonb))
  WHEN history->>'ledger_version' IS DISTINCT FROM current_ledger
    OR (history->>'cutoff')::timestamptz>valuation_cutoff::timestamptz THEN
    jsonb_build_object('state','unavailable','generation_id',generation_id,'reason','history_version_mismatch')
  ELSE jsonb_build_object('state','ready',${envelope},
    'periods',(SELECT jsonb_object_agg(name,jsonb_build_object('state',value->'state','start',value->'start',
      'end',value->'end','requested_start',value->'requested_start','shorter_coverage',value->'shorter_coverage'))
      FROM jsonb_each(history->'periods') AS periods(name,value)),
    'period',(period-ARRAY['points','estimated_return'])||jsonb_build_object(
      'points',CASE WHEN period->>'state'='ready' THEN
        (SELECT coalesce(jsonb_agg(jsonb_build_object('cutoff',point->'cutoff','equity_eur',point->'equity_eur') ORDER BY ordinal),'[]'::jsonb)
         FROM jsonb_array_elements(period->'points') WITH ORDINALITY AS points(point,ordinal)) ELSE '[]'::jsonb END,
      'estimated_return',(period->'estimated_return')-ARRAY['daily','excluded_prefunding_intervals'])) END AS result FROM selected`;
const detailsSql = context + `, page AS (
  SELECT *,coalesce((SELECT jsonb_agg(point ORDER BY ordinal) FROM jsonb_array_elements(period->'points') WITH ORDINALITY AS p(point,ordinal)
    WHERE ordinal>$3::integer AND ordinal<=$3::integer+7),'[]'::jsonb) AS points FROM selected
) SELECT CASE
  WHEN period IS NULL THEN jsonb_build_object('state','unavailable','generation_id',generation_id,'reason','history_not_supplied')
  WHEN history->>'ledger_version' IS DISTINCT FROM current_ledger
    OR (history->>'cutoff')::timestamptz>valuation_cutoff::timestamptz THEN
    jsonb_build_object('state','unavailable','generation_id',generation_id,'reason','history_version_mismatch')
  WHEN $3::integer>=jsonb_array_length(period->'points') THEN
    jsonb_build_object('state','unavailable','generation_id',generation_id,'reason','history_page_unavailable')
  ELSE jsonb_build_object('state','ready',${envelope},'offset',$3::text,'points',points,
    'next_offset',CASE WHEN $3::integer+7<jsonb_array_length(period->'points') THEN ($3::integer+7)::text ELSE NULL END,
    'daily',(SELECT coalesce(jsonb_agg(day ORDER BY ordinal),'[]'::jsonb)
      FROM jsonb_array_elements(coalesce(period->'estimated_return'->'daily','[]'::jsonb)) WITH ORDINALITY AS d(day,ordinal)
      WHERE day->>'cutoff'>=points->0->>'cutoff' AND day->>'cutoff'<=points->(jsonb_array_length(points)-1)->>'cutoff')) END AS result FROM page`;

function validEnvelope(result: Row, request: HistoryRequest) {
  return result.generation_id === request.generation_id && result.period_name === request.period
    && typeof result.ledger_version === 'string' && !!result.ledger_version
    && typeof result.settings_version === 'string' && !!result.settings_version && midnight(result.cutoff);
}
function validSummary(result: Row) {
  if (!object(result.periods) || Object.keys(result.periods).sort().join(',') !== [...periods].sort().join(',')) return false;
  const period = result.period;
  if (!object(period) || !['ready', 'unavailable'].includes(period.state) || !midnight(period.start)
      || period.end !== result.cutoff || !midnight(period.requested_start) || typeof period.shorter_coverage !== 'boolean'
      || !strings(period.diagnostics) || !Array.isArray(period.points)) return false;
  const estimate = period.estimated_return;
  if (!object(estimate) || !['ready', 'unavailable'].includes(estimate.state)
      || estimate.method !== 'geometrically_linked_daily_modified_dietz' || estimate.cutoff !== period.end
      || !strings(estimate.diagnostics) || (estimate.state === 'ready' ? !decimal(estimate.percent) : estimate.percent !== null)) return false;
  if (period.state === 'unavailable') return estimate.state !== 'ready';
  return object(period.attribution) && ['retained_gain_change_eur', 'realized_gain_change_eur', 'net_income_eur', 'portfolio_costs_eur', 'net_external_flows_eur', 'net_gain_eur'].every(key => decimal(period.attribution[key]))
    && Array.isArray(period.assets) && period.assets.every((asset: unknown) => object(asset) && typeof asset.broker_asset_id === 'string' && decimal(asset.retained_gain_change_eur) && decimal(asset.realized_gain_change_eur))
    && period.points.length >= 2 && period.points.every((point: unknown, index: number, points: Row[]) => object(point) && midnight(point.cutoff) && decimal(point.equity_eur)
      && (index === 0 ? point.cutoff === period.start : Date.parse(point.cutoff) - Date.parse(points[index - 1].cutoff) === 86400000)
      && (index !== points.length - 1 || point.cutoff === period.end));
}
function validDetails(result: Row, request: HistoryRequest) {
  return result.offset === request.offset && (result.next_offset === null || result.next_offset === String(Number(request.offset) + 7))
    && Array.isArray(result.points) && result.points.length > 0 && result.points.length <= 7
    && result.points.every((point: unknown) => object(point) && midnight(point.cutoff) && (point.equity_eur === null || decimal(point.equity_eur)) && object(point.observed_prices))
    && Array.isArray(result.daily) && result.daily.length <= 7;
}
export function historyStore(query: Query): HistoryReader {
  return {
    async read(value, signal) {
      const request = historyRequest(value);
      const rows = await query(request.offset === undefined ? summarySql : detailsSql,
        [request.generation_id, request.period, ...(request.offset === undefined ? [] : [request.offset])], signal);
      if (!rows.length) return { state: 'unavailable', generation_id: request.generation_id, reason: 'generation_unavailable' };
      const result = rows[0].result;
      if (!object(result) || !exact(result) || result.generation_id !== request.generation_id) throw Error('invalid_history');
      if (result.state === 'unavailable' && ['history_not_supplied', 'history_version_mismatch', 'history_page_unavailable'].includes(result.reason)) return result;
      if (result.state !== 'ready' || !validEnvelope(result, request)
          || !(request.offset === undefined ? validSummary(result) : validDetails(result, request))) throw Error('invalid_history');
      return result;
    },
  };
}
export function neonHistoryStore(url: string): HistoryReader {
  const sql = neon(url);
  return historyStore(async (query, params, signal) => await sql.query(query, params, { fetchOptions: { signal } }));
}
