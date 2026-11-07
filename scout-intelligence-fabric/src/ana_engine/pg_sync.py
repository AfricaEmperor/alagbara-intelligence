"""SQLite <-> Supabase/PostgreSQL parity tooling for the radar store (R3-D).

  canonical(store)        -> canonical JSON view of the SQLite store
  backfill_sql(store)     -> a SQL script (single transaction, idempotent, never overwrites). It is only GENERATED
                             here; this module never connects to a database to write.
  pg_canonical(run_psql)  -> the same canonical view read from PostgreSQL through a caller-supplied psql command
                             (SELECT only)
  diff(a, b)              -> human-readable differences; empty list == parity for everything covered

Parity is only claimed for what the reconciliation covers and only after it has actually run clean.
"""
from __future__ import annotations

import json
import shlex
import subprocess
from datetime import UTC, datetime
from typing import Any, Callable

from .store import RadarStore

SECTIONS = ("evidence", "venues", "parties", "events", "obs_event", "decisions", "audit")


def _ts(value: str | None) -> str | None:
    """Normalize any ISO-8601 timestamp to UTC with microseconds, so SQLite text and timestamptz compare equal."""
    if value is None:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")


def canonical(store: RadarStore) -> dict[str, Any]:
    db = store.db
    out: dict[str, Any] = {k: {} for k in SECTIONS}
    for oid, doc in db.execute("SELECT observation_id, doc FROM evidence"):
        out["evidence"][oid] = json.loads(doc)
    for vid, doc in db.execute("SELECT venue_id, doc FROM venues"):
        out["venues"][vid] = json.loads(doc)
    for pid, doc in db.execute("SELECT party_id, doc FROM parties"):
        out["parties"][pid] = json.loads(doc)
    for eid, doc in db.execute("SELECT event_id, doc FROM events"):
        out["events"][eid] = {"doc": json.loads(doc), "version": store.event_version(eid)}
    for oid, eid in db.execute("SELECT observation_id, event_id FROM obs_event"):
        out["obs_event"][oid] = eid
    for row in db.execute("SELECT decision_id,event_id,decision,reviewer,note,version_seen,version_after,"
                          "resulting_status,kind,at FROM decisions"):
        did, eid, dec, rev, note, vs, va, rs, kind, at = row
        out["decisions"][did] = {"event_id": eid, "decision": dec, "reviewer": rev, "note": note or None,
                                 "version_seen": vs, "version_after": va, "resulting_status": rs,
                                 "kind": kind, "at": _ts(at)}
    for aid, at, actor, action, subject, detail in db.execute("SELECT id,at,actor,action,subject,detail FROM audit"):
        out["audit"][str(aid)] = {"at": _ts(at), "actor": actor, "action": action, "subject": subject,
                                  "detail": json.loads(detail or "{}")}
    return out


