create table public.alagbara_cases (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  signal text not null,
  pulse text,

  facts jsonb not null default '[]'::jsonb,
  unknowns jsonb not null default '[]'::jsonb,
  assumptions jsonb not null default '[]'::jsonb,
  analysis text,
  recommendation text,
  next_action text,
  risks jsonb not null default '[]'::jsonb,
  confidence text check (confidence in ('low','medium','high')),

  human_decision jsonb,
  execution jsonb,
  result jsonb,
  lesson text
);

comment on table public.alagbara_cases is 'ALAGBARA Decision Loop Domain 0 — one row per case, from signal through lesson. Canonical atomic object; never deleted, only appended to as it moves through its lifecycle.';

alter table public.alagbara_cases enable row level security;

-- Mirrors the existing project convention (narrow, per-action anon policies)
-- rather than a single ALL policy. No delete policy: cases are a permanent
-- audit trail by design, not a cosmetic feature.
create policy "anon can read alagbara cases"
  on public.alagbara_cases for select
  using (true);

create policy "anon can insert alagbara cases"
  on public.alagbara_cases for insert
  with check (true);

create policy "anon can update alagbara cases"
  on public.alagbara_cases for update
  using (true)
  with check (true);

create or replace function public.set_alagbara_case_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger alagbara_cases_set_updated_at
  before update on public.alagbara_cases
  for each row execute function public.set_alagbara_case_updated_at();
