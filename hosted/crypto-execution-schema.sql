-- Review and apply only to an approved database. Actual FIFO comes exclusively from Python.
BEGIN;
CREATE TABLE IF NOT EXISTS hosted_crypto_reports (
  report_id text PRIMARY KEY, coin text NOT NULL REFERENCES hosted_crypto_plan_state(coin),
  plan_id text NOT NULL REFERENCES hosted_crypto_plan_history(plan_id), stage_id text NOT NULL,
  quantity numeric NOT NULL CHECK(quantity>0), status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','cancelled','resolved')),
  generation_id text NOT NULL REFERENCES hosted_snapshot_generations(generation_id), ledger_version text NOT NULL,
  note text NOT NULL DEFAULT '', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS hosted_crypto_execution_capacity (
  execution_id text PRIMARY KEY, broker_asset_id text NOT NULL, total_quantity numeric NOT NULL CHECK(total_quantity>0),
  allocated_quantity numeric NOT NULL DEFAULT 0 CHECK(allocated_quantity>=0 AND allocated_quantity<=total_quantity),
  execution_facts jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS hosted_crypto_match_allocations (
  allocation_id text PRIMARY KEY, operation_id text NOT NULL UNIQUE, coin text NOT NULL,
  plan_id text NOT NULL REFERENCES hosted_crypto_plan_history(plan_id), stage_id text NOT NULL,
  report_id text NOT NULL REFERENCES hosted_crypto_reports(report_id),
  execution_id text NOT NULL REFERENCES hosted_crypto_execution_capacity(execution_id),
  quantity_start numeric NOT NULL CHECK(quantity_start>=0), quantity_end numeric NOT NULL,
  CHECK(quantity_end>quantity_start), UNIQUE(execution_id,quantity_start),
  receipt jsonb NOT NULL, ledger_version text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS hosted_crypto_execution_operations (
  operation_id text PRIMARY KEY, request jsonb NOT NULL, result jsonb NOT NULL
);
-- Exact fractions interpolate a canonical published execution projection, not raw FIFO lots.
CREATE OR REPLACE FUNCTION hosted_fraction(n numeric,d numeric) RETURNS jsonb LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE common numeric;
BEGIN
  IF d=0 OR trunc(n)<>n OR trunc(d)<>d THEN RAISE EXCEPTION 'Invalid rational'; END IF;
  IF d<0 THEN n:=-n; d:=-d; END IF;
  common:=gcd(abs(n),d);
  RETURN jsonb_build_object('numerator',trim_scale(div(n,common))::text,'denominator',trim_scale(div(d,common))::text);
END; $$;
CREATE OR REPLACE FUNCTION hosted_decimal_fraction(value text) RETURNS jsonb LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE amount numeric; denominator numeric;
BEGIN
  IF value IS NULL OR value !~ '^-?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?$' OR length(value)>150 THEN RAISE EXCEPTION 'Invalid decimal'; END IF;
  amount:=value::numeric;
  IF scale(amount)>150 THEN RAISE EXCEPTION 'Decimal precision limit'; END IF;
  denominator:=('1'||repeat('0',scale(amount)))::numeric;
  RETURN hosted_fraction(amount*denominator,denominator);
END; $$;
CREATE OR REPLACE FUNCTION hosted_fraction_op(a jsonb,b jsonb,operation text) RETURNS jsonb LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE an numeric:=(a->>'numerator')::numeric; ad numeric:=(a->>'denominator')::numeric;
  bn numeric:=(b->>'numerator')::numeric; bd numeric:=(b->>'denominator')::numeric;
BEGIN
  CASE operation
    WHEN '+' THEN RETURN hosted_fraction(an*bd+bn*ad,ad*bd);
    WHEN '-' THEN RETURN hosted_fraction(an*bd-bn*ad,ad*bd);
    WHEN '*' THEN RETURN hosted_fraction(an*bn,ad*bd);
    WHEN '/' THEN RETURN hosted_fraction(an*bd,ad*bn);
    ELSE RAISE EXCEPTION 'Invalid rational operation';
  END CASE;
END; $$;
CREATE OR REPLACE FUNCTION hosted_fraction_money(value jsonb) RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE n numeric; d numeric; cents numeric;
BEGIN
  IF value IS NULL THEN RETURN 'Unavailable'; END IF;
  n:=(value->>'numerator')::numeric; d:=(value->>'denominator')::numeric;
  cents:=div(abs(n)*100,d);
  IF 2*mod(abs(n)*100,d)>=d THEN cents:=cents+1; END IF;
  RETURN (CASE WHEN n<0 AND cents>0 THEN '-' ELSE '' END)||trim_scale(div(cents,100))::text||'.'||lpad(trim_scale(mod(cents,100))::text,2,'0');
END; $$;
CREATE OR REPLACE FUNCTION hosted_execution_cost_at(facts jsonb,q numeric) RETURNS jsonb LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE point jsonb; previous jsonb; x numeric; fraction jsonb;
BEGIN
  previous:=jsonb_build_object('quantity','0','cost_eur','0');
  IF q=0 THEN RETURN hosted_fraction(0,1); END IF;
  FOR point IN SELECT value FROM jsonb_array_elements(facts->'cost_breakpoints') LOOP
    x:=(point->>'quantity')::numeric;
    IF x>=q AND x>(previous->>'quantity')::numeric THEN
      fraction:=hosted_fraction_op(hosted_decimal_fraction((q-(previous->>'quantity')::numeric)::text),hosted_decimal_fraction((x-(previous->>'quantity')::numeric)::text),'/');
      RETURN hosted_fraction_op(hosted_decimal_fraction(previous->>'cost_eur'),hosted_fraction_op(
        hosted_fraction_op(hosted_decimal_fraction(point->>'cost_eur'),hosted_decimal_fraction(previous->>'cost_eur'),'-'),fraction,'*'),'+');
    END IF;
    previous:=point;
  END LOOP;
  RAISE EXCEPTION 'Outside canonical execution projection';
END; $$;
CREATE OR REPLACE FUNCTION hosted_actual_execution_receipt(facts jsonb,a numeric,b numeric) RETURNS jsonb LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE ratio jsonb; gross jsonb; fees jsonb; cost jsonb; gain jsonb; residual jsonb; result jsonb;
  previous_quantity numeric:=-1; previous_cost numeric:=-1; point jsonb;
BEGIN
  IF a<0 OR b<=a OR b>(facts->>'quantity')::numeric THEN RAISE EXCEPTION 'Execution allocation range'; END IF;
  ratio:=hosted_fraction_op(hosted_decimal_fraction((b-a)::text),hosted_decimal_fraction(facts->>'quantity'),'/');
  gross:=CASE WHEN facts->>'gross_proceeds_eur' IS NOT NULL THEN hosted_fraction_op(hosted_decimal_fraction(facts->>'gross_proceeds_eur'),ratio,'*') ELSE NULL END;
  IF facts->>'coverage'='verified_complete' AND facts->>'allocation_policy'='canonical40-breakpoints-exact-rational-v1'
     AND facts->>'fees_eur' IS NOT NULL AND facts->>'disposed_cost_eur' IS NOT NULL AND facts->>'realized_gain_eur' IS NOT NULL
     AND jsonb_array_length(facts->'cost_breakpoints') BETWEEN 2 AND 4097 THEN
    FOR point IN SELECT value FROM jsonb_array_elements(facts->'cost_breakpoints') LOOP
      IF (point->>'quantity')::numeric<=previous_quantity OR (point->>'cost_eur')::numeric<previous_cost THEN RAISE EXCEPTION 'Invalid canonical cost projection'; END IF;
      previous_quantity:=(point->>'quantity')::numeric; previous_cost:=(point->>'cost_eur')::numeric;
    END LOOP;
    IF facts->'cost_breakpoints'->0<>jsonb_build_object('quantity','0','cost_eur','0')
       OR previous_quantity<>(facts->>'quantity')::numeric OR previous_cost<>(facts->>'disposed_cost_eur')::numeric THEN RAISE EXCEPTION 'Canonical projection endpoints'; END IF;
    fees:=hosted_fraction_op(hosted_decimal_fraction(facts->>'fees_eur'),ratio,'*');
    cost:=hosted_fraction_op(hosted_execution_cost_at(facts,b),hosted_execution_cost_at(facts,a),'-');
    -- Canonical40's final arithmetic rounding is allocated explicitly, so all receipts
    -- telescope to the original recorded execution gain, not a newly rounded total.
    residual:=hosted_fraction_op(hosted_decimal_fraction(facts->>'realized_gain_eur'),hosted_fraction_op(
      hosted_fraction_op(hosted_decimal_fraction(facts->>'gross_proceeds_eur'),hosted_decimal_fraction(facts->>'fees_eur'),'-'),hosted_decimal_fraction(facts->>'disposed_cost_eur'),'-'),'-');
    residual:=hosted_fraction_op(residual,ratio,'*');
    gain:=hosted_fraction_op(hosted_fraction_op(hosted_fraction_op(gross,fees,'-'),cost,'-'),residual,'+');
  END IF;
  result:=jsonb_build_object('state',CASE WHEN gain IS NULL THEN 'unverified' ELSE 'verified' END,'execution_id',facts->>'execution_id',
    'executed_at',facts->>'executed_at','source_timezone',facts->'source_timezone',
    'quantity',trim_scale(b-a)::text,'range_start',trim_scale(a)::text,'range_end',trim_scale(b)::text,
    'gross_proceeds',gross,'fees',fees,'disposed_cost',cost,'realized_gain',gain,'canonical_rounding_allocation',residual,
    'recorded_execution_gain_eur',facts->>'realized_gain_eur',
    'display',jsonb_build_object('gross_proceeds_eur',hosted_fraction_money(gross),'fees_eur',hosted_fraction_money(fees),
      'disposed_cost_eur',hosted_fraction_money(cost),'realized_gain_eur',hosted_fraction_money(gain)),
    'rounding_note','Displayed EUR amounts are rounded separately to cents and may not add exactly; exact rational receipts preserve recorded execution totals.');
  RETURN result;
END; $$;
REVOKE ALL ON FUNCTION hosted_fraction(numeric,numeric),hosted_decimal_fraction(text),hosted_fraction_op(jsonb,jsonb,text),hosted_fraction_money(jsonb),hosted_execution_cost_at(jsonb,numeric),hosted_actual_execution_receipt(jsonb,numeric,numeric) FROM PUBLIC;
CREATE TABLE IF NOT EXISTS hosted_crypto_execution_state (
  coin text PRIMARY KEY REFERENCES hosted_crypto_plan_state(coin), version bigint NOT NULL DEFAULT 0
);
INSERT INTO hosted_crypto_execution_state(coin) VALUES('BTC-EUR'),('ETH-EUR') ON CONFLICT DO NOTHING;

-- A canonical execution may be republished in another ledger without changing its facts.
CREATE OR REPLACE FUNCTION hosted_execution_facts(facts jsonb) RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
  SELECT facts - ARRAY['ledger_version','ledger_cutoff','financial_settings_version']
$$;
CREATE OR REPLACE FUNCTION hosted_read_crypto_executions(requested_coin text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE plan jsonb; model jsonb; generation text; current_version text; position jsonb;
  reports jsonb; allocations jsonb; executions jsonb; stages jsonb; pending numeric; matched numeric; reconciled boolean; correction boolean;
BEGIN
  IF requested_coin IS NULL OR requested_coin NOT IN ('BTC-EUR','ETH-EUR') THEN RAISE EXCEPTION 'Invalid execution coin'; END IF;
  SELECT h.plan,e.version::text INTO plan,current_version FROM hosted_crypto_plan_state s
    JOIN hosted_crypto_execution_state e USING(coin) LEFT JOIN hosted_crypto_plan_history h ON h.plan_id=s.current_plan_id WHERE s.coin=requested_coin;
  SELECT p.generation_id,g.read_model INTO generation,model FROM hosted_snapshot_pointer p JOIN hosted_snapshot_generations g USING(generation_id) WHERE p.singleton;
  SELECT value INTO position FROM jsonb_array_elements(model->'ledger'->'positions') WHERE value->>'broker_asset_id'=plan->>'asset_id';
  SELECT coalesce(jsonb_agg(to_jsonb(r)||jsonb_build_object('quantity',r.quantity::text,'matched_quantity',trim_scale(coalesce(a.quantity,0))::text,
      'pending_quantity',trim_scale(CASE WHEN r.status='open' THEN r.quantity-coalesce(a.quantity,0) ELSE 0 END)::text) ORDER BY r.created_at,r.report_id),'[]')
    INTO reports FROM hosted_crypto_reports r LEFT JOIN LATERAL
      (SELECT sum(quantity_end-quantity_start) AS quantity FROM hosted_crypto_match_allocations WHERE report_id=r.report_id) a ON true
    WHERE r.coin=requested_coin;
  SELECT coalesce(jsonb_agg(to_jsonb(a)||jsonb_build_object('quantity',trim_scale(quantity_end-quantity_start)::text,
      'quantity_start',trim_scale(quantity_start)::text,'quantity_end',trim_scale(quantity_end)::text) ORDER BY created_at,allocation_id),'[]')
    INTO allocations FROM hosted_crypto_match_allocations a WHERE a.coin=requested_coin;
  SELECT coalesce(jsonb_object_agg(s->>'stage_id',jsonb_build_object('pending_quantity',trim_scale(coalesce(p.quantity,0))::text,'matched_quantity',trim_scale(coalesce(m.quantity,0))::text)),'{}')
    INTO stages FROM jsonb_array_elements(plan->'stages') s
    LEFT JOIN LATERAL (SELECT sum((r->>'pending_quantity')::numeric) AS quantity FROM jsonb_array_elements(reports) r WHERE r->>'stage_id'=s->>'stage_id' AND r->>'plan_id'=plan->>'plan_id') p ON true
    LEFT JOIN LATERAL (SELECT sum((a->>'quantity')::numeric) AS quantity FROM jsonb_array_elements(allocations) a WHERE a->>'stage_id'=s->>'stage_id' AND a->>'plan_id'=plan->>'plan_id') m ON true;
  SELECT coalesce(sum((value->>'pending_quantity')::numeric),0) INTO pending FROM jsonb_each(stages);
  SELECT coalesce(sum((value->>'matched_quantity')::numeric),0) INTO matched FROM jsonb_each(stages);
  SELECT coalesce(jsonb_agg(d||jsonb_build_object('available_quantity',trim_scale(greatest(0,(d->>'quantity')::numeric-coalesce(c.allocated_quantity,0)))::text,
      'eligible',plan IS NOT NULL AND d->>'asset_kind'='Cryptocurrency' AND d->>'broker_asset_id'=plan->>'asset_id'
        AND (d->>'executed_at')::timestamptz>=(plan->>'accepted_at')::timestamptz
        AND (c.execution_id IS NULL OR hosted_execution_facts(c.execution_facts)=hosted_execution_facts(d))
        AND coalesce(c.allocated_quantity,0)<(d->>'quantity')::numeric) ORDER BY d->>'executed_at',d->>'execution_id'),'[]')
    INTO executions FROM jsonb_array_elements(coalesce(model->'ledger'->'disposals','[]')) d
      LEFT JOIN hosted_crypto_execution_capacity c ON c.execution_id=d->>'execution_id'
    WHERE d->>'symbol'=requested_coin AND d->>'asset_kind'='Cryptocurrency';
  correction:=EXISTS(SELECT FROM hosted_crypto_execution_capacity c WHERE c.allocated_quantity>0
      AND EXISTS(SELECT FROM hosted_crypto_match_allocations a WHERE a.execution_id=c.execution_id AND a.coin=requested_coin AND a.plan_id=plan->>'plan_id')
      AND NOT EXISTS(SELECT FROM jsonb_array_elements(coalesce(model->'ledger'->'disposals','[]')) d WHERE d->>'execution_id'=c.execution_id AND hosted_execution_facts(d)=hosted_execution_facts(c.execution_facts)));
  reconciled:=NOT correction AND plan IS NOT NULL AND position IS NOT NULL
    AND (position->>'quantity')::numeric>=(plan->>'held_quantity_at_acceptance')::numeric-matched
    AND (position->>'quantity')::numeric-pending>=(plan->>'core_quantity')::numeric
    AND NOT EXISTS(SELECT FROM jsonb_array_elements(executions) d WHERE d->>'broker_asset_id'=plan->>'asset_id'
      AND ((d->>'executed_at') IS NULL OR ((d->>'executed_at')::timestamptz>=(plan->>'accepted_at')::timestamptz AND (d->>'available_quantity')::numeric>0)))
    ;
  RETURN jsonb_build_object('state','ready','coin',requested_coin,'version',current_version,'generation_id',generation,'plan',plan,
    'reports',reports,'allocations',allocations,'executions',executions,
    'progress',jsonb_build_object('pending_quantity',trim_scale(pending)::text,'matched_quantity',trim_scale(matched)::text,'stages',stages,
      'reconciliation_required',correction,'reconciliation_reason',CASE WHEN correction THEN 'execution_facts_changed_review' ELSE NULL END,
      'reconciled_ledger_version',CASE WHEN reconciled THEN model->>'ledger_version' ELSE NULL END));
END; $$;

CREATE OR REPLACE FUNCTION hosted_record_crypto_execution(requested jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE prior hosted_crypto_execution_operations; context jsonb; model jsonb; plan jsonb; stage jsonb; progress jsonb;
  report hosted_crypto_reports; capacity hosted_crypto_execution_capacity; facts jsonb; receipt jsonb;
  quantity numeric; allocated numeric; matched numeric; pending numeric; chosen_report_id text; response jsonb; reason text;
BEGIN
  IF NOT requested ?& ARRAY['coin','operation_id','action','quantity','expected_version','generation_id','plan_id','stage_id']
    OR requested->>'coin' NOT IN ('BTC-EUR','ETH-EUR') OR requested->>'action' NOT IN ('report','match')
    OR requested->>'operation_id' !~ '^[A-Za-z0-9_-]{8,100}$'
    OR requested->>'quantity' !~ '^[0-9]{1,18}(\.[0-9]{1,18})?$' OR (requested->>'quantity')::numeric<=0
    OR requested->>'expected_version' !~ '^[0-9]{1,18}$'
    OR EXISTS(SELECT FROM jsonb_each(requested) WHERE value='null') THEN RAISE EXCEPTION 'Invalid execution operation'; END IF;
  quantity:=(requested->>'quantity')::numeric;
  PERFORM pg_advisory_xact_lock(hashtextextended(requested->>'operation_id',58));
  SELECT * INTO prior FROM hosted_crypto_execution_operations WHERE operation_id=requested->>'operation_id';
  IF FOUND THEN
    IF prior.request=requested THEN RETURN prior.result; END IF;
    RETURN jsonb_build_object('state','conflict','reason','operation_id_reused');
  END IF;
  -- Pointer, plan and per-coin execution state are locked in a fixed order.
  SELECT g.read_model INTO model FROM hosted_snapshot_pointer p JOIN hosted_snapshot_generations g USING(generation_id) WHERE p.singleton FOR SHARE OF p;
  PERFORM 1 FROM hosted_crypto_plan_state WHERE coin=requested->>'coin' FOR SHARE;
  PERFORM 1 FROM hosted_crypto_execution_state WHERE coin=requested->>'coin' FOR UPDATE;
  context:=hosted_read_crypto_executions(requested->>'coin'); plan:=context->'plan'; progress:=context->'progress';
  SELECT value INTO stage FROM jsonb_array_elements(plan->'stages') WHERE value->>'stage_id'=requested->>'stage_id';
  IF context->>'generation_id' IS DISTINCT FROM requested->>'generation_id' OR context->>'version' IS DISTINCT FROM requested->>'expected_version'
     OR plan->>'plan_id' IS DISTINCT FROM requested->>'plan_id' THEN reason:='snapshot_or_plan_changed';
  ELSIF stage IS NULL OR plan->>'state'<>'accepted' THEN reason:='plan_reconciliation_required';
  END IF;
  IF reason IS NULL THEN
    matched:=coalesce((progress->'stages'->(requested->>'stage_id')->>'matched_quantity')::numeric,0);
    pending:=coalesce((progress->'stages'->(requested->>'stage_id')->>'pending_quantity')::numeric,0);
    IF requested ? 'report_id' THEN
      SELECT * INTO report FROM hosted_crypto_reports WHERE hosted_crypto_reports.report_id=requested->>'report_id' AND coin=requested->>'coin' AND plan_id=plan->>'plan_id' AND stage_id=requested->>'stage_id' FOR UPDATE;
      IF NOT FOUND OR report.status<>'open' THEN reason:='report_not_found';
      ELSE
        SELECT coalesce(sum(quantity_end-quantity_start),0) INTO allocated FROM hosted_crypto_match_allocations WHERE hosted_crypto_match_allocations.report_id=report.report_id;
        IF quantity>report.quantity-allocated THEN reason:='report_quantity_exceeded'; END IF;
      END IF;
    ELSIF quantity+matched+pending>(stage->>'quantity')::numeric THEN reason:='stage_quantity_exceeded';
    END IF;
  END IF;
  IF reason IS NULL AND requested->>'action'='match' THEN
    SELECT value INTO facts FROM jsonb_array_elements(coalesce(model->'ledger'->'disposals','[]')) WHERE value->>'execution_id'=requested->>'execution_id'
      AND value->>'broker_asset_id'=plan->>'asset_id' AND value->>'symbol'=requested->>'coin' AND value->>'asset_kind'='Cryptocurrency';
    IF facts IS NULL THEN reason:='execution_not_found';
    ELSIF facts->>'executed_at' IS NULL OR (facts->>'executed_at')::timestamptz<(plan->>'accepted_at')::timestamptz THEN reason:='execution_before_plan';
    ELSE
      INSERT INTO hosted_crypto_execution_capacity(execution_id,broker_asset_id,total_quantity,execution_facts)
        VALUES(facts->>'execution_id',plan->>'asset_id',(facts->>'quantity')::numeric,facts) ON CONFLICT DO NOTHING;
      SELECT * INTO capacity FROM hosted_crypto_execution_capacity WHERE execution_id=facts->>'execution_id' FOR UPDATE;
      IF hosted_execution_facts(capacity.execution_facts)<>hosted_execution_facts(facts) THEN reason:='execution_facts_changed_review';
      ELSIF capacity.allocated_quantity+quantity>capacity.total_quantity THEN reason:='execution_capacity_exhausted'; END IF;
    END IF;
  ELSIF reason IS NULL THEN
    -- A pending report reserves currently held tactical units. A match consumes an
    -- already imported sale and must not subtract that sale from holdings twice.
    IF NOT coalesce((SELECT (value->>'quantity')::numeric FROM jsonb_array_elements(model->'ledger'->'positions') WHERE value->>'broker_asset_id'=plan->>'asset_id' AND value->>'symbol'=requested->>'coin' AND value->>'asset_kind'='Cryptocurrency')
      - (progress->>'pending_quantity')::numeric - quantity >= (plan->>'core_quantity')::numeric,false)
      THEN reason:='pending_quantity_exceeds_available_core'; END IF;
  END IF;
  IF reason IS NOT NULL THEN response:=jsonb_build_object('state','conflict','reason',reason);
  ELSE
    chosen_report_id:=coalesce(requested->>'report_id','report-'||(requested->>'operation_id'));
    IF NOT requested ? 'report_id' THEN
      INSERT INTO hosted_crypto_reports(report_id,coin,plan_id,stage_id,quantity,generation_id,ledger_version,note)
        VALUES(chosen_report_id,requested->>'coin',plan->>'plan_id',requested->>'stage_id',quantity,context->>'generation_id',model->>'ledger_version',coalesce(requested->>'note',''));
    END IF;
    IF requested->>'action'='match' THEN
      receipt:=hosted_actual_execution_receipt(facts,capacity.allocated_quantity,capacity.allocated_quantity+quantity);
      INSERT INTO hosted_crypto_match_allocations(allocation_id,operation_id,coin,plan_id,stage_id,report_id,execution_id,quantity_start,quantity_end,receipt,ledger_version)
        VALUES('allocation-'||(requested->>'operation_id'),requested->>'operation_id',requested->>'coin',plan->>'plan_id',requested->>'stage_id',chosen_report_id,facts->>'execution_id',capacity.allocated_quantity,capacity.allocated_quantity+quantity,receipt,model->>'ledger_version');
      UPDATE hosted_crypto_execution_capacity SET allocated_quantity=allocated_quantity+quantity WHERE execution_id=facts->>'execution_id';
      UPDATE hosted_crypto_reports r SET status='resolved' WHERE r.report_id=chosen_report_id AND r.quantity=(SELECT sum(quantity_end-quantity_start) FROM hosted_crypto_match_allocations a WHERE a.report_id=r.report_id);
    END IF;
    UPDATE hosted_crypto_execution_state SET version=version+1 WHERE coin=requested->>'coin';
    response:=jsonb_build_object('state',CASE WHEN requested->>'action'='match' THEN 'matched' ELSE 'reported' END,'report_id',chosen_report_id,'receipt',receipt);
  END IF;
  INSERT INTO hosted_crypto_execution_operations VALUES(requested->>'operation_id',requested,response);
  RETURN response;
END; $$;
REVOKE ALL ON FUNCTION hosted_execution_facts(jsonb),hosted_read_crypto_executions(text),hosted_record_crypto_execution(jsonb) FROM PUBLIC;
COMMIT;
