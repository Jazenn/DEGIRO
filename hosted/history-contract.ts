// Validate the persisted history envelope without recalculating financial results.
type RecordValue = Record<string, unknown>;
const object = (value: unknown): value is RecordValue => !!value && typeof value === 'object' && !Array.isArray(value);
const decimal = (value: unknown) => typeof value === 'string' && /^-?\d+(?:\.\d+)?(?:E[+-]?\d+)?$/i.test(value);
const midnight = (value: unknown): value is string => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T00:00:00Z$/.test(value) && Number.isFinite(Date.parse(value));
const strings = (value: unknown) => Array.isArray(value) && value.every(item => typeof item === 'string');
export function validHistory(history: unknown, model: RecordValue): boolean {
  if (history === undefined) return true;
  if (!object(history) || history.schema_version !== 'observed-history-v1'
      || history.ledger_version !== model.ledger_version || history.settings_version !== model.settings_version
      || !midnight(history.cutoff) || Date.parse(history.cutoff) > Date.parse(String(model.cutoff)) || !object(history.periods)) return false;
  if (!Object.keys(history.periods).length) return strings(history.diagnostics);
  if (Object.keys(history.periods).sort().join(',') !== ['ALL', 'YTD', '1Y', '3M', '1M', '1W'].sort().join(',')) return false;
  return Object.values(history.periods).every(period => {
    if (!object(period) || !['ready', 'unavailable'].includes(String(period.state))
        || !midnight(period.start) || period.end !== history.cutoff || !midnight(period.requested_start)
        || typeof period.shorter_coverage !== 'boolean' || !strings(period.diagnostics) || !Array.isArray(period.points)) return false;
    if (period.state === 'unavailable') return period.attribution === undefined;
    if (!object(period.attribution) || !['retained_gain_change_eur', 'realized_gain_change_eur', 'net_income_eur', 'portfolio_costs_eur', 'net_external_flows_eur', 'net_gain_eur'].every(key => decimal(period.attribution && (period.attribution as RecordValue)[key]))
        || !Array.isArray(period.assets) || !period.assets.every(asset => object(asset) && typeof asset.broker_asset_id === 'string' && decimal(asset.retained_gain_change_eur) && decimal(asset.realized_gain_change_eur))) return false;
    return period.points.length >= 2 && period.points.every((point, index, points) => object(point)
      && midnight(point.cutoff) && decimal(point.equity_eur) && object(point.observed_prices)
      && (index === 0 ? point.cutoff === period.start : Date.parse(point.cutoff) - Date.parse((points[index - 1] as RecordValue).cutoff as string) === 86400000)
      && (index !== points.length - 1 || point.cutoff === period.end));
  });
}
