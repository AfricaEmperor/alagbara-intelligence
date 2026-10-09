-- Ownership column. No default — the backend must always set this
-- explicitly from a server-verified identity, never implicitly.
alter table public.alagbara_cases
  add column user_id uuid not null references auth.users(id);

-- Drop the old permissive anon-key policies. This is the actual
-- constitutional change: from "anyone with the key" to "only the owner".
drop policy "anon can read alagbara cases" on public.alagbara_cases;
drop policy "anon can insert alagbara cases" on public.alagbara_cases;
drop policy "anon can update alagbara cases" on public.alagbara_cases;

-- auth.uid() is resolved by Postgres from the caller's verified JWT claims
-- (set by PostgREST when the request carries that user's access token) —
-- it is NOT something a client can spoof by sending a field. This is the
-- actual enforcement layer; the backend's own JWT verification is the
-- second, independent layer in front of it.
create policy "users can read their own cases"
  on public.alagbara_cases for select
  using (auth.uid() = user_id);

create policy "users can insert their own cases"
  on public.alagbara_cases for insert
  with check (auth.uid() = user_id);

create policy "users can update their own cases"
  on public.alagbara_cases for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Still no delete policy. Ownership doesn't grant erasure — the audit
-- trail is permanent regardless of who's asking.
