"""Local persistence for the radar graph (SQLite, stdlib). Same logical shape as the Supabase
migration in supabase/migrations/*radar*.sql, which is NOT applied by this code.

Documents are JSON; uniqueness constraints give idempotency; every state change is audited.
"""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from radar_contracts import (
    CITY,
    TIMEZONE,
    ContractError,
    Event,
    EvidenceRecord,
    FieldClaim,
    Party,
    Venue,
    validate_event,
    validate_evidence,
    validate_venue,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence(observation_id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS venues(venue_id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS parties(party_id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS obs_event(observation_id TEXT PRIMARY KEY, event_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, actor TEXT,
  action TEXT, subject TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS event_versions(event_id TEXT PRIMARY KEY, version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS decisions(decision_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, decision TEXT NOT NULL,
  reviewer TEXT NOT NULL, note TEXT, version_seen INTEGER, version_after INTEGER, resulting_status TEXT,
  kind TEXT NOT NULL DEFAULT 'human', at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decision_rejections(decision_id TEXT PRIMARY KEY, reason TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS applied_decisions(decision_id TEXT PRIMARY KEY, applied_at TEXT);
CREATE TABLE IF NOT EXISTS failures(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, source_id TEXT,
  reason TEXT, alternative TEXT);
"""


class StaleWrite(RuntimeError):
    """The event changed since the caller read it; nothing was written."""


class DecisionConflict(ValueError):
    """A decision_id was reused with a different payload."""


DECISION_STATUS = {"approve": "approved", "reject": "rejected", "request_correction": "correction_requested"}
DECISION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{7,63}$")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _claim_from(d: dict[str, Any]) -> FieldClaim:
    return FieldClaim(d["field"], d["value"], d["state"], tuple(d["evidence_ids"]),
                      d.get("snippet"), d.get("method", "unknown"))


def event_from_doc(d: dict[str, Any]) -> Event:
    d = dict(d)
    d["field_claims"] = [_claim_from(c) for c in d["field_claims"]]
    return Event(**d)


class RadarStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.media_dir = self.root / "media"
        dbfile = self.root / "radar.sqlite3"
        self._backup_before_migration(dbfile)
        # autocommit mode: transactions are explicit (see transaction()); busy timeout serializes writers
        self.db = sqlite3.connect(dbfile, isolation_level=None, timeout=30)
        self._depth = 0
        self.db.executescript(SCHEMA)
        # local migration v1 -> v2: version every pre-existing event at 1 (idempotent)
        self.db.execute("INSERT OR IGNORE INTO event_versions SELECT event_id, 1 FROM events")

    @staticmethod
    def _backup_before_migration(dbfile: Path) -> None:
        """If an existing pre-ZR-01 database is opened, keep a consistent copy first (rollback = restore it)."""
        bak = dbfile.with_name(dbfile.name + ".pre-zr01.bak")
        if not dbfile.exists() or bak.exists():
            return
        src = sqlite3.connect(dbfile)
        try:
            has = src.execute("SELECT 1 FROM sqlite_master WHERE name='event_versions'").fetchone()
            if not has:
                dst = sqlite3.connect(bak)
                src.backup(dst)
                dst.close()
        finally:
            src.close()

    @contextmanager
    def transaction(self):
        """Atomic, write-locked unit of work (re-entrant). Any exception rolls everything back."""
        if self._depth == 0:
            self.db.execute("BEGIN IMMEDIATE")
        self._depth += 1
        try:
            yield
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self.db.execute("ROLLBACK")
            raise
        else:
            self._depth -= 1
            if self._depth == 0:
                self.db.execute("COMMIT")

    def close(self) -> None:
        self.db.close()

    # ---- audit / failures ------------------------------------------------------------------
    def audit(self, actor: str, action: str, subject: str, detail: dict | None = None) -> None:
        self.db.execute("INSERT INTO audit(at,actor,action,subject,detail) VALUES(?,?,?,?,?)",
                        (now_iso(), actor, action, subject, json.dumps(detail or {})))

    def audit_log(self) -> list[dict]:
        cur = self.db.execute("SELECT at,actor,action,subject,detail FROM audit ORDER BY id")
        return [dict(zip(("at", "actor", "action", "subject", "detail"), r)) for r in cur]

    def record_failure(self, source_id: str, reason: str, alternative: str) -> None:
        self.db.execute("INSERT INTO failures(at,source_id,reason,alternative) VALUES(?,?,?,?)",
                        (now_iso(), source_id, reason, alternative))

    def failures(self) -> list[dict]:
        cur = self.db.execute("SELECT at,source_id,reason,alternative FROM failures ORDER BY id")
        return [dict(zip(("at", "source_id", "reason", "alternative"), r)) for r in cur]

    # ---- evidence --------------------------------------------------------------------------
    def add_evidence(self, ev: EvidenceRecord) -> bool:
        validate_evidence(ev)
        cur = self.db.execute("INSERT OR IGNORE INTO evidence VALUES(?,?)",
                              (ev.observation_id, json.dumps(ev.to_dict())))
        return cur.rowcount == 1

    def get_evidence(self, observation_id: str) -> dict | None:
        r = self.db.execute("SELECT doc FROM evidence WHERE observation_id=?", (observation_id,)).fetchone()
        return json.loads(r[0]) if r else None

    def all_evidence(self) -> list[dict]:
        return [json.loads(r[0]) for r in self.db.execute("SELECT doc FROM evidence ORDER BY rowid")]

    def event_for_observation(self, observation_id: str) -> str | None:
        r = self.db.execute("SELECT event_id FROM obs_event WHERE observation_id=?", (observation_id,)).fetchone()
        return r[0] if r else None

    def link_observation(self, observation_id: str, event_id: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO obs_event VALUES(?,?)", (observation_id, event_id))

    # ---- events / venues / parties ---------------------------------------------------------
    def event_version(self, event_id: str) -> int | None:
        r = self.db.execute("SELECT version FROM event_versions WHERE event_id=?", (event_id,)).fetchone()
        if r:
            return r[0]
        if self.db.execute("SELECT 1 FROM events WHERE event_id=?", (event_id,)).fetchone():
            self.db.execute("INSERT OR IGNORE INTO event_versions VALUES(?,1)", (event_id,))  # legacy row
            return 1
        return None

    def put_event(self, ev: Event, expected_version: int | None = None) -> int:
        """Optimistic concurrency. expected_version=None creates a NEW event (fails if it exists);
        otherwise updates only if the stored version still equals expected_version. Returns new version."""
        validate_event(ev)
        doc = json.dumps(ev.to_dict())
        with self.transaction():
            cur = self.event_version(ev.event_id)
            if expected_version is None:
                if cur is not None:
                    raise StaleWrite(f"event {ev.event_id} already exists at version {cur}; "
                                     "re-read and pass expected_version")
                self.db.execute("INSERT INTO events VALUES(?,?)", (ev.event_id, doc))
                self.db.execute("INSERT INTO event_versions VALUES(?,1)", (ev.event_id,))
                return 1
            if cur != expected_version:
                raise StaleWrite(f"event {ev.event_id} is at version {cur}, caller saw {expected_version}")
            self.db.execute("UPDATE events SET doc=? WHERE event_id=?", (doc, ev.event_id))
            self.db.execute("UPDATE event_versions SET version=version+1 WHERE event_id=?", (ev.event_id,))
            return expected_version + 1

    def get_event(self, event_id: str) -> Event | None:
        r = self.db.execute("SELECT doc FROM events WHERE event_id=?", (event_id,)).fetchone()
        return event_from_doc(json.loads(r[0])) if r else None

    def events(self) -> list[Event]:
        return [event_from_doc(json.loads(r[0])) for r in self.db.execute("SELECT doc FROM events ORDER BY rowid")]

    def put_venue(self, v: Venue) -> None:
        validate_venue(v)
        self.db.execute("INSERT OR REPLACE INTO venues VALUES(?,?)", (v.venue_id, json.dumps(v.to_dict())))

    def venues(self) -> list[Venue]:
        return [Venue(**json.loads(r[0])) for r in self.db.execute("SELECT doc FROM venues ORDER BY rowid")]

    def get_venue(self, venue_id: str) -> Venue | None:
        r = self.db.execute("SELECT doc FROM venues WHERE venue_id=?", (venue_id,)).fetchone()
        return Venue(**json.loads(r[0])) if r else None

    def put_party(self, p: Party) -> None:
        self.db.execute("INSERT OR REPLACE INTO parties VALUES(?,?)", (p.party_id, json.dumps(p.to_dict())))

    def parties(self) -> list[Party]:
        return [Party(**json.loads(r[0])) for r in self.db.execute("SELECT doc FROM parties ORDER BY rowid")]

    # ---- human review ----------------------------------------------------------------------
    def review_decision(self, event_id: str, decision: str, reviewer: str, note: str = "",
                        decision_id: str | None = None,
                        expected_version: int | None = None) -> tuple[Event, str]:
        """Record one human decision atomically (state + decision row + audit row in one transaction).
        Returns (event, "applied"|"duplicate"). Raises StaleWrite / DecisionConflict / KeyError / ContractError.
        decision_id is the caller's idempotency key: replaying it changes nothing and audits nothing."""
        if decision not in DECISION_STATUS:
            raise ContractError(f"decision must be one of {sorted(DECISION_STATUS)}")
        if not reviewer or not reviewer.strip():
            raise PermissionError("a named human reviewer is required")
        decision_id = decision_id or str(uuid.uuid4())
        if not DECISION_ID_RE.match(decision_id):
            raise ContractError("decision_id must be 8-64 chars of [A-Za-z0-9-]")
        with self.transaction():
            row = self.db.execute("SELECT event_id, decision, reviewer FROM decisions WHERE decision_id=?",
                                  (decision_id,)).fetchone()
            if row:
                if row != (event_id, decision, reviewer):
                    raise DecisionConflict(f"decision_id {decision_id} already used for a different decision")
                return self.get_event(event_id), "duplicate"
            if self.db.execute("SELECT 1 FROM applied_decisions WHERE decision_id=?", (decision_id,)).fetchone():
                return self.get_event(event_id), "duplicate"  # legacy (pre-ZR-01) application record
            ev = self.get_event(event_id)
            if ev is None:
                raise KeyError(event_id)
            seen = self.event_version(event_id)
            if expected_version is not None and expected_version != seen:
                raise StaleWrite(f"event {event_id} is at version {seen}, reviewer saw {expected_version}")
            before = ev.review_status
            ev.review_status = DECISION_STATUS[decision]
            after = self.put_event(ev, expected_version=seen)
            self.db.execute("INSERT INTO decisions VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (decision_id, event_id, decision, reviewer, note, expected_version, after,
                             ev.review_status, "human", now_iso()))
            self.audit(reviewer, f"review:{decision}", event_id,
                       {"decision_id": decision_id, "from": before, "to": ev.review_status,
                        "version": after, "note": note})
            return ev, "applied"

    def review(self, event_id: str, decision: str, reviewer: str, note: str = "",
               decision_id: str | None = None, expected_version: int | None = None) -> Event:
        return self.review_decision(event_id, decision, reviewer, note, decision_id, expected_version)[0]

    def record_system_reopen(self, event_id: str, from_status: str, reason: str) -> None:
        """Explicit, audited, history-preserving transition back to pending (never a silent overwrite)."""
        sid = f"sys-{uuid.uuid4()}"
        self.db.execute("INSERT INTO decisions VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (sid, event_id, "reopen", "system:ana", reason, None, None, "pending", "system", now_iso()))
        self.audit("ana", "review_reopened", event_id, {"from": from_status, "reason": reason, "decision_id": sid})

    def decisions(self, event_id: str | None = None) -> list[dict]:
        q = "SELECT decision_id,event_id,decision,reviewer,note,version_seen,version_after,resulting_status,kind,at FROM decisions"
        cur = self.db.execute(q + (" WHERE event_id=?" if event_id else "") + " ORDER BY at, rowid",
                              (event_id,) if event_id else ())
        keys = ("decision_id", "event_id", "decision", "reviewer", "note", "version_seen", "version_after",
                "resulting_status", "kind", "at")
        return [dict(zip(keys, r)) for r in cur]

    def apply_decisions(self, source: Path) -> dict[str, int]:
        """Apply human decisions exported by PULSE (a directory of <decision_id>.json files, or a JSONL file).
        Each row needs decision_id, event_id, decision, reviewer (server-derived id) and version_seen.
        Idempotent per decision_id; stale or invalid rows are rejected, counted and audited, never guessed at."""
        out = {"applied": 0, "skipped_duplicate": 0, "rejected": 0, "stale": 0}
        source = Path(source)
        if not source.exists():
            return out
        if source.is_dir():
            items = [(f.name, f.read_text(encoding="utf-8")) for f in sorted(source.glob("*.json"))]
        else:
            items = [(f"line{i}", ln) for i, ln in enumerate(source.read_text(encoding="utf-8").splitlines())]
        parsed = []
        for name, text in items:
            if not text.strip():
                continue
            try:
                parsed.append((name, json.loads(text)))
            except json.JSONDecodeError:
                out["rejected"] += 1
                self.audit("system", "decision_rejected", name, {"error": "JSONDecodeError"})
        parsed.sort(key=lambda t: (str(t[1].get("decided_at", "")) if isinstance(t[1], dict) else "", t[0]))
        for name, d in parsed:
            did = str(d.get("decision_id", "")) if isinstance(d, dict) else ""
            if did and self.db.execute("SELECT 1 FROM decision_rejections WHERE decision_id=?", (did,)).fetchone():
                out["skipped_duplicate"] += 1          # already rejected once: no second count, no second audit row
                continue
            try:
                if "version_seen" not in d:
                    raise ValueError("version_seen is required")
                _, status = self.review_decision(d["event_id"], d["decision"], d["reviewer"], d.get("note", ""),
                                                 d["decision_id"], int(d["version_seen"]))
                out["applied" if status == "applied" else "skipped_duplicate"] += 1
            except StaleWrite as exc:
                out["stale"] += 1
                self._reject(did or name, "decision_rejected_stale", str(exc))
            except (KeyError, ValueError, PermissionError, TypeError, AttributeError, DecisionConflict) as exc:
                out["rejected"] += 1
                self._reject(did or name, "decision_rejected", type(exc).__name__)
        return out

    def _reject(self, key: str, action: str, reason: str) -> None:
        """Record a rejected decision once (keyed by decision_id) with one audit row."""
        with self.transaction():
            cur = self.db.execute("INSERT OR IGNORE INTO decision_rejections VALUES(?,?,?)", (key, reason, now_iso()))
            if cur.rowcount == 1:
                self.audit("system", action, key, {"error": reason})

    # ---- feed for PULSE --------------------------------------------------------------------
    def export_feed(self, generated_at: str | None = None) -> dict[str, Any]:
        venues = {v.venue_id: v for v in self.venues()}
        evidence = {e["observation_id"]: e for e in self.all_evidence()}
        parties = {p.party_id: p for p in self.parties()}
        events = []
        for ev in self.events():
            d = ev.to_dict()
            d["version"] = self.event_version(ev.event_id)
            d["venue"] = venues[ev.venue_id].to_dict() if ev.venue_id in venues else None
            d["organizer"] = parties[ev.organizer_id].to_dict() if ev.organizer_id in parties else None
            d["performers"] = [parties[p].to_dict() for p in ev.performer_ids if p in parties]
            d["evidence"] = [evidence[r] for r in ev.evidence_references if r in evidence]
            events.append(d)
        return {"contract_version": "1.0.0", "city": CITY, "timezone": TIMEZONE,
                "generated_at": generated_at or now_iso(), "events": events,
                "venues": [v.to_dict() for v in venues.values()],
                "review": {"pending": [e["event_id"] for e in events if e["review_status"] == "pending"]}}
