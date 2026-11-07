"""R3-D: SQLite <-> PostgreSQL parity, against a DISPOSABLE local PostgreSQL only (skipped if unavailable).
Never touches Supabase. Covers what pg_sync.canonical covers; see AP001_PERSISTENCE_DESIGN.md for the gaps."""
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from ana_engine.pg_sync import backfill_sql, canonical, diff, pg_canonical, psql_runner
from ana_engine.pipeline import run_upload
from ana_engine.store import DecisionConflict, StaleWrite
from conftest import POSTER_A, POSTER_B
from radar_contracts import ContractError
from scout_fabric.text_providers import SidecarTextProvider

SUPA = Path(__file__).resolve().parents[2] / "supabase"
P = SidecarTextProvider()
REV = "11111111-1111-1111-1111-111111111111"


def _pg_ok() -> bool:
    return bool(shutil.which("psql") and shutil.which("runuser") and os.geteuid() == 0 and shutil.which("pg_lsclusters"))


pytestmark = pytest.mark.skipif(not _pg_ok(), reason="local PostgreSQL tooling unavailable")


def sh(*args, check=True, **kw):
    return subprocess.run(args, capture_output=True, text=True, check=check, **kw)


def psql(db, sql, role=None, claims_sub=None, check=True):
    pre = ""
    if claims_sub:
        pre += f"select set_config('request.jwt.claims', '{{\"sub\":\"{claims_sub}\",\"role\":\"authenticated\"}}', false);\n"
    if role:
        pre += f"set role {role};\n"
    r = subprocess.run(["runuser", "-u", "postgres", "--", "psql", "-X", "-q", "-A", "-t", "-v", "VERBOSITY=verbose",
                        "-v", "ON_ERROR_STOP=1", "-d", db, "-c", pre + sql], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr)
    return r


@pytest.fixture
def pgdb(tmp_path):
    if "online" not in sh("pg_lsclusters").stdout:
        sh("pg_ctlcluster", "16", "main", "start"); sh("sleep", "2")
    import tempfile
    work = Path(tempfile.mkdtemp(prefix="radar_pg_")); os.chmod(work, 0o755)    # must be readable by the postgres OS user
    shutil.copy(SUPA / "tests" / "stub_supabase.sql", work / "stub.sql")
    shutil.copy(SUPA / "migrations" / "20261105000000_ap001_event_radar.sql.DRAFT", work / "mig.sql")
    for f in work.iterdir():
        os.chmod(f, 0o644)
    db = "radar_parity_" + uuid.uuid4().hex[:8]
    sh("runuser", "-u", "postgres", "--", "createdb", db)
    sh("runuser", "-u", "postgres", "--", "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", db, "-f", str(work / "stub.sql"))
    sh("runuser", "-u", "postgres", "--", "psql", "-X", "-q", "-d", db, "-c", f'grant create on database "{db}" to postgres_sim')
    sh("runuser", "-u", "postgres", "--", "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", db, "-c", "set role postgres_sim", "-f", str(work / "mig.sql"))
    psql(db, f"insert into auth.users(id,email,email_confirmed_at,raw_app_meta_data) values ('{REV}','rev@example.test',now(),'{{\"radar_role\":\"reviewer\"}}')")
    yield db, work
    sh("runuser", "-u", "postgres", "--", "dropdb", "--if-exists", db, check=False)
    shutil.rmtree(work, ignore_errors=True)


@pytest.fixture
def populated(store, registry, poster):
    """A store with every history shape: approval, explicit system reopen, re-approval, contradictions, parties."""
    a = run_upload(store, registry, poster("a.png", POSTER_A, 1), "src-upload-1", P)["event_id"]
    store.review_decision(a, "approve", REV, "ok", "dec-par-0001-aaaa", store.event_version(a))
    run_upload(store, registry, poster("b.png", POSTER_B, 2), "src-upload-2", P)                # conflict -> system reopen
    store.review_decision(a, "approve", REV, "again", "dec-par-0002-bbbb", store.event_version(a))
    other = run_upload(store, registry, poster("o.png", "RETRO SESSION\n10/10/2026\nde 21h à 02h\nLieu : Bar Fictif, Akpakpa\nDJ Gamma\n", 3), "src-upload-1", P)["event_id"]
    return store, a, other


def apply_backfill(db, sql, work, tag="bf"):
    f = work / f"{tag}.sql"; f.write_text("set role service_role;\n" + sql); os.chmod(f, 0o644)
    return subprocess.run(["runuser", "-u", "postgres", "--", "psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-d", db, "-f", str(f)],
                          capture_output=True, text=True)


def pg_view(db):
    return pg_canonical(psql_runner(f"runuser -u postgres -- psql -d {db}"))


def test_backfill_reconciles_with_zero_differences(pgdb, populated):
    db, work = pgdb
    store, a, other = populated
    c = canonical(store)
    assert len(c["events"]) == 2 and len(c["decisions"]) == 3 and c["audit"] and c["obs_event"]   # non-trivial history
    assert sorted(d["kind"] for d in c["decisions"].values()) == ["human", "human", "system"]
    r = apply_backfill(db, backfill_sql(store), work)
    assert r.returncode == 0, r.stderr
    assert diff(c, pg_view(db)) == []


def test_backfill_is_idempotent(pgdb, populated):
    db, work = pgdb
    store, *_ = populated
    sql = backfill_sql(store)
    assert apply_backfill(db, sql, work, "one").returncode == 0
    first = pg_view(db)
    r2 = apply_backfill(db, sql, work, "two")
    assert r2.returncode == 0, r2.stderr
    assert "unchanged" in r2.stdout and "inserted" not in r2.stdout            # events: no-op the second time
    assert pg_view(db) == first and diff(canonical(store), first) == []


