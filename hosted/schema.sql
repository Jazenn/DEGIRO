-- Review and apply ONLY to the explicitly approved synthetic staging database.
BEGIN;
CREATE TABLE IF NOT EXISTS hosted_snapshot_generations (
  generation_id text PRIMARY KEY,
  published_at timestamptz NOT NULL DEFAULT now(),
  data_classification text NOT NULL CHECK (data_classification IN ('synthetic', 'private')),
  read_model jsonb NOT NULL CHECK ((read_model->>'calculation_version' = 'decimal-accounting-v1'
    AND read_model->'ledger'->>'schema_version' = 'ledger-v1') IS TRUE)
);
CREATE TABLE IF NOT EXISTS hosted_snapshot_pointer (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  generation_id text NOT NULL REFERENCES hosted_snapshot_generations(generation_id)
);
-- Generations are append-only, including for the ingestion role.
CREATE OR REPLACE FUNCTION reject_hosted_snapshot_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Snapshot generations are immutable'; END; $$;
DROP TRIGGER IF EXISTS hosted_snapshot_immutable ON hosted_snapshot_generations;
CREATE TRIGGER hosted_snapshot_immutable BEFORE UPDATE OR DELETE ON hosted_snapshot_generations
  FOR EACH ROW EXECUTE FUNCTION reject_hosted_snapshot_mutation();
COMMIT;
-- Worker DATABASE_URL role: grant SELECT on these two tables ONLY.
-- Publisher credentials stay in the Python runner, never in the browser/Worker read role.