def _lit(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def _json(v: Any) -> str:
    return _lit(json.dumps(v, ensure_ascii=False, sort_keys=True)) + "::jsonb"


def backfill_sql(store: RadarStore) -> str:
    """Idempotent, atomic, non-overwriting. Run as the worker role (service_role) against the TARGET database only
    after Sovereign authorization. Re-running is a no-op; an existing row that DIFFERS aborts the whole script."""
    c = canonical(store)
    lines = ["-- AP-001 SQLite -> PostgreSQL backfill (generated). Idempotent; never overwrites; one transaction.",
             "begin;"]
    for oid, doc in c["evidence"].items():
        lines.append(f"insert into radar.evidence(observation_id, content_hash, doc) values ({_lit(oid)}, "
                     f"{_lit(doc['content_hash'])}, {_json(doc)}) on conflict (observation_id) do nothing;")
    for vid, doc in c["venues"].items():
        lines.append(f"insert into radar.venues(venue_id, doc) values ({_lit(vid)}, {_json(doc)}) on conflict (venue_id) do nothing;")
    for pid, doc in c["parties"].items():
        lines.append(f"insert into radar.parties(party_id, doc) values ({_lit(pid)}, {_json(doc)}) on conflict (party_id) do nothing;")
    for eid, e in c["events"].items():
        lines.append(f"select radar.backfill_event({_json(e['doc'])}, {int(e['version'])});")
    for oid, eid in c["obs_event"].items():
        lines.append(f"insert into radar.obs_event(observation_id, event_id) values ({_lit(oid)}, {_lit(eid)}) on conflict (observation_id) do nothing;")
    for did, d in c["decisions"].items():
        lines.append("insert into radar.decisions(decision_id, event_id, decision, reviewer, note, version_seen, version_after, "
                     "resulting_status, kind, at) values (" + ", ".join(_lit(x) for x in (
                         did, d["event_id"], d["decision"], d["reviewer"], d["note"], d["version_seen"], d["version_after"],
                         d["resulting_status"], d["kind"])) + f", {_lit(d['at'])}::timestamp at time zone 'UTC') on conflict (decision_id) do nothing;")
    for aid, a in c["audit"].items():
        lines.append("insert into radar.audit(at, actor, action, subject, detail, legacy_sqlite_id) values ("
                     f"{_lit(a['at'])}::timestamp at time zone 'UTC', {_lit(a['actor'])}, {_lit(a['action'])}, {_lit(a['subject'])}, "
                     f"{_json(a['detail'])}, {int(aid)}) on conflict (legacy_sqlite_id) do nothing;")
    lines.append("commit;")
    return "\n".join(lines) + "\n"


_TS_SQL = "to_char({c} at time zone 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US')"
PG_QUERIES = {
    "evidence": "select coalesce(json_object_agg(observation_id, doc), '{}'::json) from radar.evidence",
    "venues": "select coalesce(json_object_agg(venue_id, doc), '{}'::json) from radar.venues",
    "parties": "select coalesce(json_object_agg(party_id, doc), '{}'::json) from radar.parties",
    "events": "select coalesce(json_object_agg(event_id, json_build_object('doc', doc, 'version', version)), '{}'::json) from radar.events",
    "obs_event": "select coalesce(json_object_agg(observation_id, event_id), '{}'::json) from radar.obs_event",
    "decisions": ("select coalesce(json_object_agg(decision_id, json_build_object('event_id', event_id, 'decision', decision, "
                  "'reviewer', reviewer, 'note', note, 'version_seen', version_seen, 'version_after', version_after, "
                  "'resulting_status', resulting_status, 'kind', kind, 'at', " + _TS_SQL.format(c="at") + ")), '{}'::json) from radar.decisions"),
    "audit": ("select coalesce(json_object_agg(legacy_sqlite_id::text, json_build_object('at', " + _TS_SQL.format(c="at") + ", "
              "'actor', actor, 'action', action, 'subject', subject, 'detail', detail)), '{}'::json) "
              "from radar.audit where legacy_sqlite_id is not null"),
}


def psql_runner(psql_cmd: str) -> Callable[[str], str]:
    base = shlex.split(psql_cmd)

    def run(sql: str) -> str:
        r = subprocess.run([*base, "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", sql],
                           capture_output=True, text=True, check=False, timeout=120)
        if r.returncode != 0:
            raise RuntimeError(f"psql failed: {r.stderr.strip()[:300]}")
        return r.stdout
    return run


def pg_canonical(run_psql: Callable[[str], str]) -> dict[str, Any]:
    return {k: json.loads(run_psql(q).strip() or "{}") for k, q in PG_QUERIES.items()}


def diff(a: dict[str, Any], b: dict[str, Any], a_name: str = "sqlite", b_name: str = "postgres") -> list[str]:
    out: list[str] = []
    for sec in SECTIONS:
        ka, kb = set(a.get(sec, {})), set(b.get(sec, {}))
        for k in sorted(ka - kb):
            out.append(f"{sec}: {k} only in {a_name}")
        for k in sorted(kb - ka):
            out.append(f"{sec}: {k} only in {b_name}")
        for k in sorted(ka & kb):
            if a[sec][k] != b[sec][k]:
                out.append(f"{sec}: {k} differs")
    return out
