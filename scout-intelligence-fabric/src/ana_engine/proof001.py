"""ALAGBARA-PROOF-001: repeatable local signal-to-outcome proof.

Source capture is opt-in and bounded to one HTTPS URL. Captured bytes are hashed
and stored through the existing RadarStore EvidenceRecord contract. No publishing,
outreach, production mutation, or autonomous crawling.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PROOF_ID = "ALAGBARA-PROOF-001"
MARKET = "lagos"
DOMAIN = "events-nightlife-hospitality"
MAX_SOURCE_BYTES = 2_000_000
USER_AGENT = "ALAGBARA-PROOF-001/0.1 (bounded source capture)"


def capture_source(signal: dict[str, Any], store_root: Path, timeout: int = 12) -> dict[str, Any]:
    """Fetch one operator-supplied HTTPS source, hash bytes, and persist EvidenceRecord."""
    url = str(signal.get("source_url", ""))
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source_url must be credential-free HTTPS")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"})
    with urlopen(request, timeout=timeout) as response:
        content = response.read(MAX_SOURCE_BYTES + 1)
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type", "unknown")
    if len(content) > MAX_SOURCE_BYTES:
        raise ValueError(f"source exceeds {MAX_SOURCE_BYTES} byte capture limit")
    final = urlparse(final_url)
    if final.scheme != "https" or not final.hostname:
        raise ValueError("redirected source must remain HTTPS")
    digest = hashlib.sha256(content).hexdigest()
    observation_id = "obs-" + digest[:24]
    from radar_contracts import EvidenceRecord, validate_evidence
    from ana_engine.store import RadarStore
    collected_at = datetime.now(timezone.utc).isoformat()
    ev = EvidenceRecord(
        observation_id=observation_id,
        source_id=signal["signal_id"],
        source_platform=parsed.hostname or "unknown",
        source_url=final_url,
        collection_method="bounded_https_fetch",
        collected_at=collected_at,
        content_hash=digest,
        evidence_state="observed",
        raw_media_reference=None,
        extraction_version="proof001-source-capture-v0.1",
        media_type="html" if "html" in content_type.lower() else "text",
        metadata={"content_type": content_type, "byte_count": len(content),
                  "redirected_from": url if final_url != url else None},
    )
    validate_evidence(ev)
    store = RadarStore(Path(store_root))
    try:
        inserted = store.add_evidence(ev)
        persisted = store.get_evidence(observation_id)
    finally:
        store.close()
    return {"captured": True, "inserted": inserted, "evidence": persisted,
            "sha256": digest, "byte_count": len(content), "content_type": content_type}


def build_proof(signal: dict[str, Any], *, action_authorized: bool = False,
                outcome: str = "recorded", captured_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    required = ("signal_id", "source_url", "observed_at", "event_title", "venue_name")
    missing = [k for k in required if not signal.get(k)]
    if missing:
        raise ValueError(f"signal missing required fields: {', '.join(missing)}")
    if not str(signal["source_url"]).startswith("https://"):
        raise ValueError("source_url must be HTTPS")
    source_node = {
        "id": signal["signal_id"], "kind": "signal", "source": signal["source_url"],
        "observed_at": signal["observed_at"],
        "provenance_status": "captured_and_hashed" if captured_evidence else "source_reference_only",
        "evidence_id": captured_evidence.get("evidence", {}).get("observation_id") if captured_evidence else None,
        "content_hash": captured_evidence.get("sha256") if captured_evidence else None,
    }
    event = {"id": "event:" + signal["signal_id"], "title": signal["event_title"],
             "fact_state": "source_captured" if captured_evidence else "operator_supplied_uncaptured",
             "source_signal": source_node["id"]}
    venue = {"id": "venue:" + signal["venue_name"].strip().lower().replace(" ", "-"),
             "name": signal["venue_name"], "fact_state": event["fact_state"],
             "source_signal": source_node["id"]}
    relationship = {"from": event["id"], "to": venue["id"], "type": "hosted_at",
                    "evidence": source_node.get("evidence_id") or source_node["id"],
                    "state": "source_captured_claim" if captured_evidence else "uncaptured_claim"}
    opportunity = {
        "id": "opportunity:" + signal["signal_id"], "qualification": "candidate",
        "rationale": "Event/venue signal may support a hospitality or experience partnership; "
                     "commercial fit and organizer identity remain unconfirmed.",
        "next_action": "internally qualify organizer, venue contact path, audience fit and pilot offer",
        "confidence": "low",
        "uncertainties": ["organizer identity not resolved",
                         "commercial interest and willingness-to-pay not tested"],
    }
    authority = {"actor": "proof-runner", "action": "internal_qualification_task",
                "allowed": True, "basis": "non-external, non-production action only"}
    if not action_authorized:
        action = {"status": "blocked", "type": "internal_qualification_task",
                  "reason": "explicit execution authorization flag not supplied"}
    else:
        action = {"status": "executed", "type": "internal_qualification_task",
                  "task": {"id": "task:" + signal["signal_id"], "title": opportunity["next_action"],
                           "created_in": "proof-artifact-only; no external system mutation"}}
    feedback = {"outcome": outcome if action["status"] == "executed" else "not_executed",
                "linked_to": [source_node["id"], event["id"], venue["id"], opportunity["id"]],
                "recorded_at": datetime.now(timezone.utc).isoformat()}
    limits = []
    if not captured_evidence:
        limits.append("source not fetched or independently verified")
    limits.extend(["artifact-only task execution; no external system mutation",
                   "event/venue identity resolution remains manual"])
    return {"proof_id": PROOF_ID, "market": MARKET, "domain": DOMAIN,
            "provenance": {"source": source_node, "verification": "CAPTURED" if captured_evidence else "NOT_CAPTURED",
                           "capture": captured_evidence},
            "graph": {"entities": [event, venue], "relationships": [relationship]},
            "opportunity": opportunity, "authority": authority, "action": action,
            "feedback": feedback, "proof_limits": limits}


def main() -> None:
    parser = argparse.ArgumentParser(description=PROOF_ID + " local proof runner")
    parser.add_argument("--signal-json", required=True, help="operator-supplied signal JSON")
    parser.add_argument("--output", default="proof001-result.json")
    parser.add_argument("--store-root", default=".proof001-store", help="local evidence store directory")
    parser.add_argument("--capture-source", action="store_true", help="fetch and persist source evidence locally")
    parser.add_argument("--authorize-internal-action", action="store_true",
                       help="allow artifact-only internal qualification task creation")
    parser.add_argument("--outcome", default="recorded")
    args = parser.parse_args()
    signal = json.loads(Path(args.signal_json).read_text(encoding="utf-8"))
    capture = capture_source(signal, Path(args.store_root)) if args.capture_source else None
    result = build_proof(signal, action_authorized=args.authorize_internal_action, outcome=args.outcome,
                         captured_evidence=capture)
    output = Path(args.output)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"proof_id": PROOF_ID, "output": str(output),
                     "source_captured": bool(capture), "action": result["action"]["status"],
                     "feedback": result["feedback"]["outcome"]}, indent=2))


if __name__ == "__main__":
    main()
