"""Adversarial acceptance fixture for Reconstruction Kernel v0.1."""
import json
from pathlib import Path
from scout.evidence_passport import EvidencePassport
from scout.trade_event import TradeEvent
from scout.graph_proposal import GraphProposal
from scout.validation_engine import ValidationEngine
from scout.canonical_graph import CanonicalGraph
from scout.unknown_ledger import UnknownLedger
from scout.contradiction_ledger import ContradictionLedger
from pulses.salt_trade_pulse import build

def run():
    raw = [
        {"id":"A","exporter":"A","importer":"B","quantity_t":100,"price_usd":18585},
        {"id":"B","exporter":"A","importer":None,"quantity_t":100,"price_usd":18585},
        {"id":"C","exporter":None,"importer":"C","quantity_t":50,"price_usd":9000},
        {"id":"D","exporter":"A","importer":"B","quantity_t":100,"price_usd":18585},
        {"id":"E","exporter":"A","importer":"B","quantity_t":120,"price_usd":21000},
    ]
    passports={}
    for r in raw:
        p=EvidencePassport.from_record(
            source="ADVERSARIAL_FIXTURE",
            source_type="TEST",
            raw_record=r,
            observations=r,
            confidence="HIGH",
        )
        passports[p.evidence_id]=p

    events=[]
    for r,p in zip(raw,passports.values()):
        events.append(TradeEvent(
            event_id=f"TE-{r['id']}",
            evidence_ids=[p.evidence_id],
            period="2024",
            reporter="BENIN",
            partner="GHANA",
            exporter=r["exporter"],
            importer=r["importer"],
            origin="GHANA",
            destination="BENIN",
            entry_point=None,
            product={"class":"REFINED_IODIZED_SALT","packaging":"25KG_BAG"},
            quantity={"value":r["quantity_t"],"unit":"T"},
            trade_value={"value":r["price_usd"],"currency":"USD","basis":"FOB"},
            attributes={}
        ))

    proposals=[]
    for e in events:
        if e.exporter and e.importer:
            proposals.append(e.propose("SUPPLIED",e.exporter,e.importer,{
                "quantity_t":e.quantity["value"],
                "price_usd":e.trade_value["value"]
            }))
        else:
            proposals.append(e.propose(
                "SUPPLIED",
                e.exporter or "UNKNOWN_EXPORTER",
                e.importer or "UNKNOWN_IMPORTER",
                {"quantity_t":e.quantity["value"]}
            ))

    # Explicit contradiction is represented by competing source-backed values.
    engine=ValidationEngine(passports)
    accepted, unknown, conflicts=engine.validate(proposals)

    graph=CanonicalGraph()
    graph.project(accepted)

    unknowns=UnknownLedger()
    for e in events:
        if not e.importer:
            unknowns.add(e.event_id,"importer","SOURCE_DID_NOT_DISCLOSE",
                         "HIGH",["CUSTOMS_RECORD","BILL_OF_LADING"])
        if not e.exporter:
            unknowns.add(e.event_id,"exporter","SOURCE_DID_NOT_DISCLOSE",
                         "HIGH",["CUSTOMS_RECORD","BILL_OF_LADING"])

    contradictions=ContradictionLedger()
    contradictions.add(
        subject="A->B",
        attribute="quantity_t",
        values=[{"source":"TE-A","value":100},{"source":"TE-E","value":120}],
        evidence_ids=events[0].evidence_ids+events[4].evidence_ids,
        possible_explanations=["duplicate/related records","reporting discrepancy"],
        next_evidence=["source_record_ids","customs_declaration"]
    )

    pulse=build(graph,unknowns,contradictions,events,as_of="2026-09-25T15:50:00+01:00")

    assertions = {
        "evidence_passports_created": len(passports)==5,
        "trade_events_created": len(events)==5,
        "accepted_edges_have_evidence": all(e["evidence_ids"] for e in graph.edges.values()),
        "unknown_importer_preserved": any(x["field"]=="importer" for x in unknowns.to_list()),
        "unknown_exporter_preserved": any(x["field"]=="exporter" for x in unknowns.to_list()),
        "contradiction_preserved": len(contradictions.items)==1,
        "canonical_graph_excludes_unknown_proposals": all(e["status"]=="ACCEPTED" for e in graph.edges.values()),
        "pulse_generated": pulse["version"]=="0.1",
    }
    assertions["PASS"]=all(assertions.values())
    out={"assertions":assertions,"counts":{
        "evidence":len(passports),"events":len(events),
        "canonical_edges":len(graph.edges),"unknowns":len(unknowns.items),
        "contradictions":len(contradictions.items)
    },"pulse":pulse}
    Path("data/reconstruction_kernel_v0_1_test.json").parent.mkdir(parents=True,exist_ok=True)
    Path("data/reconstruction_kernel_v0_1_test.json").write_text(
        json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(out,indent=2,ensure_ascii=False))
    return 0 if assertions["PASS"] else 1

if __name__=="__main__":
    raise SystemExit(run())
