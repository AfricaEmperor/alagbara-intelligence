-- PROPOSED SECURITY BOUNDARY — review-only until approved.
-- Apply only after the migration baseline is reconciled and this SQL is reviewed.
-- This migration is forward-only; it does not reset or rewrite production history.

begin;

-- Privileged request lifecycle RPCs are server-only. The server must use
-- SUPABASE_SERVICE_ROLE_KEY; that key must never be exposed to browser code.
revoke all on table public.big_intelligence_requests from anon, authenticated;
revoke all on table public.big_intelligence_evidence from anon, authenticated;
grant all on table public.big_intelligence_requests to service_role;
grant all on table public.big_intelligence_evidence to service_role;

create or replace function public.create_big_intelligence_request(
  p_question text,
  p_market text default null,
  p_decision text default null,
  p_useful text default null,
  p_source text default 'big-consulting-ui'
)
returns jsonb
language plpgsql
security definer
set search_path to ''
as $function$
declare
  v_id uuid;
  v_nonce text := gen_random_uuid()::text;
begin
  if p_question is null or char_length(trim(p_question)) < 1 or char_length(trim(p_question)) > 4000 then
    raise exception 'question must be between 1 and 4000 characters';
  end if;

  insert into public.big_intelligence_requests(question, market, decision, useful, source, metadata)
  values (
    trim(p_question),
    nullif(trim(p_market), ''),
    nullif(trim(p_decision), ''),
    nullif(trim(p_useful), ''),
    coalesce(nullif(trim(p_source), ''), 'big-consulting-ui'),
    jsonb_build_object('internal_nonce', v_nonce)
  )
  returning id into v_id;

  return jsonb_build_object('id', v_id, 'internal_nonce', v_nonce);
end;
$function$;

create or replace function public.update_big_intelligence_request_status(
  p_id uuid, p_nonce text, p_status text
)
returns boolean
language plpgsql
security definer
set search_path to ''
as $function$
begin
  if p_status not in ('received','scouting','pulsed','analyzing','response_ready','engagement_proposed','engaged','completed') then
    raise exception 'invalid intelligence status';
  end if;

  update public.big_intelligence_requests
  set status = p_status
  where id = p_id and metadata->>'internal_nonce' = p_nonce;
  return found;
end;
$function$;

create or replace function public.record_big_intelligence_evidence(
  p_id uuid, p_nonce text, p_evidence jsonb
)
returns integer
language plpgsql
security definer
set search_path to ''
as $function$
declare
  inserted_count integer := 0;
  item jsonb;
  source_url_value text;
  claim_value text;
begin
  if not exists (
    select 1 from public.big_intelligence_requests
    where id = p_id and metadata->>'internal_nonce' = p_nonce
  ) then
    raise exception 'invalid request authorization';
  end if;
  if jsonb_typeof(p_evidence) <> 'array' then raise exception 'evidence must be an array'; end if;

  for item in select value from jsonb_array_elements(p_evidence) loop
    source_url_value := nullif(trim(item->>'source_url'), '');
    claim_value := nullif(trim(item->>'claim'), '');
    if source_url_value is null or claim_value is null then continue; end if;

    insert into public.big_intelligence_evidence(
      request_id, source_url, source_title, source_domain, source_type,
      published_at, claim, excerpt, reliability, evidence_status, metadata
    ) values (
      p_id, source_url_value, nullif(item->>'source_title',''),
      nullif(item->>'source_domain',''), coalesce(nullif(item->>'source_type',''),'web'),
      case when nullif(item->>'published_at','') is null then null else (item->>'published_at')::timestamptz end,
      claim_value, nullif(item->>'excerpt',''), coalesce(nullif(item->>'reliability',''),'unrated'),
      coalesce(nullif(item->>'evidence_status',''),'observed'), coalesce(item->'metadata','{}'::jsonb)
    );
    inserted_count := inserted_count + 1;
  end loop;
  return inserted_count;
end;
$function$;

