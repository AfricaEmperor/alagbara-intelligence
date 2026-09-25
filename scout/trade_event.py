"""Normalized source-described trade event."""
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

@dataclass
class TradeEvent:
    event_id: str
    evidence_ids: list[str]
    period: Optional[str]
    reporter: Optional[str]
    partner: Optional[str]
    exporter: Optional[str]
    importer: Optional[str]
    origin: Optional[str]
    destination: Optional[str]
    entry_point: Optional[str]
    product: Dict[str, Any]
    quantity: Dict[str, Any]
    trade_value: Dict[str, Any]
    attributes: Dict[str, Any]
    epistemic_status: str = "OBSERVED"

    def to_dict(self):
        return asdict(self)

    def propose(self, predicate: str, subject: str, object_: str, attributes=None):
        from scout.graph_proposal import GraphProposal
        return GraphProposal(
            proposal_id=GraphProposal.make_id(subject,predicate,object_,self.event_id),
            subject=subject, predicate=predicate, object=object_,
            status="PROPOSED", evidence_ids=list(self.evidence_ids),
            attributes=attributes or {}, event_id=self.event_id
        )
