-- Apply only to the approved isolated staging database with the schema owner.
BEGIN;
CREATE TABLE IF NOT EXISTS hosted_owner_identity (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  google_sub text NOT NULL UNIQUE,
  owner_email text NOT NULL,
  bound_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS hosted_sessions (
  token_hash text PRIMARY KEY CHECK (length(token_hash) = 64),
  google_sub text NOT NULL REFERENCES hosted_owner_identity(google_sub),
  owner_email text NOT NULL,
  expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS hosted_sessions_expiry ON hosted_sessions(expires_at);
COMMIT;
-- Substitute the existing staging Worker role identifier, quoting it as an identifier.
-- GRANT SELECT, INSERT ON hosted_owner_identity TO "<worker-role>";
-- GRANT SELECT, INSERT, DELETE ON hosted_sessions TO "<worker-role>";
-- No UPDATE/DELETE grant on hosted_owner_identity. Snapshot tables remain SELECT-only.
-- Schema-owner recovery: revoke sessions and explicitly reset binding only after verifying
-- the replacement Google account. Never automatically replace a subject on email changes.
-- Optional maintenance by the schema owner: DELETE FROM hosted_sessions WHERE expires_at <= now();
