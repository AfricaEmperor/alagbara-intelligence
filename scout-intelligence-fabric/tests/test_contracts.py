from scout_fabric.models import Observation, Provenance
from scout_fabric.normalize import canonicalize_url, normalize_whitespace, stable_observation_id

def test_stable_id_is_deterministic():
    assert stable_observation_id("https://example.org/a", "X", "Y") == stable_observation_id("https://example.org/a", "X", "Y")

def test_whitespace_normalization():
    assert normalize_whitespace("  a\\n  b  ") == "a b"

def test_url_fragment_removed_and_query_preserved():
    assert canonicalize_url("HTTPS://Example.org/a?x=1#section") == "https://example.org/a?x=1"

def test_provenance_requires_absolute_http_url():
    provenance = Provenance("https://example.org", "2026-10-02T09:00:00+00:00", "2026-10-02T09:01:00+00:00", "public_page", "test")
    provenance.validate()
    bad = Provenance("example.org", "2026-10-02T09:00:00+00:00", "2026-10-02T09:01:00+00:00", "public_page", "test")
    try:
        bad.validate()
    except ValueError:
        pass
    else:
        raise AssertionError("invalid source URL should fail")
