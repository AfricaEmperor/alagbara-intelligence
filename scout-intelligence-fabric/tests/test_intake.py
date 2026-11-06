import json
import subprocess
import sys
from pathlib import Path

import pytest

from scout_fabric.intake import IntakeRefused, build_bundle, load_registry

FX = Path(__file__).parent.parent / "fixtures"
REG = load_registry(str(FX / "registry.synthetic.json"))
T = "2026-11-06T10:00:00+00:00"


def bundle(src, url, f):
    return build_bundle(REG[src], url, (FX / f).read_text(encoding="utf-8"), collected_at=T)


def test_lagos_and_cotonou_bundles_have_provenance_and_candidate():
    for src, url, f, city in [
        ("synthetic-lagos", "https://lagos-fixture.test/rooftop", "lagos_venue.html", "Lagos"),
        ("synthetic-cotonou", "https://cotonou-fixture.test/maquis", "cotonou_venue.html", "Cotonou"),
    ]:
        b = bundle(src, url, f)
        assert b["contract"] == "scout-candidate/0.1" and b["source"]["city"] == city
        prov = b["observation"]["provenance"]
        assert prov["raw_record_ref"].startswith("sha256:") and len(prov["raw_record_ref"]) == 71
        assert b["observation"]["state"] == "unverified"
        assert b["candidate"]["venue"]["name"] and b["candidate"]["event"]["startAt"]


def test_bundle_is_deterministic_and_hash_tracks_content():
    a = bundle("synthetic-lagos", "https://lagos-fixture.test/rooftop", "lagos_venue.html")
    b = bundle("synthetic-lagos", "https://lagos-fixture.test/rooftop", "lagos_venue.html")
    d = bundle("synthetic-lagos", "https://lagos-fixture.test/rooftop/", "lagos_venue_duplicate.html")
    assert a == b
    assert a["observation"]["provenance"]["raw_record_ref"] != d["observation"]["provenance"]["raw_record_ref"]


def test_unauthorized_or_wrong_host_refused():
    html = (FX / "lagos_venue.html").read_text()
    with pytest.raises(IntakeRefused):
        build_bundle(REG["unauthorized-example"], "https://example.org/x", html)
    with pytest.raises(IntakeRefused):
        build_bundle(REG["synthetic-lagos"], "https://evil.test/x", html)


def test_missing_facts_stay_none():
    b = bundle("synthetic-lagos", "https://lagos-fixture.test/bare", "lagos_unqualified.html")
    assert b["candidate"]["event"] is None and b["candidate"]["venue"]["address"] is None


def test_cli_roundtrip(tmp_path):
    out = tmp_path / "o.json"
    r = subprocess.run([sys.executable, "-m", "scout_fabric.cli_intake_entry", "--registry", str(FX / "registry.synthetic.json"),
                        "--source", "synthetic-cotonou", "--url", "https://cotonou-fixture.test/maquis",
                        "--html-file", str(FX / "cotonou_venue.html"), "-o", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(out.read_text())["source"]["id"] == "synthetic-cotonou"
    r = subprocess.run([sys.executable, "-m", "scout_fabric.cli_intake_entry", "--registry", str(FX / "registry.synthetic.json"),
                        "--source", "unauthorized-example", "--url", "https://example.org/x",
                        "--html-file", str(FX / "cotonou_venue.html")], capture_output=True, text=True)
    assert r.returncode == 2 and "refused" in r.stderr
