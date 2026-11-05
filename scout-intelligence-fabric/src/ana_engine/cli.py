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
    s = sub.add_parser("pg-backfill-sql", help="GENERATE (never run) an idempotent SQLite->PostgreSQL backfill script")
    s.add_argument("--output", required=True)
    s = sub.add_parser("pg-reconcile", help="compare this SQLite store with PostgreSQL via a read-only psql command")
    s.add_argument("--psql", required=True, help='e.g. "psql -d <db>" (SELECT statements only are issued)')
    s = sub.add_parser("export-feed"); s.add_argument("--output", default="-")
    a = ap.parse_args(argv)

    root = Path(a.data)
    registry = SourceRegistry(root / "sources.json")
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
        if a.cmd == "pg-backfill-sql":
            write_atomic(Path(a.output), backfill_sql(store)); print("wrote", a.output); return 0
        if a.cmd == "pg-reconcile":
            diffs = diff(canonical(store), pg_canonical(psql_runner(a.psql)))
            print(json.dumps({"parity": not diffs, "differences": diffs}, indent=2)); return 0 if not diffs else 4
        if a.cmd == "apply-decisions":
            print(json.dumps(store.apply_decisions(Path(a.file)))); return 0
        if a.cmd == "export-feed":
            out = json.dumps(store.export_feed(), indent=2, ensure_ascii=False)
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
