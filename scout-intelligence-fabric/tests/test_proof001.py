from ana_engine.proof001 import build_proof, capture_source


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
    assert result["provenance"]["verification"] == "NOT_CAPTURED"
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


def test_capture_source_persists_hashed_evidence(tmp_path):
    import hashlib
    from unittest.mock import patch
    from ana_engine import proof001

    body = b"<html>proof001 test source</html>"

    class FakeResponse:
        headers = {"Content-Type": "text/html; charset=utf-8"}
        def read(self, limit):
            return body
        def geturl(self):
            return "https://example.org/public-event"

    with patch.object(proof001, "urlopen", return_value=FakeResponse()):
        captured = capture_source(sample(), tmp_path / "evidence-store")

    assert captured["captured"] is True
    assert captured["inserted"] is True
    assert captured["sha256"] == hashlib.sha256(body).hexdigest()
    assert captured["evidence"]["content_hash"] == captured["sha256"]
    assert captured["evidence"]["collection_method"] == "bounded_https_fetch"
    assert captured["evidence"]["source_url"] == sample()["source_url"]


def test_captured_evidence_changes_provenance_state():
    captured = {"captured": True, "sha256": "a" * 64,
                "evidence": {"observation_id": "obs-test"}}
    result = build_proof(sample(), captured_evidence=captured)
    assert result["provenance"]["verification"] == "CAPTURED"
    assert result["provenance"]["source"]["evidence_id"] == "obs-test"
    assert result["graph"]["relationships"][0]["evidence"] == "obs-test"
