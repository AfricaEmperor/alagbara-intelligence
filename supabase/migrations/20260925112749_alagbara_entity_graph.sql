create table if not exists public.alagbara_entities (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  type text not null,
  name text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, type, name)
);

create table if not exists public.alagbara_relationships (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  case_id uuid references public.alagbara_cases(id) on delete set null,
  from_entity_id uuid not null references public.alagbara_entities(id) on delete cascade,
  to_entity_id uuid not null references public.alagbara_entities(id) on delete cascade,
  type text not null,
  valid_from timestamptz,
  valid_to timestamptz,
  evidence_ids uuid[] not null default '{}',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  check (from_entity_id <> to_entity_id)
);

create index if not exists alagbara_entities_user_type_idx
  on public.alagbara_entities(user_id, type);
create index if not exists alagbara_relationships_user_idx
  on public.alagbara_relationships(user_id, created_at desc);
create index if not exists alagbara_relationships_from_idx
  on public.alagbara_relationships(from_entity_id);
create index if not exists alagbara_relationships_to_idx
  on public.alagbara_relationships(to_entity_id);
create index if not exists alagbara_relationships_case_idx
  on public.alagbara_relationships(case_id);

alter table public.alagbara_entities enable row level security;
alter table public.alagbara_relationships enable row level security;

do $$ begin
  create policy "users can read own graph entities" on public.alagbara_entities
    for select to authenticated using ((select auth.uid()) = user_id);
exception when duplicate_object then null; end $$;
do $$ begin
  create policy "users can insert own graph entities" on public.alagbara_entities
    for insert to authenticated with check ((select auth.uid()) = user_id);
exception when duplicate_object then null; end $$;
do $$ begin
  create policy "users can update own graph entities" on public.alagbara_entities
    for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);
exception when duplicate_object then null; end $$;

do $$ begin
  create policy "users can read own graph relationships" on public.alagbara_relationships
    for select to authenticated using ((select auth.uid()) = user_id);
exception when duplicate_object then null; end $$;
do $$ begin
  create policy "users can insert own graph relationships" on public.alagbara_relationships
    for insert to authenticated with check ((select auth.uid()) = user_id);
exception when duplicate_object then null; end $$;

create or replace function public.alagbara_case_graph(p_case_id uuid)
returns jsonb
language sql
security invoker
set search_path=public
as $$
  select jsonb_build_object(
    'entities', coalesce((
      select jsonb_agg(jsonb_build_object(
        'id', e.id, 'type', e.type, 'name', e.name, 'metadata', e.metadata
      ) order by e.name)
      from public.alagbara_entities e
      where e.user_id = (select auth.uid())
        and exists (
          select 1 from public.alagbara_relationships r
          where r.case_id = p_case_id
            and r.user_id = (select auth.uid())
            and (r.from_entity_id=e.id or r.to_entity_id=e.id)
        )
    ), '[]'::jsonb),
    'relationships', coalesce((
      select jsonb_agg(jsonb_build_object(
        'id', r.id,
        'from_entity_id', r.from_entity_id,
        'to_entity_id', r.to_entity_id,
        'type', r.type,
        'evidence_ids', r.evidence_ids,
        'metadata', r.metadata
      ) order by r.created_at)
      from public.alagbara_relationships r
      where r.case_id = p_case_id
        and r.user_id = (select auth.uid())
    ), '[]'::jsonb)
  );
$$;
