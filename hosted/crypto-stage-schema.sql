-- Additive reviewed SALE costs only; purchase fees are never inherited.
BEGIN;
CREATE TABLE IF NOT EXISTS hosted_crypto_sale_costs (
  coin text PRIMARY KEY REFERENCES hosted_crypto_sale_permissions(coin),
  revision text NOT NULL CHECK(length(revision)>0),
  permission_revision text NOT NULL,
  fixed_fee_eur numeric NOT NULL CHECK(fixed_fee_eur>=0),
  fee_rate_pct numeric NOT NULL CHECK(fee_rate_pct BETWEEN 0 AND 100),
  minimum_fee_eur numeric NOT NULL CHECK(minimum_fee_eur>=0),
  spread_allowance_pct numeric NOT NULL CHECK(spread_allowance_pct BETWEEN 0 AND 100),
  fee_status text NOT NULL CHECK(fee_status IN ('known','estimated')),
  all_costs_reviewed boolean NOT NULL CHECK(all_costs_reviewed),
  evidence text NOT NULL CHECK(length(evidence)>0),
  spread_evidence text NOT NULL CHECK(length(spread_evidence)>0),
  valid_from timestamptz NOT NULL,
  valid_until timestamptz NOT NULL CHECK(valid_until>valid_from)
);
COMMIT;
-- Worker SELECT only; no default costs or permissions inserted. Explicit staging authorization required.
