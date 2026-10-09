alter table public.alagbara_cases
  add column if not exists evidence jsonb not null default '[]'::jsonb,
  add column if not exists state jsonb not null default '{}'::jsonb,
  add column if not exists provenance jsonb not null default '{}'::jsonb,
  add column if not exists events jsonb not null default '[]'::jsonb,
  add column if not exists claims jsonb not null default '[]'::jsonb;

create index if not exists alagbara_cases_events_gin on public.alagbara_cases using gin (events);
create index if not exists alagbara_cases_evidence_gin on public.alagbara_cases using gin (evidence);

create table if not exists public.alagbara_claims (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.alagbara_cases(id) on delete cascade,
  type text not null check (type in ('FACT','ASSUMPTION','HYPOTHESIS','ANOMALY','RECOMMENDATION','OTHER')),
  text text not null,
  evidence_ids uuid[] not null default '{}',
  status text not null check (status in ('MODEL_DERIVED','PROPOSED','VERIFIED','REJECTED')),
  derived_by text not null default 'ANA',
  created_at timestamptz not null default now()
);
create index if not exists alagbara_claims_case_idx on public.alagbara_claims(case_id, created_at desc);
alter table public.alagbara_claims enable row level security;
do $$ begin
  create policy "users can read own claims" on public.alagbara_claims for select using (exists (select 1 from public.alagbara_cases c where c.id=case_id and c.user_id=auth.uid()));
exception when duplicate_object then null; end $$;
do $$ begin
  create policy "users can insert own claims" on public.alagbara_claims for insert with check (exists (select 1 from public.alagbara_cases c where c.id=case_id and c.user_id=auth.uid()));
exception when duplicate_object then null; end $$;