def test_reconciliation_detects_divergence(pgdb, populated):
    db, work = pgdb
    store, a, other = populated
    assert apply_backfill(db, backfill_sql(store), work).returncode == 0
    psql(db, f"update radar.events set doc = jsonb_set(doc,'{{title}}','\"TAMPERED\"') where event_id = '{a}'")
    psql(db, "update radar.venues set doc = jsonb_set(doc,'{district}','\"Nowhere\"')")
    d = diff(canonical(store), pg_view(db))
    assert f"events: {a} differs" in d and any(x.startswith("venues:") for x in d) and len(d) == 2 + (0 if len(canonical(store)["venues"]) == 1 else len(canonical(store)["venues"]) - 1)


def test_conflicting_existing_row_aborts_everything_and_is_not_overwritten(pgdb, populated):
    db, work = pgdb
    store, a, other = populated
    ev = canonical(store)["events"][a]
    bad = dict(ev["doc"], title="DIFFERENT")
    psql(db, f"select radar.backfill_event('{json.dumps(bad)}'::jsonb, {ev['version']})", role="service_role")
    r = apply_backfill(db, backfill_sql(store), work)
    assert r.returncode != 0 and "backfill conflict" in r.stderr
    after = psql(db, f"select doc->>'title' from radar.events where event_id = '{a}'").stdout.strip()
    assert after == "DIFFERENT"                                                    # never overwritten
    assert psql(db, "select count(*) from radar.evidence").stdout.strip() == "0"   # whole script rolled back


def test_interrupted_backfill_leaves_nothing_then_recovers(pgdb, populated):
    db, work = pgdb
    store, *_ = populated
    sql = backfill_sql(store)
    cut = sql.rstrip().rsplit("commit;", 1)[0]                                     # connection ends before COMMIT
    apply_backfill(db, cut, work, "cut")
    counts = psql(db, "select (select count(*) from radar.evidence)||'|'||(select count(*) from radar.events)||'|'||(select count(*) from radar.decisions)||'|'||(select count(*) from radar.audit)").stdout.strip()
    assert counts == "0|0|0|0"
    assert apply_backfill(db, sql, work, "full").returncode == 0
    assert diff(canonical(store), pg_view(db)) == []


def _pg_review(db, event, decision, did, version, note=""):
    r = psql(db, f"select radar.review_event('{did}','{event}','{decision}',{version},'{note}')", role="authenticated", claims_sub=REV, check=False)
    if r.returncode == 0:
        return json.loads(r.stdout.strip().splitlines()[-1])["status"]
    return re.search(r"ERROR:\s+(\w{5}):", r.stderr).group(1)


def _lite_review(store, event, decision, did, version, note=""):
    try:
        return store.review_decision(event, decision, REV, note, did, version)[1]
    except StaleWrite:
        return "40001"
    except DecisionConflict:
        return "23505"
    except KeyError:
        return "P0002"
    except ContractError:
        return "22023"


def test_review_operation_behaves_identically_on_both_stores(pgdb, populated):
    db, work = pgdb
    store, a, other = populated
    assert apply_backfill(db, backfill_sql(store), work).returncode == 0
    v = store.event_version(other)
    steps = [("apply", dict(decision="reject", did="dec-par-0010-cccc", version=v)),
             ("replay (old version)", dict(decision="reject", did="dec-par-0010-cccc", version=v)),
             ("stale", dict(decision="approve", did="dec-par-0011-dddd", version=v)),
             ("id reuse, other decision", dict(decision="approve", did="dec-par-0010-cccc", version=v)),
             ("invalid decision", dict(decision="publish", did="dec-par-0012-eeee", version=v + 1)),
             ("invalid decision id", dict(decision="approve", did="short", version=v + 1)),
             ("fresh version, other decision", dict(decision="request_correction", did="dec-par-0013-ffff", version=v + 1))]
    rows = []
    for name, kw in steps:
        s, g = _lite_review(store, other, **kw), _pg_review(db, other, **kw)
        rows.append((name, s, g)); assert s == g, (name, s, g)
    assert [r[1] for r in rows] == ["applied", "duplicate", "40001", "23505", "22023", "22023", "applied"]
    assert _lite_review(store, "evt_ghost", "approve", "dec-par-0014-gggg", 1) == _pg_review(db, "evt_ghost", "approve", "dec-par-0014-gggg", 1) == "P0002"
    lite, pg = canonical(store), pg_view(db)
    from datetime import datetime
    for sec in ("events", "obs_event", "evidence", "venues", "parties"):
        assert lite[sec] == pg[sec], sec                                          # states and versions identical
    assert lite["decisions"].keys() == pg["decisions"].keys()
    new_ids = {"dec-par-0010-cccc", "dec-par-0013-ffff"}
    for did, row in lite["decisions"].items():
        a, b = dict(row), dict(pg["decisions"][did])
        ta, tb = a.pop("at"), b.pop("at")
        assert a == b, did                                                         # every field identical except the clock stamp
        if did in new_ids:                                                         # each store stamped its own clock: bounded, not equal
            assert abs((datetime.fromisoformat(ta) - datetime.fromisoformat(tb)).total_seconds()) < 5
        else:
            assert ta == tb                                                        # backfilled rows: exact
    n_lite = sum(1 for x in lite["audit"].values() if x["action"].startswith("review:") and x["subject"] == other)
    n_pg = int(psql(db, f"select count(*) from radar.audit where action like 'review:%' and subject = '{other}'").stdout.strip())
    assert n_lite == 2 and n_pg == 2                                               # one audit row per applied decision (the 2 new ones; backfilled rows have none for 'other')
