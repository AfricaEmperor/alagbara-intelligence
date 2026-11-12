"""MUSEOPS-PI-001 acceptance tests. Fixtures are SYNTHETIC (fictional); real research fixtures use the same schema."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ana_engine.store import RadarStore
from partner_intel import (
    AttributeClaim,
    ClaimConflict,
    Entity,
    RelationshipClaim,
    TimePeriod,
    build_profile,
)
from partner_intel.fixtures import load_fixture
from radar_contracts import ContractError

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "partner_intel"
A, B, C = (FIX / f"synthetic-{n}.json" for n in ("a-awards-sponsorship", "b-brand-platform-talent", "c-venue-activation"))


@pytest.fixture
def load(tmp_path):
    stores = []

    def _load(path, mutate=None):
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if mutate:
            raw = mutate(copy.deepcopy(raw))
        f = tmp_path / f"fx{len(stores)}.json"
        f.write_text(json.dumps(raw), encoding="utf-8")
        s = RadarStore(tmp_path / f"data{len(stores)}")
        stores.append(s)
        book, meta = load_fixture(f, s)
        return book, meta, build_profile(book, meta["focus"], meta["as_of"])
    yield _load
    for s in stores:
        s.close()


def ids(items):
    return {i["claim_id"] for i in items}


# ---- traceability -----------------------------------------------------------------------------
def test_every_claim_traces_to_ledger_evidence(load):
    for path in (A, B, C):
        book, _meta, _p = load(path)
        for c in [*book.relationships.values(), *book.attributes.values()]:
            prov = book.provenance(c)
            assert prov, c.claim_id
            for p in prov:
                ev = book.store.get_evidence(p["observation_id"])
                assert ev is not None and p["source_url"].startswith("https://") and p["collection_method"] == "fixture"
                assert p["capture_date"] and p["observation_date"] and p["evidence_state"] and p["content_hash"]
                assert c.raw_excerpt and " ".join(c.raw_excerpt.split()).lower() in " ".join(ev["metadata"]["captured_text"].split()).lower()


def test_relationship_retains_all_required_fields(load):
    _book, _m, p = load(A)
    rel = p["relationships"]["historical"][0]
    for key in ("evidence_ids", "observed_at", "state", "period", "asserted", "raw_excerpt", "interpretation", "contradiction_ids", "provenance"):
        assert key in rel
    prov = rel["provenance"][0]
    assert {"source_id", "source_url", "collection_method", "capture_date", "observation_date", "raw_evidence", "evidence_state"} <= set(prov)
    assert prov["capture_date"] != prov["observation_date"]  # capture date is distinct from the date the source states


def test_claim_citing_missing_or_untraceable_evidence_is_rejected(load):
    book, _m, _p = load(A)
    base = dict(claim_id="x1", observed_at="2026-01-01", state="observed", raw_excerpt="nothing like this", subject="org_meridian",
                relation="OWNS", object="brand_aurelia")
    with pytest.raises(ContractError, match="not in the ledger"):
        book.add_relationship(RelationshipClaim(evidence_ids=("deadbeef",), **base))
    some = next(iter(book.relationships.values())).evidence_ids
    with pytest.raises(ContractError, match="does not occur"):
        book.add_relationship(RelationshipClaim(evidence_ids=some, **base))


def test_claim_state_cannot_exceed_its_evidence(load):
    book, _m, _p = load(A)
    blog = next(c for c in book.relationships.values() if c.claim_id == "a-r6").evidence_ids
    with pytest.raises(ContractError, match="exceeds the strength"):
        book.add_relationship(RelationshipClaim(claim_id="x2", evidence_ids=blog, observed_at="2024-04-02", state="observed",
                                                raw_excerpt="are wrong", subject="brand_aurelia", relation="ACTIVATES", object="event_lsa24"))


def test_endpoint_typing_is_enforced(load):
    book, _m, _p = load(A)
    ev = next(iter(book.relationships.values())).evidence_ids
    with pytest.raises(ContractError, match="not an allowed endpoint"):
        book.add_relationship(RelationshipClaim(claim_id="x3", evidence_ids=ev, observed_at="2024-02-20", state="observed",
                                                raw_excerpt="Meridian Spirits Group owns", subject="person_okoro", relation="OWNS", object="brand_aurelia"))


# ---- coexistence and contradictions -------------------------------------------------------------
def test_conflicting_claims_coexist_and_are_never_overwritten(load):
    book, _m, p = load(A)
    assert {"a-r5", "a-r6"} <= set(book.relationships)  # assertion and denial both stored
    kinds = {c["kind"]: set(c["claim_ids"]) for c in p["contradictions"]}
    assert kinds["assertion_denial"] == {"a-r5", "a-r6"}
    same = book.relationships["a-r5"]
    assert book.add_relationship(same) is same                              # identical re-add is a no-op
    with pytest.raises(ClaimConflict):                                      # different payload under same id is refused
        book.add_relationship(RelationshipClaim(**{**same.to_dict(), "evidence_ids": same.evidence_ids, "state": "derived",
                                                    "period": same.period}))
    assert book.relationships["a-r5"] is same


def test_contradictions_are_deterministic_and_visible_in_profile(load, tmp_path):
    _b1, _m1, p1 = load(A)
    _b2, _m2, p2 = load(A)
    assert p1["contradictions"] == p2["contradictions"] and p1["contradictions"]
    assert all(r["contradiction_ids"] for r in p1["relationships"]["historical"] if r["claim_id"] in ("a-r5",))


def test_representation_conflict_in_b_is_visible_via_intermediaries(load):
    _b, _m, p = load(B)
    assert any(c["kind"] == "assertion_denial" and set(c["claim_ids"]) == {"b-r4", "b-r6"} for c in p["contradictions"])


def test_unknown_period_conflicts_stay_visible():
    assert TimePeriod().may_overlap(TimePeriod("2020-01-01", "2020-12-31"))
    assert not TimePeriod("2020-01-01", "2020-12-31").may_overlap(TimePeriod("2021-01-01", "2021-12-31"))


# ---- function vs authority, intermediary vs causation --------------------------------------------
def test_function_is_distinct_from_decision_authority(load):
    _b, _m, p = load(A)
    f = p["functions_and_roles"][0]
    assert f["leaders"] and f["leaders"][0]["subject"] == "person_okoro"
    assert f["authority_inferred_from_function"] is False
    assert f["decision_authority"][0]["state"] == "unknown"


def test_authority_requires_its_own_evidence(load):
    def add_authority(raw):
        raw["evidence"].append(dict(key="z1", source_id="synthetic-z", source_platform="public_html", url="https://fixtures.invalid/z",
                                    collected_at="2026-11-01T09:00:00+00:00", published_at="2026-11-01", evidence_state="observed",
                                    raw_text="Adaeze Okoro signs off all partnership spend at Meridian Spirits Group."))
        raw["attributes"].append(dict(claim_id="z-a1", entity="person_okoro", attribute="DECISION_AUTHORITY", value="signs off partnership spend",
                                      evidence=["z1"], observed_at="2026-11-01", state="observed", raw_excerpt="signs off all partnership spend",
                                      period=dict(start="2026-11-01", end=None)))
        return raw
    _b, _m, p = load(A, add_authority)
    assert p["functions_and_roles"][0]["decision_authority"][0]["claim_id"] == "z-a1"


def test_intermediary_presence_is_not_causation(load):
    for path in (A, B, C):
        _b, _m, p = load(path)
        assert p["candidate_intermediaries"]
        for i in p["candidate_intermediaries"]:
            assert i["causation_established"] is False and "not evidence" in i["note"]
    _b, _m, pa = load(A)
    assert pa["candidate_intermediaries"][0]["basis"] == ["co_presence"]
    _b, _m, pc = load(C)
    assert pc["candidate_intermediaries"][0]["basis"] == ["introduction_evidenced"]


# ---- historical vs current; WATCH / QUALIFIED / ACTIVATABLE --------------------------------------
def test_a_historical_sponsorship_never_becomes_a_current_opportunity(load):
    _b, _m, p = load(A)
    assert p["opportunity"]["state"] == "WATCH"
    assert {r["claim_id"] for r in p["relationships"]["historical"]} >= {"a-r5"}
    assert p["commercial_need"] == []


def test_missing_commercial_need_produces_watch_even_with_capacity_intent_and_intro(load):
    drop = lambda raw: {**raw, "attributes": [a for a in raw["attributes"] if a["attribute"] != "COMMERCIAL_NEED"]}
    _b, _m, p = load(C, drop)
    assert p["opportunity"]["state"] == "WATCH"
    assert p["next_human_question"]["target_unknown"] == "commercial_need"


def test_expired_need_is_not_current(load):
    def expire(raw):
        for a in raw["attributes"]:
            if a["attribute"] == "COMMERCIAL_NEED":
                a["period"] = dict(start="2025-01-01", end="2025-06-30")
        return raw
    _b, _m, p = load(C, expire)
    assert p["opportunity"]["state"] == "WATCH"


def test_b_is_qualified_not_activatable(load):
    _b, _m, p = load(B)
    assert p["opportunity"]["state"] == "QUALIFIED"
    assert p["next_human_question"]["target_unknown"] == "commercial_intent"


def test_c_is_activatable_and_next_question_targets_authority(load):
    _b, _m, p = load(C)
    assert p["opportunity"]["state"] == "ACTIVATABLE"
    q = p["next_human_question"]
    assert q["target_unknown"] == "decision_authority" and "does not establish authority" in q["question"]
    assert {c["kind"] for c in p["contradictions"]} == {"period_conflict"}   # visible, non-blocking


def test_blocking_contradiction_prevents_activation(load):
    def deny_need(raw):
        raw["evidence"].append(dict(key="z2", source_id="synthetic-z2", source_platform="public_html", url="https://fixtures.invalid/z2",
                                    collected_at="2026-11-02T09:00:00+00:00", published_at="2026-11-02", evidence_state="observed",
                                    raw_text="Meridian Spirits Group has paused all Lagos venue partnerships for 2027."))
        raw["attributes"].append(dict(claim_id="z-a2", entity="org_meridian", attribute="COMMERCIAL_NEED", value="Lagos venue partner", asserted=False,
                                      evidence=["z2"], observed_at="2026-11-02", state="observed", raw_excerpt="paused all Lagos venue partnerships",
                                      period=dict(start="2026-11-02", end="2027-12-31")))
        return raw
    _b, _m, p = load(C, deny_need)
    assert p["opportunity"]["state"] == "QUALIFIED"
    assert any("contradiction" in r for r in p["opportunity"]["rationale"])
    assert p["next_human_question"]["target_unknown"].startswith("contradiction:")


def test_unverified_intent_or_missing_introduction_blocks_activation(load):
    def weak(raw):
        raw["relationships"] = [r for r in raw["relationships"] if r["relation"] != "INTRODUCES"]
        return raw
    _b, _m, p = load(C, weak)
    assert p["opportunity"]["state"] == "QUALIFIED"
    assert p["next_human_question"]["target_unknown"] == "intermediary_path"


def test_interpretation_text_never_changes_state(load):
    def reword(raw):
        for c in raw["relationships"] + raw["attributes"]:
            c["interpretation"] = "This is a perfect, urgent, ready-to-activate opportunity."
        return raw
    no_need = lambda raw: {**raw, "attributes": [a for a in raw["attributes"] if a["attribute"] != "COMMERCIAL_NEED"]}
    for path, variant in ((A, None), (B, None), (C, None), (C, no_need)):
        both = (lambda r, v=variant: reword(v(r))) if variant else reword
        _b, _m, base = load(path, variant)
        _b, _m, changed = load(path, both)
        assert changed["opportunity"]["state"] == base["opportunity"]["state"]
        assert changed["next_human_question"] == base["next_human_question"]


def test_profile_has_all_twelve_sections_and_valid_state(load):
    for path in (A, B, C):
        _b, _m, p = load(path)
        for k in ("identity", "organizational_context", "functions_and_roles", "relationships", "candidate_intermediaries", "commercial_capacity",
                  "commercial_need", "commercial_intent", "visibility_bias", "contradictions", "unknowns", "next_human_question", "opportunity"):
            assert k in p, k
        assert p["opportunity"]["state"] in ("WATCH", "QUALIFIED", "ACTIVATABLE")
        assert p["next_human_question"]["question"].endswith("?") or p["next_human_question"]["target_unknown"] == "none"


def test_visibility_bias_is_reported(load):
    _b, _m, p = load(A)
    assert p["visibility_bias"]["explicit_claims"] and "online-only" in p["visibility_bias"]["note"]


# ---- reuse guarantees ---------------------------------------------------------------------------
def test_evidence_lives_only_in_the_existing_radar_ledger(load):
    book, meta, _p = load(C)
    assert len(book.store.all_evidence()) == len(meta["evidence_keys"])
    tables = {r[0] for r in book.store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not any("partner" in t or "claim" in t or "relationship" in t for t in tables)  # no second store / new tables


def test_fixtures_are_labelled_synthetic():
    for path in (A, B, C):
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["synthetic"] is True and raw["note"].startswith("SYNTHETIC") and raw["schema"] == "partner-fixture/0.1"
        assert all(e["url"].startswith("https://fixtures.invalid/") for e in raw["evidence"])


def test_attribute_claim_validation():
    with pytest.raises(ContractError):
        AttributeClaim(claim_id="q", evidence_ids=(), observed_at="2026-01-01", state="observed", raw_excerpt="x", entity="e", attribute="COMMERCIAL_NEED", value="v")
    with pytest.raises(ContractError):
        AttributeClaim(claim_id="q", evidence_ids=("a",), observed_at="2026-01-01", state="observed", raw_excerpt="x", entity="e", attribute="BOGUS", value="v")
    with pytest.raises(ContractError):
        Entity("e", "ROBOT", "n")
