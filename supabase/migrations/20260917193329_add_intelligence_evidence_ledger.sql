create table if not exists public.big_intelligence_evidence (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null references public.big_intelligence_requests(id) on delete cascade,
  source_url text not null,
  source_title text,
  source_domain text,
  source_type text,
  published_at timestamptz,
  observed_at timestamptz not null default now(),
  claim text not null,
  excerpt text,
  reliability text not null default 'unrated',
  evidence_status text not null default 'observed',
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists idx_big_intelligence_evidence_request on public.big_intelligence_evidence(request_id, observed_at desc);
alter table public.big_intelligence_evidence enable row level security;
revoke all on public.big_intelligence_evidence from anon, authenticated;

create or replace function public.record_big_intelligence_evidence(
  p_id uuid,
  p_nonce text,
  p_evidence jsonb
) returns integer
language plpgsql security definer set search_path = public
as $$
declare
  inserted_count integer := 0;
  item jsonb;
  source_url_value text;
  claim_value text;
begin
  if not exists (select 1 from public.big_intelligence_requests where id = p_id and metadata->>'internal_nonce' = p_nonce) then
    raise exception 'invalid request authorization';
  end if;
  if jsonb_typeof(p_evidence) <> 'array' then raise exception 'evidence must be an array'; end if;
  for item in select value from jsonb_array_elements(p_evidence) loop
    source_url_value := nullif(trim(item->>'source_url'), '');
    claim_value := nullif(trim(item->>'claim'), '');
    if source_url_value is null or claim_value is null then continue; end if;
    insert into public.big_intelligence_evidence(request_id, source_url, source_title, source_domain, source_type, published_at, claim, excerpt, reliability, evidence_status, metadata)
    values (
      p_id,
      source_url_value,
      nullif(item->>'source_title',''),
      nullif(item->>'source_domain',''),
      coalesce(nullif(item->>'source_type',''),'web'),
      case when nullif(item->>'published_at','') is null then null else (item->>'published_at')::timestamptz end,
      claim_value,
      nullif(item->>'excerpt',''),
      coalesce(nullif(item->>'reliability',''),'unrated'),
      coalesce(nullif(item->>'evidence_status',''),'observed'),
      coalesce(item->'metadata','{}'::jsonb)
    );
    inserted_count := inserted_count + 1;
  end loop;
  return inserted_count;
end;
$$;
revoke all on function public.record_big_intelligence_evidence(uuid,text,jsonb) from public, anon, authenticated;
grant execute on function public.record_big_intelligence_evidence(uuid,text,jsonb) to anon, authenticated;
