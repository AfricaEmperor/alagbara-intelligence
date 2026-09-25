# SCOUT-WEB-02C

UN Comtrade BEN / 2024 / HS2501 / IMPORT -> Evidence Passport -> TradeEvent -> DuckDB -> GraphProposal -> SaltPulse v0.1.

This vertical slice deliberately does not infer importer/exporter identity, packaging, brand, corridor, SKU, or HIMMA market share from aggregate Comtrade records.

Run:
1. pip install -r requirements-scout-web-02c.txt
2. python scout/comtrade_adapter.py
3. python scout/pipeline.py data/raw/comtrade_ben_2501_2024.json
4. python scout/duckdb_load.py
5. python pulses/salt_pulse.py

Acceptance:
- raw source record reproducible
- derived values traceable to evidence
- observed vs derived preserved
- contradictions not silently resolved
- SaltPulse generated automatically
