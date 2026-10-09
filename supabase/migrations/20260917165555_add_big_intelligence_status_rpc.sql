create or replace function public.update_big_intelligence_request_status(p_id uuid, p_nonce text, p_status text)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_status not in ('received','scouting','pulsed','analyzing','response_ready','engagement_proposed','engaged','completed') then
    raise exception 'invalid intelligence status';
  end if;
  update public.big_intelligence_requests
  set status = p_status
  where id = p_id
    and metadata->>'internal_nonce' = p_nonce;
  return found;
end;
$$;
revoke all on function public.update_big_intelligence_request_status(uuid,text,text) from public;
grant execute on function public.update_big_intelligence_request_status(uuid,text,text) to anon, authenticated;
