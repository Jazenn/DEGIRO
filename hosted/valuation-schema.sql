-- Review and apply only to an explicitly approved database branch.
BEGIN;
CREATE TABLE IF NOT EXISTS hosted_quote_mappings (
  symbol text PRIMARY KEY,
  provider text NOT NULL CHECK(provider IN ('binance','yahoo')),
  provider_symbol text NOT NULL,
  evidence text NOT NULL CHECK(length(evidence)>0)
);
-- Populate verified broker identity -> EUR provider listing mappings with dated source evidence.
-- No automatic symbol guessing or default private holdings are inserted.
CREATE OR REPLACE FUNCTION hosted_publish_valuation(new_generation text, expected_generation text,
  expected_settings bigint, proposed jsonb, deadline timestamptz)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE current_generation text; current_settings bigint; classification text; original jsonb;
BEGIN
  SELECT generation_id INTO current_generation FROM hosted_snapshot_pointer WHERE singleton FOR UPDATE;
  SELECT version INTO current_settings FROM hosted_targets WHERE singleton FOR SHARE;
  IF current_generation IS DISTINCT FROM expected_generation OR current_settings IS DISTINCT FROM expected_settings
    OR clock_timestamp() >= deadline THEN RETURN false; END IF;
  SELECT data_classification,read_model INTO classification,original FROM hosted_snapshot_generations WHERE generation_id=current_generation;
  IF proposed->>'ledger_version' IS DISTINCT FROM original->>'ledger_version'
    OR proposed->>'calculation_version' IS DISTINCT FROM original->>'calculation_version'
    OR proposed->>'settings_version' IS DISTINCT FROM original->>'settings_version'
    OR proposed->>'rebalancing_targets_version' IS DISTINCT FROM expected_settings::text
    OR proposed->'portfolio_history' IS DISTINCT FROM original->'portfolio_history'
    OR proposed->'ledger'->'charges' IS DISTINCT FROM original->'ledger'->'charges'
    OR proposed->'ledger'->'cash_balance_eur' IS DISTINCT FROM original->'ledger'->'cash_balance_eur'
    OR ((proposed->'ledger') - ARRAY['positions','market_value_eur','equity_eur','net_gain_eur','attributed_gain_eur'])
      IS DISTINCT FROM ((original->'ledger') - ARRAY['positions','market_value_eur','equity_eur','net_gain_eur','attributed_gain_eur'])
    OR (SELECT jsonb_agg(position - ARRAY['market_value_eur','held_gain_eur'] ORDER BY ordinal)
        FROM jsonb_array_elements(proposed->'ledger'->'positions') WITH ORDINALITY AS p(position, ordinal))
      IS DISTINCT FROM (SELECT jsonb_agg(position - ARRAY['market_value_eur','held_gain_eur'] ORDER BY ordinal)
        FROM jsonb_array_elements(original->'ledger'->'positions') WITH ORDINALITY AS p(position, ordinal))
    OR (proposed - ARRAY['ledger','cutoff','rebalancing_targets_version','observed_prices','crypto_quote_eligibility','crypto_quote_eligible_until','contribution_inputs','valuation_refreshed_at'])
      IS DISTINCT FROM (original - ARRAY['ledger','cutoff','rebalancing_targets_version','observed_prices','crypto_quote_eligibility','crypto_quote_eligible_until','contribution_inputs','valuation_refreshed_at'])
    THEN RAISE EXCEPTION 'Inconsistent valuation'; END IF;
  INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES(new_generation,classification,proposed);
  UPDATE hosted_snapshot_pointer SET generation_id=new_generation WHERE singleton;
  RETURN true;
END; $$;
REVOKE ALL ON FUNCTION hosted_publish_valuation(text,text,bigint,jsonb,timestamptz) FROM PUBLIC;
COMMIT;
-- Worker role requires SELECT on hosted_quote_mappings and EXECUTE on this function only.
-- Never grant Worker INSERT/UPDATE on Snapshot tables or UPDATE on verified mappings.

