"""Canonical graph projection: accepted propositions only."""
from typing import Any, Dict, Iterable

class CanonicalGraph:
    def __init__(self):
        self.nodes: Dict[str,Dict[str,Any]]={}
        self.edges: Dict[str,Dict[str,Any]]={}

    def add_node(self,node_id,kind,**attrs):
        self.nodes[node_id]={"id":node_id,"kind":kind,**attrs}

    def add_edge(self,proposal):
        if proposal.status!="ACCEPTED":
            raise ValueError("CanonicalGraph accepts ACCEPTED proposals only")
        self.edges[proposal.proposal_id]=proposal.to_dict()

    def project(self, proposals: Iterable[Any]):
        for p in proposals:
            if p.status=="ACCEPTED":
                self.add_edge(p)
        return self.to_dict()

    def to_dict(self):
        return {"nodes":list(self.nodes.values()),"edges":list(self.edges.values())}
