do $$ begin alter publication supabase_realtime add table public.alagbara_cases; exception when duplicate_object then null; end $$;
