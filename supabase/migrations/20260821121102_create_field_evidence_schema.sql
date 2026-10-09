-- ALAGBARA / HIMMA Commercial Expansion — Field Evidence layer
-- Layer sequence: Market Intelligence → Field Evidence → Case Management → Economic Traceability → ALAGBARA

create table public.cases (
  id uuid primary key default gen_random_uuid(),
  case_code text not null unique,              -- e.g. 'CASE-001'
  name text not null,                            -- e.g. 'SHIELD CORPORATION'
  country text not null default 'BENIN',
  status text not null default 'ouvert' check (status in ('ouvert','en_cours','clos')),
  description text,
  opened_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.market_field_observations (
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

create index idx_market_field_observations_case_id on public.market_field_observations(case_id);

-- Enable RLS
alter table public.cases enable row level security;
alter table public.market_field_observations enable row level security;

-- Anon can INSERT field observations (the public-facing form uses the anon/publishable key)
create policy "anon can insert field observations"
  on public.market_field_observations
  for insert
  to anon
  with check (true);

-- Anon can SELECT cases (needed so the form can look up / display the case, but not modify it)
create policy "anon can read cases"
  on public.cases
  for select
  to anon
  using (true);

-- Seed first case
insert into public.cases (case_code, name, country, status, description)
values ('CASE-001', 'SHIELD CORPORATION', 'BENIN', 'ouvert', 'Premier cas ALAGBARA — Commercial Expansion Layer');
