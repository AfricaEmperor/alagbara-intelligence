import hashlib

import scout_fabric.tracking as tracking
from scout_fabric.tracking import _HTMLSignals, _detect, _validate_public_target, render_markdown, scan_tracking


def test_detects_meta_pixel_from_multiple_fingerprints():
    html = """
    <script src="https://connect.facebook.net/en_US/fbevents.js"></script>
    <script>fbq('init', '123456789'); fbq('track', 'PageView');</script>
    """
    parser = _HTMLSignals()
    parser.feed(html)
    found = _detect(html, parser)
    assert len(found) == 1
    assert found[0].technology_id == "meta_pixel"
    assert found[0].confidence == "high"
    assert any("fbevents.js" in evidence for evidence in found[0].evidence)


def test_detects_google_tag_manager():
    html = '<script src="https://www.googletagmanager.com/gtm.js?id=GTM-ABC123"></script>'
    parser = _HTMLSignals()
    parser.feed(html)
    found = _detect(html, parser)
    assert any(item.technology_id == "google_tag_manager" for item in found)


def test_script_src_and_inline_script_are_inspected():
    html = '<script src="https://analytics.tiktok.com/i18n/pixel/events.js"></script><script>ttq.load("x")</script>'
    parser = _HTMLSignals()
    parser.feed(html)
    found = _detect(html, parser)
    assert any(item.technology_id == "tiktok_pixel" for item in found)


def test_scan_observations_match_shared_contract(monkeypatch):
    payload = b'<script src="https://connect.facebook.net/en_US/fbevents.js"></script><script>fbq("init", "123");</script>'
    monkeypatch.setattr(
        tracking,
        "_fetch_public_html",
        lambda url: ("https://example.org/", payload, "utf-8"),
    )
    report = scan_tracking("https://example.org")
    observation = report["observations"][0]
    assert set(observation) == {"observation_id", "subject", "claim", "state", "attributes", "provenance"}
    assert observation["state"] == "observed"
    assert observation["attributes"]["confidence"] == "high"
    provenance = observation["provenance"]
    assert {"source_url", "observed_at", "collected_at", "collection_method", "adapter", "raw_record_ref"} <= set(provenance)
    assert provenance["raw_record_ref"] == "sha256:" + hashlib.sha256(payload).hexdigest()


def test_no_detection_is_not_reported_as_absence(monkeypatch):
    payload = b"<html><body>Plain page</body></html>"
    monkeypatch.setattr(
        tracking,
        "_fetch_public_html",
        lambda url: ("https://example.org/", payload, "utf-8"),
    )
    report = scan_tracking("https://example.org")
    assert report["detections"] == []
    assert report["assessment"]["status"] == "no_supported_signatures_observed"
    assert "does not prove tracking is absent" in report["assessment"]["summary"]


def test_markdown_report_has_limitations_and_unknowns():
    report = {
        "target_url": "https://example.org",
        "resolved_url": "https://example.org/",
        "scanned_at": "2026-01-01T00:00:00Z",
        "scan_id": "scan-test",
        "detections": [],
        "assessment": {
            "summary": "No supported signatures observed.",
            "opportunities": ["Validate using authorized owner access."],
            "unknowns": ["Campaign performance"],
        },
        "coverage": {"known_limitations": ["Static HTML only."]},
        "source_integrity": {"sha256": "abc"},
    }
    rendered = render_markdown(report)
    assert "Unknowns" in rendered
    assert "Static HTML only" in rendered
    assert "No supported signatures" in rendered


def test_private_ip_target_is_rejected():
    try:
        _validate_public_target("http://127.0.0.1")
    except ValueError as exc:
        assert "non-public" in str(exc)
    else:
        raise AssertionError("private target should be blocked")


def test_embedded_url_credentials_are_rejected():
    try:
        _validate_public_target("https://user:pass@example.org/")
    except ValueError as exc:
        assert "credentials" in str(exc)
    else:
        raise AssertionError("embedded credentials should be blocked")
