#!/usr/bin/env python3
"""Mutation check for the radar migration tests: break the migration on purpose, confirm the suite notices.
A surviving mutant means a guarantee is NOT actually tested. Disposable local PostgreSQL only."""
import os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "..", "migrations", "20261105000000_ap001_event_radar.sql.DRAFT")).read()

def sub(old, new, count=1):
    assert SRC.count(old) >= 1, f"mutation anchor missing: {old[:60]!r}"
    return lambda s: s.replace(old, new, count)

MUTANTS = {
 "M1 review_event without pinned search_path": sub("language plpgsql security definer set search_path = '' as $$\ndeclare\n  v_uid", "language plpgsql security definer as $$\ndeclare\n  v_uid"),
 "M2 no replay (decision_id) handling": sub("  if found then\n    if v_prior.event_id", "  if false then\n    if v_prior.event_id"),
 "M3 no stale-version check in review_event": sub("  if v_version <> p_expected_version then\n    raise exception 'stale version: event is at %, reviewer saw %'", "  if false then\n    raise exception 'stale version: event is at %, reviewer saw %'"),
 "M4 RLS disabled on radar.events": sub("alter table radar.events              enable row level security;\n", ""),
 "M5 anon granted SELECT on radar.events": sub("commit;\n\n-- ====", "grant select on radar.events to anon;\ncommit;\n\n-- ===="),
 "M6 no reviewer check in review_event": sub("  if radar.reviewer_role() is null then\n    raise exception 'not a reviewer' using errcode = '42501';\n  end if;\n", ""),
 "M7 exactly-one-row guard removed": sub("  if v_rows <> 1 then                                  -- exactly one intended row, BEFORE any audit record exists", "  if false then"),
 "M8 decisions no longer append-only": sub("create trigger decisions_append_only before update or delete on radar.decisions          for each row execute function radar.deny_mutation();\n", ""),
 "M9 authenticated granted direct INSERT on events": sub("commit;\n\n-- ====", "grant insert on radar.events to authenticated;\ncommit;\n\n-- ===="),
}
survived = []
for name, mut in MUTANTS.items():
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
        f.write(mut(SRC)); path = f.name
    os.chmod(path, 0o644)
    r = subprocess.run([os.path.join(HERE, "run_local_pg.sh")], env={**os.environ, "RADAR_MIGRATION": path}, capture_output=True, text=True)
    os.unlink(path)
    out = r.stdout + r.stderr
    fails = re.findall(r"^\s*\d+\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|.*\|\s*FAIL\s*$", out, re.M)
    conc = re.search(r"concurrency checks: stale-after-lock=(\d) same-decision-id-idempotent=(\d)", out)
    broke = bool(fails) or r.returncode != 0
    status = "KILLED " if broke else "SURVIVED"
    detail = "; ".join(f"[{g}] {n[:55]}" for g, n in fails[:3]) or ("migration failed to apply" if "MIGRATION FAILED" in out else ("concurrency check failed" if conc and "0" in conc.groups() else "-"))
    print(f"{status} {name:55} failing tests: {len(fails):2}  {detail}")
    if not broke: survived.append(name)
print(f"\n{len(MUTANTS) - len(survived)}/{len(MUTANTS)} mutants killed" + (f"; SURVIVORS: {survived}" if survived else ""))
sys.exit(1 if survived else 0)
