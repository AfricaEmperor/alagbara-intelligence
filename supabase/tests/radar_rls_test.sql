-- AP-001 radar migration: grants / RLS / function behavior tests. Runs against a disposable local PostgreSQL.
-- Executed as a superuser; individual cases switch role with SET ROLE and set JWT claims, like PostgREST does.
\set ON_ERROR_STOP off
\pset pager off
create schema t;
create table t.results (n serial, grp text, name text, expected text, actual text, pass boolean generated always as (expected = actual) stored);
grant usage on schema t to public;
create function t.rec(g text, n text, e text, a text) returns void language sql security definer as
  $$ insert into t.results(grp, name, expected, actual) values (g, n, e, a) $$;
grant execute on function t.rec(text, text, text, text) to public;
create function t.try(q text) returns text language plpgsql as
  $$ begin execute q; return 'ok'; exception when others then return 'err:' || sqlstate; end $$;
create function t.rows(q text) returns text language plpgsql as
  $$ declare n bigint; begin execute 'select count(*) from (' || q || ') x' into n; return 'rows:' || n;
     exception when others then return 'err:' || sqlstate; end $$;
create function t.val(q text) returns text language plpgsql as
  $$ declare r text; begin execute q into r; return coalesce(r, 'null'); exception when others then return 'err:' || sqlstate; end $$;
create function t.as(uid text, r text) returns void language plpgsql as $$
  begin
    perform set_config('request.jwt.claims', case when uid is null then '' else json_build_object('sub', uid, 'role', r)::text end, false);
    perform set_config('request.jwt.claim.sub', '', false);
    execute 'set role ' || quote_ident(r);
  end $$;
grant execute on function t.try(text), t.rows(text), t.val(text), t.as(text, text) to public;
\o /dev/null

-- ---------------------------------------------------------------------------------------------- identities (fictional)
\set rev   '11111111-1111-1111-1111-111111111111'
\set rev2  '11111111-1111-1111-1111-222222222222'
\set adm   '22222222-2222-2222-2222-222222222222'
\set plain '33333333-3333-3333-3333-333333333333'
\set spoof '44444444-4444-4444-4444-444444444444'
\set unc   '55555555-5555-5555-5555-555555555555'
\set ban   '66666666-6666-6666-6666-666666666666'
\set del   '77777777-7777-7777-7777-777777777777'
\set badr  '88888888-8888-8888-8888-888888888888'
insert into auth.users (id, email, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, banned_until, deleted_at) values
 (:'rev',  'rev@example.test',   now(), '{"radar_role":"reviewer"}', '{}', null, null),
 (:'rev2', 'rev2@example.test',  now(), '{"radar_role":"reviewer"}', '{}', null, null),
 (:'adm',  'adm@example.test',   now(), '{"radar_role":"admin"}', '{}', null, null),
 (:'plain','plain@example.test', now(), '{}', '{}', null, null),
 (:'spoof','spoof@example.test', now(), '{}', '{"radar_role":"reviewer"}', null, null),
 (:'unc',  'unc@example.test',   null,  '{"radar_role":"reviewer"}', '{}', null, null),
 (:'ban',  'ban@example.test',   now(), '{"radar_role":"reviewer"}', '{}', now() + interval '1 day', null),
 (:'del',  'del@example.test',   now(), '{"radar_role":"reviewer"}', '{}', null, now()),
 (:'badr', 'badr@example.test',  now(), '{"radar_role":"superuser"}', '{}', null, null);

