"""Operability: backup / verify / restore, store integrity check, manifest batch ingest."""
import csv
import json
import sqlite3

import pytest

from ana_engine import ops
from ana_engine.cli import main as cli
from ana_engine.pg_sync import canonical, diff
from ana_engine.pipeline import run_upload
from ana_engine.store import RadarStore
from conftest import POSTER_A, POSTER_B, make_png
from scout_fabric.text_providers import SidecarTextProvider

P = SidecarTextProvider()


@pytest.fixture
def full(store, registry, poster):
    a = run_upload(store, registry, poster("a.png", POSTER_A, 1), "src-upload-1", P)["event_id"]
    run_upload(store, registry, poster("b.png", POSTER_B, 2), "src-upload-2", P)
    store.review_decision(a, "approve", "operator:Awa", "", "dec-ops-0001-aaaa", store.event_version(a))
    return store


def test_verify_store_clean_then_detects_each_kind_of_damage(full):
    res = ops.verify_store(full)
    assert res["ok"] and res["counts"]["evidence"] == 2 and res["counts"]["events"] == 1
    media = sorted(full.media_dir.iterdir())
    original = media[0].read_bytes()
    media[0].write_bytes(original + b"x")                                           # altered evidence
    assert any("hash does not match" in p for p in ops.verify_store(full)["problems"])
    media[0].unlink()                                                               # missing evidence
    assert any("media file missing" in p for p in ops.verify_store(full)["problems"])
    media[0].write_bytes(original)
    (full.media_dir / ("f" * 64 + ".png")).write_bytes(b"\x89PNG stray")           # orphan
    assert any("orphan media" in p for p in ops.verify_store(full)["problems"])
    (full.media_dir / ("f" * 64 + ".png")).unlink()
    assert ops.verify_store(full)["ok"]
    eid = full.events()[0].event_id
    full.db.execute("UPDATE events SET doc = json_set(doc, '$.review_status', 'rejected') WHERE event_id=?", (eid,))
    assert any("disagrees with last decision" in p for p in ops.verify_store(full)["problems"])
    full.db.execute("INSERT INTO obs_event VALUES('dangling','evt_nope')")
    assert any("dangling" in p for p in ops.verify_store(full)["problems"])


def test_backup_verifies_restores_and_round_trips_exactly(full, tmp_path):
    bdir = tmp_path / "bk"
    m = ops.backup(full.root, bdir)
    assert m["media_files"] == 2 and ops.verify_backup(bdir) == []
    with pytest.raises(FileExistsError):
        ops.backup(full.root, bdir)                                                 # never overwrite a backup
    target = tmp_path / "restored"
    assert ops.restore(bdir, target) is None
    r = RadarStore(target)
    assert diff(canonical(full), canonical(r)) == [] and ops.verify_store(r)["ok"]
    r.close()


def test_tampered_backup_is_refused_and_existing_data_is_protected(full, tmp_path):
    bdir = tmp_path / "bk"
    ops.backup(full.root, bdir)
    next((bdir / "media").iterdir()).write_bytes(b"corrupted")
    assert any("hash mismatch" in p for p in ops.verify_backup(bdir))
    with pytest.raises(ValueError):
        ops.restore(bdir, tmp_path / "x")
    good = tmp_path / "bk2"
    ops.backup(full.root, good)
    with pytest.raises(FileExistsError):
        ops.restore(good, full.root)                                                # live data: refuses without force
    aside = ops.restore(good, full.root, force=True)                                # moved aside, not deleted
    assert aside and (aside / "radar.sqlite3").is_file() and (aside / "media").is_dir()


def test_backup_is_consistent_while_a_writer_is_active(full, tmp_path, registry, poster):
    full.db.execute("BEGIN IMMEDIATE")                                              # another process mid-transaction
    full.db.execute("INSERT INTO audit(at,actor,action,subject,detail) VALUES('x','y','uncommitted','z','{}')")
    ops.backup(full.root, tmp_path / "bk")                                          # uses the backup API: sees committed data only
    full.db.execute("ROLLBACK")
    chk = sqlite3.connect(tmp_path / "bk" / "radar.sqlite3")
    assert chk.execute("SELECT COUNT(*) FROM audit WHERE action='uncommitted'").fetchone()[0] == 0


