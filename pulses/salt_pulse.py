import json, duckdb
from datetime import datetime, timezone
from pathlib import Path

def build():
    con=duckdb.connect("data/scout_web_02c.duckdb",read_only=True)
    rows=con.execute("""SELECT reporter, partner, period,
        product->>'hs_code' AS hs_code,
        quantity->>'value' AS quantity,
        quantity->>'unit' AS quantity_unit
        FROM trade_events ORDER BY partner""").fetchall()
    pulse={
      "pulse_id":"SALT_PULSE_v0.1","subject":"REGIONAL_SALT_MARKET",
      "as_of":datetime.now(timezone.utc).isoformat(),
      "scope":{"reporter":"BENIN","period":2024,"hs_code":"2501","flow":"IMPORT"},
      "facts":{"trade_events_observed":len(rows),"partners_observed":len({r[1] for r in rows})},
      "flows":[{"partner":r[1],"period":r[2],"hs_code":r[3],
                "quantity":r[4],"quantity_unit":r[5]} for r in rows],
      "derived":[],"contradictions":[],
      "unknowns":["Importer/exporter identities are unavailable in aggregate Comtrade records.",
                  "Packaging, SKU, brand and corridor are unavailable at this aggregation level.",
                  "Aggregate Comtrade does not establish HIMMA-addressable market share."],
      "next_evidence":["Acquire bilateral/mirror records for priority partners.",
                       "Acquire transaction-level records for importer/exporter and packaging resolution."],
      "confidence":{"source":"HIGH","actor_resolution":"UNKNOWN",
                    "packaging_resolution":"UNKNOWN","corridor_resolution":"UNKNOWN"}}
    Path("pulses").mkdir(exist_ok=True)
    Path("pulses/salt_pulse_v0.1.json").write_text(json.dumps(pulse,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(pulse,indent=2,ensure_ascii=False))
    con.close()

if __name__=="__main__":
    build()
