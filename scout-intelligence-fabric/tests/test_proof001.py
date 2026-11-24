from ana_engine.proof001 import build_proof


def sample():
    return {
        "signal_id": "lagos-signal-001",
        "source_url": "https://example.org/public-event",
        "observed_at": "2026-11-24T10:00:00+01:00",
        "event_title": "Example Lagos Experience",
        "venue_name": "Example Venue",
    }


def test_signal_to_outcome_path_and_provenance():
    result = build_proof(sample(), action_authorized=True, outcome="qualification_task_created")
    assert result["proof_id"] == "ALAGBARA-PROOF-001"
    assert result["provenance"]["verification"] == "NOT_FETCH_VERIFIED"
    assert result["graph"]["relationships"][0]["evidence"] == "lagos-signal-001"
    assert result["opportunity"]["rationale"]
    assert result["opportunity"]["next_action"]
    assert result["action"]["status"] == "executed"
    assert result["feedback"]["outcome"] == "qualification_task_created"
    assert result["opportunity"]["id"] in result["feedback"]["linked_to"]


def test_action_fails_closed_without_authorization():
    result = build_proof(sample(), action_authorized=False)
    assert result["action"]["status"] == "blocked"
    assert result["feedback"]["outcome"] == "not_executed"


def test_rejects_non_https_source():
    bad = sample()
    bad["source_url"] = "http://example.org/event"
    try:
        build_proof(bad)
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("HTTP source must fail validation")


def test_missing_required_signal_fields():
    bad = sample()
    bad.pop("venue_name")
    try:
        build_proof(bad)
    except ValueError as exc:
        assert "venue_name" in str(exc)
    else:
        raise AssertionError("missing required field must fail")
