-- Apply only to an explicitly approved branch after reviewing broker evidence.
BEGIN;
CREATE TABLE IF NOT EXISTS hosted_execution_terms (
  asset_id text PRIMARY KEY,
  revision text NOT NULL CHECK(length(revision)>0),
  quantity_step numeric NOT NULL CHECK(quantity_step>0),
  minimum_quantity numeric NOT NULL CHECK(minimum_quantity>=quantity_step),
  minimum_notional_eur numeric NOT NULL CHECK(minimum_notional_eur>=0),
  fixed_fee_eur numeric NOT NULL CHECK(fixed_fee_eur>=0),
  fee_rate_pct numeric NOT NULL CHECK(fee_rate_pct>=0 AND fee_rate_pct<=100),
  minimum_fee_eur numeric NOT NULL CHECK(minimum_fee_eur>=0),
  fee_status text NOT NULL CHECK(fee_status IN ('known','estimated')),
  fee_scope text NOT NULL CHECK(fee_scope='all_purchase_charges'),
  currency text NOT NULL CHECK(currency='EUR'),
  evidence text NOT NULL CHECK(length(evidence)>0),
  valid_from timestamptz NOT NULL,
  valid_until timestamptz NOT NULL CHECK(valid_until>valid_from)
);
COMMIT;
-- Worker needs SELECT only. No automatic tariff, zero-fee or fractional-quantity defaults.
-- A reviewer supplies dated asset/broker/venue-specific evidence covering ALL purchase charges,
-- quote currency, order constraints and the validity interval. Any unsupported charging model
-- remains unavailable until modeled; do not squeeze it into an unverified flat/rate estimate.
