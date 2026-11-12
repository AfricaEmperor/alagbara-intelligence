"""Deterministic fixture loader (schema partner-fixture/0.1). OFFLINE: no network, no registry access.

Evidence goes into the existing RadarStore ledger as ordinary EvidenceRecords (collection_method
"fixture"), so claims are traced exactly as live evidence would be. Fixtures flagged `synthetic: true` are
FICTIONAL and assert nothing about real organisations.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ana_engine.store import RadarStore
from radar_contracts import ContractError, EvidenceRecord

from .claimbook import ClaimBook
from .models import AttributeClaim, Entity, RelationshipClaim, TimePeriod

SCHEMA = "partner-fixture/0.1"


def _period(d: dict[str, Any] | None) -> TimePeriod:
    return TimePeriod(**(d or {}))


def load_fixture(path: Path | str, store: RadarStore) -> tuple[ClaimBook, dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema") != SCHEMA:
        raise ContractError(f"unsupported fixture schema {raw.get('schema')!r}")
    book, keys = ClaimBook(store), {}
    for e in raw["entities"]:
        book.add_entity(Entity(e["entity_id"], e["type"], e["name"], tuple(e.get("aliases", ()))))
    for ev in raw["evidence"]:
        text = ev["raw_text"]
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        rec = EvidenceRecord(
            observation_id=hashlib.sha256(f"{ev['source_id']}\n{h}".encode()).hexdigest(), source_id=ev["source_id"],
            source_platform=ev.get("source_platform", "public_html"), source_url=ev["url"], collection_method="fixture",
            collected_at=ev["collected_at"], content_hash=h, evidence_state=ev["evidence_state"], raw_media_reference=None,
            extraction_version=SCHEMA, media_type="text",
            metadata={"captured_text": text, "published_at": ev.get("published_at"), "synthetic": bool(raw.get("synthetic"))})
        store.add_evidence(rec)
        keys[ev["key"]] = rec.observation_id
    common = lambda c: dict(
        claim_id=c["claim_id"], evidence_ids=tuple(keys[k] for k in c.get("evidence", ())), observed_at=c["observed_at"],
        state=c["state"], period=_period(c.get("period")), asserted=c.get("asserted", True),
        raw_excerpt=c.get("raw_excerpt", ""), interpretation=c.get("interpretation", ""))
    for c in raw["relationships"]:
        book.add_relationship(RelationshipClaim(**common(c), subject=c["subject"], relation=c["relation"], object=c["object"],
                                                counterparty=c.get("counterparty")))
    for c in raw["attributes"]:
        book.add_attribute(AttributeClaim(**common(c), entity=c["entity"], attribute=c["attribute"], value=c.get("value", "")))
    return book, {"fixture_id": raw["fixture_id"], "synthetic": bool(raw.get("synthetic")), "as_of": raw["as_of"], "focus": raw["focus"],
                  "title": raw["title"], "evidence_keys": keys}
