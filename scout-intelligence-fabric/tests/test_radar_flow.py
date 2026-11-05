import shutil

import pytest
from conftest import POSTER_A, POSTER_B, make_mp4, make_png

from ana_engine.extract import extract_event
from ana_engine.pipeline import run_upload
from radar_contracts import TIMEZONE, ContractError, validate_event
from scout_fabric.intake import RejectedUpload, ingest_upload
from scout_fabric.sources import FacebookPageAdapter, UnauthorizedSource
from scout_fabric.text_providers import SidecarTextProvider

P = SidecarTextProvider()
needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg unavailable")


def claims(ex, f):
    return [c.value for c in ex.claims if c.field == f]


# AT-01 / AT-02 -------------------------------------------------------------------------------
def test_at01_at02_authorized_image_upload_ingested(store, registry, poster):
    out = run_upload(store, registry, poster("a.png", POSTER_A), "src-upload-1", P)
    ev = store.get_evidence(out["observation_id"])
    assert out["evidence_created"] and ev["media_type"] == "image"
    assert ev["metadata"]["dimensions"] == {"width": 8, "height": 8}
    assert ev["evidence_state"] == "unverified" and ev["metadata"]["context_verified"] is False


# AT-03 ---------------------------------------------------------------------------------------
@needs_ffmpeg
def test_at03_video_upload_accepted(store, registry, tmp_path):
    ev, created = ingest_upload(make_mp4(tmp_path / "v.mp4"), "src-upload-1", registry, store.media_dir)
    assert created and ev.media_type == "video" and "duration" in ev.metadata


# AT-04..07 ----------------------------------------------------------------------------------
def test_at04_to_at07_extraction(store, registry, poster):
    ex = extract_event(POSTER_A, "obs1", "unverified", "sidecar")
    assert claims(ex, "title") == ["AFRO NIGHT VOL.3"]                      # AT-04
    assert claims(ex, "start_date") == ["2026-11-14"]                       # AT-05
    assert claims(ex, "venue") == ["Club Exemple"] and claims(ex, "district") == ["Haie Vive"]  # AT-06
    assert claims(ex, "organizer") == ["Studio Fictif"]                     # AT-07
    assert set(claims(ex, "performer")) == {"DJ Alpha", "DJ Beta", "Artiste Demo"}
    assert "Studio Fictif" not in claims(ex, "performer")                   # organizer != performer
    assert all(c.state in ("derived", "unverified") for c in ex.claims)     # never "observed"
    assert all(c.evidence_ids == ("obs1",) for c in ex.claims)


def test_at05_weekday_or_missing_year_stays_unknown():
    ex = extract_event("SOIREE ZOUK\nSamedi soir\nLieu : Bar Test\n", "o")
    assert "start_date" in ex.unknown and not claims(ex, "start_date")
    ex2 = extract_event("SOIREE ZOUK\n14 novembre\nLieu : Bar Test\n", "o")
    assert "start_date" in ex2.unknown and ex2.partial_date == {"day": 14, "month": 11}


def test_at06_unknown_venue_marked_unknown(store, registry, poster):
    out = run_upload(store, registry, poster("n.png", "KARAOKE NIGHT\n20/12/2026\n"), "src-upload-1", P)
    ev = store.get_event(out["event_id"])
    assert ev.venue_id is None and "venue" in ev.unknown_fields
    validate_event(ev)


def test_event_fields_in_stored_event_and_timezone(store, registry, poster):
    out = run_upload(store, registry, poster("a.png", POSTER_A), "src-upload-1", P)
    ev = store.get_event(out["event_id"])
    assert ev.timezone == TIMEZONE == "Africa/Porto-Novo"
    assert ev.start_at == "2026-11-14T22:00:00+01:00" and ev.end_at == "2026-11-15T04:00:00+01:00"
    assert ev.review_status == "pending" and ev.venue_id and ev.organizer_id and len(ev.performer_ids) == 3
    roles = {p.role for p in store.parties()}
    assert {"organizer", "dj", "artist"} <= roles


# AT-08 / AT-10 / AT-11 ----------------------------------------------------------------------
def test_at08_at10_at11_duplicate_merge_preserves_contradiction_and_provenance(store, registry, poster):
    a = run_upload(store, registry, poster("a.png", POSTER_A, 1), "src-upload-1", P)
    b = run_upload(store, registry, poster("b.png", POSTER_B, 2), "src-upload-2", P)
    assert a["event_id"] == b["event_id"]                                    # AT-08: one canonical event
    assert len(store.events()) == 1
    ev = store.get_event(a["event_id"])
    assert set(ev.evidence_references) == {a["observation_id"], b["observation_id"]}  # AT-11
    conflict = {c["field"]: c for c in ev.contradictions}
    assert "start_time" in conflict                                          # AT-10: 22:00 vs 23:00 kept
    assert {v["value"] for v in conflict["start_time"]["values"]} == {"22:00", "23:00"}
    assert len([c for c in ev.field_claims if c.field == "start_time"]) == 2  # nothing overwritten
    assert ev.confidence == "low"                                            # contradiction lowers confidence
    assert len(store.venues()) == 1                                          # same venue resolved once
    validate_event(ev)


def test_same_venue_same_day_different_title_not_merged(store, registry, poster):
    run_upload(store, registry, poster("a.png", POSTER_A, 1), "src-upload-1", P)
    other = "RUMBA ELECTRIQUE\n14 novembre 2026\nLieu : Club Exemple\n"
    run_upload(store, registry, poster("c.png", other, 3), "src-upload-1", P)
    assert len(store.events()) == 2


