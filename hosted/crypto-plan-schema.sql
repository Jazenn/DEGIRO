-- Apply only to an explicitly approved database. No allocation or broker rules are seeded.
BEGIN;
CREATE TABLE IF NOT EXISTS hosted_crypto_sale_permissions (
  coin text PRIMARY KEY CHECK(coin IN ('BTC-EUR','ETH-EUR')),
  asset_id text NOT NULL UNIQUE REFERENCES hosted_execution_terms(asset_id),
  symbol text NOT NULL,
  revision text NOT NULL CHECK(length(revision)>0),
  quantity_terms_revision text NOT NULL,
  quantity_rules_apply_to_sales boolean NOT NULL CHECK(quantity_rules_apply_to_sales),
  evidence text NOT NULL CHECK(length(evidence)>0),
  valid_from timestamptz NOT NULL,
  valid_until timestamptz NOT NULL CHECK(valid_until>valid_from)
);
CREATE TABLE IF NOT EXISTS hosted_crypto_plan_state (
  coin text PRIMARY KEY CHECK(coin IN ('BTC-EUR','ETH-EUR')),
  version bigint NOT NULL DEFAULT 0,
  current_plan_id text
);
INSERT INTO hosted_crypto_plan_state(coin) VALUES('BTC-EUR'),('ETH-EUR') ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS hosted_crypto_plan_history (
  plan_id text PRIMARY KEY,
  coin text NOT NULL REFERENCES hosted_crypto_plan_state(coin),
  accepted_at timestamptz NOT NULL,
  plan jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS hosted_crypto_plan_operations (
  operation_id text PRIMARY KEY,
  request jsonb NOT NULL,
  result jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS hosted_crypto_plan_events (
  event_id text PRIMARY KEY,
  coin text NOT NULL REFERENCES hosted_crypto_plan_state(coin),
  plan_id text NOT NULL REFERENCES hosted_crypto_plan_history(plan_id),
  operation_id text NOT NULL UNIQUE,
  event_type text NOT NULL,
  event_body jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION hosted_accept_crypto_plan(requested jsonb, proposed jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE current_state hosted_crypto_plan_state; prior hosted_crypto_plan_operations;
  permission hosted_crypto_sale_permissions; quantity_terms hosted_execution_terms;
  generation text; model jsonb; position jsonb; market_version text; response jsonb;
  stages_total numeric; holding numeric; core numeric; tactical numeric; replacement_check jsonb; old_plan_id text;
BEGIN
  IF requested->>'coin' NOT IN ('BTC-EUR','ETH-EUR') OR requested->>'operation_id' !~ '^[A-Za-z0-9_-]{8,100}$' THEN RAISE EXCEPTION 'Invalid plan operation'; END IF;
  -- Same operation across either coin is serialized before all state locks.
  PERFORM pg_advisory_xact_lock(hashtextextended(requested->>'operation_id',56));
  SELECT * INTO prior FROM hosted_crypto_plan_operations WHERE operation_id=requested->>'operation_id';
  IF FOUND THEN
    IF prior.request=requested THEN RETURN prior.result; END IF;
    RETURN jsonb_build_object('state','conflict','reason','operation_id_reused');
  END IF;
  SELECT p.generation_id,g.read_model INTO generation,model
    FROM hosted_snapshot_pointer p JOIN hosted_snapshot_generations g USING(generation_id)
    WHERE p.singleton=true FOR SHARE OF p;
  SELECT * INTO current_state FROM hosted_crypto_plan_state WHERE coin=requested->>'coin' FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Missing coin state'; END IF;
  old_plan_id:=current_state.current_plan_id;
  IF requested ? 'replace_plan_id' THEN
    -- Same lock order as execution commands: Snapshot, plan, then execution state.
    PERFORM 1 FROM hosted_crypto_execution_state WHERE coin=current_state.coin FOR UPDATE;
    replacement_check:=hosted_review_crypto_replacement(requested);
  END IF;
  IF generation IS DISTINCT FROM requested->>'generation_id' OR current_state.version::text<>requested->>'expected_version' THEN
    response:=jsonb_build_object('state','conflict','reason','snapshot_or_plan_changed','version',current_state.version::text);
  ELSIF requested ? 'replace_plan_id' AND (requested->>'replace_plan_id' IS DISTINCT FROM old_plan_id OR old_plan_id IS NULL) THEN
    response:=jsonb_build_object('state','conflict','reason','replacement_plan_changed');
  ELSIF requested ? 'replace_plan_id' AND replacement_check->>'state'<>'ready' THEN
    response:=replacement_check;
  ELSIF current_state.current_plan_id IS NOT NULL AND NOT (requested ? 'replace_plan_id') THEN
    response:=jsonb_build_object('state','replacement_required','reason','accepted_plan_is_immutable','version',current_state.version::text);
  ELSE
    SELECT * INTO permission FROM hosted_crypto_sale_permissions WHERE coin=current_state.coin FOR SHARE;
    SELECT * INTO quantity_terms FROM hosted_execution_terms WHERE asset_id=permission.asset_id FOR SHARE;
    SELECT version INTO market_version FROM hosted_crypto_market_history WHERE coin=current_state.coin FOR SHARE;
    SELECT value INTO position FROM jsonb_array_elements(model->'ledger'->'positions') WHERE value->>'broker_asset_id'=permission.asset_id;
    IF permission.revision IS DISTINCT FROM requested->>'terms_revision'
       OR permission.quantity_terms_revision IS DISTINCT FROM quantity_terms.revision
       OR market_version IS DISTINCT FROM requested->>'market_version'
       OR proposed->'source_market'->>'valid_until' IS NULL
       OR clock_timestamp()<permission.valid_from OR clock_timestamp()>=permission.valid_until
       OR clock_timestamp()<quantity_terms.valid_from OR clock_timestamp()>=quantity_terms.valid_until
       OR clock_timestamp()>=(proposed->'source_market'->>'valid_until')::timestamptz THEN
      response:=jsonb_build_object('state','conflict','reason','reviewed_inputs_changed');
    ELSE
      IF requested ? 'replace_plan_id' AND (length(trim(requested->>'replacement_reason'))<10
        OR length(requested->>'replacement_reason')>1000 OR requested->>'replacement_reason' IS NULL
        OR proposed->>'replaces_plan_id' IS DISTINCT FROM old_plan_id
        OR proposed->>'replacement_reason' IS DISTINCT FROM requested->>'replacement_reason'
        OR proposed->>'reviewed_execution_version' IS DISTINCT FROM requested->>'expected_execution_version') THEN
        RAISE EXCEPTION 'Invalid reviewed replacement';
      END IF;
      holding:=(position->>'quantity')::numeric;
      core:=(proposed->>'core_quantity')::numeric;
      tactical:=(proposed->>'original_tactical_quantity')::numeric;
      SELECT sum((value->>'quantity')::numeric) INTO stages_total FROM jsonb_array_elements(proposed->'stages');
      IF NOT proposed ?& ARRAY['plan_id','plan_version','coin','asset_id','ledger_version','financial_settings_version','held_quantity_at_acceptance','core_quantity','original_tactical_quantity','rounding_residual_quantity','accepted_at','stages']
        OR EXISTS(SELECT FROM jsonb_each(proposed) e WHERE e.key IN ('plan_id','plan_version','coin','asset_id','ledger_version','financial_settings_version','held_quantity_at_acceptance','core_quantity','original_tactical_quantity','rounding_residual_quantity','accepted_at','stages') AND e.value='null'::jsonb)
        OR position IS NULL OR position->>'asset_kind'<>'Cryptocurrency' OR position->>'symbol'<>permission.symbol
        OR position->>'cost_coverage'<>'verified_complete'
        OR proposed->>'asset_id'<>permission.asset_id OR proposed->>'coin'<>current_state.coin
        OR proposed->>'plan_id'<>('plan-'||(requested->>'operation_id'))
        OR (proposed->>'plan_version')::numeric<>current_state.version+1
        OR proposed->>'ledger_version' IS DISTINCT FROM model->>'ledger_version'
        OR proposed->>'financial_settings_version' IS DISTINCT FROM model->>'settings_version'
        OR holding IS NULL OR core IS NULL OR tactical IS NULL OR stages_total IS NULL OR core<=0 OR tactical<=0
        OR core<>(requested->>'core_quantity')::numeric
        OR holding<>(proposed->>'held_quantity_at_acceptance')::numeric OR core+tactical<>holding
        OR stages_total>tactical OR (proposed->>'rounding_residual_quantity')::numeric<>tactical-stages_total
        OR jsonb_array_length(proposed->'stages')<>3
        OR (SELECT sum((value->>'proportion_pct')::numeric) FROM jsonb_array_elements(proposed->'stages'))<>100
        OR NOT ((proposed->'stages'->0->>'level_eur')::numeric<(proposed->'stages'->1->>'level_eur')::numeric AND (proposed->'stages'->1->>'level_eur')::numeric<(proposed->'stages'->2->>'level_eur')::numeric)
        OR EXISTS(SELECT FROM jsonb_array_elements(proposed->'stages') WITH ORDINALITY s(r,ordinal) WHERE
          r->>'stage_id' IS DISTINCT FROM (proposed->>'plan_id')||':'||ordinal::text OR r->>'state' IS DISTINCT FROM 'unfinished'
          OR r->>'quantity' IS NULL OR r->>'proportion_pct' IS NULL OR r->>'level_eur' IS NULL
          OR (r->>'proportion_pct')::numeric<>(requested->'proportions'->>(ordinal::integer-1))::numeric
          OR (r->>'level_eur')::numeric<>(requested->'levels_eur'->>(ordinal::integer-1))::numeric
          OR (r->>'quantity')::numeric<quantity_terms.minimum_quantity
          OR (r->>'proportion_pct')::numeric<=0 OR (r->>'level_eur')::numeric<=0
          OR (r->>'quantity')::numeric<>floor(tactical*(r->>'proportion_pct')::numeric/100/quantity_terms.quantity_step)*quantity_terms.quantity_step
          OR mod((r->>'quantity')::numeric,quantity_terms.quantity_step)<>0
          OR (r->>'quantity')::numeric*(r->>'level_eur')::numeric<quantity_terms.minimum_notional_eur)
      THEN RAISE EXCEPTION 'Invalid protected stage quantities'; END IF;
      INSERT INTO hosted_crypto_plan_history(plan_id,coin,accepted_at,plan)
        VALUES(proposed->>'plan_id',current_state.coin,(proposed->>'accepted_at')::timestamptz,proposed);
      UPDATE hosted_crypto_plan_state SET version=version+1,current_plan_id=proposed->>'plan_id' WHERE coin=current_state.coin RETURNING * INTO current_state;
      INSERT INTO hosted_crypto_plan_events(event_id,coin,plan_id,operation_id,event_type,event_body)
        VALUES('accept-'||(requested->>'operation_id'),current_state.coin,proposed->>'plan_id',requested->>'operation_id',
          CASE WHEN old_plan_id IS NULL THEN 'accepted' ELSE 'replacement_accepted' END,proposed);
      response:=jsonb_build_object('state','accepted','coin',current_state.coin,'version',current_state.version::text,'plan',proposed);
    END IF;
  END IF;
  INSERT INTO hosted_crypto_plan_operations VALUES(requested->>'operation_id',requested,response);
  RETURN response;
END; $$;
REVOKE ALL ON FUNCTION hosted_accept_crypto_plan(jsonb,jsonb) FROM PUBLIC;
COMMIT;
-- Worker SELECT: state/history, operation_id/request/result, sale_permissions, execution_terms.
-- Worker EXECUTE hosted_accept_crypto_plan(jsonb,jsonb). No direct mutation grants.
-- Reviewer confirms direct coin identity, sale permissions and applicability of the referenced
-- quantity/minimum terms to sales. Purchase-fee facts are NOT sale-fee evidence.
