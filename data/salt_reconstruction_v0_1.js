export const saltState = {
  title: "SALT INTELLIGENCE",
  version: "RECONSTRUCTION KERNEL v0.1",
  asOf: "25 Sep 2026",
  dataPeriod: "2024",
  status: "PARTIAL RECONSTRUCTION",
  flows: [
    { id:"flow-gh", type:"aggregate", source:"GHANA", destination:"BENIN", quantity:"5,667.07 t", sourceLabel:"WITS / 2024", note:"Benin-reported imports; mirror discrepancy open.", status:"CONTRADICTED" },
    { id:"flow-sn", type:"aggregate", source:"SENEGAL", destination:"BENIN", quantity:"19,992.4 t", sourceLabel:"WITS / 2024", note:"Aggregate reporter-partner observation.", status:"ACCEPTED" },
    { id:"flow-eg", type:"aggregate", source:"EGYPT", destination:"BENIN", quantity:"14,909.1 t", sourceLabel:"WITS / 2024", note:"Aggregate reporter-partner observation.", status:"ACCEPTED" },
    { id:"flow-in", type:"aggregate", source:"INDIA", destination:"BENIN", quantity:"9,404.16 t", sourceLabel:"WITS / 2024", note:"Aggregate reporter-partner observation.", status:"ACCEPTED" }
  ],
  events: [
    { id:"evt-gh-2024-05-17", exporter:"Regency Salt Limited", importer:"UNKNOWN", origin:"Ghana", destination:"Benin", quantity:"100 t", product:"Refined iodized salt", packaging:"4,000 × 25 kg", date:"17 May 2024", source:"Volza", status:"UNKNOWN", reason:"Importer unresolved" },
    { id:"evt-in-2024-03-23", exporter:"UNKNOWN", importer:"UNKNOWN", origin:"India", destination:"Benin", quantity:"140 t", product:"Triple refined free-flow iodised salt", packaging:"25 kg bags", date:"23 Mar 2024", source:"Volza", status:"UNKNOWN", reason:"Actors unresolved" }
  ],
  contradictions: [
    { id:"CON-0001", subject:"GHANA → BENIN / 2024", attribute:"quantity", sourceA:"Benin import report", valueA:"5,667.07 t", sourceB:"Ghana export mirror", valueB:"144.60 t", status:"OPEN", nextEvidence:"Reconstruct bilateral transaction records; test duplication, timing and classification." }
  ],
  unknowns: [
    { id:"UNK-0001", subject:"Ghana transaction / 100 t", field:"importer", reason:"Importer not exposed in the selected record.", importance:"HIGH", nextEvidence:"Resolve through transaction-level customs / trade records." },
    { id:"UNK-0002", subject:"India transaction / 140 t", field:"actors", reason:"Buyer and supplier identity not resolved in the selected record.", importance:"HIGH", nextEvidence:"Resolve buyer, supplier and shipping record." },
    { id:"UNK-0003", subject:"Benin salt flows / 2024", field:"corridor", reason:"Aggregate trade data does not establish physical route.", importance:"MEDIUM", nextEvidence:"Transaction records, customs entry/exit and shipping evidence." },
    { id:"UNK-0004", subject:"WITS aggregate flows", field:"packaging", reason:"Aggregate HS250100 data does not expose packaging.", importance:"MEDIUM", nextEvidence:"Transaction-level product descriptions and packing records." }
  ],
  nextScout: [
    { id:"SCOUT-03A", title:"Ghana contradiction", priority:"HIGH", question:"Why does the 2024 Ghana→Benin quantity differ between reporters?", target:"Bilateral transaction records", output:"Resolved event set / explanation of discrepancy." },
    { id:"SCOUT-03B", title:"Resolve transaction actors", priority:"HIGH", question:"Who imported the 100 t Ghana event and the 140 t India event?", target:"Customs / transaction-level records", output:"Resolved importer / exporter identities." },
    { id:"SCOUT-03C", title:"India transaction layer", priority:"MEDIUM", question:"What buyers, suppliers, formats and prices sit behind the India flow?", target:"Transaction records", output:"Actor + product + price + corridor evidence." },
    { id:"SCOUT-03D", title:"Senegal / Egypt decomposition", priority:"MEDIUM", question:"How do the 19,992.4 t and 14,909.1 t aggregates decompose into transactions?", target:"Transaction-level trade evidence", output:"Counterparty and transaction structure." }
  ]
};