"""ZR-01 persistence integrity: optimistic concurrency, idempotent decisions, atomic ingest, local migration."""
import json
import sqlite3
import threading

import pytest

from ana_engine.pipeline import run_upload
from ana_engine.store import DecisionConflict, RadarStore, StaleWrite
from conftest import POSTER_A, POSTER_B
from radar_contracts import ContractError
from scout_fabric.text_providers import SidecarTextProvider

P = SidecarTextProvider()
D1, D2, D3 = "dec-00000001-aaaa", "dec-00000002-bbbb", "dec-00000003-cccc"


def seeded(store, registry, poster):
    out = run_upload(store, registry, poster("a.png", POSTER_A, 1), "src-upload-1", P)
    return out["event_id"], store.event_version(out["event_id"])


def assert_consistent(store, event_id):
    """Audit/decision history must agree with the resulting event state."""
    ev = store.get_event(event_id)
    hist = store.decisions(event_id)
    if hist:
        assert hist[-1]["resulting_status"] == ev.review_status, (hist, ev.review_status)
    human = [h for h in hist if h["kind"] == "human"]
    audited = [a for a in store.audit_log() if a["action"].startswith("review:") and a["subject"] == event_id]
    assert len(audited) == len(human)  # exactly one audit row per applied human decision
    assert len({h["decision_id"] for h in hist}) == len(hist)


# --- the original defect, reproduced and now prevented ----------------------------------------
def test_original_lost_update_is_now_rejected(store, registry, poster):
    eid, v = seeded(store, registry, poster)
    w1, w2 = RadarStore(store.root), RadarStore(store.root)
    stale = w2.get_event(eid)                                   # worker 2 reads version v
    w1.review_decision(eid, "approve", "rev-1", decision_id=D1, expected_version=v)  # approval lands
    stale.evidence_references.append("late-observation")
    with pytest.raises(StaleWrite):
        w2.put_event(stale, expected_version=v)                 # stale write rejected
    final = store.get_event(eid)
    assert final.review_status == "approved" and "late-observation" not in final.evidence_references
    assert store.event_version(eid) == v + 1
    assert_consistent(store, eid)


def test_put_event_without_version_cannot_overwrite_existing(store, registry, poster):
    eid, _ = seeded(store, registry, poster)
    with pytest.raises(StaleWrite):
        store.put_event(store.get_event(eid))


def test_stale_review_is_rejected_and_writes_nothing(store, registry, poster):
    eid, v = seeded(store, registry, poster)
    run_upload(store, registry, poster("b.png", POSTER_B, 2), "src-upload-2", P)   # merge bumps version
    assert store.event_version(eid) == v + 1
    n_audit = len(store.audit_log())
    with pytest.raises(StaleWrite):
        store.review_decision(eid, "approve", "rev-1", decision_id=D1, expected_version=v)
    assert store.get_event(eid).review_status == "pending"
    assert store.decisions(eid) == [] and len(store.audit_log()) == n_audit


# --- concurrent ingestion vs approval ----------------------------------------------------------
@pytest.mark.parametrize("round_", range(12))
def test_concurrent_ingestion_cannot_erase_an_approval(tmp_path, registry, poster, round_):
    base = tmp_path / f"race{round_}"
    s0 = RadarStore(base)
    eid, v = seeded(s0, registry, poster)
    pb = poster(f"b{round_}.png", POSTER_B, 20 + round_)
    barrier, res, errs = threading.Barrier(2), {}, []

    def ingest():
        try:
            st = RadarStore(base); barrier.wait()
            res["ingest"] = run_upload(st, registry, pb, "src-upload-2", P); st.close()
        except Exception as e:  # noqa: BLE001
            errs.append(e)

    def approve():
        try:
            st = RadarStore(base); barrier.wait()
            try:
                st.review_decision(eid, "approve", "rev-1", decision_id=D1, expected_version=v); res["approve"] = "applied"
            except StaleWrite:
                res["approve"] = "stale"
            st.close()
        except Exception as e:  # noqa: BLE001
            errs.append(e)

    ts = [threading.Thread(target=ingest), threading.Thread(target=approve)]
    [t.start() for t in ts]; [t.join(30) for t in ts]
    assert not errs, errs
    ev = s0.get_event(eid)
    assert len(ev.evidence_references) == 2                      # the ingestion always lands
    assert_consistent(s0, eid)
    hist = s0.decisions(eid)
    if res["approve"] == "applied":
        # approval is never silently lost: it is in history, and if the event is no longer approved
        # an explicit audited system reopen follows it (new contradiction merged after the approval).
        assert any(h["decision"] == "approve" for h in hist)
        assert ev.review_status == "approved" or hist[-1]["kind"] == "system"
    else:
        assert res["approve"] == "stale" and ev.review_status == "pending" and hist == []


