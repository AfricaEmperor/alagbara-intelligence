create or replace function public.get_recent_big_intelligence_memory(p_limit integer default 5)
returns table (
  question text,
  market text,
  decision text,
  useful text,
  pulse text,
  analysis text,
  recommendation text,
  outcome text,
  created_at timestamptz
)
language sql
security definer
set search_path = public
as $$
  select r.question, r.market, r.decision, r.useful, r.pulse, r.analysis, r.recommendation, r.outcome, r.created_at
  from public.big_intelligence_requests r
  order by r.created_at desc
  limit least(greatest(coalesce(p_limit, 5), 1), 20);
$$;
revoke all on function public.get_recent_big_intelligence_memory(integer) from public;
grant execute on function public.get_recent_big_intelligence_memory(integer) to anon, authenticated;