create or replace function public.complete_big_intelligence_request(
  p_id uuid, p_nonce text, p_status text, p_pulse text, p_facts jsonb,
  p_unknowns jsonb, p_assumptions jsonb, p_analysis text, p_recommendation text,
  p_risks jsonb, p_confidence text, p_outcome text default null
)
returns boolean
language plpgsql
security definer
set search_path to ''
as $function$
declare
  v_updated integer;
begin
  update public.big_intelligence_requests
  set status=p_status, pulse=p_pulse, facts=p_facts, unknowns=p_unknowns,
      assumptions=p_assumptions, analysis=p_analysis, recommendation=p_recommendation,
      risks=p_risks, confidence=p_confidence, outcome=p_outcome
  where id=p_id and metadata->>'internal_nonce'=p_nonce;
  get diagnostics v_updated = row_count;
  return v_updated = 1;
end;
$function$;

-- The unscoped cross-request memory function is disabled until an owner/tenant
-- boundary is implemented. It is deliberately not granted to service_role.
revoke all on function public.get_recent_big_intelligence_memory(integer) from public, anon, authenticated, service_role;

create or replace function public.read_big_intelligence_empire_ops(p_id uuid, p_token text)
returns jsonb
language plpgsql
security definer
set search_path to ''
as $function$
declare
  v_row jsonb;
begin
  select jsonb_build_object(
    'id',r.id,'question',r.question,'pulse',r.pulse,'facts',r.facts,
    'unknowns',r.unknowns,'recommendation',r.recommendation,
    'empire_ops_loop_id',r.empire_ops_loop_id,'empire_ops_status',r.empire_ops_status,
    'empire_ops_state',r.empire_ops_state,'empire_ops_events',r.empire_ops_events
  )
  into v_row
  from public.big_intelligence_requests r
  where r.id=p_id and r.empire_ops_token=p_token;
  if v_row is null then raise exception 'case not found or invalid EmpireOps token'; end if;
  return v_row;
end;
$function$;

create or replace function public.write_big_intelligence_empire_ops(
  p_id uuid, p_token text, p_loop_id uuid, p_status text, p_state jsonb, p_events jsonb
)
returns boolean
language plpgsql
security definer
set search_path to ''
as $function$
begin
  if p_token is null or length(trim(p_token)) < 32 then
    raise exception 'a server-generated EmpireOps token is required';
  end if;

  update public.big_intelligence_requests
  set empire_ops_token = coalesce(empire_ops_token, p_token),
      empire_ops_loop_id = p_loop_id,
      empire_ops_status = p_status,
      empire_ops_state = p_state,
      empire_ops_events = p_events
  where id = p_id
    and (empire_ops_token = p_token or empire_ops_token is null);
  return found;
end;
$function$;

-- Remove client-callable execution from every privileged RPC. Only server-side
-- service-role clients may invoke these; request-specific nonces remain internal.
revoke all on function public.create_big_intelligence_request(text,text,text,text,text) from public, anon, authenticated;
revoke all on function public.update_big_intelligence_request_status(uuid,text,text) from public, anon, authenticated;
revoke all on function public.record_big_intelligence_evidence(uuid,text,jsonb) from public, anon, authenticated;
revoke all on function public.complete_big_intelligence_request(uuid,text,text,text,jsonb,jsonb,jsonb,text,text,jsonb,text,text) from public, anon, authenticated;
revoke all on function public.read_big_intelligence_empire_ops(uuid,text) from public, anon, authenticated;
revoke all on function public.write_big_intelligence_empire_ops(uuid,text,uuid,text,jsonb,jsonb) from public, anon, authenticated;

grant execute on function public.create_big_intelligence_request(text,text,text,text,text) to service_role;
grant execute on function public.update_big_intelligence_request_status(uuid,text,text) to service_role;
grant execute on function public.record_big_intelligence_evidence(uuid,text,jsonb) to service_role;
grant execute on function public.complete_big_intelligence_request(uuid,text,text,text,jsonb,jsonb,jsonb,text,text,jsonb,text,text) to service_role;
grant execute on function public.read_big_intelligence_empire_ops(uuid,text) to service_role;
grant execute on function public.write_big_intelligence_empire_ops(uuid,text,uuid,text,jsonb,jsonb) to service_role;

commit;