def test_approval_then_conflicting_merge_reopens_explicitly_keeping_history(store, registry, poster):
    eid, v = seeded(store, registry, poster)
    store.review_decision(eid, "approve", "rev-1", decision_id=D1, expected_version=v)
    run_upload(store, registry, poster("b.png", POSTER_B, 2), "src-upload-2", P)
    ev = store.get_event(eid)
    kinds = [(h["kind"], h["decision"]) for h in store.decisions(eid)]
    assert ev.review_status == "pending" and kinds == [("human", "approve"), ("system", "reopen")]
    assert any(a["action"] == "review_reopened" for a in store.audit_log())
    assert_consistent(store, eid)


def test_corroborating_evidence_does_not_disturb_approval(store, registry, poster):
    eid, v = seeded(store, registry, poster)
    store.review_decision(eid, "approve", "rev-1", decision_id=D1, expected_version=v)
    run_upload(store, registry, poster("c.png", POSTER_A, 9), "src-upload-2", P)   # same facts, new source
    ev = store.get_event(eid)
    assert ev.review_status == "approved" and len(ev.evidence_references) == 2 and ev.contradictions == []
    assert [h["kind"] for h in store.decisions(eid)] == ["human"]


# --- idempotent decisions ---------------------------------------------------------------------
def test_valid_decision_changes_only_the_intended_event(store, registry, poster):
    eid, v = seeded(store, registry, poster)
    other = run_upload(store, registry, poster("o.png", "AUTRE\n05/12/2026\nLieu : Bar Test\n", 5), "src-upload-1", P)["event_id"]
    ev, status = store.review_decision(eid, "approve", "rev-1", "ok", D1, v)
    assert status == "applied" and ev.review_status == "approved"
    assert store.get_event(other).review_status == "pending"


def test_replaying_a_decision_has_no_additional_effect(store, registry, poster):
    eid, v = seeded(store, registry, poster)
    store.review_decision(eid, "approve", "rev-1", "", D1, v)
    ver, n_audit, n_dec = store.event_version(eid), len(store.audit_log()), len(store.decisions())
    for _ in range(3):
        ev, status = store.review_decision(eid, "approve", "rev-1", "", D1, v)   # even with the old version
        assert status == "duplicate" and ev.review_status == "approved"
    assert (store.event_version(eid), len(store.audit_log()), len(store.decisions())) == (ver, n_audit, n_dec)
    assert_consistent(store, eid)


def test_decision_id_reuse_with_different_payload_is_rejected(store, registry, poster):
    eid, v = seeded(store, registry, poster)
    store.review_decision(eid, "approve", "rev-1", "", D1, v)
    with pytest.raises(DecisionConflict):
        store.review_decision(eid, "reject", "rev-1", "", D1, v)
    assert store.get_event(eid).review_status == "approved"


def test_invalid_decisions_write_nothing(store, registry, poster):
    eid, v = seeded(store, registry, poster)
    n = len(store.audit_log())
    with pytest.raises(ContractError):
        store.review_decision(eid, "approve", "rev-1", "", "short", v)
    with pytest.raises(KeyError):
        store.review_decision("evt_missing", "approve", "rev-1", "", D2, 1)
    with pytest.raises(PermissionError):
        store.review_decision(eid, "approve", "  ", "", D3, v)
    assert store.decisions() == [] and len(store.audit_log()) == n


def test_apply_decisions_directory_replay_stale_and_invalid(store, registry, poster, tmp_path):
    eid, v = seeded(store, registry, poster)
    d = tmp_path / "decisions"; d.mkdir()
    rows = {
        "ok": {"decision_id": D1, "event_id": eid, "decision": "approve", "reviewer": "u-1", "version_seen": v, "decided_at": "1"},
        "stale": {"decision_id": D2, "event_id": eid, "decision": "reject", "reviewer": "u-2", "version_seen": v, "decided_at": "2"},
        "nover": {"decision_id": D3, "event_id": eid, "decision": "reject", "reviewer": "u-2", "decided_at": "3"},
        "ghost": {"decision_id": "dec-ghost-0001", "event_id": "evt_nope", "decision": "approve", "reviewer": "u-1", "version_seen": 1, "decided_at": "4"},
    }
    for k, r in rows.items():
        (d / f"{k}.json").write_text(json.dumps(r))
    (d / "broken.json").write_text("{not json")
    first = store.apply_decisions(d)
    assert first == {"applied": 1, "skipped_duplicate": 0, "rejected": 3, "stale": 1}, first
    assert store.get_event(eid).review_status == "approved"
    assert store.apply_decisions(d)["applied"] == 0                       # replay of the whole directory
    assert [h["decision_id"] for h in store.decisions(eid)] == [D1]
    assert_consistent(store, eid)


