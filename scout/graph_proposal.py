"""Epistemically explicit graph proposition."""
from dataclasses import dataclass, asdict
from typing import Any, Dict
import hashlib

VALID_STATUSES={"PROPOSED","ACCEPTED","UNKNOWN","CONTRADICTED","REJECTED"}

@dataclass
class GraphProposal:
    proposal_id: str
    subject: str
    predicate: str
    object: str
    status: str
    evidence_ids: list[str]
    attributes: Dict[str, Any]
    event_id: str

    def __post_init__(self):
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Invalid proposal status: {self.status}")

    @staticmethod
    def make_id(subject,predicate,object_,event_id):
        raw=f"{subject}|{predicate}|{object_}|{event_id}"
        return "GP_"+hashlib.sha256(raw.encode()).hexdigest()[:16].upper()

    def to_dict(self): return asdict(self)
