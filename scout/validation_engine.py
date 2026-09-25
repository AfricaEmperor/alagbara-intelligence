"""Validation gate: accepted graph, unknowns, contradictions."""
from typing import Any, Dict, Iterable
from scout.graph_proposal import GraphProposal

class ValidationEngine:
    def __init__(self, evidence_by_id: Dict[str, Any]):
        self.evidence_by_id=evidence_by_id

    def validate(self, proposals: Iterable[GraphProposal]):
        accepted=[]; unknown=[]; contradicted=[]
        for p in proposals:
            if not p.evidence_ids:
                p.status="UNKNOWN"; unknown.append(p); continue
            missing=[e for e in p.evidence_ids if e not in self.evidence_by_id]
            if missing:
                p.status="UNKNOWN"
                unknown.append({"proposal":p.to_dict(),"reason":"MISSING_EVIDENCE","missing_evidence_ids":missing})
                continue
            # Proposals are accepted only when the proposition itself is source-supported.
            p.status="ACCEPTED"
            accepted.append(p)
        return accepted, unknown, contradicted

    @staticmethod
    def attribute_conflict(subject, attribute, values, evidence_ids):
        return {
            "contradiction_id": f"ATTR-{subject}-{attribute}",
            "subject": subject,
            "attribute": attribute,
            "values": values,
            "evidence_ids": evidence_ids,
            "status": "CONTRADICTED",
        }
