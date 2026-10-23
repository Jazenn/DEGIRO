import type { PlanTerms, PlanRequest } from './crypto-plan';
export const now = '2026-10-23T12:00:00Z';
export const snapshot = { generation_id: 'g1', read_model: { ledger_version: 'ledger1', settings_version: 'financial1', calculation_version: 'decimal-accounting-v1', ledger: { positions: [{ broker_asset_id: 'direct-btc', symbol: 'BTC-EUR', asset_kind: 'Cryptocurrency', quantity: '1.01', cost_coverage: 'verified_complete' }] } } };
export const terms: PlanTerms = { coin: 'BTC-EUR', asset_id: 'direct-btc', symbol: 'BTC-EUR', revision: 'sale1', quantity_terms_revision: 'quantity1',
  quantity_step: '0.1', minimum_quantity: '0.1', minimum_notional_eur: '0', evidence: 'synthetic sale permission and compatible quantity rules', quantity_evidence: 'synthetic quantity rules',
  valid_from: '2026-01-01T00:00:00Z', valid_until: '2027-01-01T00:00:00Z', quantity_valid_from: '2026-01-01T00:00:00Z', quantity_valid_until: '2027-01-01T00:00:00Z' };
export const request: PlanRequest = { coin: 'BTC-EUR', operation_id: 'operation-123', expected_version: '0', generation_id: 'g1', market_version: 'market1', terms_revision: 'sale1', templates: {purchase:['35','20','10'],sale:['75','90','95']}, core_quantity: '0.2', proportions: ['50','30','20'], levels_eur: ['100','200','300'] };
