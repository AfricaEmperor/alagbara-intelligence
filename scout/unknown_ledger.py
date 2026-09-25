"""First-class unresolved questions."""
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

@dataclass
class UnknownItem:
    unknown_id: str
    subject: str
    field: str
    status: str
    reason: str
    importance: str = "MEDIUM"
    next_evidence: List[str] = None
    context: Dict[str,Any] = None

    def to_dict(self):
        d=asdict(self)
        d["next_evidence"]=d["next_evidence"] or []
        d["context"]=d["context"] or {}
        return d

class UnknownLedger:
    def __init__(self): self.items=[]
    def add(self, subject, field, reason, importance="MEDIUM", next_evidence=None, context=None):
        item=UnknownItem(
            unknown_id=f"UNK-{len(self.items)+1:04d}", subject=subject, field=field,
            status="OPEN", reason=reason, importance=importance,
            next_evidence=next_evidence or [], context=context or {})
        self.items.append(item); return item
    def to_list(self): return [x.to_dict() for x in self.items]
