"""SaltTradePulse v0.1: bounded state, not recommendation."""
from datetime import datetime, timezone
from typing import Any, Dict

def build(graph, unknowns, contradictions, events, as_of=None):
    as_of=as_of or datetime.now(timezone.utc).isoformat()
    observed=[]
    for e in events:
        observed.append({
            "event_id":e.event_id,
            "reporter":e.reporter,
            "partner":e.partner,
            "exporter":e.exporter,
            "importer":e.importer,
            "quantity":e.quantity,
            "product":e.product,
            "evidence_ids":e.evidence_ids,
        })
    return {
        "pulse_id":f"SALT-PULSE-{as_of.replace(':','').replace('-','')}",
        "version":"0.1",
        "subject":"WEST_AFRICA_SALT_TRADE",
        "as_of":as_of,
        "facts":{"canonical_nodes":len(graph.nodes),"canonical_edges":len(graph.edges)},
        "observed":observed,
        "derived":[],
        "routes":[],
        "prices":[],
        "demand":[],
        "contradictions":contradictions.to_list(),
        "unknowns":unknowns.to_list(),
        "next_evidence":[
            item["next_evidence"] for item in unknowns.to_list()
            if item["next_evidence"]
        ],
        "confidence":{
            "canonical_graph":"SOURCE_BOUNDED",
            "commercial_interpretation":"NOT_ASSESSED"
        }
    }
