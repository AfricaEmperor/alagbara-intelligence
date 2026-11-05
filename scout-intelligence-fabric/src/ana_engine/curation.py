"""Operator curation: corrections to extracted events, venue directory edits and merges.

Principles (all enforced by tests):
  * A correction is a NEW claim (state observed, method `human:correction`, evidence = the poster the human looked at).
    The original extraction is never edited or removed.
  * Conflicts a human has settled stay on record, marked resolved.
  * Correcting an already-decided event is an explicit, audited reopen (never silent).
  * Every operation is one transaction, versioned (stale rejected) and idempotent by a caller-supplied id.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date

from radar_contracts import EVENT_CATEGORIES, VENUE_TYPES, ContractError, FieldClaim, Venue, validate_contact, validate_link
from radar_contracts import validate_venue

from .pipeline import _party, confidence, find_conflicts, make_start_end, norm_name, resolve_venue
from .store import DecisionConflict, RadarStore, StaleWrite, now_iso

CORRECTABLE = ("title", "start_date", "start_time", "end_time", "venue", "district", "category", "organizer",
               "performer", "ticket", "description")
UNKNOWN_TOKEN = "!unknown"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{7,63}$")


def is_human(c: FieldClaim) -> bool:
    return c.method.startswith("human:")


def effective(claims: list[FieldClaim], field: str) -> FieldClaim | None:
    """The claim a reader should see: the latest human claim if any, otherwise the first machine claim with a value."""
    human = [c for c in claims if c.field == field and is_human(c)]
    if human:
        return human[-1]
    return next((c for c in claims if c.field == field and c.value), None)


def _val(c: FieldClaim | None) -> str | None:
    return c.value if c and c.value else None


def validate_change(field: str, value: str) -> str:
    v = value.strip()
    if field == "title" and not 1 <= len(v) <= 120:
        raise ContractError("title must be 1-120 characters")
    if field == "start_date":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ContractError("start_date must be YYYY-MM-DD")
        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ContractError("start_date is not a real calendar date") from exc
    if field in ("start_time", "end_time") and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
        raise ContractError(f"{field} must be HH:MM (00:00-23:59)")
    if field == "venue" and not 1 <= len(v) <= 80:
        raise ContractError("venue must be 1-80 characters")
    if field in ("district", "organizer") and not 1 <= len(v) <= 80:
        raise ContractError(f"{field} must be 1-80 characters")
    if field == "category" and v not in EVENT_CATEGORIES:
        raise ContractError(f"category must be one of {EVENT_CATEGORIES}")
    if field == "ticket" and not 1 <= len(v) <= 120:
        raise ContractError("ticket must be 1-120 characters")
    if field == "description" and not 1 <= len(v) <= 500:
        raise ContractError("description must be 1-500 characters")
    if field == "performer":
        names = [n.strip() for n in v.split(",") if n.strip()]
        if not 1 <= len(names) <= 12 or any(len(n) > 60 for n in names):
            raise ContractError("performers: 1-12 comma-separated names, each up to 60 characters")
        return ", ".join(names)
    return v


def _performers(claims: list[FieldClaim]) -> list[tuple[str, str]]:
    human = [c for c in claims if c.field == "performer" and is_human(c)]
    if human:
        if not human[-1].value:
            return []
        return [(n.strip(), "dj" if n.strip().upper().startswith("DJ") else "artist")
                for n in human[-1].value.split(",") if n.strip()]
    out, seen = [], set()
    for c in claims:
        if c.field == "performer" and c.value and not is_human(c) and norm_name(c.value) not in seen:
            seen.add(norm_name(c.value))
            out.append((c.value, "dj" if c.method.endswith(":dj") else "artist"))
    return out


def recompute(store: RadarStore, ev, evidence_id: str) -> None:
    """Derive every canonical field of the event from its claims (effective = latest human, else first machine)."""
    claims = ev.field_claims
    eff = {f: effective(claims, f) for f in CORRECTABLE}
    ev.title = _val(eff["title"])
    ev.description = _val(eff["description"])
    pseudo = [c for f in ("start_date", "start_time", "end_time") if (c := eff[f]) and c.value]
    ev.start_at, ev.end_at, _ = make_start_end(pseudo)
    if ev.status != "cancelled":
        ev.status = "scheduled" if ev.start_at else "unknown"
    vname = _val(eff["venue"])
    if vname:
        venue, _ = resolve_venue(store, vname, _val(eff["district"]), evidence_id)
        ev.venue_id = venue.venue_id
    else:
        ev.venue_id = None
    org = _val(eff["organizer"])
    ev.organizer_id = _party(store, org, "organizer", ev.event_id, evidence_id).party_id if org else None
    ev.performer_ids = [_party(store, n, role, ev.event_id, evidence_id).party_id for n, role in _performers(claims)]
    ev.event_category = _val(eff["category"])
    unknown = []
    for f, label in (("title", "title"), ("start_date", "start_date"), ("start_time", "start_time"), ("end_time", "end_time"),
                     ("venue", "venue"), ("district", "district"), ("organizer", "organizer"), ("ticket", "ticket"),
                     ("category", "category")):
        if not _val(eff[f]):
            unknown.append(label)
    if not ev.performer_ids:
        unknown.append("performer")
    ev.unknown_fields = sorted(unknown)
    ev.contradictions = find_conflicts(claims)


def apply_correction(store: RadarStore, event_id: str, changes: dict[str, str], reviewer: str, note: str,
                     correction_id: str, expected_version: int, evidence_id: str | None = None):
    """Returns (event, "applied"|"duplicate"). Raises StaleWrite / DecisionConflict / ContractError / KeyError."""
    if not reviewer or not reviewer.strip():
        raise PermissionError("a named human reviewer is required")
    if not ID_RE.match(correction_id or ""):
        raise ContractError("correction_id must be 8-64 chars of [A-Za-z0-9-]")
    if not changes:
        raise ContractError("no changes supplied")
    for f in changes:
        if f not in CORRECTABLE:
            raise ContractError(f"field {f!r} cannot be corrected")
    cleaned = {f: (None if v.strip() == UNKNOWN_TOKEN else validate_change(f, v)) for f, v in changes.items()}
    payload = json.dumps(cleaned, sort_keys=True)
    with store.transaction():
        row = store.db.execute("SELECT event_id, reviewer, changes FROM corrections WHERE correction_id=?",
                               (correction_id,)).fetchone()
        if row:
            if row != (event_id, reviewer, payload):
                raise DecisionConflict(f"correction_id {correction_id} already used for a different correction")
            return store.get_event(event_id), "duplicate"
        ev = store.get_event(event_id)
        if ev is None:
            raise KeyError(event_id)
        seen = store.event_version(event_id)
        if expected_version != seen:
            raise StaleWrite(f"event {event_id} is at version {seen}, reviewer saw {expected_version}")
        evid = evidence_id or ev.evidence_references[0]
        if evid not in ev.evidence_references:
            raise ContractError("evidence_id must be evidence of this event")
        before = {f: _val(effective(ev.field_claims, f)) for f in cleaned}
        real = {f: v for f, v in cleaned.items() if before[f] != v}
        if not real:
            raise ContractError("the corrections equal the current values; nothing to change")
        for f, v in real.items():
            ev.field_claims.append(FieldClaim(f, v, "observed" if v else "unknown", (evid,),
                                              (note or "")[:200] or None, f"human:correction:{reviewer}"[:80]))
        recompute(store, ev, evid)
        previous = ev.review_status
        if previous != "pending":                       # changed content needs a fresh decision: explicit, audited
            store.record_system_reopen(event_id, previous, "event corrected by reviewer")
            ev.review_status = "pending"
        ev.confidence = confidence(ev, False)
        after = store.put_event(ev, expected_version=seen)
        store.db.execute("INSERT INTO corrections VALUES(?,?,?,?,?,?,?,?)",
                         (correction_id, event_id, reviewer, payload, note or "", seen, after, now_iso()))
        store.audit(reviewer, "event_corrected", event_id,
                    {"correction_id": correction_id, "fields": sorted(real), "before": {f: before[f] for f in real},
                     "after": real, "version": after, "reopened": previous != "pending"})
        return ev, "applied"


def corrections(store: RadarStore, event_id: str) -> list[dict]:
    cur = store.db.execute("SELECT correction_id,reviewer,changes,note,version_seen,version_after,at FROM corrections "
                           "WHERE event_id=? ORDER BY at, rowid", (event_id,))
    return [{"correction_id": r[0], "reviewer": r[1], "changes": json.loads(r[2]), "note": r[3] or None,
             "version_seen": r[4], "version_after": r[5], "at": r[6]} for r in cur]


# ------------------------------------------------------------------------------------------------ venue directory
def update_venue(store: RadarStore, venue_id: str, operator: str, *, venue_type=None, address=None, district=None,
                 latitude=None, longitude=None, add_links=None, add_contacts=None, verification_status=None,
                 verification_note=None, evidence_id=None) -> Venue:
    """Operator edits to a venue. `None` leaves a field unchanged. Links/contacts are validated; a contact may only be
    marked authorized with a written authorization note; `verified` needs a note."""
    if not operator or not operator.strip():
        raise PermissionError("a named operator is required")
    with store.transaction():
        v = store.get_venue(venue_id)
        if v is None:
            raise KeyError(venue_id)
        if v.merged_into:
            raise ContractError("this venue was merged; edit the surviving record")
        changed = {}
        for name, val in (("venue_type", venue_type), ("address", address), ("district", district),
                          ("latitude", latitude), ("longitude", longitude)):
            if val is not None and getattr(v, name) != val:
                changed[name] = [getattr(v, name), val]
                setattr(v, name, val)
        for link in add_links or []:
            link = {**link, "source_evidence": link.get("source_evidence") or ([evidence_id] if evidence_id else [])}
            validate_link(link)
            if not any(x["url"] == link["url"] for x in v.links):
                v.links.append(link)
                changed.setdefault("links", []).append(link["url"])
        for c in add_contacts or []:
            c = {**c, "value": str(c.get("value", "")).strip(), "source_evidence": c.get("source_evidence") or ([evidence_id] if evidence_id else [])}
            validate_contact(c)
            if not any(x["kind"] == c["kind"] and x["value"] == c["value"] for x in v.contacts):
                v.contacts.append(c)
                changed.setdefault("contacts", []).append(f"{c['kind']}:{'authorized' if c.get('authorized') else 'internal'}")
        if verification_status is not None and verification_status != v.verification_status:
            changed["verification_status"] = [v.verification_status, verification_status]
            v.verification_status = verification_status
            if verification_status == "verified":
                v.verified_by, v.verified_at = operator, now_iso()
        if verification_note is not None:
            v.verification_note = verification_note.strip() or None
        validate_venue(v)
        if not changed and verification_note is None:
            raise ContractError("nothing to change")
        store.put_venue(v)
        store.audit(operator, "venue_updated", venue_id, {"changed": changed})
        return v


def merge_venues(store: RadarStore, source_id: str, target_id: str, operator: str) -> Venue:
    """Fold a duplicate venue into the surviving one. Nothing is deleted: the source keeps `merged_into`, its name
    becomes an alias of the target (so future uploads resolve to the target), events are repointed with a version bump."""
    if not operator or not operator.strip():
        raise PermissionError("a named operator is required")
    if source_id == target_id:
        raise ContractError("cannot merge a venue into itself")
    with store.transaction():
        src, dst = store.get_venue(source_id), store.get_venue(target_id)
        if src is None or dst is None:
            raise KeyError(source_id if src is None else target_id)
        if src.merged_into or dst.merged_into:
            raise ContractError("both venues must be active (not already merged)")
        moved = []
        for ev in store.events():
            if ev.venue_id == source_id:
                v = store.event_version(ev.event_id)
                ev.venue_id = target_id
                store.put_event(ev, expected_version=v)
                moved.append(ev.event_id)
        for name in [src.name, *src.aliases]:
            if norm_name(name) != norm_name(dst.name) and name not in dst.aliases:
                dst.aliases.append(name)
        dst.source_references = list(dict.fromkeys(dst.source_references + src.source_references))
        for link in src.links:
            if not any(x["url"] == link["url"] for x in dst.links):
                dst.links.append(link)
        for c in src.contacts:
            if not any(x["kind"] == c["kind"] and x["value"] == c["value"] for x in dst.contacts):
                dst.contacts.append(c)
        dst.candidate_matches = [m for m in dst.candidate_matches if m != source_id]
        src.merged_into = target_id
        store.put_venue(dst)
        store.put_venue(src)
        store.audit(operator, "venue_merged", target_id, {"merged": source_id, "events_moved": moved})
        return dst


def venue_events(store: RadarStore, venue_id: str):
    return [e for e in store.events() if e.venue_id == venue_id]
