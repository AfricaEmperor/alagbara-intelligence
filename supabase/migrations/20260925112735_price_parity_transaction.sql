create or replace function public.record_price_parity_pulse(
  p_case_id uuid,p_evidence jsonb,p_claims jsonb,p_pulse jsonb,p_event jsonb)
returns public.alagbara_cases language plpgsql security invoker set search_path=public as $$
declare updated_case public.alagbara_cases;
begin
  if not exists(select 1 from public.alagbara_cases where id=p_case_id) then raise exception 'case not found'; end if;
  insert into public.alagbara_claims(id,case_id,type,text,evidence_ids,status,derived_by,created_at)
  select (item->>'id')::uuid,p_case_id,item->>'type',item->>'text',
    coalesce(array(select (value::text)::uuid from jsonb_array_elements_text(coalesce(item->'evidence_ids','[]'::jsonb)) as value),'{}'::uuid[]),
    item->>'status',coalesce(item->>'derived_by','ANA'),coalesce((item->>'created_at')::timestamptz,now())
  from jsonb_array_elements(coalesce(p_claims,'[]'::jsonb)) item;
  update public.alagbara_cases set
    evidence=coalesce(evidence,'[]'::jsonb)||coalesce(p_evidence,'[]'::jsonb),
    claims=coalesce(claims,'[]'::jsonb)||coalesce(p_claims,'[]'::jsonb),
    events=coalesce(events,'[]'::jsonb)||jsonb_build_array(p_event),
    price_parity=p_pulse,
    state=jsonb_set(coalesce(state,'{}'::jsonb),'{price_parity}',p_pulse,true)
  where id=p_case_id returning * into updated_case;
  return updated_case;
end $$;
