"""Resolution + orchestration: evidence -> text -> extraction -> venue/event resolution -> store."""
from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from difflib import SequenceMatcher
from pathlib import Path

from radar_contracts import CITY, TIMEZONE, Event, EvidenceRecord, FieldClaim, Party, Venue
from scout_fabric.intake import RejectedUpload, ingest_upload
from scout_fabric.sources import SourceRegistry, UnauthorizedSource
from scout_fabric.text_providers import TextProvider

from .extract import Extraction, extract_event, fold
from .store import RadarStore

TITLE_STOP = {"le", "la", "les", "the", "de", "du", "des", "et", "and", "night", "soiree", "party", "by", "presents"}
CONFLICT_FIELDS = ("start_date", "start_time", "end_time", "venue", "organizer", "district")


def norm_title(t: str | None) -> str:
    words = re.sub(r"[^a-z0-9 ]", " ", fold(t or "")).split()
    return " ".join(w for w in words if w not in TITLE_STOP)


def norm_name(n: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(n))


def _h(*parts: str, n: int = 12) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:n]


def first(claims: list[FieldClaim], name: str) -> FieldClaim | None:
    return next((c for c in claims if c.field == name), None)


def make_start_end(claims: list[FieldClaim]) -> tuple[str | None, str | None, list[str]]:
    """Africa/Porto-Novo is UTC+1 with no DST. Date-only start_at when time is unknown (no invented time)."""
    d, st, et = first(claims, "start_date"), first(claims, "start_time"), first(claims, "end_time")
    unknown: list[str] = []
    if not d:
        return None, None, ["start_date"]
    if not st:
        unknown.append("start_time")
        return d.value, None, unknown
    start = f"{d.value}T{st.value}:00+01:00"
    end = None
    if et:
        day = date.fromisoformat(d.value)
        if et.value < st.value:  # overnight set, e.g. 22h -> 04h (derived)
            day += timedelta(days=1)
        end = f"{day.isoformat()}T{et.value}:00+01:00"
    else:
        unknown.append("end_time")
    return start, end, unknown


def resolve_venue(store: RadarStore, name: str, district: str | None, evidence_id: str) -> tuple[Venue, list[str]]:
    """Exact/alias match reuses; fuzzy match creates a NEW unverified venue that points at the candidate."""
    key = norm_name(name)
    venues = store.venues()
    for v in venues:
        if key == norm_name(v.name) or key in {norm_name(a) for a in v.aliases}:
            if evidence_id not in v.source_references:
                v.source_references.append(evidence_id)
            if district and not v.district:
                v.district = district
            store.put_venue(v)
            return v, []
    cands = [v.venue_id for v in venues
             if SequenceMatcher(None, key, norm_name(v.name)).ratio() >= 0.85]
    v = Venue(venue_id=f"ven_{_h(key, CITY)}", name=name.strip(), district=district, address=None,
              latitude=None, longitude=None, venue_type=None, source_references=[evidence_id],
              verification_status="candidate" if cands else "unverified", candidate_matches=cands)
    store.put_venue(v)
    return v, cands


def _party(store: RadarStore, name: str, role: str, event_id: str, ev_id: str) -> Party:
    kind = "person" if role in ("dj", "artist") else "organization"
    others = [p.party_id for p in store.parties()
              if norm_name(p.name) == norm_name(name) and not p.party_id.endswith(_h(event_id))]
    p = Party(party_id=f"{role[:3]}_{_h(role, norm_name(name), event_id)}", name=name, kind=kind,
              role=role, evidence_ids=[ev_id], identity_verified=False, possible_same_as=others)
    store.put_party(p)
    return p


def _norm_claim_value(c: FieldClaim) -> str:
    return norm_name(c.value or "")


def _conflict_sig(conflicts: list[dict]) -> frozenset:
    return frozenset((c["field"], frozenset(norm_name(v["value"]) for v in c["values"])) for c in conflicts)


def find_conflicts(claims: list[FieldClaim]) -> list[dict]:
    out = []
    for f in CONFLICT_FIELDS:
        groups: dict[str, dict] = {}
        for c in claims:
            if c.field == f and c.value:
                g = groups.setdefault(_norm_claim_value(c), {"value": c.value, "evidence_ids": []})
                g["evidence_ids"] += [e for e in c.evidence_ids if e not in g["evidence_ids"]]
        if len(groups) > 1:
            out.append({"field": f, "values": list(groups.values())})
    return out


def confidence(ev: Event, unverified_text: bool) -> str:
    sources = len(ev.evidence_references)
    core = ev.title and ev.start_at and ev.venue_id
    if ev.contradictions or not ev.title:
        return "low"
    if sources >= 2 and core:
        return "high"
    if core and not unverified_text:
        return "medium"
    return "low" if not core else "medium"


def find_match(store: RadarStore, title: str | None, start_date: str | None, venue_id: str | None) -> tuple[Event | None, list[str]]:
    """Returns (auto_merge_target, pending_review_candidates). Never merges on venue alone."""
    if not title:
        return None, []
    nt, cands = norm_title(title), []
    for e in store.events():
        et = norm_title(e.title)
        same_date = bool(start_date and e.start_at and e.start_at[:10] == start_date)
        if et and et == nt and same_date:
            return e, []
        ratio = SequenceMatcher(None, nt, et).ratio() if et else 0
        date_unknown = not start_date or not e.start_at
        if (et == nt and date_unknown) or (ratio >= 0.78 and (same_date or (date_unknown and venue_id and e.venue_id == venue_id))):
            cands.append(e.event_id)
    return None, cands


