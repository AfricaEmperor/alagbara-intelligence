"""ClaimBook: validated, non-overwriting collection of entities and claims over the EXISTING evidence ledger.

The ledger is `ana_engine.store.RadarStore` (evidence table). This module adds no table and no file: claims
live in memory for the duration of a run and are exported with `to_dict()`. Durable claim persistence is
the explicit next task (a table inside RadarStore, not a second store).
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from ana_engine.store import RadarStore
from radar_contracts import ContractError

from .models import ENDPOINTS, AttributeClaim, Contradiction, Entity, RelationshipClaim

_RANK = {"observed": 3, "derived": 2, "unverified": 1, "unknown": 0}


class ClaimConflict(ValueError):
    """A claim_id/entity_id was reused with a different payload. Claims are never overwritten."""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


class ClaimBook:
    def __init__(self, store: RadarStore):
        self.store = store
        self.entities: dict[str, Entity] = {}
        self.relationships: dict[str, RelationshipClaim] = {}
        self.attributes: dict[str, AttributeClaim] = {}

    # ---- writes (validate, never overwrite) -------------------------------------------------
    def add_entity(self, e: Entity) -> Entity:
        old = self.entities.get(e.entity_id)
        if old is not None:
            if old != e:
                raise ClaimConflict(f"entity {e.entity_id!r} already exists with different content")
            return old
        self.entities[e.entity_id] = e
        return e

    def _check_evidence(self, claim: Any) -> None:
        best, traced = 0, False
        for oid in claim.evidence_ids:
            ev = self.store.get_evidence(oid)
            if ev is None:
                raise ContractError(f"claim {claim.claim_id!r} cites evidence {oid!r} that is not in the ledger")
            best = max(best, _RANK[ev["evidence_state"]])
            text = str((ev.get("metadata") or {}).get("captured_text", ""))
            traced = traced or (bool(claim.raw_excerpt) and _norm(claim.raw_excerpt) in _norm(text))
        if claim.state != "unknown":
            if not traced:
                raise ContractError(f"claim {claim.claim_id!r}: raw_excerpt does not occur in any cited evidence")
            if _RANK[claim.state] > best:
                raise ContractError(f"claim {claim.claim_id!r} state {claim.state!r} exceeds the strength of its evidence")

    def add_relationship(self, c: RelationshipClaim) -> RelationshipClaim:
        subj, obj = self._entity(c.subject), self._entity(c.object)
        allowed_s, allowed_o = ENDPOINTS[c.relation]
        if subj.type not in allowed_s or obj.type not in allowed_o:
            raise ContractError(f"{c.relation}: {subj.type}->{obj.type} is not an allowed endpoint pair")
        if c.counterparty:
            self._entity(c.counterparty)
        return self._put(self.relationships, c)

    def add_attribute(self, c: AttributeClaim) -> AttributeClaim:
        self._entity(c.entity)
        return self._put(self.attributes, c)

    def _put(self, bucket: dict[str, Any], c: Any) -> Any:
        if c.claim_id in self.relationships or c.claim_id in self.attributes:
            old = bucket.get(c.claim_id)
            if old == c:
                return old
            raise ClaimConflict(f"claim {c.claim_id!r} already exists; claims are never overwritten")
        self._check_evidence(c)
        bucket[c.claim_id] = c
        return c

    def _entity(self, entity_id: str) -> Entity:
        try:
            return self.entities[entity_id]
        except KeyError:
            raise ContractError(f"unknown entity {entity_id!r}") from None

    # ---- reads ------------------------------------------------------------------------------
    def provenance(self, claim: Any) -> list[dict[str, Any]]:
        """Resolve a claim's evidence from the ledger: source, method, capture date, raw evidence."""
        out = []
        for oid in claim.evidence_ids:
            ev = self.store.get_evidence(oid) or {}
            out.append({
                "observation_id": oid, "source_id": ev.get("source_id"), "source_platform": ev.get("source_platform"),
                "source_url": ev.get("source_url"), "collection_method": ev.get("collection_method"),
                "capture_date": ev.get("collected_at"), "observation_date": claim.observed_at,
                "evidence_state": ev.get("evidence_state"), "content_hash": ev.get("content_hash"),
                "raw_evidence": claim.raw_excerpt,
            })
        return out

    def contradictions(self) -> list[Contradiction]:
        """Derive conflicts. Deterministic. Conservative: unknown periods may overlap anything."""
        found: dict[str, Contradiction] = {}

        def add(kind: str, subject: str, ids: list[str], text: str) -> None:
            ids = sorted(set(ids))
            cid = "CON-" + hashlib.sha1(f"{kind}|{'|'.join(ids)}".encode()).hexdigest()[:10]
            found.setdefault(cid, Contradiction(cid, kind, subject, tuple(ids), text))

        rel = [c for c in self.relationships.values() if c.state != "unknown"]
        by_triple: dict[tuple, list[RelationshipClaim]] = {}
        for c in rel:
            by_triple.setdefault((c.subject, c.relation, c.object, c.counterparty), []).append(c)
        for (s, r, o, _cp), group in by_triple.items():
            for a in group:
                for b in group:
                    if a.claim_id < b.claim_id and a.period.may_overlap(b.period):
                        if a.asserted != b.asserted:
                            add("assertion_denial", f"{s} {r} {o}", [a.claim_id, b.claim_id],
                                f"One source asserts and another denies '{s} {r} {o}' over overlapping or unknown periods.")
                        elif a.period != b.period and not a.period.unknown and not b.period.unknown:
                            add("period_conflict", f"{s} {r} {o}", [a.claim_id, b.claim_id],
                                f"Sources give different periods for '{s} {r} {o}' that overlap.")
        owners: dict[str, list[RelationshipClaim]] = {}
        for c in rel:
            if c.relation == "OWNS" and c.asserted:
                owners.setdefault(c.object, []).append(c)
        for obj, group in owners.items():
            for a in group:
                for b in group:
                    if a.claim_id < b.claim_id and a.subject != b.subject and a.period.may_overlap(b.period):
                        add("conflicting_owner", f"owner of {obj}", [a.claim_id, b.claim_id],
                            f"Different owners ({a.subject}, {b.subject}) of {obj} are claimed over overlapping or unknown periods "
                            "(may be co-ownership; not resolved).")
        by_attr: dict[tuple, list[AttributeClaim]] = {}
        for c in self.attributes.values():
            if c.state != "unknown":
                by_attr.setdefault((c.entity, c.attribute), []).append(c)
        for (e, attr), group in by_attr.items():
            for a in group:
                for b in group:
                    if a.claim_id < b.claim_id and a.period.may_overlap(b.period):
                        if a.asserted != b.asserted:
                            add("assertion_denial", f"{e} {attr}", [a.claim_id, b.claim_id],
                                f"One source asserts and another denies {attr} for {e}.")
                        elif a.asserted and _norm(a.value) != _norm(b.value):
                            add("conflicting_values", f"{e} {attr}", [a.claim_id, b.claim_id],
                                f"Sources give different values for {attr} of {e}.")
        return sorted(found.values(), key=lambda x: x.contradiction_id)

    def to_dict(self) -> dict[str, Any]:
        return {"contract": "partner-intel/0.1",
                "entities": [vars(e) | {"aliases": list(e.aliases)} for e in self.entities.values()],
                "relationships": [c.to_dict() for c in self.relationships.values()],
                "attributes": [c.to_dict() for c in self.attributes.values()],
                "contradictions": [c.to_dict() for c in self.contradictions()]}
