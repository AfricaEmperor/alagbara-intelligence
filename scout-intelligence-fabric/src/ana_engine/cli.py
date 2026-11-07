"""`radar` CLI: operator entry point for the Event Radar loop. No outreach, no publishing."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

from scout_fabric.sources import Source, SourceRegistry, UnauthorizedSource
from scout_fabric.text_providers import ChainProvider, SidecarTextProvider, TesseractProvider

from . import ops
from .pg_sync import backfill_sql, canonical, diff, pg_canonical, psql_runner
from .pipeline import run_upload
from .store import DecisionConflict, RadarStore, StaleWrite


def write_atomic(dest: Path, text: str) -> None:
    """Write-then-rename so readers (PULSE) see either the complete old feed or the complete new one,
    never a truncated file, even if the process dies mid-write."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="radar")
    ap.add_argument("--data", default="radar-data", help="data directory (default ./radar-data)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("register-source"); s.add_argument("source_id"); s.add_argument("platform"); s.add_argument("label")
    s = sub.add_parser("approve-source"); s.add_argument("source_id"); s.add_argument("--by", required=True)
    s = sub.add_parser("ingest-upload"); s.add_argument("source_id"); s.add_argument("files", nargs="+")
    s = sub.add_parser("review"); s.add_argument("event_id"); s.add_argument("decision", choices=["approve", "reject", "request_correction"])
    s.add_argument("--by", required=True); s.add_argument("--note", default="")
    s.add_argument("--decision-id", default=None, help="idempotency key (generated and printed if omitted)")
    s.add_argument("--expected-version", type=int, default=None, help="reject if the event changed since you read it")
    s = sub.add_parser("apply-decisions"); s.add_argument("file")
    s = sub.add_parser("backup", help="consistent backup of database + media + manifest"); s.add_argument("--out", required=True)
    s = sub.add_parser("verify-backup"); s.add_argument("path")
    s = sub.add_parser("restore", help="restore a verified backup (existing data moved aside, only with --force)"); s.add_argument("path"); s.add_argument("--force", action="store_true")
    sub.add_parser("report", help="extraction quality measured from reviewer corrections (reviewed events only)")
    sub.add_parser("verify", help="read-only integrity check of the store (media hashes, links, decisions)")
    s = sub.add_parser("ingest-manifest", help="batch ingest from a CSV manifest (permission_note required per poster)")
    s.add_argument("manifest"); s.add_argument("--root", required=True); s.add_argument("--report", required=True)
    s = sub.add_parser("serve", help="start the local operator console (loopback only)")
    s.add_argument("--port", type=int, default=8750); s.add_argument("--feed", required=True, help="where Publish writes the approved feed")
    s.add_argument("--key", default=None, help="launch key (default: random, printed once)"); s.add_argument("--key-file", default=None)
    s.add_argument("--pulse-url", default=None)
    s = sub.add_parser("pg-backfill-sql", help="GENERATE (never run) an idempotent SQLite->PostgreSQL backfill script")
    s.add_argument("--output", required=True)
    s = sub.add_parser("pg-reconcile", help="compare this SQLite store with PostgreSQL via a read-only psql command")
    s.add_argument("--psql", required=True, help='e.g. "psql -d <db>" (SELECT statements only are issued)')
    s = sub.add_parser("export-feed"); s.add_argument("--output", default="-"); s.add_argument("--approved-only", action="store_true")
    a = ap.parse_args(argv)

    root = Path(a.data)
    registry = SourceRegistry(root / "sources.json")
    if a.cmd == "serve":
        from .operator_app import OperatorApp, run_server
        app = OperatorApp(root, Path(a.feed), a.key or os.environ.get("RADAR_OPERATOR_KEY"), a.pulse_url)
        if a.key_file:
            kf = Path(a.key_file); kf.parent.mkdir(parents=True, exist_ok=True); kf.write_text(app.key); os.chmod(kf, 0o600)
        srv = run_server(app, "127.0.0.1", a.port)
        print(f"AP-001 operator console: http://127.0.0.1:{srv.server_address[1]}/  (loopback only)\nLaunch key: {app.key}\nData: {root.resolve()}  Feed: {Path(a.feed).resolve()}", flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("stopped")
        return 0
    if a.cmd == "backup":
        m = ops.backup(root, Path(a.out)); print(json.dumps({"backup": a.out, "files": len(m["files"]), "media_files": m["media_files"]})); return 0
    if a.cmd == "verify-backup":
        pr = ops.verify_backup(Path(a.path)); print(json.dumps({"ok": not pr, "problems": pr})); return 0 if not pr else 5
    if a.cmd == "restore":
        try:
            aside = ops.restore(Path(a.path), root, a.force)
        except (FileExistsError, ValueError) as exc:
            print(f"refused: {exc}", file=sys.stderr); return 5
        print(json.dumps({"restored": True, "previous_data_moved_to": str(aside) if aside else None})); return 0
    if a.cmd == "register-source":
        registry.register(Source(a.source_id, a.platform, a.label)); print("registered (pending approval)")
        return 0
    if a.cmd == "approve-source":
        registry.approve(a.source_id, a.by); print("approved by", a.by)
        return 0
    store = RadarStore(root)
    try:
        if a.cmd == "ingest-upload":
            provider = ChainProvider(SidecarTextProvider(), TesseractProvider())
            rc = 0
            for f in a.files:
                try:
                    print(json.dumps(run_upload(store, registry, Path(f), a.source_id, provider)))
                except (UnauthorizedSource, ValueError) as exc:
                    print(json.dumps({"file": f, "rejected": str(exc)}), file=sys.stderr); rc = 2
            return rc
        if a.cmd == "review":
            did = a.decision_id or str(uuid.uuid4())
            try:
                ev, status = store.review_decision(a.event_id, a.decision, a.by, a.note, did, a.expected_version)
            except (StaleWrite, DecisionConflict) as exc:
                print(f"rejected: {exc}", file=sys.stderr); return 3
            print(ev.event_id, "->", ev.review_status, f"({status}, decision_id={did})")
            return 0
        if a.cmd == "report":
            print(json.dumps(ops.report(store), indent=2)); return 0
        if a.cmd == "verify":
            res = ops.verify_store(store); print(json.dumps(res, indent=2)); return 0 if res["ok"] else 6
        if a.cmd == "ingest-manifest":
            print(json.dumps(ops.ingest_manifest(store, registry, Path(a.manifest), Path(a.root), Path(a.report)))); return 0
        if a.cmd == "pg-backfill-sql":
            write_atomic(Path(a.output), backfill_sql(store)); print("wrote", a.output); return 0
        if a.cmd == "pg-reconcile":
            diffs = diff(canonical(store), pg_canonical(psql_runner(a.psql)))
            print(json.dumps({"parity": not diffs, "differences": diffs}, indent=2)); return 0 if not diffs else 4
        if a.cmd == "apply-decisions":
            print(json.dumps(store.apply_decisions(Path(a.file)))); return 0
        if a.cmd == "export-feed":
            out = json.dumps(store.export_feed(approved_only=a.approved_only), indent=2, ensure_ascii=False)
            if a.output == "-":
                print(out)
            else:
                write_atomic(Path(a.output), out)
            return 0
    finally:
        store.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
