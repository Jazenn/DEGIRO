-- Apply after crypto-execution-schema. Synthetic tests do not authorize deployment.
BEGIN;
CREATE OR REPLACE FUNCTION hosted_review_crypto_replacement(requested jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE execution_version bigint; pending numeric;
BEGIN
  SELECT version INTO execution_version FROM hosted_crypto_execution_state WHERE coin=requested->>'coin';
  IF execution_version IS NULL OR execution_version::text IS DISTINCT FROM requested->>'expected_execution_version' THEN
    RETURN jsonb_build_object('state','conflict','reason','execution_state_changed');
  END IF;
  SELECT coalesce(sum(greatest(0,r.quantity-coalesce((SELECT sum(a.quantity_end-a.quantity_start)
      FROM hosted_crypto_match_allocations a WHERE a.report_id=r.report_id),0))),0) INTO pending
    FROM hosted_crypto_reports r WHERE r.plan_id=requested->>'replace_plan_id' AND r.status='open';
  IF pending>0 THEN RETURN jsonb_build_object('state','conflict','reason','pending_reports_require_resolution'); END IF;
  RETURN jsonb_build_object('state','ready');
END; $$;
REVOKE ALL ON FUNCTION hosted_review_crypto_replacement(jsonb) FROM PUBLIC;
CREATE TABLE IF NOT EXISTS hosted_crypto_report_events (
  operation_id text PRIMARY KEY, report_id text NOT NULL REFERENCES hosted_crypto_reports(report_id),
  event_type text NOT NULL CHECK(event_type='cancelled'), reason text NOT NULL,
  previous_report jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION hosted_cancel_crypto_report(requested jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE prior hosted_crypto_execution_operations; current_version bigint; generation text;
  active_plan text; report hosted_crypto_reports; response jsonb;
BEGIN
  IF requested->>'coin' NOT IN ('BTC-EUR','ETH-EUR') OR requested->>'operation_id' !~ '^[A-Za-z0-9_-]{8,100}$'
    OR requested->>'action' IS DISTINCT FROM 'cancel' OR requested->>'note' IS NULL
    OR length(trim(requested->>'note'))<10 OR length(requested->>'note')>1000 THEN RAISE EXCEPTION 'Invalid cancellation'; END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(requested->>'operation_id',58));
  SELECT * INTO prior FROM hosted_crypto_execution_operations WHERE operation_id=requested->>'operation_id';
  IF FOUND THEN
    IF prior.request=requested THEN RETURN prior.result; END IF;
    RETURN jsonb_build_object('state','conflict','reason','operation_id_reused');
  END IF;
  SELECT generation_id INTO generation FROM hosted_snapshot_pointer WHERE singleton=true FOR SHARE;
  SELECT current_plan_id INTO active_plan FROM hosted_crypto_plan_state WHERE coin=requested->>'coin' FOR SHARE;
  SELECT version INTO current_version FROM hosted_crypto_execution_state WHERE coin=requested->>'coin' FOR UPDATE;
  SELECT * INTO report FROM hosted_crypto_reports WHERE report_id=requested->>'report_id' AND coin=requested->>'coin' FOR UPDATE;
  IF current_version IS NULL OR current_version::text IS DISTINCT FROM requested->>'expected_version'
    OR generation IS DISTINCT FROM requested->>'generation_id' OR active_plan IS DISTINCT FROM requested->>'plan_id'
    OR report.plan_id IS DISTINCT FROM active_plan OR report.status IS DISTINCT FROM 'open' THEN
    response:=jsonb_build_object('state','conflict','reason','snapshot_plan_or_report_changed');
  ELSE
    INSERT INTO hosted_crypto_report_events(operation_id,report_id,event_type,reason,previous_report)
      VALUES(requested->>'operation_id',report.report_id,'cancelled',requested->>'note',to_jsonb(report));
    -- Matched allocations and globally consumed execution capacity remain immutable.
    UPDATE hosted_crypto_reports r SET status='cancelled' WHERE r.report_id=report.report_id;
    UPDATE hosted_crypto_execution_state SET version=version+1 WHERE coin=report.coin RETURNING version INTO current_version;
    response:=jsonb_build_object('state','cancelled','coin',report.coin,'version',current_version::text,'report_id',report.report_id);
  END IF;
  INSERT INTO hosted_crypto_execution_operations VALUES(requested->>'operation_id',requested,response);
  RETURN response;
END; $$;
REVOKE ALL ON FUNCTION hosted_cancel_crypto_report(jsonb) FROM PUBLIC;
COMMIT;
-- Worker EXECUTE hosted_review_crypto_replacement(jsonb), hosted_cancel_crypto_report(jsonb);
-- SELECT report event history. No mutation privileges.
