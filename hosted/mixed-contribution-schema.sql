-- Apply only to an explicitly approved branch. No real account configuration is seeded.
BEGIN;
ALTER TABLE hosted_execution_terms ADD COLUMN IF NOT EXISTS spread_allowance_pct numeric
  CHECK(spread_allowance_pct>=0 AND spread_allowance_pct<=100);
ALTER TABLE hosted_execution_terms ADD COLUMN IF NOT EXISTS spread_evidence text;
CREATE TABLE IF NOT EXISTS hosted_contribution_assets (
  asset_id text PRIMARY KEY,
  symbol text NOT NULL,
  asset_kind text NOT NULL CHECK(asset_kind IN ('ETF','Cryptocurrency')),
  identity_evidence text NOT NULL CHECK(length(identity_evidence)>0),
  verified_at timestamptz NOT NULL
);
COMMIT;
-- SELECT-only Worker access to hosted_contribution_assets. Existing terms SELECT grants cover new columns.
-- Review broker asset identity and EUR quote mapping independently. Missing/mismatched identities
-- never fall back to a crypto ETP, inferred ISIN or synthetic holding.
-- Crypto terms require an explicit reviewed spread allowance AND evidence in addition to commission,
-- verified quantity step and minimums. NULL means unknown, never zero. The dated all-in terms must
-- explain whether their rate is commission only; do not count a spread allowance twice.
