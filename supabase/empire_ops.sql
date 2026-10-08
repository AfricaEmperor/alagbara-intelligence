-- EmpireOps primitive on the canonical ALAGBARA intelligence case.
alter table public.big_intelligence_requests
  add column if not exists empire_ops_loop_id uuid,
  add column if not exists empire_ops_status text,
  add column if not exists empire_ops_state jsonb not null default '{}'::jsonb,
  add column if not exists empire_ops_events jsonb not null default '[]'::jsonb;

create index if not exists idx_big_intelligence_requests_empire_ops_loop_id
  on public.big_intelligence_requests(empire_ops_loop_id);
