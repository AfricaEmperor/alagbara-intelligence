"""MUSEOPS-PI-001 Partner Intelligence contracts (partner-intel/0.1).

REUSE, not rebuild: evidence is `radar_contracts.EvidenceRecord` held in the existing `ana_engine.RadarStore`
evidence ledger, and evidence states are `radar_contracts.EVIDENCE_STATES`. This module only adds what the
Radar contracts do not have: partner entities, relationship claims and attribute claims that REFERENCE
evidence by `observation_id`. Nothing here stores or fetches anything.

Rules enforced by the dataclasses/validators:
  * a claim never carries its own evidence: it points at ledger records (source reference, collection method
    and capture date are resolved from the ledger, never copied by hand);
  * a claim keeps what the source SAID (`raw_excerpt`) separate from what an analyst THINKS (`interpretation`);
  * conflicting claims coexist; contradictions are derived, never resolved by overwriting;
  * organisational function is not decision authority; intermediary presence is not causation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from radar_contracts import EVIDENCE_STATES, ContractError

CONTRACT_VERSION = "partner-intel/0.1"

ENTITY_TYPES = ("BRAND", "ORGANIZATION", "FUNCTION", "PERSON", "AGENCY", "DISTRIBUTOR", "VENUE", "EVENT", "MUSE", "TALENT")
RELATION_TYPES = ("OWNS", "EMPLOYS", "LEADS_FUNCTION", "DISTRIBUTES", "ACTIVATES", "ORGANIZES",
                  "PERFORMS_AT", "REPRESENTS", "INTRODUCES", "PARTNERS_WITH")
ATTRIBUTES = ("COMMERCIAL_CAPACITY", "COMMERCIAL_NEED", "COMMERCIAL_INTENT", "VISIBILITY_BIAS", "DECISION_AUTHORITY")

_ANY_PARTY = ("BRAND", "ORGANIZATION", "AGENCY", "DISTRIBUTOR", "VENUE", "EVENT", "PERSON", "MUSE", "TALENT")
#: allowed (subject types, object types) per relation. Endpoint typing only; it never implies authority.
ENDPOINTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "OWNS": (("ORGANIZATION", "BRAND"), ("BRAND", "ORGANIZATION", "VENUE", "FUNCTION")),
    "EMPLOYS": (("ORGANIZATION", "AGENCY", "DISTRIBUTOR"), ("PERSON",)),
    "LEADS_FUNCTION": (("PERSON",), ("FUNCTION",)),
    "DISTRIBUTES": (("DISTRIBUTOR", "ORGANIZATION"), ("BRAND",)),
    "ACTIVATES": (("BRAND", "ORGANIZATION", "AGENCY", "DISTRIBUTOR"), ("EVENT", "VENUE")),
    "ORGANIZES": (("ORGANIZATION", "AGENCY", "PERSON", "VENUE"), ("EVENT",)),
    "PERFORMS_AT": (("TALENT", "MUSE", "PERSON"), ("EVENT", "VENUE")),
    "REPRESENTS": (("AGENCY", "PERSON"), ("TALENT", "MUSE", "BRAND", "ORGANIZATION")),
    "INTRODUCES": (("PERSON", "AGENCY", "ORGANIZATION"), _ANY_PARTY),
    "PARTNERS_WITH": (_ANY_PARTY, _ANY_PARTY),
}


def _d(value: str | None, label: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError(f"{label} must be an ISO date (YYYY-MM-DD): {value!r}") from exc


@dataclass(frozen=True)
class TimePeriod:
    """Period the CLAIM is about (not when it was observed). Both ends None = period UNKNOWN."""
    start: str | None = None
    end: str | None = None

    def __post_init__(self) -> None:
        s, e = _d(self.start, "period.start"), _d(self.end, "period.end")
        if s and e and s > e:
            raise ContractError("period.start is after period.end")

    @property
    def unknown(self) -> bool:
        return self.start is None and self.end is None

    def covers(self, as_of: str) -> bool:
        """True only when the evidence PROVES the period includes `as_of`. Unknown periods are never current."""
        if self.unknown:
            return False
        a, s, e = _d(as_of, "as_of"), _d(self.start, ""), _d(self.end, "")
        return (s is None or s <= a) and (e is None or a <= e)

    def is_historical(self, as_of: str) -> bool:
        e = _d(self.end, "")
        return e is not None and e < _d(as_of, "as_of")

    def may_overlap(self, other: TimePeriod) -> bool:
        """Conservative: an unknown period may overlap anything, so conflicts stay visible."""
        if self.unknown or other.unknown:
            return True
        s1, e1, s2, e2 = _d(self.start, ""), _d(self.end, ""), _d(other.start, ""), _d(other.end, "")
        return (s1 is None or e2 is None or s1 <= e2) and (s2 is None or e1 is None or s2 <= e1)


@dataclass(frozen=True)
class Entity:
    entity_id: str
    type: str
    name: str
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.entity_id or not self.name:
            raise ContractError("entity_id and name are required")
        if self.type not in ENTITY_TYPES:
            raise ContractError(f"unknown entity type {self.type!r}")


@dataclass(frozen=True)
class _ClaimBase:
    claim_id: str
    evidence_ids: tuple[str, ...]      # ledger observation_ids (EvidenceRecord.observation_id)
    observed_at: str                   # when the SOURCE states/published it (ISO date) - not the capture date
    state: str                         # observed | derived | unverified | unknown (radar EVIDENCE_STATES)
    period: TimePeriod = field(default_factory=TimePeriod)
    asserted: bool = True              # False = the source explicitly DENIES the statement
    raw_excerpt: str = ""              # what the source said, verbatim (must occur in the evidence text)
    interpretation: str = ""           # analyst reading; never used by profile/opportunity logic

    def _check(self) -> None:
        if not self.claim_id:
            raise ContractError("claim_id is required")
        if self.state not in EVIDENCE_STATES:
            raise ContractError(f"invalid claim state {self.state!r}")
        if self.state != "unknown" and not self.evidence_ids:
            raise ContractError(f"claim {self.claim_id!r} has no source reference")
        if self.state != "unknown" and not self.raw_excerpt:
            raise ContractError(f"claim {self.claim_id!r} has no raw evidence excerpt")
        _d(self.observed_at, "observed_at")


@dataclass(frozen=True)
class RelationshipClaim(_ClaimBase):
    subject: str = ""
    relation: str = ""
    object: str = ""
    counterparty: str | None = None    # INTRODUCES only: subject introduces `object` to `counterparty`

    def __post_init__(self) -> None:
        self._check()
        if self.relation not in RELATION_TYPES:
            raise ContractError(f"unknown relation {self.relation!r}")
        if not self.subject or not self.object:
            raise ContractError("subject and object are required")
        if self.counterparty and self.relation != "INTRODUCES":
            raise ContractError("counterparty is only valid for INTRODUCES")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence_ids"] = list(self.evidence_ids)
        return d


@dataclass(frozen=True)
class AttributeClaim(_ClaimBase):
    entity: str = ""
    attribute: str = ""
    value: str = ""

    def __post_init__(self) -> None:
        self._check()
        if self.attribute not in ATTRIBUTES:
            raise ContractError(f"unknown attribute {self.attribute!r}")
        if not self.entity or (self.asserted and not self.value):
            raise ContractError("entity and (for asserted claims) value are required")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence_ids"] = list(self.evidence_ids)
        return d


@dataclass(frozen=True)
class Contradiction:
    """A conflict between claims. Both sides stay in the book; this only points at them."""
    contradiction_id: str
    kind: str                           # assertion_denial | conflicting_values | conflicting_owner | period_conflict
    subject: str                        # human-readable key of what conflicts
    claim_ids: tuple[str, ...]
    description: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["claim_ids"] = list(self.claim_ids)
        return d
