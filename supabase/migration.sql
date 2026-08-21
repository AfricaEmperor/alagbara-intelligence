-- ALAGBARA / HIMMA Commercial Expansion — Field Evidence layer
-- Layer sequence: Market Intelligence → Field Evidence → Case Management → Economic Traceability → ALAGBARA
-- Strictly separate from himma-foods-crm — do not run against it.

create table if not exists public.cases (
  id uuid primary key default gen_random_uuid(),
  case_code text not null unique,
  name text not null,
  country text not null default 'BENIN',
  status text not null default 'ouvert' check (status in ('ouvert','en_cours','clos')),
  description text,
  opened_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.market_field_observations (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete restrict,
  outlet_name text not null,
  outlet_type text not null default 'Pharmacie',
  city text not null default 'Cotonou',
  district text,
  respondent_role text,
  observed_at timestamptz not null default now(),
  demand jsonb not null default '{}'::jsonb,
  brands text[] not null default '{}',
  prices jsonb not null default '[]'::jsonb,
  customer_criteria text[] not null default '{}',
  supply_channels text[] not null default '{}',
  market_potential text,
  priority_products text[] not null default '{}',
  observations text,
  created_at timestamptz not null default now()
);

create index if not exists idx_market_field_observations_case_id
  on public.market_field_observations(case_id);

alter table public.cases enable row level security;
alter table public.market_field_observations enable row level security;

drop policy if exists "anon can insert field observations" on public.market_field_observations;
create policy "anon can insert field observations"
  on public.market_field_observations
  for insert to anon with check (true);

drop policy if exists "anon can read cases" on public.cases;
create policy "anon can read cases"
  on public.cases
  for select to anon using (true);

insert into public.cases (case_code, name, country, status, description)
values ('CASE-001', 'SHIELD CORPORATION', 'BENIN', 'ouvert', 'Premier cas ALAGBARA — Commercial Expansion Layer')
on conflict (case_code) do nothing;