-- ---------------------------------------------------------------------------------------------- seed via the worker role
select t.as(null, 'service_role');
select t.rec('seed', 'upsert event A (create)', 'ok', t.try($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_a','title','A','timezone','Africa/Porto-Novo','review_status','pending','evidence_references',jsonb_build_array('obs_a')), null) $q$));
select t.rec('seed', 'upsert event B (create)', 'ok', t.try($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_b','title','B','timezone','Africa/Porto-Novo','review_status','pending','evidence_references',jsonb_build_array('obs_b')), null) $q$));
select t.rec('seed', 'upsert event C (create)', 'ok', t.try($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_c','title','C','timezone','Africa/Porto-Novo','review_status','pending','evidence_references',jsonb_build_array('obs_c')), null) $q$));
select t.rec('seed', 'insert evidence (service_role)', 'ok', t.try($q$ insert into radar.evidence(observation_id, content_hash, doc) values (repeat('a',64), repeat('b',64), jsonb_build_object('observation_id', repeat('a',64), 'content_hash', repeat('b',64))) $q$));
select t.rec('seed', 'insert venue (service_role)', 'ok', t.try($q$ insert into radar.venues(venue_id, doc) values ('ven_x', '{"venue_id":"ven_x","city":"Cotonou"}') $q$));
select t.rec('seed', 'link observation (service_role)', 'ok', t.try($q$ insert into radar.obs_event values (repeat('a',64), 'evt_a') $q$));
reset role;

-- ================================================================================================ A. anon: nothing
select t.as(null, 'anon');
select t.rec('anon', 'SELECT radar.' || c.relname, 'err:42501', t.rows('select * from radar.' || c.relname))
  from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'radar' and c.relkind = 'r' order by c.relname;
select t.rec('anon', 'INSERT/UPDATE/DELETE/TRUNCATE events', 'err:42501|err:42501|err:42501|err:42501',
  t.try($q$ insert into radar.events(event_id, doc) values ('x','{}') $q$) || '|' || t.try($q$ update radar.events set version = 99 $q$) || '|' || t.try($q$ delete from radar.events $q$) || '|' || t.try($q$ truncate radar.events $q$));
select t.rec('anon', 'EXECUTE review_event', 'err:42501', t.try($q$ select radar.review_event('dec-00000001-aaaa','evt_a','approve',1,'') $q$));
select t.rec('anon', 'EXECUTE public.radar_review_event', 'err:42501', t.try($q$ select public.radar_review_event('dec-00000001-aaaa','evt_a','approve',1,'') $q$));
select t.rec('anon', 'EXECUTE upsert_event / backfill_event', 'err:42501|err:42501',
  t.try($q$ select radar.upsert_event('{}'::jsonb, null) $q$) || '|' || t.try($q$ select radar.backfill_event('{}'::jsonb, 1) $q$));
select t.rec('anon', 'EXECUTE is_reviewer', 'err:42501', t.try($q$ select radar.is_reviewer() $q$));
reset role;

-- ================================================================================================ B. authenticated, NOT reviewers
\set people '(:''plain''), (:''spoof''), (:''unc''), (:''ban''), (:''del''), (:''badr'')'
select t.as(:'plain', 'authenticated');
select t.rec('non-reviewer(no role)', 'SELECT events/evidence/venues/parties/obs_event/decisions', 'rows:0|rows:0|rows:0|rows:0|rows:0|rows:0',
  t.rows('select * from radar.events') || '|' || t.rows('select * from radar.evidence') || '|' || t.rows('select * from radar.venues') || '|' || t.rows('select * from radar.parties') || '|' || t.rows('select * from radar.obs_event') || '|' || t.rows('select * from radar.decisions'));
select t.rec('non-reviewer(no role)', 'review_event -> not a reviewer', 'err:42501', t.try($q$ select radar.review_event('dec-00000002-bbbb','evt_a','approve',1,'') $q$));
select t.rec('non-reviewer(no role)', 'public wrapper -> not a reviewer', 'err:42501', t.try($q$ select public.radar_review_event('dec-00000002-bbbb','evt_a','approve',1,'') $q$));
select t.rec('non-reviewer(no role)', 'direct writes denied', 'err:42501|err:42501|err:42501',
  t.try($q$ insert into radar.events(event_id, doc) values ('x','{}') $q$) || '|' || t.try($q$ update radar.events set version = 9 $q$) || '|' || t.try($q$ delete from radar.decisions $q$));
select t.rec('non-reviewer(no role)', 'cannot read auth.users', 'err:42501', t.rows('select * from auth.users'));
select t.rec('non-reviewer(no role)', 'is_reviewer() = false', 'false', t.val('select radar.is_reviewer()::text'));
reset role;
select t.as(:'spoof', 'authenticated');
select t.rec('non-reviewer(role only in user_metadata)', 'SELECT events', 'rows:0', t.rows('select * from radar.events'));
select t.rec('non-reviewer(role only in user_metadata)', 'review_event', 'err:42501', t.try($q$ select radar.review_event('dec-00000003-cccc','evt_a','approve',1,'') $q$));
reset role;
select t.as(:'unc', 'authenticated');
select t.rec('non-reviewer(email unconfirmed)', 'SELECT events / review_event', 'rows:0|err:42501', t.rows('select * from radar.events') || '|' || t.try($q$ select radar.review_event('dec-00000004-dddd','evt_a','approve',1,'') $q$));
reset role;
select t.as(:'ban', 'authenticated');
select t.rec('non-reviewer(banned)', 'SELECT events / review_event', 'rows:0|err:42501', t.rows('select * from radar.events') || '|' || t.try($q$ select radar.review_event('dec-00000005-eeee','evt_a','approve',1,'') $q$));
reset role;
select t.as(:'del', 'authenticated');
select t.rec('non-reviewer(deleted)', 'SELECT events / review_event', 'rows:0|err:42501', t.rows('select * from radar.events') || '|' || t.try($q$ select radar.review_event('dec-00000006-ffff','evt_a','approve',1,'') $q$));
reset role;
select t.as(:'badr', 'authenticated');
select t.rec('non-reviewer(unknown role value)', 'SELECT events / review_event', 'rows:0|err:42501', t.rows('select * from radar.events') || '|' || t.try($q$ select radar.review_event('dec-00000007-gggg','evt_a','approve',1,'') $q$));
reset role;
select t.as(null, 'authenticated');
select t.rec('authenticated, no subject', 'review_event -> not authenticated', 'err:28000', t.try($q$ select radar.review_event('dec-00000008-hhhh','evt_a','approve',1,'') $q$));
select t.rec('authenticated, no subject', 'SELECT events', 'rows:0', t.rows('select * from radar.events'));
reset role;

-- ================================================================================================ C. reviewer: read-only
select t.as(:'rev', 'authenticated');
select t.rec('reviewer', 'SELECT events (3 seeded)', 'rows:3', t.rows('select * from radar.events'));
select t.rec('reviewer', 'SELECT evidence/venues/obs_event', 'rows:1|rows:1|rows:1', t.rows('select * from radar.evidence') || '|' || t.rows('select * from radar.venues') || '|' || t.rows('select * from radar.obs_event'));
select t.rec('reviewer', 'audit is admin-only (reviewer sees none)', 'rows:0', t.rows('select * from radar.audit'));
select t.rec('reviewer', 'failures / rejections admin-only', 'rows:0|rows:0', t.rows('select * from radar.failures') || '|' || t.rows('select * from radar.decision_rejections'));
select t.rec('reviewer', 'direct INSERT/UPDATE/DELETE/TRUNCATE on events denied', 'err:42501|err:42501|err:42501|err:42501',
  t.try($q$ insert into radar.events(event_id, doc) values ('x','{}') $q$) || '|' || t.try($q$ update radar.events set doc = '{}' $q$) || '|' || t.try($q$ delete from radar.events $q$) || '|' || t.try($q$ truncate radar.events $q$));
select t.rec('reviewer', 'direct writes to decisions/audit/evidence denied', 'err:42501|err:42501|err:42501',
  t.try($q$ insert into radar.decisions values ('dec-hack-00001','evt_a','approve','x',null,1,2,'approved','human',now()) $q$) || '|' || t.try($q$ insert into radar.audit(actor,action) values ('x','y') $q$) || '|' || t.try($q$ update radar.evidence set doc = '{}' $q$));
select t.rec('reviewer', 'cannot call ingestion / backfill functions', 'err:42501|err:42501',
  t.try($q$ select radar.upsert_event('{}'::jsonb, null) $q$) || '|' || t.try($q$ select radar.backfill_event('{}'::jsonb, 1) $q$));
select t.rec('reviewer', 'is_reviewer() = true, is_admin() = false', 'true|false', t.val('select radar.is_reviewer()::text') || '|' || t.val('select radar.is_admin()::text'));
reset role;
select t.as(:'adm', 'authenticated');
select t.rec('admin', 'audit visible to admin', 'rows:3', t.rows('select * from radar.audit'));   -- 3 event_created rows so far
select t.rec('admin', 'is_admin() = true', 'true', t.val('select radar.is_admin()::text'));
reset role;

-- ================================================================================================ D. review_event behavior
select t.as(:'rev', 'authenticated');
select t.rec('review', 'approve with the right version', 'applied|2|approved',
  t.val($q$ select (radar.review_event('dec-0000a001-aaaa','evt_a','approve',1,'checked poster'))->>'status' $q$) || '|' ||
  t.val($q$ select version::text from radar.events where event_id='evt_a' $q$) || '|' || t.val($q$ select review_status from radar.events where event_id='evt_a' $q$));
select t.rec('review', 'column status == JSON status', 'approved|approved', t.val($q$ select review_status from radar.events where event_id='evt_a' $q$) || '|' || t.val($q$ select doc->>'review_status' from radar.events where event_id='evt_a' $q$));
select t.rec('review', 'replay with an OLD version is a no-op (duplicate)', 'duplicate|2',
  t.val($q$ select (radar.review_event('dec-0000a001-aaaa','evt_a','approve',1,'checked poster'))->>'status' $q$) || '|' || t.val($q$ select version::text from radar.events where event_id='evt_a' $q$));
select t.rec('review', 'replay x3 adds no decision row', 'rows:1', t.rows($q$ select * from radar.decisions where event_id='evt_a' $q$));
select t.rec('review', 'decision_id reused with a different decision', 'err:23505', t.try($q$ select radar.review_event('dec-0000a001-aaaa','evt_a','reject',1,'') $q$));
select t.rec('review', 'decision_id reused for a different event', 'err:23505', t.try($q$ select radar.review_event('dec-0000a001-aaaa','evt_b','approve',1,'') $q$));
select t.rec('review', 'stale version rejected, nothing changes', 'err:40001|2|approved',
  t.try($q$ select radar.review_event('dec-0000a002-bbbb','evt_a','reject',1,'') $q$) || '|' || t.val($q$ select version::text from radar.events where event_id='evt_a' $q$) || '|' || t.val($q$ select review_status from radar.events where event_id='evt_a' $q$));
select t.rec('review', 'unknown event', 'err:P0002', t.try($q$ select radar.review_event('dec-0000a003-cccc','evt_ghost','approve',1,'') $q$));
select t.rec('review', 'invalid decision / id / version / note', 'err:22023|err:22023|err:22023|err:22023',
  t.try($q$ select radar.review_event('dec-0000a004-dddd','evt_b','publish',1,'') $q$) || '|' || t.try($q$ select radar.review_event('short','evt_b','approve',1,'') $q$) ||
  '|' || t.try($q$ select radar.review_event('dec-0000a005-eeee','evt_b','approve',0,'') $q$) || '|' || t.try($q$ select radar.review_event('dec-0000a006-ffff','evt_b','approve',1,repeat('x',501)) $q$));
select t.rec('review', 'public wrapper works and is idempotent', 'applied|duplicate',
  t.val($q$ select (public.radar_review_event('dec-0000b001-aaaa','evt_b','request_correction',1,''))->>'status' $q$) || '|' || t.val($q$ select (public.radar_review_event('dec-0000b001-aaaa','evt_b','request_correction',1,''))->>'status' $q$));
select t.rec('review', 'only the intended event changed (C untouched)', 'pending|1', t.val($q$ select review_status from radar.events where event_id='evt_c' $q$) || '|' || t.val($q$ select version::text from radar.events where event_id='evt_c' $q$));
reset role;
select t.as(:'rev2', 'authenticated');
select t.rec('review', 'second reviewer reusing first reviewer''s decision_id -> rejected', 'err:23505', t.try($q$ select radar.review_event('dec-0000a001-aaaa','evt_a','approve',1,'checked poster') $q$));
select t.rec('review', 'second reviewer decides C', 'applied', t.val($q$ select (radar.review_event('dec-0000c001-aaaa','evt_c','reject',1,'dup'))->>'status' $q$));
reset role;

-- --- guard: exactly one intended row must update before any audit row exists
create function t.skip_update() returns trigger language plpgsql as $$ begin return null; end $$;
create trigger t_skip before update on radar.events for each row execute function t.skip_update();
select t.as(:'rev', 'authenticated');
select t.rec('integrity', 'zero rows updated -> XX001, no decision/audit rows', 'err:XX001|rows:0',
  t.try($q$ select radar.review_event('dec-0000d001-aaaa','evt_b','approve',2,'') $q$) || '|' || t.rows($q$ select * from radar.decisions where decision_id='dec-0000d001-aaaa' $q$));
reset role;
select t.rec('integrity', '...and no audit row for it', 'rows:0', t.rows($q$ select * from radar.audit where detail->>'decision_id'='dec-0000d001-aaaa' $q$));
drop trigger t_skip on radar.events;

-- --- atomicity: if the audit insert fails, the event update and decision insert roll back too
alter table radar.audit add constraint t_block check (action <> 'review:approve') not valid;
select t.as(:'rev', 'authenticated');
select t.rec('integrity', 'audit failure rolls back event + decision (one transaction)', 'err:23514|2|correction_requested|rows:0',
  t.try($q$ select radar.review_event('dec-0000d002-bbbb','evt_b','approve',2,'') $q$) || '|' || t.val($q$ select version::text from radar.events where event_id='evt_b' $q$) || '|' || t.val($q$ select review_status from radar.events where event_id='evt_b' $q$) || '|' || t.rows($q$ select * from radar.decisions where decision_id='dec-0000d002-bbbb' $q$));
reset role;
alter table radar.audit drop constraint t_block;

-- --- search_path hardening
select t.rec('hardening', 'every SECURITY DEFINER function pins search_path = ''''', '0',
  (select count(*)::text from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where p.prosecdef and n.nspname in ('radar','public') and (p.proname like 'radar%' or n.nspname = 'radar')
      and not exists (select 1 from unnest(p.proconfig) c where c = 'search_path=""')));
create schema attacker; create table attacker.events (event_id text, doc jsonb, version int); grant usage on schema attacker to public; grant all on attacker.events to public;
insert into attacker.events values ('evt_b', '{}', 2);
create function attacker.now() returns timestamptz language sql as $$ select '1999-01-01'::timestamptz $$; grant execute on function attacker.now() to public;
select t.as(:'rev', 'authenticated');
set search_path = attacker, public;
select t.rec('hardening', 'hostile search_path cannot redirect the definer functions (decoy table untouched)', 'applied|0|0',
  t.val($q$ select (radar.review_event('dec-0000e001-aaaa','evt_b','approve',2,''))->>'status' $q$) || '|' ||
  t.val($q$ select count(*)::text from attacker.events where doc <> '{}'::jsonb $q$) || '|' ||
  t.val($q$ select count(*)::text from radar.audit where at < '2000-01-01' $q$));
reset role; reset search_path;

-- ================================================================================================ F. ingestion (service_role)
select t.as(null, 'service_role');
select t.rec('ingest', 'create pending event', '1', t.val($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_i','title','I','timezone','Africa/Porto-Novo','review_status','pending','evidence_references',jsonb_build_array('obs_i')), null)::text $q$));
select t.rec('ingest', 'creating an existing event again -> unique violation', 'err:23505', t.try($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_i','title','I','timezone','Africa/Porto-Novo','review_status','pending','evidence_references',jsonb_build_array('obs_i')), null) $q$));
select t.rec('ingest', 'new events must be pending', 'err:22023', t.try($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_j','timezone','Africa/Porto-Novo','review_status','approved','evidence_references',jsonb_build_array('o')), null) $q$));
select t.rec('ingest', 'update with the right version bumps it', '2', t.val($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_i','title','I2','timezone','Africa/Porto-Novo','review_status','pending','evidence_references',jsonb_build_array('obs_i','obs_i2')), 1)::text $q$));
select t.rec('ingest', 'stale update rejected', 'err:40001', t.try($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_i','title','I3','timezone','Africa/Porto-Novo','review_status','pending','evidence_references',jsonb_build_array('o')), 1) $q$));
select t.rec('ingest', 'ingestion cannot approve; row unchanged', 'err:42501|2|pending',
  t.try($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_i','title','I','timezone','Africa/Porto-Novo','review_status','approved','evidence_references',jsonb_build_array('o')), 2) $q$) || '|' || t.val($q$ select version::text from radar.events where event_id='evt_i' $q$) || '|' || t.val($q$ select review_status from radar.events where event_id='evt_i' $q$));
select t.rec('ingest', 'reopen WITHOUT a reason is refused (evt_c is rejected)', 'err:42501',
  t.try($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_c','title','C','timezone','Africa/Porto-Novo','review_status','pending','evidence_references',jsonb_build_array('o')), 2) $q$));
select t.rec('ingest', 'reopen of an approved event WITH a reason', '3|pending', t.val($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_a','title','A','timezone','Africa/Porto-Novo','review_status','pending','evidence_references',jsonb_build_array('obs_a','obs_a2')), 2, 'new observation introduced a contradiction')::text $q$) || '|' || t.val($q$ select review_status from radar.events where event_id='evt_a' $q$));
select t.rec('ingest', 'reopen recorded as system decision + audit row; human approval kept', 'approve:human|reopen:system|rows:1',
  (select string_agg(decision || ':' || kind, '|' order by version_after) from radar.decisions where event_id = 'evt_a') || '|' || t.rows($q$ select * from radar.audit where subject='evt_a' and action='review_reopened' $q$));
select t.rec('ingest', 'contract checks: wrong timezone / empty evidence', 'err:23514|err:23514',
  t.try($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_i','timezone','UTC','review_status','pending','evidence_references',jsonb_build_array('o')), 2) $q$) || '|' || t.try($q$ select radar.upsert_event(jsonb_build_object('event_id','evt_i','timezone','Africa/Porto-Novo','review_status','pending','evidence_references','[]'::jsonb), 2) $q$));
select t.rec('ingest', 'service_role cannot UPDATE/DELETE events or touch history directly', 'err:42501|err:42501|err:42501|err:42501|err:42501',
  t.try($q$ update radar.events set version = 99 $q$) || '|' || t.try($q$ delete from radar.events $q$) || '|' || t.try($q$ update radar.decisions set note = 'x' $q$) || '|' || t.try($q$ delete from radar.audit $q$) || '|' || t.try($q$ truncate radar.events $q$));
select t.rec('ingest', 'evidence: duplicate observation / mismatched doc / update', 'err:23505|err:23514|err:42501',
  t.try($q$ insert into radar.evidence(observation_id, content_hash, doc) values (repeat('a',64), repeat('b',64), jsonb_build_object('observation_id', repeat('a',64), 'content_hash', repeat('b',64))) $q$) || '|' ||
  t.try($q$ insert into radar.evidence(observation_id, content_hash, doc) values (repeat('c',64), repeat('d',64), '{"observation_id":"x","content_hash":"y"}') $q$) || '|' || t.try($q$ update radar.evidence set doc = '{}' $q$));
select t.rec('backfill', 'insert-if-absent preserves doc and version', 'inserted|5',
  t.val($q$ select radar.backfill_event(jsonb_build_object('event_id','evt_bf','timezone','Africa/Porto-Novo','review_status','approved','evidence_references',jsonb_build_array('o')), 5) $q$) || '|' || t.val($q$ select version::text from radar.events where event_id='evt_bf' $q$));
select t.rec('backfill', 'same row again is a no-op', 'unchanged',
  t.val($q$ select radar.backfill_event(jsonb_build_object('event_id','evt_bf','timezone','Africa/Porto-Novo','review_status','approved','evidence_references',jsonb_build_array('o')), 5) $q$));
select t.rec('backfill', 'a DIFFERENT row for the same id is a conflict, never overwritten', 'err:23505|5',
  t.try($q$ select radar.backfill_event(jsonb_build_object('event_id','evt_bf','timezone','Africa/Porto-Novo','review_status','pending','evidence_references',jsonb_build_array('o')), 6) $q$) || '|' || t.val($q$ select version::text from radar.events where event_id='evt_bf' $q$));
reset role;

-- ================================================================================================ G. owner-level guarantees
set role postgres_sim;
select t.rec('immutability', 'even the owner cannot UPDATE/DELETE history', 'err:42501|err:42501|err:42501|err:42501',
  t.try($q$ update radar.decisions set note = 'tamper' $q$) || '|' || t.try($q$ delete from radar.audit $q$) || '|' || t.try($q$ update radar.evidence set doc = '{}' $q$) || '|' || t.try($q$ delete from radar.obs_event $q$));
select t.rec('immutability', 'even the owner cannot TRUNCATE: plain (refused by FK) / CASCADE (refused by trigger) / history tables', 'err:0A000|err:42501|err:42501|err:42501',
  t.try($q$ truncate radar.events $q$) || '|' || t.try($q$ truncate radar.events cascade $q$) || '|' || t.try($q$ truncate radar.decisions $q$) || '|' || t.try($q$ truncate radar.audit $q$));
select t.rec('immutability', 'review_status cannot be written independently of the JSON document', 'err:428C9',
  t.try($q$ update radar.events set review_status = 'approved' where event_id = 'evt_i' $q$));
reset role;

-- ================================================================================================ H. consistency invariants
select t.rec('consistency', 'column review_status == JSON review_status for every event', 'rows:0', t.rows($q$ select 1 from radar.events where review_status is distinct from doc->>'review_status' $q$));
select t.rec('consistency', 'last decision of each event matches its status', 'rows:0', t.rows($q$
  select 1 from radar.events e where exists (select 1 from radar.decisions d where d.event_id = e.event_id)
    and e.review_status <> (select d.resulting_status from radar.decisions d where d.event_id = e.event_id order by d.version_after desc limit 1) $q$));
select t.rec('consistency', 'exactly one audit row per human decision', 'rows:0', t.rows($q$
  select 1 from (select event_id, count(*) n from radar.decisions where kind = 'human' group by 1) d
  left join (select subject, count(*) n from radar.audit where action like 'review:%' group by 1) a on a.subject = d.event_id
  where coalesce(a.n, 0) <> d.n $q$));
select t.rec('consistency', 'version == 1 + human decisions + ingest updates (a reopen is one ingest update)', 'rows:0', t.rows($q$
  select 1 from radar.events e where e.event_id in ('evt_a','evt_b','evt_c')
    and e.version <> 1 + (select count(*) from radar.decisions d where d.event_id = e.event_id and d.kind = 'human')
                       + (select count(*) from radar.audit a where a.subject = e.event_id and a.action = 'event_updated') $q$));
select t.rec('hardening', 'RLS enabled on every radar table', 'rows:0', t.rows($q$ select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'radar' and c.relkind = 'r' and not c.relrowsecurity $q$));
select t.rec('grants', 'anon holds NO privilege of any kind on any radar table', 'rows:0', t.rows($q$
  select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
  cross join unnest(array['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p
  where n.nspname = 'radar' and c.relkind = 'r' and has_table_privilege('anon', c.oid, p) $q$));
select t.rec('grants', 'authenticated holds ONLY SELECT on radar tables (no write-class privilege, independent of RLS)', 'rows:0', t.rows($q$
  select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
  cross join unnest(array['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p
  where n.nspname = 'radar' and c.relkind = 'r' and has_table_privilege('authenticated', c.oid, p) $q$));
select t.rec('grants', 'service_role: never DELETE/TRUNCATE; UPDATE only on venues/parties; no INSERT on events', 'rows:0', t.rows($q$
  select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
  cross join unnest(array['INSERT','UPDATE','DELETE','TRUNCATE']) p
  where n.nspname = 'radar' and c.relkind = 'r' and has_table_privilege('service_role', c.oid, p)
    and ( p in ('DELETE','TRUNCATE')
       or (p = 'UPDATE' and c.relname not in ('venues','parties'))
       or (p = 'INSERT' and c.relname = 'events') ) $q$));
select t.rec('grants', 'anon has no USAGE on schema radar; authenticated/service_role do', 'false|true|true',
  has_schema_privilege('anon', 'radar', 'usage')::text || '|' || has_schema_privilege('authenticated', 'radar', 'usage')::text || '|' || has_schema_privilege('service_role', 'radar', 'usage')::text);
select t.rec('hardening', 'no radar table grant to PUBLIC or anon', 'rows:0', t.rows($q$ select 1 from information_schema.role_table_grants where table_schema = 'radar' and grantee in ('PUBLIC','anon') $q$));
select t.rec('hardening', 'no radar function executable by PUBLIC (explicit ACL, no default)', 'rows:0', t.rows($q$
  select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where (n.nspname = 'radar' or p.proname = 'radar_review_event')
     and (p.proacl is null or exists (select 1 from aclexplode(p.proacl) a where a.grantee = 0)) $q$));
select t.rec('hardening', 'no INSERT/UPDATE/DELETE policy exists on any radar table', 'rows:0', t.rows($q$ select 1 from pg_policies where schemaname = 'radar' and cmd <> 'SELECT' $q$));
select t.rec('hardening', 'migration created no table in public', 'rows:0', t.rows($q$ select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r' $q$));

\o
\echo
\echo ==== RESULTS ====
select n, grp, name, expected, actual, case when pass then 'PASS' else 'FAIL' end as result from t.results order by n;
select count(*) filter (where pass) || '/' || count(*) || ' passed' as summary from t.results;
