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


## Live-source gate — 2026-09-25

The direct UN Comtrade preview request was attempted from both the web retrieval runtime and a network-capable container path. Both failed before HTTP response retrieval because `comtradeapi.un.org` was not reachable/resolvable from the available execution environments.

Canonical-source rule:
- DIRECT_COMTRADE = canonical EvidencePassport source when raw API JSON is successfully acquired.
- WITS/UN Comtrade snapshot = fallback/reference only; it must not be silently promoted to canonical.
- SCOUT-WEB-02D is gated until the direct raw JSON is acquired and compared field-by-field against the WITS snapshot.

The documented public preview endpoint is `/public/v1/preview/C/A/HS`, with a 500-record preview limit. See the UN Comtrade API documentation.
