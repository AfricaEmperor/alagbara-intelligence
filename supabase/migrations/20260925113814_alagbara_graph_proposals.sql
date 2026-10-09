create table if not exists public.alagbara_graph_proposals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  case_id uuid not null references public.alagbara_cases(id) on delete cascade,
  proposal_type text not null check (proposal_type in ('ENTITY','RELATIONSHIP','BATCH')),
  payload jsonb not null default '{}'::jsonb,
  evidence_ids uuid[] not null default '{}',
  proposed_by text not null default 'ANA',
  status text not null default 'PROPOSED' check (status in ('PROPOSED','ACCEPTED','REJECTED','NEEDS_EVIDENCE')),
  validation jsonb not null default '{}'::jsonb,
  decided_by uuid references auth.users(id),
  decided_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists alagbara_graph_proposals_case_idx on public.alagbara_graph_proposals(user_id, case_id, created_at desc);
create index if not exists alagbara_graph_proposals_status_idx on public.alagbara_graph_proposals(user_id, status);

alter table public.alagbara_graph_proposals enable row level security;

drop policy if exists "Users can read own graph proposals" on public.alagbara_graph_proposals;
create policy "Users can read own graph proposals"
on public.alagbara_graph_proposals for select to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert own graph proposals" on public.alagbara_graph_proposals;
create policy "Users can insert own graph proposals"
on public.alagbara_graph_proposals for insert to authenticated
with check (
  (select auth.uid()) = user_id
  and exists (
    select 1 from public.alagbara_cases c
    where c.id = case_id and c.user_id = (select auth.uid())
  )
);

drop policy if exists "Users can update own graph proposals" on public.alagbara_graph_proposals;
create policy "Users can update own graph proposals"
on public.alagbara_graph_proposals for update to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create or replace function public.alagbara_accept_graph_proposal(p_proposal_id uuid)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  p public.alagbara_graph_proposals%rowtype;
  c public.alagbara_cases%rowtype;
  item jsonb;
  entity_item jsonb;
  rel_item jsonb;
  from_id uuid;
  to_id uuid;
  entity_id uuid;
  entity_key text;
  valid_count integer;
  missing_count integer;
  result jsonb;
begin
  select * into p
  from public.alagbara_graph_proposals
  where id = p_proposal_id and user_id = (select auth.uid())
  for update;

  if not found then raise exception 'graph proposal not found'; end if;
  if p.status <> 'PROPOSED' then raise exception 'proposal is not PROPOSED'; end if;

  select * into c
  from public.alagbara_cases
  where id = p.case_id and user_id = (select auth.uid());

  if not found then raise exception 'case not found'; end if;

  select count(*) into valid_count
  from unnest(p.evidence_ids) eid
  where exists (
    select 1
    from jsonb_array_elements(coalesce(c.evidence, '[]'::jsonb)) e
    where (e->>'id')::uuid = eid
  );

  missing_count := cardinality(p.evidence_ids) - valid_count;

  if missing_count > 0 then
    update public.alagbara_graph_proposals
    set status = 'NEEDS_EVIDENCE',
        validation = jsonb_build_object('valid_evidence_count', valid_count, 'missing_evidence_count', missing_count),
        decided_by = (select auth.uid()),
        decided_at = now()
    where id = p.id;
    return jsonb_build_object('status','NEEDS_EVIDENCE','proposal_id',p.id,'valid_evidence_count',valid_count,'missing_evidence_count',missing_count);
  end if;

  if p.proposal_type in ('ENTITY','BATCH') then
    for entity_item in select * from jsonb_array_elements(coalesce(p.payload->'entities','[]'::jsonb)) loop
      insert into public.alagbara_entities(user_id,type,name,metadata,updated_at)
      values (
        (select auth.uid()),
        upper(trim(entity_item->>'type')),
        trim(entity_item->>'name'),
        coalesce(entity_item->'metadata','{}'::jsonb),
        now()
      )
      on conflict (user_id,type,name) do update set metadata = public.alagbara_entities.metadata || excluded.metadata, updated_at = now()
      returning id into entity_id;
    end loop;
  end if;

  if p.proposal_type in ('RELATIONSHIP','BATCH') then
    for rel_item in select * from jsonb_array_elements(coalesce(p.payload->'relationships','[]'::jsonb)) loop
      select id into from_id from public.alagbara_entities
      where user_id = (select auth.uid())
        and type = upper(trim(rel_item->>'from_type'))
        and name = trim(rel_item->>'from_name');

      select id into to_id from public.alagbara_entities
      where user_id = (select auth.uid())
        and type = upper(trim(rel_item->>'to_type'))
        and name = trim(rel_item->>'to_name');

      if from_id is null or to_id is null then
        raise exception 'relationship references missing canonical entity';
      end if;

      insert into public.alagbara_relationships(
        user_id,case_id,from_entity_id,to_entity_id,type,valid_from,valid_to,evidence_ids,metadata
      )
      values (
        (select auth.uid()),p.case_id,from_id,to_id,
        upper(trim(rel_item->>'type')),
        nullif(rel_item->>'valid_from','')::timestamptz,
        nullif(rel_item->>'valid_to','')::timestamptz,
        p.evidence_ids,
        coalesce(rel_item->'metadata','{}'::jsonb)
      );
    end loop;
  end if;

  update public.alagbara_graph_proposals
  set status='ACCEPTED',
      validation=jsonb_build_object('evidence_count', cardinality(p.evidence_ids), 'canonicalized_at', now()),
      decided_by=(select auth.uid()),
      decided_at=now()
  where id=p.id;

  select public.alagbara_case_graph(p.case_id) into result;
  return jsonb_build_object('status','ACCEPTED','proposal_id',p.id,'graph',result);
end;
$$;

revoke all on function public.alagbara_accept_graph_proposal(uuid) from public;
grant execute on function public.alagbara_accept_graph_proposal(uuid) to authenticated;
