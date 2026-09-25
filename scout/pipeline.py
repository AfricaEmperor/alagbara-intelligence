from __future__ import annotations
import json, hashlib
from pathlib import Path

def stable_id(prefix,value):
    h=hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()[:16]
    return f"{prefix}_{h}"

def source_rows(raw):
    data=raw.get("payload",{}).get("data",[])
    return data if isinstance(data,list) else []

def evidence_passports(raw):
    out=[]
    for row in source_rows(raw):
        eid=stable_id("EVP",row)
        out.append({
          "evidence_id":eid,"source":"UN Comtrade","source_type":"OFFICIAL_TRADE_STATISTICS",
          "retrieved_at":raw["acquired_at"],"raw_record":row,
          "observations":{"reporter":row.get("reporterDesc"),"partner":row.get("partnerDesc"),
            "period":row.get("refYear"),"flow":row.get("flowDesc"),"hs_code":row.get("cmdCode"),
            "quantity":row.get("netWgt"),"quantity_unit":"kg",
            "quantity_reported":row.get("qty"),"quantity_reported_unit":row.get("qtyUnitAbbr"),
            "trade_value":row.get("primaryValue"),"trade_value_unit":"USD",
            "cif_value":row.get("cifvalue"),"fob_value":row.get("fobvalue"),
            "is_quantity_estimated":row.get("isNetWgtEstimated"),
            "is_reported":row.get("isReported"),"is_aggregate":row.get("isAggregate")},
          "provenance":{"source_url":raw["source_url"],"query":raw["query"]},
          "epistemic_status":"OBSERVED","confidence":"HIGH"})
    return out

def trade_events(evidence):
    out=[]
    for ev in evidence:
        o=ev["observations"]
        out.append({
          "event_id":stable_id("TE",ev["evidence_id"]),"event_type":"TRADE_EVENT",
          "reporter":o["reporter"],"partner":o["partner"],"partner2":None,
          "period":o["period"],"flow":o["flow"],
          "product":{"hs_code":str(o["hs_code"]) if o["hs_code"] is not None else None},
          "quantity":{"value":o["quantity"],"unit":o["quantity_unit"]},
          "trade_value":{"value":o["trade_value"]},"evidence_ids":[ev["evidence_id"]],
          "epistemic_status":"OBSERVED"})
    return out

def graph_proposals(events):
    # "World" is an aggregate total, not a bilateral actor edge.
    return [{
      "proposal_id":stable_id("GP",e["event_id"]),"subject":e["reporter"],
      "predicate":"IMPORTED_FROM","object":e["partner"],
      "validity":{"status":"PROPOSED"},"evidence_ids":e["evidence_ids"],
      "observed_at":str(e["period"]),"confidence":"HIGH",
      "attributes":{"hs_code":e["product"]["hs_code"],"quantity":e["quantity"],
                    "trade_value":e["trade_value"]}}
      for e in events if e["partner"] != "World"]

def run(raw_path):
    raw=json.loads(Path(raw_path).read_text(encoding="utf-8"))
    ev=evidence_passports(raw); te=trade_events(ev); gp=graph_proposals(te)
    out=Path("data/normalized"); out.mkdir(parents=True,exist_ok=True)
    for name,data in [("evidence_passports.jsonl",ev),("trade_events.jsonl",te),("graph_proposals.jsonl",gp)]:
        (out/name).write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in data),encoding="utf-8")
    return len(ev),len(te),len(gp)

if __name__=="__main__":
    import sys
    print(run(sys.argv[1] if len(sys.argv)>1 else "data/raw/comtrade_ben_2501_2024.json"))
