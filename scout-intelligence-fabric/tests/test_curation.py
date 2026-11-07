"""Curation: corrections, venue directory, merge, publish feed. Synthetic fixtures only."""
import json

import pytest

from ana_engine.curation import UNKNOWN_TOKEN, apply_correction, corrections, effective, merge_venues, update_venue
from ana_engine.pipeline import run_upload
from ana_engine.store import DecisionConflict, StaleWrite
from conftest import POSTER_A, POSTER_B
from radar_contracts import ContractError, validate_contact, validate_event, validate_link
from scout_fabric.text_providers import SidecarTextProvider

P = SidecarTextProvider()
C1, C2, C3, C4 = "cor-00000001-aaaa", "cor-00000002-bbbb", "cor-00000003-cccc", "cor-00000004-dddd"
REV = "operator:Awa"


def seed(store, registry, poster, text=POSTER_A, name="a.png", n=1, src="src-upload-1"):
    out = run_upload(store, registry, poster(name, text, n), src, P)
    return out["event_id"], store.event_version(out["event_id"])


def test_correction_adds_a_human_claim_and_preserves_the_original_extraction(store, registry, poster):
    eid, v = seed(store, registry, poster, "NUIT AFRO\nSamedi 28 novembre 2026\nLieu : Club Exemple, Haie Vive\nDJ Alpha\n")
    before = [c.to_dict() for c in store.get_event(eid).field_claims]
    ev, status = apply_correction(store, eid, {"title": "NUIT AFRO VOL. 3", "end_time": "04:00", "start_time": "22:00"}, REV, "read from the poster", C1, v)
    assert status == "applied" and ev.title == "NUIT AFRO VOL. 3"
    assert ev.start_at == "2026-11-28T22:00:00+01:00" and ev.end_at == "2026-11-29T04:00:00+01:00"
    assert [c.to_dict() for c in ev.field_claims][: len(before)] == before                    # originals untouched, in order
    human = [c for c in ev.field_claims if c.method.startswith("human:")]
    assert {c.field for c in human} == {"title", "end_time", "start_time"} and all(c.state == "observed" and c.evidence_ids for c in human)
    assert "end_time" not in ev.unknown_fields and store.event_version(eid) == v + 1
    assert [c["fields"] for c in [json.loads(a["detail"]) for a in store.audit_log() if a["action"] == "event_corrected"]] == [["end_time", "start_time", "title"]]
    validate_event(ev)


def test_correction_replay_conflict_stale_and_noop(store, registry, poster):
    eid, v = seed(store, registry, poster)
    apply_correction(store, eid, {"title": "NEW TITLE"}, REV, "", C1, v)
    n_audit, n_claims, ver = len(store.audit_log()), len(store.get_event(eid).field_claims), store.event_version(eid)
    for _ in range(3):
        assert apply_correction(store, eid, {"title": "NEW TITLE"}, REV, "", C1, v)[1] == "duplicate"   # replay, even with the old version
    assert (len(store.audit_log()), len(store.get_event(eid).field_claims), store.event_version(eid)) == (n_audit, n_claims, ver)
    with pytest.raises(DecisionConflict):
        apply_correction(store, eid, {"title": "OTHER"}, REV, "", C1, v)
    with pytest.raises(StaleWrite):
        apply_correction(store, eid, {"title": "OTHER"}, REV, "", C2, v)                              # v is now stale
    with pytest.raises(ContractError):
        apply_correction(store, eid, {"title": "NEW TITLE"}, REV, "", C3, ver)                        # equals current value
    assert store.get_event(eid).title == "NEW TITLE" and len(corrections(store, eid)) == 1


@pytest.mark.parametrize("changes", [{"start_date": "2026-02-30"}, {"start_date": "28/11/2026"}, {"start_time": "25:00"},
                                     {"end_time": "4h"}, {"category": "rave"}, {"nonsense": "x"}, {"title": ""}, {"performer": ""},
                                     {"venue": "x" * 81}, {}])
def test_invalid_corrections_are_rejected_and_write_nothing(store, registry, poster, changes):
    eid, v = seed(store, registry, poster)
    n = len(store.audit_log())
    with pytest.raises(ContractError):
        apply_correction(store, eid, changes, REV, "", C1, v)
    assert store.event_version(eid) == v and len(store.audit_log()) == n


def test_unknown_token_clears_a_field_without_inventing_one(store, registry, poster):
    eid, v = seed(store, registry, poster)
    assert any(c.field == "ticket" for c in store.get_event(eid).field_claims)
    ev, _ = apply_correction(store, eid, {"ticket": UNKNOWN_TOKEN}, REV, "price not on the poster", C1, v)
    assert "ticket" in ev.unknown_fields and effective(ev.field_claims, "ticket").value is None
    assert effective(ev.field_claims, "ticket").state == "unknown"


