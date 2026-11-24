"""ALAGBARA-PROOF-001: repeatable local signal-to-outcome proof.

This executable slice deliberately uses a real source URL as a provenance reference,
but does not fetch it, contact anyone, publish, or mutate a production system.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROOF_ID = "ALAGBARA-PROOF-001"
MARKET = "lagos"
DOMAIN = "events-nightlife-hospitality"


def build_proof(signal: dict[str, Any], *, action_authorized: bool = False,
                outcome: str = "recorded") -> dict[str, Any]:
    required = ("signal_id", "source_url", "observed_at", "event_title", "venue_name")
    missing = [k for k in required if not signal.get(k)]
    if missing:
        raise ValueError(f"signal missing required fields: {', '.join(missing)}")
    if not str(signal["source_url"]).startswith("https://"):
        raise ValueError("source_url must be HTTPS")
    signal_node = {
        "id": signal["signal_id"],
        "kind": "signal",
        "source": signal["source_url"],
        "observed_at": signal["observed_at"],
        "provenance_status": "source_reference_provided_not_fetch_verified",
    }
    event = {"id": "event:" + signal["signal_id"], "title": signal["event_title"],
             "fact_state": "observed_from_operator_supplied_signal",
             "source_signal": signal_node["id"]}
    venue = {"id": "venue:" + signal["venue_name"].strip().lower().replace(" ", "-"),
             "name": signal["venue_name"], "fact_state": "observed_from_operator_supplied_signal",
             "source_signal": signal_node["id"]}
    relationship = {"from": event["id"], "to": venue["id"], "type": "hosted_at",
                    "evidence": signal_node["id"], "state": "observed_claim"}
    opportunity = {
        "id": "opportunity:" + signal["signal_id"],
        "qualification": "candidate",
        "rationale": "Verified event/venue signal may support a hospitality or experience partnership; "
                     "commercial fit and organizer identity remain unconfirmed.",
        "next_action": "internally qualify organizer, venue contact path, audience fit and pilot offer",
        "confidence": "low",
        "uncertainties": ["source page not fetched by this proof runner", "organizer identity not resolved",
                         "commercial interest and willingness-to-pay not tested"],
    }
    authority = {"actor": "proof-runner",
                "action": "internal_qualification_task",
                "allowed": True,
                "basis": "non-external, non-production action only"}
    if not action_authorized:
        action = {"status": "blocked", "type": "internal_qualification_task",
                  "reason": "explicit execution authorization flag not supplied"}
    else:
        action = {"status": "executed", "type": "internal_qualification_task",
                  "task": {"id": "task:" + signal["signal_id"], "title": opportunity["next_action"],
                           "created_in": "proof-artifact-only; no external system mutation"}}
    feedback = {"outcome": outcome if action["status"] == "executed" else "not_executed",
                "linked_to": [signal_node["id"], event["id"], venue["id"], opportunity["id"]],
                "recorded_at": datetime.now(timezone.utc).isoformat()}
    return {"proof_id": PROOF_ID, "market": MARKET, "domain": DOMAIN,
            "provenance": {"source": signal_node, "verification": "NOT_FETCH_VERIFIED"},
            "graph": {"entities": [event, venue], "relationships": [relationship]},
            "opportunity": opportunity, "authority": authority, "action": action,
            "feedback": feedback,
            "proof_limits": ["fixture/operator-supplied signal; no live acquisition",
                             "artifact-only task execution; no production database, outreach or deployment"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=PROOF_ID + " local proof runner")
    parser.add_argument("--signal-json", required=True, help="operator-supplied signal JSON")
    parser.add_argument("--output", default="proof001-result.json")
    parser.add_argument("--authorize-internal-action", action="store_true",
                       help="allow artifact-only internal qualification task creation")
    parser.add_argument("--outcome", default="recorded")
    args = parser.parse_args()
    signal = json.loads(Path(args.signal_json).read_text(encoding="utf-8"))
    result = build_proof(signal, action_authorized=args.authorize_internal_action, outcome=args.outcome)
    output = Path(args.output)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    print(json.dumps({"proof_id": PROOF_ID, "output": str(output), "action": result["action"]["status"],
                     "feedback": result["feedback"]["outcome"]}, indent=2))


if __name__ == "__main__":
    main()
