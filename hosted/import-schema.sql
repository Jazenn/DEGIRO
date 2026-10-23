-- Apply only to an explicitly approved database. CSV bytes are private records.
BEGIN;
CREATE TABLE IF NOT EXISTS hosted_import_jobs (
  job_id text PRIMARY KEY,
  content_hash text NOT NULL UNIQUE,
  csv_content bytea NOT NULL CHECK (octet_length(csv_content) BETWEEN 1 AND 5242880),
  state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','processing','completed','failed')),
  history_state text NOT NULL DEFAULT 'unavailable' CHECK(history_state IN ('unavailable','pending','processing','completed','failed')),
  attempts integer NOT NULL DEFAULT 0,
  diagnostics jsonb NOT NULL DEFAULT '[]',
  generation_id text REFERENCES hosted_snapshot_generations(generation_id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);
COMMIT;
-- Worker role: SELECT (job_id, content_hash, state, history_state, attempts,
-- diagnostics, generation_id, created_at, updated_at), INSERT (job_id,
-- content_hash, csv_content), UPDATE (content_hash, state, diagnostics, updated_at).
-- Never grant SELECT(csv_content) to the Worker. Python publisher owns raw access.
