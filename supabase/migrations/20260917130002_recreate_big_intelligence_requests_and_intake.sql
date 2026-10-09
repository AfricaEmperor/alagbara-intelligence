create table if not exists public.big_intelligence_requests (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  status text not null default 'received' check (status in ('received','scouting','pulsed','analyzing','response_ready','engagement_proposed','engaged','completed')),
  question text not null check (char_length(trim(question)) between 1 and 4000),
  market text,
  decision text,
  useful text,
  contact text,
  source text not null default 'big-consulting-ui',
  pulse text,
  facts jsonb,
  unknowns jsonb,
  assumptions jsonb,
  analysis text,
  recommendation text,
  risks jsonb,
  confidence text,
  engagement_status text not null default 'unqualified' check (engagement_status in ('unqualified','qualified','proposed','accepted','declined','completed')),
  outcome text,
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists big_intelligence_requests_created_at_idx on public.big_intelligence_requests (created_at desc);
create index if not exists big_intelligence_requests_status_idx on public.big_intelligence_requests (status);
alter table public.big_intelligence_requests enable row level security;
revoke all on public.big_intelligence_requests from anon, authenticated;

create or replace function public.create_big_intelligence_request(
  p_question text,
  p_market text default null,
  p_decision text default null,
  p_useful text default null,
  p_source text default 'big-consulting-ui'
) returns jsonb language plpgsql security definer set search_path = public as $$
declare v_id uuid; v_nonce text := gen_random_uuid()::text;
begin
  if p_question is null or char_length(trim(p_question)) < 1 or char_length(trim(p_question)) > 4000 then raise exception 'question must be between 1 and 4000 characters'; end if;
  insert into public.big_intelligence_requests(question,market,decision,useful,source,metadata)
  values(trim(p_question),nullif(trim(p_market),''),nullif(trim(p_decision),''),nullif(trim(p_useful),''),coalesce(nullif(trim(p_source),''),'big-consulting-ui'),jsonb_build_object('internal_nonce',v_nonce))
  returning id into v_id;
  return jsonb_build_object('id',v_id,'internal_nonce',v_nonce);
end; $$;

create or replace function public.complete_big_intelligence_request(
  p_id uuid, p_nonce text, p_status text, p_pulse text, p_facts jsonb, p_unknowns jsonb, p_assumptions jsonb,
  p_analysis text, p_recommendation text, p_risks jsonb, p_confidence text, p_outcome text default null
) returns boolean language plpgsql security definer set search_path = public as $$
declare v_updated integer;
begin
  update public.big_intelligence_requests set status=p_status,pulse=p_pulse,facts=p_facts,unknowns=p_unknowns,assumptions=p_assumptions,
    analysis=p_analysis,recommendation=p_recommendation,risks=p_risks,confidence=p_confidence,outcome=p_outcome,
    metadata=coalesce(metadata,'{}'::jsonb)-'internal_nonce'
  where id=p_id and metadata->>'internal_nonce'=p_nonce;
  get diagnostics v_updated=row_count;
  return v_updated=1;
end; $$;
grant execute on function public.create_big_intelligence_request(text,text,text,text,text) to anon, authenticated;
grant execute on function public.complete_big_intelligence_request(uuid,text,text,text,jsonb,jsonb,jsonb,text,text,jsonb,text,text) to anon, authenticated;
