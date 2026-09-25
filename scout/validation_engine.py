"""Validation gate for source-backed graph proposals.

Policy:
- ACCEPTED only when referenced evidence exists.
- UNKNOWN when evidence is absent or a required relationship endpoint is unresolved.
- CONTRADICTED is reserved for explicit source disagreement; it never silently
  resolves competing values.
"""
from typing import Any, Dict, Iterable, List, Tuple
from scout.graph_proposal import GraphProposal

class ValidationEngine:
    def __init__(self, evidence_by_id: Dict[str, Any]):
        self.evidence_by_id = evidence_by_id

    def validate(
        self, proposals: Iterable[GraphProposal]
    ) -> Tuple[List[GraphProposal], List[Dict[str, Any]], List[Dict[str, Any]]]:
        accepted, unknown, contradicted = [], [], []
        proposals = list(proposals)

        # A proposal can only enter the canonical graph if every cited passport exists.
        for p in proposals:
            missing = [eid for eid in p.evidence_ids if eid not in self.evidence_by_id]
            if not p.evidence_ids or missing:
                p.status = "UNKNOWN"
                unknown.append({
                    "proposal": p.to_dict(),
                    "reason": "MISSING_EVIDENCE" if missing else "NO_EVIDENCE",
                    "missing_evidence_ids": missing,
                })
                continue
            p.status = "ACCEPTED"
            accepted.append(p)

        # Explicitly competing values on the same edge become attribute-level
        # contradictions. The edge itself can remain accepted.
        groups: Dict[tuple, List[GraphProposal]] = {}
        for p in accepted:
            groups.setdefault((p.subject, p.predicate, p.object), []).append(p)

        for key, group in groups.items():
            for attribute in self._conflicting_attributes(group):
                values = []
                evidence_ids = []
                for p in group:
                    if attribute in p.attributes:
                        values.append({
                            "proposal_id": p.proposal_id,
                            "value": p.attributes[attribute],
                        })
                        evidence_ids.extend(p.evidence_ids)
                contradicted.append({
                    "subject": key[0],
                    "predicate": key[1],
                    "object": key[2],
                    "attribute": attribute,
                    "status": "CONTRADICTED",
                    "values": values,
                    "evidence_ids": sorted(set(evidence_ids)),
                })
        return accepted, unknown, contradicted

    @staticmethod
    def _conflicting_attributes(group: List[GraphProposal]) -> List[str]:
        keys = set().union(*(p.attributes.keys() for p in group))
        conflicts = []
        for key in keys:
            values = {
                repr(p.attributes[key])
                for p in group
                if key in p.attributes
            }
            if len(values) > 1:
                conflicts.append(key)
        return conflicts