def test_stage_name_alone_does_not_merge_people(store, registry, poster):
    run_upload(store, registry, poster("a.png", POSTER_A, 1), "src-upload-1", P)
    run_upload(store, registry, poster("d.png", "AUTRE SOIREE\n05/12/2026\nLieu : Bar Test\nDJ Alpha\n", 4), "src-upload-1", P)
    alphas = [p for p in store.parties() if p.name == "DJ Alpha"]
    assert len(alphas) == 2 and alphas[0].party_id != alphas[1].party_id
    assert all(not p.identity_verified for p in alphas)
    assert any(p.possible_same_as for p in alphas)                           # flagged for review


# AT-09 --------------------------------------------------------------------------------------
def test_at09_reingestion_is_idempotent(store, registry, poster):
    p = poster("a.png", POSTER_A)
    first = run_upload(store, registry, p, "src-upload-1", P)
    second = run_upload(store, registry, p, "src-upload-1", P)
    assert first["observation_id"] == second["observation_id"] and not second["evidence_created"]
    assert len(store.events()) == 1 and len(store.all_evidence()) == 1
    assert len(store.get_event(first["event_id"]).field_claims) == len(
        [c for c in extract_event(POSTER_A, "x", "unverified").claims])
    assert len(store.parties()) == 4  # 1 organizer + 3 performers, not doubled


# AT-12 --------------------------------------------------------------------------------------
def test_at12_unauthorized_acquisition_rejected_and_recorded(store, registry, poster):
    for sid in ("src-pending", "src-unknown"):
        with pytest.raises(UnauthorizedSource):
            run_upload(store, registry, poster("a.png", POSTER_A), sid, P)
    assert store.events() == [] and store.all_evidence() == []
    assert {f["source_id"] for f in store.failures()} == {"src-pending", "src-unknown"}
    assert all(f["alternative"] for f in store.failures())


def test_facebook_boundary_refuses_without_graph_client(registry):
    with pytest.raises(UnauthorizedSource) as e:
        FacebookPageAdapter(registry).fetch_page_posts("src-fb", "2026-11-05T00:00:00+00:00")
    assert "not configured" in e.value.reason and e.value.alternative
    with pytest.raises(UnauthorizedSource):  # unapproved/other-platform source never reaches the client
        FacebookPageAdapter(registry, graph_client=object()).fetch_page_posts("src-upload-1", "x")


def test_upload_rejects_wrong_content_and_mismatched_extension(store, registry, tmp_path):
    fake = tmp_path / "x.png"; fake.write_bytes(b"not an image at all")
    with pytest.raises(RejectedUpload):
        ingest_upload(fake, "src-upload-1", registry, store.media_dir)
    vid = tmp_path / "y.mp4"; make_png(tmp_path / "z.png"); vid.write_bytes((tmp_path / "z.png").read_bytes())
    with pytest.raises(RejectedUpload):
        ingest_upload(vid, "src-upload-1", registry, store.media_dir)


# AT-15 --------------------------------------------------------------------------------------
def test_at15_human_review_changes_state_and_is_audited(store, registry, poster):
    out = run_upload(store, registry, poster("a.png", POSTER_A), "src-upload-1", P)
    with pytest.raises(PermissionError):
        store.review(out["event_id"], "approve", "  ")
    with pytest.raises(ContractError):
        store.review(out["event_id"], "publish", "ops")
    assert store.review(out["event_id"], "approve", "reviewer@example").review_status == "approved"
    assert store.review(out["event_id"], "request_correction", "reviewer@example", "check time").review_status == "correction_requested"
    log = [a for a in store.audit_log() if a["action"].startswith("review:")]
    assert [a["actor"] for a in log] == ["reviewer@example"] * 2


def test_new_conflicting_evidence_reopens_approved_event(store, registry, poster):
    a = run_upload(store, registry, poster("a.png", POSTER_A, 1), "src-upload-1", P)
    store.review(a["event_id"], "approve", "reviewer@example")
    run_upload(store, registry, poster("b.png", POSTER_B, 2), "src-upload-2", P)
    assert store.get_event(a["event_id"]).review_status == "pending"


def test_feed_contains_provenance_and_review_state(store, registry, poster):
    out = run_upload(store, registry, poster("a.png", POSTER_A), "src-upload-1", P)
    feed = store.export_feed("2026-11-05T00:00:00+00:00")
    e = feed["events"][0]
    assert feed["timezone"] == "Africa/Porto-Novo" and e["event_id"] == out["event_id"]
    assert e["venue"]["name"] == "Club Exemple" and e["evidence"][0]["content_hash"]
    assert out["event_id"] in feed["review"]["pending"]


def test_missing_text_is_skipped_not_invented(store, registry, poster):
    out = run_upload(store, registry, poster("e.png", None), "src-upload-1", P)
    assert out["event_id"] is None and store.events() == []
    assert any(a["action"] == "extraction_skipped" for a in store.audit_log())


def test_apply_decisions_from_pulse_is_idempotent_and_rejects_bad_rows(store, registry, poster, tmp_path):
    import json
    out = run_upload(store, registry, poster("a.png", POSTER_A), "src-upload-1", P)
    f = tmp_path / "decisions.jsonl"
    good = {"decision_id": "d1", "event_id": out["event_id"], "decision": "approve", "reviewer": "Reviewer One", "note": ""}
    bad = {"decision_id": "d2", "event_id": out["event_id"], "decision": "publish", "reviewer": "x"}
    anon = {"decision_id": "d3", "event_id": out["event_id"], "decision": "reject", "reviewer": " "}
    f.write_text("\n".join(json.dumps(r) for r in (good, bad, anon)) + "\nnot json\n")
    assert store.apply_decisions(f) == {"applied": 1, "skipped_duplicate": 0, "rejected": 3}
    assert store.apply_decisions(f)["applied"] == 0
    assert store.get_event(out["event_id"]).review_status == "approved"
