"""Operations: backup / verify-backup / restore, store integrity check, manifest-driven batch ingest."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from scout_fabric.sources import SourceRegistry, UnauthorizedSource
from scout_fabric.text_providers import ChainProvider, SidecarTextProvider, StaticTextProvider, TesseractProvider

from .pipeline import run_upload
from .store import RadarStore

DB_NAME = "radar.sqlite3"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------ backup / restore
def backup(data_root: Path, dest: Path) -> dict:
    """Consistent online backup of the database (SQLite backup API; safe while the operator app runs) + media, with a
    sha256 manifest. Refuses to write into a non-empty directory."""
    data_root, dest = Path(data_root), Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"{dest} is not empty")
    dest.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(data_root / DB_NAME)
    dst = sqlite3.connect(dest / DB_NAME)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    media_dir = data_root / "media"
    if media_dir.is_dir():
        (dest / "media").mkdir()
        for f in sorted(media_dir.iterdir()):
            if f.is_file():
                shutil.copy2(f, dest / "media" / f.name)
    for extra in ("sources.json",):
        if (data_root / extra).is_file():
            shutil.copy2(data_root / extra, dest / extra)
    files = {str(p.relative_to(dest)): sha256_file(p) for p in sorted(dest.rglob("*")) if p.is_file()}
    manifest = {"created_at": datetime.now(UTC).isoformat(), "files": files, "media_files": sum(1 for k in files if k.startswith("media/"))}
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def verify_backup(src: Path) -> list[str]:
    src = Path(src)
    try:
        manifest = json.loads((src / "manifest.json").read_text())
    except (OSError, json.JSONDecodeError):
        return ["manifest.json missing or unreadable"]
    problems = []
    for rel, digest in manifest["files"].items():
        p = src / rel
        if not p.is_file():
            problems.append(f"missing: {rel}")
        elif sha256_file(p) != digest:
            problems.append(f"hash mismatch: {rel}")
    return problems


def restore(src: Path, data_root: Path, force: bool = False) -> Path | None:
    """Restore a verified backup. An existing database is moved aside (never deleted) and only with force=True."""
    src, data_root = Path(src), Path(data_root)
    problems = verify_backup(src)
    if problems:
        raise ValueError("backup failed verification: " + "; ".join(problems[:5]))
    aside = None
    if (data_root / DB_NAME).exists():
        if not force:
            raise FileExistsError(f"{data_root / DB_NAME} exists; pass force=True to move it aside and restore")
        aside = data_root / f"pre-restore-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
        aside.mkdir(parents=True)
        for name in (DB_NAME, f"{DB_NAME}-wal", f"{DB_NAME}-shm", "media", "sources.json"):
            if (data_root / name).exists():
                shutil.move(str(data_root / name), str(aside / name))
    data_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / DB_NAME, data_root / DB_NAME)
    if (src / "media").is_dir():
        shutil.copytree(src / "media", data_root / "media")
    if (src / "sources.json").is_file():
        shutil.copy2(src / "sources.json", data_root / "sources.json")
    return aside


# ------------------------------------------------------------------------------------------------ integrity
def verify_store(store: RadarStore) -> dict:
    """Read-only integrity check. Returns {"ok": bool, "problems": [...], "counts": {...}}."""
    db, problems = store.db, []
    chk = db.execute("PRAGMA integrity_check").fetchone()[0]
    if chk != "ok":
        problems.append(f"sqlite integrity_check: {chk}")
    evidence = {e["observation_id"]: e for e in store.all_evidence()}
    referenced = set()
    for oid, e in evidence.items():
        ref = e.get("raw_media_reference")
        f = store.root / ref if ref else None
        if not f or not f.is_file():
            problems.append(f"evidence {oid[:12]}: media file missing ({ref})")
        elif sha256_file(f) != e["content_hash"]:
            problems.append(f"evidence {oid[:12]}: media hash does not match content_hash (file altered or corrupt)")
        if ref:
            referenced.add(Path(ref).name)
    if store.media_dir.is_dir():
        for f in store.media_dir.iterdir():
            if f.is_file() and f.name not in referenced:
                problems.append(f"orphan media file (no evidence record): {f.name}")
    venues = {v.venue_id: v for v in store.venues()}
    events = store.events()
    for ev in events:
        for r in ev.evidence_references:
            if r not in evidence:
                problems.append(f"event {ev.event_id}: evidence {r[:12]} missing")
        if ev.venue_id and ev.venue_id not in venues:
            problems.append(f"event {ev.event_id}: venue {ev.venue_id} missing")
        elif ev.venue_id and venues[ev.venue_id].merged_into:
            problems.append(f"event {ev.event_id}: points at merged venue {ev.venue_id}")
        last = db.execute("SELECT resulting_status FROM decisions WHERE event_id=? ORDER BY version_after DESC, rowid DESC LIMIT 1",
                          (ev.event_id,)).fetchone()
        if last and last[0] != ev.review_status:
            problems.append(f"event {ev.event_id}: status {ev.review_status} disagrees with last decision {last[0]}")
        if store.event_version(ev.event_id) is None:
            problems.append(f"event {ev.event_id}: no version")
    for oid, eid in db.execute("SELECT observation_id, event_id FROM obs_event"):
        if oid not in evidence or store.get_event(eid) is None:
            problems.append(f"link {oid[:12]} -> {eid} is dangling")
    return {"ok": not problems, "problems": problems,
            "counts": {"evidence": len(evidence), "events": len(events), "venues": len(venues),
                       "decisions": db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]}}


# ------------------------------------------------------------------------------------------------ manifest ingest
MANIFEST_COLUMNS = ("file", "source_id", "permission_note")


def ingest_manifest(store: RadarStore, registry: SourceRegistry, manifest: Path, root: Path, report: Path) -> dict:
    """Batch ingest. CSV columns: file, source_id, permission_note (REQUIRED, written proof of authorization),
    optional: source_url, transcription_file. One bad row never stops the batch; every row gets a status."""
    manifest, root = Path(manifest), Path(root)
    with open(manifest, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows or any(c not in rows[0] for c in MANIFEST_COLUMNS):
        raise ValueError(f"manifest needs columns {MANIFEST_COLUMNS}")
    ocr = TesseractProvider()
    out_rows, tally = [], {"ingested": 0, "duplicate": 0, "needs_transcription": 0, "rejected": 0}
    for r in rows:
        rel, sid = (r.get("file") or "").strip(), (r.get("source_id") or "").strip()
        note = (r.get("permission_note") or "").strip()
        status, oid, eid, msg = "rejected", "", "", ""
        try:
            if not note:
                raise ValueError("permission_note is required (who authorized use of this poster, and how)")
            path = root / rel
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("file must be inside the inbox directory")
            tfile = (r.get("transcription_file") or "").strip()
            provider = StaticTextProvider((root / tfile).read_text(encoding="utf-8")) if tfile else \
                ChainProvider(SidecarTextProvider(), ocr)
            res = run_upload(store, registry, path, sid, provider, source_url=(r.get("source_url") or "").strip() or None,
                             extra_metadata={"permission_note": note, "batch": manifest.name})
            oid, eid = res["observation_id"], res["event_id"] or ""
            status = "duplicate" if not res["evidence_created"] else ("ingested" if eid else "needs_transcription")
            if status == "duplicate" and not eid:
                status = "needs_transcription"
            msg = "" if eid else "evidence preserved; no text could be read (install tesseract or supply transcription_file)"
        except UnauthorizedSource as exc:
            msg = f"{exc.reason}. {exc.alternative}"
        except Exception as exc:  # noqa: BLE001 - one bad row must not stop the batch
            msg = f"{type(exc).__name__}: {exc}"
        tally[status] += 1
        out_rows.append({"file": rel, "source_id": sid, "status": status, "observation_id": oid, "event_id": eid, "message": msg})
    report = Path(report)
    report.parent.mkdir(parents=True, exist_ok=True)
    with open(report, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "source_id", "status", "observation_id", "event_id", "message"])
        w.writeheader()
        w.writerows(out_rows)
    return tally
