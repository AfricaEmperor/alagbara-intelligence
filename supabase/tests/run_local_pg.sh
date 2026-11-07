#!/usr/bin/env bash
# Disposable-PostgreSQL test of the AP-001 radar migration. Touches ONLY a throwaway database it creates and drops
# on a LOCAL cluster. Never connects to Supabase. Usage: supabase/tests/run_local_pg.sh [output_dir]
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MIG="${RADAR_MIGRATION:-$HERE/../migrations/20261105000000_ap001_event_radar.sql.DRAFT}"
OUT="${1:-}"; [ -n "$OUT" ] && mkdir -p "$OUT"
WORK="$(mktemp -d)"; chmod 755 "$WORK"
cp "$HERE/stub_supabase.sql" "$HERE/radar_rls_test.sql" "$WORK/"; cp "$MIG" "$WORK/migration.sql"; chmod 644 "$WORK"/*
DB="radar_r3_$$"
pg() { runuser -u postgres -- psql -X -q -v ON_ERROR_STOP=1 -d "$1" "${@:2}"; }
pgt() { runuser -u postgres -- psql -X -q -At -d "$1" "${@:2}"; }
(pg_lsclusters 2>/dev/null | grep -q online) || pg_ctlcluster 16 main start 2>/dev/null; sleep 2
echo "server: $(pgt postgres -c 'show server_version')"
runuser -u postgres -- createdb "$DB" || exit 2
cleanup() { runuser -u postgres -- dropdb --if-exists "$DB" >/dev/null 2>&1; rm -rf "$WORK"; }
trap cleanup EXIT
pg "$DB" -f "$WORK/stub_supabase.sql" || { echo "stub failed"; exit 2; }
pg "$DB" -c "grant create on database \"$DB\" to postgres_sim" || exit 2
echo "== applying migration as postgres_sim (non-superuser, BYPASSRLS) to scratch database $DB"
pg "$DB" -c "set role postgres_sim" -f "$WORK/migration.sql" && echo "migration applied: OK" || { echo "MIGRATION FAILED"; exit 3; }

echo; echo "== running test suite"
runuser -u postgres -- psql -X -q -d "$DB" -f "$WORK/radar_rls_test.sql" > "$WORK/results.txt" 2>&1
cat "$WORK/results.txt"
FAILS=$(pgt "$DB" -c "select count(*) from t.results where not pass")
TOTAL=$(pgt "$DB" -c "select count(*) from t.results")

echo; echo "== concurrency: two real sessions"
UID_R=11111111-1111-1111-1111-111111111111
pg "$DB" -c "select t.as(null,'service_role')" -c "select radar.upsert_event(jsonb_build_object('event_id','evt_conc','timezone','Africa/Porto-Novo','review_status','pending','evidence_references',jsonb_build_array('o')), null)" -c "select radar.upsert_event(jsonb_build_object('event_id','evt_conc2','timezone','Africa/Porto-Novo','review_status','pending','evidence_references',jsonb_build_array('o')), null)" >/dev/null
sess() { pgt "$DB" -c "select t.as('$UID_R','authenticated')" -c "$1" 2>&1 | tr '\n' ' '; }
# (1) approve vs reject on the same version: second must wait for the lock, then be stale
( sess "begin; select radar.review_event('dec-conc-0001-aa','evt_conc','approve',1,''); select pg_sleep(1.5); commit;" > "$WORK/c1.txt" ) &
sleep 0.5
START=$(date +%s.%N)
sess "select radar.review_event('dec-conc-0002-bb','evt_conc','reject',1,'')" > "$WORK/c2.txt"
ELAPSED=$(echo "$(date +%s.%N) - $START" | bc)
wait
echo "session1: $(cat "$WORK/c1.txt" | cut -c1-150)"
echo "session2: $(cat "$WORK/c2.txt" | cut -c1-150)  (waited ${ELAPSED}s on the row lock)"
echo "final: $(pgt "$DB" -c "select review_status || ' v' || version from radar.events where event_id='evt_conc'"), decisions=$(pgt "$DB" -c "select count(*) from radar.decisions where event_id='evt_conc'")"
C1_OK=0; grep -q '"status": "applied"' "$WORK/c1.txt" && grep -q "stale version" "$WORK/c2.txt" && [ "$(pgt "$DB" -c "select review_status || version from radar.events where event_id='evt_conc'")" = "approved2" ] && [ "$(pgt "$DB" -c "select count(*) from radar.decisions where event_id='evt_conc'")" = "1" ] && C1_OK=1
# (2) the SAME decision_id from two sessions at once: one applies, the other is a duplicate, one row total
( sess "begin; select radar.review_event('dec-conc-0003-cc','evt_conc2','approve',1,''); select pg_sleep(1.5); commit;" > "$WORK/c3.txt" ) &
sleep 0.5
sess "select radar.review_event('dec-conc-0003-cc','evt_conc2','approve',1,'')" > "$WORK/c4.txt"
wait
echo "same-id s1: $(cut -c1-120 "$WORK/c3.txt")"; echo "same-id s2: $(cut -c1-120 "$WORK/c4.txt")"
C2_OK=0; grep -q '"status": "applied"' "$WORK/c3.txt" && grep -q '"status": "duplicate"' "$WORK/c4.txt" && [ "$(pgt "$DB" -c "select count(*) from radar.decisions where event_id='evt_conc2'")" = "1" ] && [ "$(pgt "$DB" -c "select count(*) from radar.audit where subject='evt_conc2' and action like 'review:%'")" = "1" ] && C2_OK=1
echo "concurrency checks: stale-after-lock=$C1_OK same-decision-id-idempotent=$C2_OK"

echo; echo "== effective TABLE privileges (from the catalog; RLS is applied on top, see RLS policies)"
MAT1="select c.relname as table_name, r.rolname as role,
  coalesce(string_agg(left(p,1), '' order by p) filter (where has_table_privilege(r.rolname, c.oid, p)), '-') as privileges_SIUDT
  from pg_class c join pg_namespace n on n.oid=c.relnamespace
  cross join (values ('anon'),('authenticated'),('service_role')) r(rolname)
  cross join unnest(array['SELECT','INSERT','UPDATE','DELETE','TRUNCATE']) p
  where n.nspname='radar' and c.relkind='r' group by 1,2 order by 1, array_position(array['anon','authenticated','service_role'], r.rolname)"
pg "$DB" -c "\\pset format aligned" -c "$MAT1" | tee "$WORK/m1.txt"
echo; echo "== effective FUNCTION execute privileges"
MAT2="select n.nspname||'.'||p.proname||'('||pg_get_function_identity_arguments(p.oid)||')' as function, p.prosecdef as definer,
  has_function_privilege('anon',p.oid,'execute') as anon, has_function_privilege('authenticated',p.oid,'execute') as authenticated,
  has_function_privilege('service_role',p.oid,'execute') as service_role
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where (n.nspname='radar' and p.proname not in ('deny_mutation','deny_truncate')) or p.proname='radar_review_event' order by 1"
pg "$DB" -c "$MAT2" | tee "$WORK/m2.txt"
echo; echo "== RLS status and policies"
pg "$DB" -c "select c.relname as table_name, c.relrowsecurity as rls_enabled from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='radar' and c.relkind='r' order by 1" | tee "$WORK/m3.txt"
pg "$DB" -c "select tablename, policyname, roles::text, cmd, qual from pg_policies where schemaname='radar' order by 1,2" | tee "$WORK/m4.txt"

echo; echo "SUMMARY: sql_tests ${TOTAL:-?} run, ${FAILS:-?} failed; concurrency stale=$C1_OK same-id=$C2_OK"
if [ -n "$OUT" ]; then cp "$WORK"/results.txt "$OUT/pg_01_results.txt"; for f in c1 c2 c3 c4; do :; done; fi
[ "${FAILS:-1}" = "0" ] && [ "$C1_OK" = "1" ] && [ "$C2_OK" = "1" ]