def process_evidence(store: RadarStore, evidence: EvidenceRecord, provider: TextProvider,
                     media_path: Path) -> Event | None:
    """Idempotent: an observation already attached to an event is not processed again."""
    existing = store.event_for_observation(evidence.observation_id)
    if existing:
        return store.get_event(existing)
    res = provider.extract(media_path, evidence.media_type)
    if not res.text:
        store.audit("ana", "extraction_skipped", evidence.observation_id, {"reason": res.note or res.method})
        return None
    with store.transaction():  # atomic: venues, parties, event, link and audit commit together or not at all
        existing = store.event_for_observation(evidence.observation_id)  # re-check under the write lock
        if existing:
            return store.get_event(existing)
        ex: Extraction = extract_event(res.text, evidence.observation_id, res.state, res.method.replace(":", "-"))
        claims = ex.claims
        start_at, end_at, unk = make_start_end(claims)
        unknown = sorted(set(ex.unknown) | set(unk))

        title_c = first(claims, "title")
        venue_c = first(claims, "venue")
        district_c = first(claims, "district")
        venue = None
        if venue_c:
            venue, _ = resolve_venue(store, venue_c.value, district_c.value if district_c else None, evidence.observation_id)
        start_date = start_at[:10] if start_at else None
        target, cands = find_match(store, title_c.value if title_c else None, start_date, venue.venue_id if venue else None)

        cat = first(claims, "category")
        base_version = None
        if target:  # same event, new observation: keep every claim, surface contradictions
            ev = target
            base_version = store.event_version(ev.event_id)
            conflicts_before = _conflict_sig(find_conflicts(ev.field_claims))
            ev.evidence_references = list(dict.fromkeys(ev.evidence_references + [evidence.observation_id]))
            ev.field_claims = ev.field_claims + claims
            ev.contradictions = find_conflicts(ev.field_claims)
            if ev.venue_id is None and venue:
                ev.venue_id = venue.venue_id
                ev.unknown_fields = [u for u in ev.unknown_fields if u != "venue"]
            if ev.start_at is None and start_at:
                ev.start_at, ev.end_at = start_at, end_at
                ev.unknown_fields = [u for u in ev.unknown_fields if u != "start_date"]
            # A human decision is only reopened (explicitly, audited, history kept) when the new evidence
            # introduces a NEW contradiction. Corroborating evidence leaves the decision intact.
            if ev.review_status in ("approved", "rejected") and _conflict_sig(ev.contradictions) != conflicts_before:
                store.record_system_reopen(ev.event_id, ev.review_status,
                                           "new observation introduced a contradiction")
                ev.review_status = "pending"
            store.audit("ana", "observation_merged", ev.event_id, {"observation": evidence.observation_id})
        else:
            eid = f"evt_{_h(norm_title(title_c.value), start_date, CITY)}" if (title_c and start_date) \
                else f"evt_{_h(evidence.observation_id)}"
            ev = Event(event_id=eid, title=title_c.value if title_c else None, description=None,
                       start_at=start_at, end_at=end_at, timezone=TIMEZONE,
                       venue_id=venue.venue_id if venue else None, organizer_id=None, performer_ids=[],
                       event_category=cat.value if cat else None, status="scheduled" if start_at else "unknown",
                       evidence_references=[evidence.observation_id], confidence="low",
                       review_status="pending", field_claims=list(claims),
                       unknown_fields=unknown, duplicate_candidates=cands)
            for note in ex.notes:  # e.g. weekday without date, day+month without year: surfaced, not inferred
                store.audit("ana", "extraction_note", ev.event_id, {"note": note})
            org_c = first(claims, "organizer")
            if org_c:
                ev.organizer_id = _party(store, org_c.value, "organizer", ev.event_id, evidence.observation_id).party_id
            for c in (c for c in claims if c.field == "performer"):
                role = "dj" if c.method.endswith(":dj") else "artist"
                ev.performer_ids.append(_party(store, c.value, role, ev.event_id, evidence.observation_id).party_id)
            ev.contradictions = find_conflicts(ev.field_claims)
        ev.confidence = confidence(ev, res.state == "unverified")
        store.put_event(ev, expected_version=base_version)  # None => create; else versioned update
        store.link_observation(evidence.observation_id, ev.event_id)
    return ev


def run_upload(store: RadarStore, registry: SourceRegistry, path: Path, source_id: str,
               provider: TextProvider) -> dict:
    """Full slice: upload -> SCOUT evidence -> ANA extraction -> event+venue -> store."""
    try:
        evidence, created = ingest_upload(path, source_id, registry, store.media_dir)
    except UnauthorizedSource as exc:
        store.record_failure(exc.source_id, exc.reason, exc.alternative)
        store.audit("scout", "acquisition_rejected", exc.source_id, {"reason": exc.reason})
        raise
    except RejectedUpload as exc:
        store.record_failure(source_id, str(exc), "Upload a PNG/JPEG/WEBP image or MP4/MOV/WEBM video.")
        raise
    store.add_evidence(evidence)
    media_path = store.root / evidence.raw_media_reference
    # sidecar text lives beside the original upload, not the content-addressed copy
    local = Path(path)
    ev = process_evidence(store, evidence, _Beside(provider, local), media_path)
    return {"observation_id": evidence.observation_id, "evidence_created": created,
            "event_id": ev.event_id if ev else None}


class _Beside:
    """Run the provider against the operator's original file (so sidecar text is found)."""
    def __init__(self, inner: TextProvider, original: Path):
        self.inner, self.original = inner, original

    def extract(self, media_path: Path, media_type: str):
        return self.inner.extract(self.original, media_type)
