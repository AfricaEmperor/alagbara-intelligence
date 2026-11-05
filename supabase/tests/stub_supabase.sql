-- Minimal stand-in for the Supabase pieces the radar migration depends on, for a DISPOSABLE local PostgreSQL only.
-- Role attributes and auth.* definitions mirror what was read (read-only) from a live project on 2026-11-05:
--   postgres: NOT superuser, BYPASSRLS | service_role: BYPASSRLS | anon, authenticated: no BYPASSRLS.
-- The real server is PostgreSQL 17 with the full Auth schema; fidelity beyond this is UNVERIFIED.
do $$
declare r record;
begin
  for r in select * from (values ('anon', false), ('authenticated', false), ('service_role', true), ('postgres_sim', true)) v(name, bypass) loop
    if not exists (select 1 from pg_roles where rolname = r.name) then execute format('create role %I nologin', r.name); end if;
    execute format('alter role %I %s', r.name, case when r.bypass then 'bypassrls' else 'nobypassrls' end);
  end loop;
  alter role postgres_sim createrole;                                   -- plays Supabase's `postgres`
end $$;

create schema auth;
create table auth.users (
  id uuid primary key, email varchar, email_confirmed_at timestamptz,
  raw_app_meta_data jsonb not null default '{}'::jsonb, raw_user_meta_data jsonb not null default '{}'::jsonb,
  banned_until timestamptz, deleted_at timestamptz, is_anonymous boolean not null default false);
create function auth.uid() returns uuid language sql stable as $$
  select coalesce(nullif(current_setting('request.jwt.claim.sub', true), ''),
                  (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub'))::uuid $$;
create function auth.jwt() returns jsonb language sql stable as $$
  select coalesce(nullif(current_setting('request.jwt.claim', true), ''), nullif(current_setting('request.jwt.claims', true), ''))::jsonb $$;
create function auth.role() returns text language sql stable as $$
  select coalesce(nullif(current_setting('request.jwt.claim.role', true), ''), (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role'))::text $$;

grant usage on schema auth to postgres_sim, anon, authenticated, service_role;
grant execute on all functions in schema auth to anon, authenticated, service_role, postgres_sim;
grant select, insert, update, delete on auth.users to postgres_sim;   -- real: postgres has arwdDxtm on auth tables
-- real: authenticated/anon have NO privileges on auth.users (not granted here)

grant usage on schema public to anon, authenticated, service_role, postgres_sim;
grant create on schema public to postgres_sim;
-- real: default privileges in `public` auto-grant ALL to the API roles (verified). Reproduced to show radar is unaffected.
alter default privileges for role postgres_sim in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges for role postgres_sim in schema public grant execute on functions to anon, authenticated, service_role;
