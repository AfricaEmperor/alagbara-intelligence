"""Partner Lead Profile: a deterministic READ MODEL over a ClaimBook. Writes nothing.

Opportunity state (WATCH / QUALIFIED / ACTIVATABLE) is derived ONLY from claims whose period provably covers
`as_of`. Historical sponsorship/activation never contributes. Free-text `interpretation` is never read.
Organisational function never implies decision authority; intermediary presence never implies causation.
"""
from __future__ import annotations

from collections import Counter, deque
from typing import Any

from .claimbook import ClaimBook
from .models import AttributeClaim, RelationshipClaim

STRUCTURAL = ("OWNS", "EMPLOYS", "LEADS_FUNCTION")
OPPORTUNITY_STATES = ("WATCH", "QUALIFIED", "ACTIVATABLE")
STRONG = ("observed", "derived")


def _live(c: Any) -> bool:
    return c.asserted and c.state != "unknown"


def _current(c: Any, as_of: str) -> bool:
    return _live(c) and c.period.covers(as_of)


def _timing(c: Any, as_of: str) -> str:
    if c.period.unknown:
        return "period_unknown"
    if c.period.covers(as_of):
        return "current"
    return "historical" if c.period.is_historical(as_of) else "future"


def _context(book: ClaimBook, entity_id: str) -> set[str]:
    """Organisational context: entities within 3 evidenced structural hops (OWNS/EMPLOYS/LEADS_FUNCTION)."""
    adj: dict[str, set[str]] = {}
    for c in book.relationships.values():
        if c.relation in STRUCTURAL and _live(c):
            adj.setdefault(c.subject, set()).add(c.object)
            adj.setdefault(c.object, set()).add(c.subject)
    seen, queue = {entity_id: 0}, deque([entity_id])
    while queue:
        cur = queue.popleft()
        if seen[cur] == 3:
            continue
        for nxt in adj.get(cur, ()):
            if nxt not in seen:
                seen[nxt] = seen[cur] + 1
                queue.append(nxt)
    return set(seen)