# --- atomicity / interrupted ingestion / recovery ---------------------------------------------
def test_interrupted_ingestion_rolls_back_and_recovers(store, registry, poster, monkeypatch):
    p = poster("a.png", POSTER_A, 1)
    original = RadarStore.put_event

    def boom(self, ev, expected_version=None):
        raise RuntimeError("simulated crash mid-ingest")

    monkeypatch.setattr(RadarStore, "put_event", boom)
    with pytest.raises(RuntimeError):
        run_upload(store, registry, p, "src-upload-1", P)
    # evidence was captured, but nothing half-written: no event, venue, party, link, or audit row
    assert len(store.all_evidence()) == 1
    assert store.events() == [] and store.venues() == [] and store.parties() == []
    assert [a for a in store.audit_log() if a["action"] != "extraction_skipped"] == []
    monkeypatch.setattr(RadarStore, "put_event", original)
    out = run_upload(store, registry, p, "src-upload-1", P)                # re-run = recovery
    assert out["event_id"] and len(store.events()) == 1 and len(store.all_evidence()) == 1


# --- local migration + rollback ---------------------------------------------------------------
def test_local_migration_backs_up_backfills_and_is_rollbackable(tmp_path):
    root = tmp_path / "legacy"; root.mkdir()
    db = sqlite3.connect(root / "radar.sqlite3")
    db.executescript("CREATE TABLE events(event_id TEXT PRIMARY KEY, doc TEXT NOT NULL);"
                     "CREATE TABLE evidence(observation_id TEXT PRIMARY KEY, doc TEXT NOT NULL);")
    db.execute("INSERT INTO events VALUES('evt_legacy','{}')"); db.commit(); db.close()
    s = RadarStore(root)
    bak = root / "radar.sqlite3.pre-zr01.bak"
    assert bak.exists()
    assert s.event_version("evt_legacy") == 1                                # backfilled
    assert s.db.execute("SELECT doc FROM events WHERE event_id='evt_legacy'").fetchone()[0] == "{}"
    s.db.execute("INSERT OR REPLACE INTO events VALUES('evt_legacy','{\"x\":1}')")   # old-style writer still works
    s.close()
    chk = sqlite3.connect(bak)                                               # rollback artifact = pre-migration state
    assert chk.execute("SELECT 1 FROM sqlite_master WHERE name='event_versions'").fetchone() is None
    assert chk.execute("SELECT doc FROM events").fetchone()[0] == "{}"
    chk.close()
    RadarStore(root).close()                                                 # second open: no new backup, no error
    assert len(list(root.glob("*.bak"))) == 1


def test_feed_exports_event_version(store, registry, poster):
    eid, v = seeded(store, registry, poster)
    assert store.export_feed()["events"][0]["version"] == v


def test_ingestion_holding_write_lock_forces_concurrent_approval_to_be_stale(tmp_path, registry, poster, monkeypatch):
    """Deterministic opposite interleaving: ingestion is mid-transaction when the reviewer (who saw version v)
    submits. The reviewer blocks on the write lock, then must be rejected as stale; the approval must not apply."""
    import time
    base = tmp_path / "lock"
    s0 = RadarStore(base)
    eid, v = seeded(s0, registry, poster)
    pb = poster("b.png", POSTER_B, 2)
    inside, reviewer_started = threading.Event(), threading.Event()
    original, out = RadarStore.put_event, {}

    def slow_put(self, ev, expected_version=None):
        if threading.current_thread().name == "ingest":
            inside.set()
            assert reviewer_started.wait(10)
            time.sleep(0.3)               # reviewer is now blocked on BEGIN IMMEDIATE
        return original(self, ev, expected_version)

    monkeypatch.setattr(RadarStore, "put_event", slow_put)

    def ingest():
        st = RadarStore(base)
        out["ingest"] = run_upload(st, registry, pb, "src-upload-2", P)
        st.close()

    def review():
        st = RadarStore(base)
        assert inside.wait(10)
        reviewer_started.set()
        try:
            st.review_decision(eid, "approve", "rev-1", decision_id=D1, expected_version=v)
            out["review"] = "applied"
        except StaleWrite:
            out["review"] = "stale"
        st.close()

    ts = [threading.Thread(target=ingest, name="ingest"), threading.Thread(target=review, name="review")]
    [t.start() for t in ts]; [t.join(30) for t in ts]
    assert out["review"] == "stale"
    ev = s0.get_event(eid)
    assert ev.review_status == "pending" and len(ev.evidence_references) == 2 and s0.decisions(eid) == []
    assert not [a for a in s0.audit_log() if a["action"] == "review:approve"]