def make_inbox(tmp_path, rows):
    inbox = tmp_path / "inbox"; inbox.mkdir()
    make_png(inbox / "good.png", 1); (inbox / "good.png.txt").write_text(POSTER_A)
    make_png(inbox / "two.png", 2); (inbox / "two.txt").write_text("BRUNCH\n20/12/2026\nLieu : Bar Fictif\n")
    (inbox / "bad.png").write_bytes(b"not an image")
    m = tmp_path / "manifest.csv"
    with open(m, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "source_id", "permission_note", "source_url", "transcription_file"]); w.writeheader(); w.writerows(rows)
    return inbox, m


def test_manifest_ingest_enforces_permission_and_reports_every_row(store, registry, tmp_path):
    ok = "Organizer replied by email 2026-11-01 granting use of this poster"
    inbox, m = make_inbox(tmp_path, [
        {"file": "good.png", "source_id": "src-upload-1", "permission_note": ok, "source_url": "https://www.facebook.com/example/posts/1"},
        {"file": "two.png", "source_id": "src-upload-1", "permission_note": ok, "transcription_file": "two.txt"},
        {"file": "good.png", "source_id": "src-upload-1", "permission_note": "", "source_url": ""},          # no permission
        {"file": "../escape.png", "source_id": "src-upload-1", "permission_note": ok},                       # traversal
        {"file": "bad.png", "source_id": "src-upload-1", "permission_note": ok},                             # not an image
        {"file": "good.png", "source_id": "src-pending", "permission_note": ok},                             # unauthorized source
        {"file": "good.png", "source_id": "src-upload-1", "permission_note": ok, "source_url": "javascript:alert(1)"}])
    tally = ops.ingest_manifest(store, registry, m, inbox, tmp_path / "report.csv")
    assert tally == {"ingested": 2, "duplicate": 0, "needs_transcription": 0, "rejected": 5}
    rows = list(csv.DictReader(open(tmp_path / "report.csv")))
    assert [r["status"] for r in rows] == ["ingested", "ingested", "rejected", "rejected", "rejected", "rejected", "rejected"]
    assert "permission_note is required" in rows[2]["message"] and "inside the inbox" in rows[3]["message"] and "pending" in rows[5]["message"]
    ev = store.all_evidence()
    assert {e["metadata"]["permission_note"] for e in ev} == {ok} and ev[0]["source_url"] == "https://www.facebook.com/example/posts/1"
    assert ev[1]["evidence_state"] == "unverified" and len(store.events()) == 2
    again = ops.ingest_manifest(store, registry, m, inbox, tmp_path / "report2.csv")              # re-run is idempotent
    assert again["ingested"] == 0 and again["duplicate"] == 2 and len(store.events()) == 2 and len(store.all_evidence()) == 2


def test_manifest_without_text_preserves_evidence_and_says_so(store, registry, tmp_path):
    inbox = tmp_path / "in"; inbox.mkdir(); make_png(inbox / "x.png", 7)
    m = tmp_path / "m.csv"; m.write_text("file,source_id,permission_note\nx.png,src-upload-1,agreed in person\n")
    import shutil
    from unittest import mock
    with mock.patch.object(shutil, "which", return_value=None):                    # no tesseract: nothing can read the poster
        tally = ops.ingest_manifest(store, registry, m, inbox, tmp_path / "r.csv")
    assert tally["needs_transcription"] == 1 and len(store.all_evidence()) == 1 and store.events() == []


def test_cli_backup_verify_restore_round_trip(full, tmp_path, capsys):
    root = str(full.root)
    assert cli(["--data", root, "backup", "--out", str(tmp_path / "b")]) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["media_files"] == 2
    assert cli(["--data", root, "verify-backup", str(tmp_path / "b")]) == 0
    assert cli(["--data", str(tmp_path / "new"), "restore", str(tmp_path / "b")]) == 0
    assert cli(["--data", str(tmp_path / "new"), "verify"]) == 0
    assert cli(["--data", root, "restore", str(tmp_path / "b")]) == 5              # refuses to clobber live data
