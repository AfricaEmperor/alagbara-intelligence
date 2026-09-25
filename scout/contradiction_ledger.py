"""Attribute-level contradiction ledger."""
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

@dataclass
class ContradictionItem:
    contradiction_id: str
    subject: str
    attribute: str
    values: List[Dict[str,Any]]
    status: str
    evidence_ids: List[str]
    possible_explanations: List[str]
    next_evidence: List[str]

    def to_dict(self): return asdict(self)

class ContradictionLedger:
    def __init__(self): self.items=[]
    def add(self, subject, attribute, values, evidence_ids, possible_explanations=None, next_evidence=None):
        item=ContradictionItem(
            contradiction_id=f"CON-{len(self.items)+1:04d}",
            subject=subject, attribute=attribute, values=values,
            status="CONTRADICTED", evidence_ids=evidence_ids,
            possible_explanations=possible_explanations or [],
            next_evidence=next_evidence or [])
        self.items.append(item); return item
    def to_list(self): return [x.to_dict() for x in self.items]
