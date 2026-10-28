-- Apply only to an explicitly approved database after reviewing the quote source.
-- This extends allowed provider names only. No mappings or fallback are seeded.
BEGIN;
ALTER TABLE hosted_quote_mappings DROP CONSTRAINT IF EXISTS hosted_quote_mappings_provider_check;
ALTER TABLE hosted_quote_mappings ADD CONSTRAINT hosted_quote_mappings_provider_check
  CHECK(provider IN ('binance','yahoo','kraken'));
COMMIT;
