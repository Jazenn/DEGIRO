-- Apply with explicit database authorization; grants are restricted to the targets function.
BEGIN;
CREATE TABLE IF NOT EXISTS hosted_targets (
  singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
  version bigint NOT NULL DEFAULT 0,
  targets jsonb NOT NULL DEFAULT '[]'
);
INSERT INTO hosted_targets(singleton) VALUES(true) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS hosted_target_operations (
  operation_id text PRIMARY KEY, expected_version bigint NOT NULL, targets jsonb NOT NULL, result jsonb NOT NULL
);
CREATE OR REPLACE FUNCTION hosted_save_targets(operation text, expected bigint, proposed jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE current_row hosted_targets; previous hosted_target_operations; response jsonb;
BEGIN
  -- Serializes cross-device edits and operation retries in one transaction.
  SELECT * INTO current_row FROM hosted_targets WHERE singleton = true FOR UPDATE;
  SELECT * INTO previous FROM hosted_target_operations WHERE operation_id = operation;
  IF FOUND THEN
    IF previous.expected_version = expected AND previous.targets = proposed THEN RETURN previous.result; END IF;
    RETURN jsonb_build_object('state','conflict','current',jsonb_build_object('version',current_row.version::text,'targets',current_row.targets));
  END IF;
  IF expected <> current_row.version THEN
    response := jsonb_build_object('state','conflict','current',jsonb_build_object('version',current_row.version::text,'targets',current_row.targets));
  ELSE
    IF jsonb_typeof(proposed) <> 'array' OR jsonb_array_length(proposed) = 0 OR jsonb_array_length(proposed) > 100
      OR EXISTS (SELECT FROM jsonb_array_elements(proposed) r WHERE (r->>'asset_id') IS NULL OR (r->>'asset_id') !~ '^[A-Za-z0-9_.:-]{1,100}$'
        OR (r->>'target_pct') IS NULL OR (r->>'target_pct') !~ '^[0-9]{1,3}(\.[0-9]{1,2})?$') THEN RAISE EXCEPTION 'Invalid targets'; END IF;
    IF (SELECT sum((r->>'target_pct')::numeric) FROM jsonb_array_elements(proposed) r) <> 100
      OR EXISTS (SELECT FROM jsonb_array_elements(proposed) r WHERE (r->>'target_pct')::numeric > 100)
      OR (SELECT count(DISTINCT r->>'asset_id') FROM jsonb_array_elements(proposed) r) <> jsonb_array_length(proposed)
      THEN RAISE EXCEPTION 'Invalid targets'; END IF;
    UPDATE hosted_targets SET version = version + 1, targets = proposed WHERE singleton = true RETURNING * INTO current_row;
    response := jsonb_build_object('state','saved','current',jsonb_build_object('version',current_row.version::text,'targets',current_row.targets));
  END IF;
  INSERT INTO hosted_target_operations VALUES(operation, expected, proposed, response);
  RETURN response;
END; $$;
REVOKE ALL ON FUNCTION hosted_save_targets(text,bigint,jsonb) FROM PUBLIC;
COMMIT;
-- Approved Worker role requires SELECT on hosted_targets and EXECUTE on hosted_save_targets(text,bigint,jsonb).
-- No UPDATE/DELETE grants, snapshot publishing rights or operation-table access are required.