def build_profile(book: ClaimBook, entity_id: str, as_of: str) -> dict[str, Any]:
    target = book._entity(entity_id)
    ctx = _context(book, entity_id)
    name = lambda i: book.entities[i].name
    contradictions = book.contradictions()
    con_by_claim: dict[str, list[str]] = {}
    for k in contradictions:
        for cid in k.claim_ids:
            con_by_claim.setdefault(cid, []).append(k.contradiction_id)

    def rel_view(c: RelationshipClaim) -> dict[str, Any]:
        return {**c.to_dict(), "timing": _timing(c, as_of), "provenance": book.provenance(c),
                "contradiction_ids": con_by_claim.get(c.claim_id, [])}

    def attr_view(c: AttributeClaim) -> dict[str, Any]:
        return {**c.to_dict(), "entity_name": name(c.entity), "timing": _timing(c, as_of), "provenance": book.provenance(c),
                "contradiction_ids": con_by_claim.get(c.claim_id, [])}

    ctx_rels = [c for c in book.relationships.values() if c.subject in ctx or c.object in ctx or (c.counterparty in ctx)]
    ctx_attrs = [c for c in book.attributes.values() if c.entity in ctx]
    by_attr = lambda a: [c for c in ctx_attrs if c.attribute == a]

    # --- 2/3 organisational context, functions and roles (function != authority) ------------------
    owners = [rel_view(c) for c in book.relationships.values() if c.relation == "OWNS" and c.object == entity_id]
    functions = []
    for f in (book.entities[i] for i in sorted(ctx) if book.entities[i].type == "FUNCTION"):
        leaders = [rel_view(c) for c in book.relationships.values() if c.relation == "LEADS_FUNCTION" and c.object == f.entity_id]
        auth = [attr_view(c) for c in ctx_attrs if c.attribute == "DECISION_AUTHORITY" and c.entity in
                {f.entity_id, *[book.relationships[x["claim_id"]].subject for x in leaders]}]
        functions.append({"function": f.name, "function_id": f.entity_id, "leaders": leaders,
                          "decision_authority": auth or [{"state": "unknown", "note": "Leading a function is not evidence of decision authority."}],
                          "authority_inferred_from_function": False})

    # --- 5 candidate intermediaries (presence != causation) --------------------------------------
    linked = {c.object for c in book.relationships.values() if c.relation in ("ACTIVATES", "PARTNERS_WITH") and c.subject in ctx and _live(c)}
    linked |= {c.subject for c in book.relationships.values() if c.relation == "PARTNERS_WITH" and c.object in ctx and _live(c)}
    performers = {c.subject for c in book.relationships.values() if c.relation == "PERFORMS_AT" and c.object in linked and _live(c)}
    cands: dict[str, dict[str, Any]] = {}

    def cand(i: str, basis: str, c: RelationshipClaim) -> None:
        if i in ctx or book.entities[i].type == "FUNCTION":
            return
        e = cands.setdefault(i, {"entity_id": i, "name": name(i), "type": book.entities[i].type, "basis": set(), "via": [],
                                 "causation_established": False,
                                 "note": "Presence in the evidence is not evidence that this party caused any introduction, deal or outcome."})
        e["basis"].add(basis); e["via"].append(rel_view(c))
    for c in book.relationships.values():
        if not _live(c):
            continue
        if c.relation == "INTRODUCES" and (c.object in ctx or c.counterparty in ctx):
            cand(c.subject, "introduction_evidenced", c)
        elif c.relation == "ORGANIZES" and c.object in linked or c.relation == "REPRESENTS" and (c.object in performers or c.object in linked):
            cand(c.subject, "co_presence", c)
    for c in book.relationships.values():
        if _live(c) and c.relation == "PERFORMS_AT" and c.object in linked:
            cand(c.subject, "co_presence", c)
    intermediaries = [{**v, "basis": sorted(v["basis"])} for v in cands.values()]
    intro_ok = any("introduction_evidenced" in v["basis"] and any(x["timing"] == "current" for x in v["via"]) for v in intermediaries)

    # --- 6-9 commercial attributes ----------------------------------------------------------------
    sec = {a: [attr_view(c) for c in by_attr(a)] for a in ("COMMERCIAL_CAPACITY", "COMMERCIAL_NEED", "COMMERCIAL_INTENT", "VISIBILITY_BIAS")}
    cur = lambda a: [c for c in by_attr(a) if _current(c, as_of)]
    need, cap, intent = cur("COMMERCIAL_NEED"), cur("COMMERCIAL_CAPACITY"), cur("COMMERCIAL_INTENT")
    ev_ids = {e for c in [*ctx_rels, *ctx_attrs] for e in c.evidence_ids}
    src_count = Counter()
    for oid in ev_ids:
        ev = book.store.get_evidence(oid) or {}
        src_count[ev.get("source_id")] += 1
    top = src_count.most_common(1)[0] if src_count else (None, 0)
    concentrated = len(ev_ids) >= 2 and top[1] / len(ev_ids) >= 0.8
    visibility = {
        "explicit_claims": sec["VISIBILITY_BIAS"],
        "single_source_concentration": {"source_id": top[0], "share": round(top[1] / len(ev_ids), 2) if ev_ids else 0.0, "warning": concentrated},
        "note": "Evidence is public, online-only and skews toward what parties choose to publicise; undisclosed relationships are invisible.",
    }

    # --- 10 contradictions touching this profile ---------------------------------------------------
    ctx_claim_ids = {c.claim_id for c in [*ctx_rels, *ctx_attrs]} | {x["claim_id"] for v in intermediaries for x in v["via"]}
    relevant = [k for k in contradictions if set(k.claim_ids) & ctx_claim_ids]
    key_ids = {c.claim_id for c in [*by_attr("COMMERCIAL_NEED"), *by_attr("COMMERCIAL_CAPACITY"), *by_attr("COMMERCIAL_INTENT")]}
    blocking = [k for k in relevant if set(k.claim_ids) & key_ids]

    # --- opportunity state -------------------------------------------------------------------------
    reasons: list[str] = []
    if not need:
        state = "WATCH"
        reasons.append("No current, evidenced commercial need (historical activity is not a current need).")
    elif not cap:
        state = "WATCH"
        reasons.append("A current need exists but there is no current evidenced commercial capacity.")
    else:
        state = "QUALIFIED"
        reasons.append("Current evidenced need and current evidenced capacity.")
        gaps = []
        if not any(c.state in STRONG for c in need):
            gaps.append("need is only unverified")
        if not any(c.state in STRONG for c in intent):
            gaps.append("no current commercial intent backed by observed/derived evidence")
        if not intro_ok:
            gaps.append("no current, evidenced introduction path to the target's organisational context")
        if blocking:
            gaps.append("unresolved contradiction on need/intent/capacity")
        if gaps:
            reasons.append("Not ACTIVATABLE: " + "; ".join(gaps) + ".")
        else:
            state = "ACTIVATABLE"
            reasons.append("Need, intent and capacity are current and evidenced; an evidenced introduction path exists; no blocking contradiction.")

    # --- 12 next human question: one consequential unknown ----------------------------------------
    authority_known = any(c.attribute == "DECISION_AUTHORITY" and _current(c, as_of) for c in ctx_attrs)
    if not need:
        nhq = ("commercial_need", f"As of {as_of}, does {target.name} (or its owner) have a current, specific commercial need that a partnership could serve, and who at the organisation can confirm it?",
               "Without a current need the lead stays WATCH; past sponsorship cannot substitute for it.")
    elif blocking:
        k = blocking[0]
        nhq = ("contradiction:" + k.contradiction_id, f"Sources conflict on {k.subject}: which statement is correct as of {as_of}, and what document settles it?",
               "An unresolved conflict on need, intent or capacity blocks activation.")
    elif not cap:
        nhq = ("commercial_capacity", f"What budget or delivery capacity does {target.name} have available now for this need?", "Need without capacity cannot qualify.")
    elif not any(c.state in STRONG for c in intent):
        nhq = ("commercial_intent", f"Has {target.name} stated, in a source we can cite, an intent to act on its need this period?", "Intent is the difference between QUALIFIED and ACTIVATABLE.")
    elif not intro_ok:
        nhq = ("intermediary_path", f"Who has a documented, current relationship that can introduce us to {target.name}'s decision makers?", "No evidenced introduction path exists.")
    elif not authority_known:
        leaders = [x["leaders"][0]["subject"] for x in functions if x["leaders"]]
        who = f" ({name(leaders[0])} leads a relevant function, which does not establish authority)" if leaders else ""
        nhq = ("decision_authority", f"Who holds sign-off authority for partnership spend at {target.name}'s organisation{who}?",
               "Function and title are not authority; an approach to the wrong person wastes the only introduction.")
    else:
        nhq = ("none", "No consequential unknown remains in the evidence; confirm freshness of the need before contact.", "Evidence ages.")

    unknowns = []
    for label, items in (("commercial_need", need), ("commercial_capacity", cap), ("commercial_intent", intent)):
        if not items:
            unknowns.append({"field": label, "reason": "no current evidenced claim"})
    if not authority_known:
        unknowns.append({"field": "decision_authority", "reason": "no evidence; function is not authority"})
    unknowns += [{"field": "period", "reason": f"relationship {c.claim_id} has an unknown period"} for c in ctx_rels if c.period.unknown]
    unknowns += [{"field": "claim", "reason": f"claim {c.claim_id} has state unknown"} for c in [*ctx_rels, *ctx_attrs] if c.state == "unknown"]

    return {
        "contract": "partner-intel/0.1", "as_of": as_of,
        "identity": {"entity_id": entity_id, "type": target.type, "name": target.name, "aliases": list(target.aliases)},
        "organizational_context": {"entities": [{"entity_id": i, "name": name(i), "type": book.entities[i].type} for i in sorted(ctx)], "ownership": owners},
        "functions_and_roles": functions,
        "relationships": {"current": [rel_view(c) for c in ctx_rels if _timing(c, as_of) == "current"],
                          "historical": [rel_view(c) for c in ctx_rels if _timing(c, as_of) == "historical"],
                          "period_unknown_or_future": [rel_view(c) for c in ctx_rels if _timing(c, as_of) in ("period_unknown", "future")]},
        "candidate_intermediaries": intermediaries,
        "commercial_capacity": sec["COMMERCIAL_CAPACITY"], "commercial_need": sec["COMMERCIAL_NEED"],
        "commercial_intent": sec["COMMERCIAL_INTENT"], "visibility_bias": visibility,
        "contradictions": [k.to_dict() for k in relevant], "unknowns": unknowns,
        "next_human_question": {"target_unknown": nhq[0], "question": nhq[1], "why_consequential": nhq[2]},
        "opportunity": {"state": state, "rationale": reasons},
    }