def test_correcting_a_decided_event_reopens_it_explicitly(store, registry, poster):
    eid, v = seed(store, registry, poster)
    store.review_decision(eid, "approve", REV, "", "dec-cur-0001-aaaa", v)
    ev, _ = apply_correction(store, eid, {"title": "CORRECTED"}, REV, "", C1, store.event_version(eid))
    hist = store.decisions(eid)
    assert ev.review_status == "pending" and [(h["kind"], h["decision"]) for h in hist] == [("human", "approve"), ("system", "reopen")]
    assert hist[-1]["resulting_status"] == "pending" and any(a["action"] == "review_reopened" for a in store.audit_log())


def test_human_correction_resolves_a_conflict_but_keeps_it_on_record(store, registry, poster):
    eid, v = seed(store, registry, poster, POSTER_A, "a.png", 1)
    run_upload(store, registry, poster("b.png", POSTER_B, 2), "src-upload-2", P)                   # 22:00 vs 23:00
    ev = store.get_event(eid)
    c = next(c for c in ev.contradictions if c["field"] == "start_time")
    assert c["resolved"] is False and {x["value"] for x in c["values"]} == {"22:00", "23:00"} and ev.confidence == "low"
    ev, _ = apply_correction(store, eid, {"start_time": "22:30"}, REV, "organizer confirmed 22:30", C1, store.event_version(eid))
    c = next(c for c in ev.contradictions if c["field"] == "start_time")
    assert c["resolved"] is True and c["resolved_value"] == "22:30" and {x["value"] for x in c["values"]} == {"22:00", "23:00"}
    assert ev.start_at == "2026-11-14T22:30:00+01:00"
    # a LATER observation must not override the human's value
    run_upload(store, registry, poster("c.png", POSTER_B, 3), "src-upload-1", P)
    assert store.get_event(eid).start_at == "2026-11-14T22:30:00+01:00"


def test_performers_and_organizer_corrections_keep_roles_separate(store, registry, poster):
    eid, v = seed(store, registry, poster)
    ev, _ = apply_correction(store, eid, {"performer": "DJ Zed, Artiste Nova", "organizer": "Collectif Test"}, REV, "", C1, v)
    parties = {p.party_id: p for p in store.parties()}
    assert sorted((parties[i].name, parties[i].role) for i in ev.performer_ids) == [("Artiste Nova", "artist"), ("DJ Zed", "dj")]
    assert parties[ev.organizer_id].name == "Collectif Test" and parties[ev.organizer_id].role == "organizer"
    assert all(not p.identity_verified for p in parties.values())


def test_venue_correction_reuses_an_existing_record_instead_of_duplicating(store, registry, poster):
    a, va = seed(store, registry, poster, POSTER_A, "a.png", 1)
    b, vb = seed(store, registry, poster, "RETRO SESSION\n10/10/2026\nLieu : Bar Fictif, Akpakpa\n", "o.png", 5)
    assert len(store.venues()) == 2
    ev, _ = apply_correction(store, b, {"venue": "Club Exemple"}, REV, "", C1, vb)
    assert ev.venue_id == store.get_event(a).venue_id and len(store.venues()) == 2               # no third record
    ev, _ = apply_correction(store, b, {"venue": "Brand New Place"}, REV, "", C2, store.event_version(b))
    assert len(store.venues()) == 3 and store.get_venue(ev.venue_id).verification_status == "unverified"


def test_update_venue_validates_and_records_everything(store, registry, poster):
    a, _ = seed(store, registry, poster)
    vid = store.get_event(a).venue_id
    v = update_venue(store, vid, "operator:Awa", venue_type="club", address="Rue Test, Haie Vive", district="Haie Vive",
                     add_links=[{"kind": "instagram", "url": "https://www.instagram.com/club_exemple", "official": True}],
                     add_contacts=[{"kind": "phone", "value": "+229 01 90 00 00 00", "authorized": True,
                                    "authorization_note": "number printed on the venue's own poster for bookings"},
                                   {"kind": "email", "value": "internal@example.test"}])
    assert v.venue_type == "club" and len(v.links) == 1 and len(v.contacts) == 2
    for bad in ({"venue_type": "nightmare"}, {"add_links": [{"kind": "instagram", "url": "http://instagram.com/x", "official": True}]},
                {"add_links": [{"kind": "facebook", "url": "https://evil.example/page", "official": True}]},
                {"add_links": [{"kind": "website", "url": "https://x.example"}]},
                {"add_contacts": [{"kind": "phone", "value": "12", "authorized": False}]},
                {"add_contacts": [{"kind": "phone", "value": "+229 01 11 11 11 11", "authorized": True}]},
                {"verification_status": "verified"}, {}):
        with pytest.raises(ContractError):
            update_venue(store, vid, "operator:Awa", **bad)
    v = update_venue(store, vid, "operator:Awa", verification_status="verified", verification_note="confirmed on the venue's official page")
    assert v.verification_status == "verified" and v.verified_by == "operator:Awa" and v.verified_at
    with pytest.raises(PermissionError):
        update_venue(store, vid, " ", venue_type="bar")
    assert sum(1 for a_ in store.audit_log() if a_["action"] == "venue_updated") == 2


