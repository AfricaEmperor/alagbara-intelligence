"""Validation gate for source-backed graph proposals."""
from typing import Any, Dict, Iterable, List, Tuple
from scout.graph_proposal import GraphProposal

UNKNOWN_ENDPOINTS={"UNKNOWN","UNKNOWN_EXPORTER","UNKNOWN_IMPORTER"}

class ValidationEngine:
    def __init__(self, evidence_by_id: Dict[str, Any]):
        self.evidence_by_id=evidence_by_id

    def validate(self, proposals: Iterable[GraphProposal]) -> Tuple[List[GraphProposal],List[Dict[str,Any]],List[Dict[str,Any]]]:
        accepted, unknown, contradicted=[],[],[]
        for p in list(proposals):
            missing=[eid for eid in p.evidence_ids if eid not in self.evidence_by_id]
            unresolved=p.subject in UNKNOWN_ENDPOINTS or p.object in UNKNOWN_ENDPOINTS
            if unresolved or not p.evidence_ids or missing:
                p.status="UNKNOWN"
                unknown.append({
                    "proposal":p.to_dict(),
                    "reason":"UNRESOLVED_ENDPOINT" if unresolved else ("MISSING_EVIDENCE" if missing else "NO_EVIDENCE"),
                    "missing_evidence_ids":missing
                })
                continue
            p.status="ACCEPTED"
            accepted.append(p)

        groups: Dict[tuple,List[GraphProposal]]={}
        for p in accepted:
            groups.setdefault((p.subject,p.predicate,p.object),[]).append(p)
        for (subject,predicate,object_),group in groups.items():
            keys=set().union(*(p.attributes.keys() for p in group))
            for attribute in keys:
                values=[{"proposal_id":p.proposal_id,"value":p.attributes[attribute]} for p in group if attribute in p.attributes]
                if len({repr(v["value"]) for v in values})>1:
                    contradicted.append({
                        "subject":subject,"predicate":predicate,"object":object_,
                        "attribute":attribute,"status":"CONTRADICTED",
                        "values":values,
                        "evidence_ids":sorted({eid for p in group for eid in p.evidence_ids})
                    })
        return accepted,unknown,contradicted
