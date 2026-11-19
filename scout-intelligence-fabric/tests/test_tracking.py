from scout_fabric.tracking import _HTMLSignals, _detect, _validate_public_target, render_markdown


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
