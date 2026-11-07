"""AP-001 Event Radar + Venue Intelligence contracts (version 1.0.0).

Rules enforced here (see validate_* functions):
  * every record distinguishes OBSERVED / DERIVED / UNVERIFIED / UNKNOWN
  * every event field keeps its source references (FieldClaim.evidence_ids)
  * conflicting claims are preserved, never overwritten
  * market identity and timezone are explicit and validated against the market registry
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

CONTRACT_VERSION = "1.1.0"   # 1.1.0: additive (venue contacts/links/verification note, corrections, review block)
TIMEZONE = "Africa/Porto-Novo"
CITY = "Cotonou"

EvidenceState = Literal["observed", "derived", "unverified", "unknown"]
EVIDENCE_STATES = ("observed", "derived", "unverified", "unknown")
REVIEW_STATUSES = ("pending", "approved", "rejected", "correction_requested")
VERIFICATION_STATUSES = ("unverified", "candidate", "verified")
EVENT_STATUSES = ("scheduled", "cancelled", "past", "unknown")
EVENT_CATEGORIES = ("club_night", "concert", "festival", "brunch", "karaoke", "afterwork", "pool_party", "comedy", "other")
VENUE_TYPES = ("club", "bar", "lounge", "restaurant", "hotel", "cultural_center", "beach_venue", "outdoor", "other")
LINK_KINDS = {"facebook": ("facebook.com", "fb.com"), "instagram": ("instagram.com",), "tiktok": ("tiktok.com",),
              "x": ("x.com", "twitter.com"), "youtube": ("youtube.com", "youtu.be"), "whatsapp": ("wa.me", "whatsapp.com"),
              "website": None}
CONTACT_KINDS = ("phone", "whatsapp", "email")
EVENT_FIELDS = (
    "title", "description", "start_date", "start_time", "end_time", "venue", "district",
    "organizer", "promoter", "performer", "ticket", "contact", "category",
)


class ContractError(ValueError):
    """Raised when a record violates the AP-001 contract."""


@dataclass(frozen=True)
class EvidenceRecord:
    observation_id: str
    source_id: str
    source_platform: str
    source_url: str | None
    collection_method: str
    collected_at: str
    content_hash: str
    evidence_state: EvidenceState
    raw_media_reference: str | None
    extraction_version: str
    media_type: str = "unknown"  # image | video | html | text
    original_filename: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FieldClaim:
    """One extracted value for one event field, tied to its evidence."""
    field: str
    value: str | None
    state: EvidenceState
    evidence_ids: tuple[str, ...]
    snippet: str | None = None
    method: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence_ids"] = list(self.evidence_ids)
        return d


@dataclass
class Venue:
    venue_id: str
    name: str
    district: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    venue_type: str | None
    source_references: list[str]
    verification_status: str = "unverified"
    city: str = CITY
    aliases: list[str] = field(default_factory=list)
    candidate_matches: list[str] = field(default_factory=list)
    # --- 1.1.0 (all optional) ---
    contacts: list[dict[str, Any]] = field(default_factory=list)   # {kind, value, authorized, authorization_note, source_evidence}
    links: list[dict[str, Any]] = field(default_factory=list)      # {kind, url, official, source_evidence}
    verification_note: str | None = None
    verified_by: str | None = None
    verified_at: str | None = None
    merged_into: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Party:
    """A person or organization referenced by an event (organizer, DJ, artist...)."""
    party_id: str
    name: str
    kind: str  # person | organization | unknown
    role: str  # organizer | promoter | dj | artist
    evidence_ids: list[str]
    identity_verified: bool = False  # never auto-true: same stage name != same person
    possible_same_as: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Event:
    event_id: str
    title: str | None
    description: str | None
    start_at: str | None
    end_at: str | None
    timezone: str
    venue_id: str | None
    organizer_id: str | None
    performer_ids: list[str]
    event_category: str | None
    status: str
    evidence_references: list[str]
    confidence: str  # low | medium | high  (derived, not a probability)
    review_status: str
    city: str = CITY
    field_claims: list[FieldClaim] = field(default_factory=list)
    unknown_fields: list[str] = field(default_factory=list)
    contradictions: list[dict[str, Any]] = field(default_factory=list)
    duplicate_candidates: list[str] = field(default_factory=list)
    contract_version: str = CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["field_claims"] = [c.to_dict() for c in self.field_claims]
        return d


def _iso(value: str, label: str) -> None:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception as exc:
        raise ContractError(f"{label} is not ISO-8601: {value!r}") from exc


def validate_evidence(e: EvidenceRecord) -> None:
    for name in ("observation_id", "source_id", "source_platform", "collection_method",
                 "content_hash", "extraction_version"):
        if not getattr(e, name):
            raise ContractError(f"evidence.{name} is required")
    if e.evidence_state not in EVIDENCE_STATES:
        raise ContractError(f"invalid evidence_state {e.evidence_state!r}")
    if len(e.content_hash) != 64 or any(c not in "0123456789abcdef" for c in e.content_hash):
        raise ContractError("content_hash must be a sha256 hex digest")
    _iso(e.collected_at, "collected_at")


def validate_claim(c: FieldClaim) -> None:
    if c.field not in EVENT_FIELDS:
        raise ContractError(f"unknown event field {c.field!r}")
    if c.state not in EVIDENCE_STATES:
        raise ContractError(f"invalid claim state {c.state!r}")
    if c.state != "unknown" and not c.evidence_ids:
        raise ContractError(f"claim for {c.field!r} has no source reference")
    if c.state == "observed" and c.method.startswith(("ocr", "rule", "derived")):
        raise ContractError("machine-extracted values may not be labelled observed")


def validate_link(k: dict[str, Any]) -> None:
    from urllib.parse import urlparse
    kind, url = k.get("kind"), str(k.get("url", ""))
    if kind not in LINK_KINDS:
        raise ContractError(f"link kind must be one of {sorted(LINK_KINDS)}")
    u = urlparse(url)
    if u.scheme != "https" or not u.hostname or u.username or u.password:
        raise ContractError("links must be https URLs without embedded credentials")
    domains = LINK_KINDS[kind]
    host = u.hostname.lower()
    if domains and not any(host == d or host.endswith("." + d) for d in domains):
        raise ContractError(f"a {kind} link must be on {domains}")
    if not k.get("source_evidence") and not k.get("official"):
        raise ContractError("a link needs source evidence or an explicit official=true confirmation")


def validate_contact(c: dict[str, Any]) -> None:
    import re
    if c.get("kind") not in CONTACT_KINDS:
        raise ContractError(f"contact kind must be one of {CONTACT_KINDS}")
    v = str(c.get("value", "")).strip()
    ok = re.fullmatch(r"[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,63}", v) if c["kind"] == "email" else re.fullmatch(r"\+?[0-9][0-9 .-]{6,20}", v)
    if not ok:
        raise ContractError(f"invalid {c.get('kind')} contact value")
    if c.get("authorized") and not str(c.get("authorization_note", "")).strip():
        raise ContractError("an authorized public contact needs an authorization_note (why it may be shown)")


def validate_venue(v: Venue) -> None:
    if not v.venue_id or not v.name:
        raise ContractError("venue_id and name are required")
    if v.city != CITY:
        raise ContractError(f"v1 venues must be in {CITY}")
    if v.verification_status not in VERIFICATION_STATUSES:
        raise ContractError(f"invalid verification_status {v.verification_status!r}")
    if not v.source_references:
        raise ContractError("venue requires at least one source reference")
    if v.venue_type is not None and v.venue_type not in VENUE_TYPES:
        raise ContractError(f"venue_type must be one of {VENUE_TYPES}")
    if v.verification_status == "verified" and not (v.verification_note or "").strip():
        raise ContractError("a verified venue needs a verification_note")
    for k in v.links:
        validate_link(k)
    for c in v.contacts:
        validate_contact(c)
    for lat_lon, lo, hi in ((v.latitude, -90, 90), (v.longitude, -180, 180)):
        if lat_lon is not None and not lo <= lat_lon <= hi:
            raise ContractError("coordinate out of range")


def validate_event(ev: Event) -> None:
    if not ev.event_id:
        raise ContractError("event_id is required")
    if ev.timezone != TIMEZONE:
        raise ContractError(f"timezone must be {TIMEZONE}")
    if ev.review_status not in REVIEW_STATUSES:
        raise ContractError(f"invalid review_status {ev.review_status!r}")
    if ev.status not in EVENT_STATUSES:
        raise ContractError(f"invalid status {ev.status!r}")
    if ev.confidence not in ("low", "medium", "high"):
        raise ContractError("confidence must be low|medium|high")
    if not ev.evidence_references:
        raise ContractError("event requires evidence_references (provenance)")
    for ts, label in ((ev.start_at, "start_at"), (ev.end_at, "end_at")):
        if ts is not None:
            _iso(ts, label)
    for c in ev.field_claims:
        validate_claim(c)
        for ref in c.evidence_ids:
            if ref not in ev.evidence_references:
                raise ContractError(f"claim {c.field!r} cites evidence {ref} not on the event")
    # unknown must be explicit: an empty title/start must be listed as unknown
    if ev.title is None and "title" not in ev.unknown_fields:
        raise ContractError("missing title must be listed in unknown_fields")
    if ev.start_at is None and "start_date" not in ev.unknown_fields:
        raise ContractError("missing start date must be listed in unknown_fields")
    if ev.venue_id is None and "venue" not in ev.unknown_fields:
        raise ContractError("missing venue must be listed in unknown_fields")
