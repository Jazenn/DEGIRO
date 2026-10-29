-- Apply only to an approved database. Public market series, no private ledger prerequisites.
BEGIN;
CREATE TABLE IF NOT EXISTS hosted_crypto_market_history (
  coin text PRIMARY KEY CHECK(coin IN ('BTC-EUR','ETH-EUR')),
  version text NOT NULL,
  observations jsonb NOT NULL DEFAULT '{}',
  attempted_at timestamptz NOT NULL,
  diagnostics jsonb NOT NULL DEFAULT '[]',
  prepared_summary jsonb
);
ALTER TABLE hosted_crypto_market_history ADD COLUMN IF NOT EXISTS prepared_summary jsonb;
COMMIT;
-- Worker: SELECT only on this table. Hosted Python publisher: INSERT, UPDATE, SELECT.