def test_merge_venues_redirects_future_uploads_and_keeps_history(store, registry, poster):
    a, _ = seed(store, registry, poster, "SOIREE ONE\n10/12/2026\nLieu : Club Exemple\n", "a.png", 1)
    b, _ = seed(store, registry, poster, "SOIREE TWO\n11/12/2026\nLieu : Le Club Exemple\n", "b.png", 2)
    va, vb = store.get_event(a).venue_id, store.get_event(b).venue_id
    assert va != vb and len(store.venues()) == 2
    assert store.get_venue(vb).verification_status == "candidate" and store.get_venue(vb).candidate_matches == [va]   # flagged, never auto-merged
    verA = store.event_version(b)
    dst = merge_venues(store, vb, va, "operator:Awa")
    assert store.get_event(b).venue_id == va and store.event_version(b) == verA + 1
    assert store.get_venue(vb).merged_into == va and "Le Club Exemple" in dst.aliases
    c, _ = seed(store, registry, poster, "SOIREE THREE\n12/12/2026\nLieu : Le Club Exemple\n", "c.png", 3)
    assert store.get_event(c).venue_id == va and len(store.venues()) == 2                      # no new record
    feed = store.export_feed()
    assert [v["venue_id"] for v in feed["venues"]] == [va]                                      # merged record hidden, not deleted
    with pytest.raises(ContractError):
        merge_venues(store, vb, va, "operator:Awa")
    with pytest.raises(ContractError):
        merge_venues(store, va, va, "operator:Awa")
    assert any(x["action"] == "venue_merged" for x in store.audit_log())


def test_approved_only_feed_is_a_safe_publish_view(store, registry, poster):
    a, va = seed(store, registry, poster, POSTER_A, "a.png", 1)
    b, _ = seed(store, registry, poster, "RETRO SESSION\n10/10/2026\nLieu : Bar Fictif, Akpakpa\n", "o.png", 5)
    vid = store.get_event(a).venue_id
    update_venue(store, vid, "operator:Awa", add_contacts=[{"kind": "phone", "value": "+229 01 90 00 00 00", "authorized": True, "authorization_note": "printed on its own poster"},
                                                          {"kind": "email", "value": "private@example.test"}])
    apply_correction(store, a, {"title": "AFRO NIGHT CORRECTED"}, "operator:Awa", "", C1, va)
    store.review_decision(a, "approve", "operator:Awa", "", "dec-pub-0001-aaaa", store.event_version(a))
    full, pub = store.export_feed(), store.export_feed(approved_only=True)
    assert len(full["events"]) == 2 and [e["event_id"] for e in pub["events"]] == [a] and pub["approved_only"] is True
    e = pub["events"][0]
    assert e["review"]["status"] == "approved" and e["review"]["human_corrected_fields"] == ["title"] and e["review"]["decided_at"]
    assert [v["venue_id"] for v in pub["venues"]] == [vid]                                      # venue of the unapproved event hidden
    v = pub["venues"][0]
    assert v["contacts"] == [{"kind": "phone", "value": "+229 01 90 00 00 00", "authorization_note": "printed on its own poster"}]
    assert v["event_ids"] == [a] and v["last_observed_at"] and v["last_event_date"] == "2026-11-14"
    blob = json.dumps(pub)
    assert "operator:Awa" not in blob and "private@example.test" not in blob and "verified_by" not in blob   # no identities / private contacts
    assert all(c["method"] == "human:correction" for c in e["field_claims"] if c["method"].startswith("human:"))


def test_link_and_contact_validators():
    validate_link({"kind": "facebook", "url": "https://www.facebook.com/x", "official": True})
    validate_link({"kind": "website", "url": "https://club.example/", "source_evidence": ["obs"]})
    with pytest.raises(ContractError):
        validate_link({"kind": "website", "url": "https://user:pw@club.example/", "official": True})
    validate_contact({"kind": "whatsapp", "value": "+229 97 00 00 00"})
    with pytest.raises(ContractError):
        validate_contact({"kind": "email", "value": "not-an-email"})
