"""Local persistence for the radar graph (SQLite, stdlib). Same logical shape as the Supabase
migration in supabase/migrations/*radar*.sql, which is NOT applied by this code.

Documents are JSON; uniqueness constraints give idempotency; every state change is audited.
"""
from __future__ import annotations

import json
import sqlite3
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
CREATE TABLE IF NOT EXISTS failures(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, source_id TEXT,
  reason TEXT, alternative TEXT);
"""


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
        self.db = sqlite3.connect(self.root / "radar.sqlite3")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    # ---- audit / failures ------------------------------------------------------------------
    def audit(self, actor: str, action: str, subject: str, detail: dict | None = None) -> None:
        self.db.execute("INSERT INTO audit(at,actor,action,subject,detail) VALUES(?,?,?,?,?)",
                        (now_iso(), actor, action, subject, json.dumps(detail or {})))
        self.db.commit()

    def audit_log(self) -> list[dict]:
        cur = self.db.execute("SELECT at,actor,action,subject,detail FROM audit ORDER BY id")
        return [dict(zip(("at", "actor", "action", "subject", "detail"), r)) for r in cur]

    def record_failure(self, source_id: str, reason: str, alternative: str) -> None:
        self.db.execute("INSERT INTO failures(at,source_id,reason,alternative) VALUES(?,?,?,?)",
                        (now_iso(), source_id, reason, alternative))
        self.db.commit()

    def failures(self) -> list[dict]:
        cur = self.db.execute("SELECT at,source_id,reason,alternative FROM failures ORDER BY id")
        return [dict(zip(("at", "source_id", "reason", "alternative"), r)) for r in cur]

    # ---- evidence --------------------------------------------------------------------------
    def add_evidence(self, ev: EvidenceRecord) -> bool:
        validate_evidence(ev)
        cur = self.db.execute("INSERT OR IGNORE INTO evidence VALUES(?,?)",
                              (ev.observation_id, json.dumps(ev.to_dict())))
        self.db.commit()
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
        self.db.commit()

    # ---- events / venues / parties ---------------------------------------------------------
    def put_event(self, ev: Event) -> None:
        validate_event(ev)
        self.db.execute("INSERT OR REPLACE INTO events VALUES(?,?)", (ev.event_id, json.dumps(ev.to_dict())))
        self.db.commit()

    def get_event(self, event_id: str) -> Event | None:
        r = self.db.execute("SELECT doc FROM events WHERE event_id=?", (event_id,)).fetchone()
        return event_from_doc(json.loads(r[0])) if r else None

    def events(self) -> list[Event]:
        return [event_from_doc(json.loads(r[0])) for r in self.db.execute("SELECT doc FROM events ORDER BY rowid")]

    def put_venue(self, v: Venue) -> None:
        validate_venue(v)
        self.db.execute("INSERT OR REPLACE INTO venues VALUES(?,?)", (v.venue_id, json.dumps(v.to_dict())))
        self.db.commit()

    def venues(self) -> list[Venue]:
        return [Venue(**json.loads(r[0])) for r in self.db.execute("SELECT doc FROM venues ORDER BY rowid")]

    def get_venue(self, venue_id: str) -> Venue | None:
        r = self.db.execute("SELECT doc FROM venues WHERE venue_id=?", (venue_id,)).fetchone()
        return Venue(**json.loads(r[0])) if r else None

    def put_party(self, p: Party) -> None:
        self.db.execute("INSERT OR REPLACE INTO parties VALUES(?,?)", (p.party_id, json.dumps(p.to_dict())))
        self.db.commit()

    def parties(self) -> list[Party]:
        return [Party(**json.loads(r[0])) for r in self.db.execute("SELECT doc FROM parties ORDER BY rowid")]

    # ---- human review ----------------------------------------------------------------------
    def review(self, event_id: str, decision: str, reviewer: str, note: str = "") -> Event:
        mapping = {"approve": "approved", "reject": "rejected", "request_correction": "correction_requested"}
        if decision not in mapping:
            raise ContractError(f"decision must be one of {sorted(mapping)}")
        if not reviewer or not reviewer.strip():
            raise PermissionError("a named human reviewer is required")
        ev = self.get_event(event_id)
        if ev is None:
            raise KeyError(event_id)
        before = ev.review_status
        ev.review_status = mapping[decision]
        self.put_event(ev)
        self.audit(reviewer, f"review:{decision}", event_id, {"from": before, "to": ev.review_status, "note": note})
        return ev

    # ---- feed for PULSE --------------------------------------------------------------------
    def export_feed(self, generated_at: str | None = None) -> dict[str, Any]:
        venues = {v.venue_id: v for v in self.venues()}
        evidence = {e["observation_id"]: e for e in self.all_evidence()}
        parties = {p.party_id: p for p in self.parties()}
        events = []
        for ev in self.events():
            d = ev.to_dict()
            d["venue"] = venues[ev.venue_id].to_dict() if ev.venue_id in venues else None
            d["organizer"] = parties[ev.organizer_id].to_dict() if ev.organizer_id in parties else None
            d["performers"] = [parties[p].to_dict() for p in ev.performer_ids if p in parties]
            d["evidence"] = [evidence[r] for r in ev.evidence_references if r in evidence]
            events.append(d)
        return {"contract_version": "1.0.0", "city": CITY, "timezone": TIMEZONE,
                "generated_at": generated_at or now_iso(), "events": events,
                "venues": [v.to_dict() for v in venues.values()],
                "review": {"pending": [e["event_id"] for e in events if e["review_status"] == "pending"]}}
