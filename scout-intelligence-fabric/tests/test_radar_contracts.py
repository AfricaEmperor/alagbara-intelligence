import json
from pathlib import Path

import pytest

from radar_contracts import (
    ContractError,
    Event,
    EvidenceRecord,
    FieldClaim,
    Venue,
    validate_claim,
    validate_event,
    validate_evidence,
    validate_venue,
)

H = "a" * 64


def ev(**kw):
    base = dict(event_id="e1", title="T", description=None, start_at="2026-11-14", end_at=None,
                timezone="Africa/Porto-Novo", venue_id="v1", organizer_id=None, performer_ids=[],
                event_category=None, status="scheduled", evidence_references=["o1"], confidence="low",
                review_status="pending")
    base.update(kw)
    return Event(**base)


def test_valid_event_passes():
    validate_event(ev())


@pytest.mark.parametrize("kw", [
    dict(timezone="UTC"), dict(review_status="live"), dict(evidence_references=[]),
    dict(title=None), dict(start_at=None), dict(venue_id=None), dict(confidence="certain"),
    dict(start_at="not-a-date"),
])
def test_invalid_events_rejected(kw):
    with pytest.raises(ContractError):
        validate_event(ev(**kw))


def test_unknown_must_be_declared_explicitly():
    validate_event(ev(title=None, unknown_fields=["title"]))


def test_claim_must_cite_event_evidence_and_not_claim_observed_for_machine_output():
    with pytest.raises(ContractError):
        validate_event(ev(field_claims=[FieldClaim("title", "T", "derived", ("other",))]))
    with pytest.raises(ContractError):
        validate_claim(FieldClaim("title", "T", "observed", ("o1",), method="rule:ocr"))
    with pytest.raises(ContractError):
        validate_claim(FieldClaim("title", "T", "derived", ()))


def test_evidence_and_venue_validation():
    e = EvidenceRecord("o", "s", "upload", None, "operator_upload", "2026-11-05T00:00:00+00:00", H, "unverified", "m", "v")
    validate_evidence(e)
    with pytest.raises(ContractError):
        validate_evidence(EvidenceRecord("o", "s", "upload", None, "m", "2026-11-05T00:00:00+00:00", "short", "unverified", None, "v"))
    v = Venue("v1", "Club", "Haie Vive", None, None, None, None, ["o"])
    validate_venue(v)
    with pytest.raises(ContractError):
        validate_venue(Venue("v1", "Club", None, None, 95.0, None, None, ["o"]))
    with pytest.raises(ContractError):
        validate_venue(Venue("v1", "Club", None, None, None, None, None, []))


def test_json_schema_required_fields_match_dataclasses():
    schema_dir = Path(__file__).parents[1] / "schemas" / "radar" / "v1"
    ev_schema = json.loads((schema_dir / "event.schema.json").read_text())
    assert set(ev_schema["required"]) <= set(Event.__dataclass_fields__)
    for f in ("event_id", "title", "description", "start_at", "end_at", "timezone", "venue_id", "organizer_id",
              "performer_ids", "event_category", "status", "evidence_references", "confidence", "review_status"):
        assert f in ev_schema["properties"]
    venue_schema = json.loads((schema_dir / "venue.schema.json").read_text())
    assert set(venue_schema["required"]) <= set(Venue.__dataclass_fields__)
    evid = json.loads((schema_dir / "evidence.schema.json").read_text())
    assert set(evid["required"]) <= set(EvidenceRecord.__dataclass_fields__)
