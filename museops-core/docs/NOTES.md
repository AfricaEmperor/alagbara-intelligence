# Notes — open items for future ADRs

- Automated screen capture as a distinct source: see `discussions/automated-screen-capture.md`. Not decided.
- `api_response` split (for example `tiktok_api_response`): deferred until an adapter exists (ADR-004 C).
- Naming overload: "Pulse" means (1) the pulse-l1 app, (2) MuseOps `Pulse` aggregate, (3) "ANA Pulse" snapshots in
  power-enterprise-control-room. Keep qualified in docs.
- Evidence-state (`observed|derived|unverified|unknown`, Scout) is not part of the MuseOps v0.1 schema. If a
  Scout→MuseOps adapter is built, a mapping ADR is needed; do not add the field implicitly.
- Contradiction detection is not implemented; `createFindings` accepts caller-supplied Contradictions only.
- The Sprint 1 extractors assign a fixed `capability_confidence` of 0.9 on a literal pattern match. This is the
  parser's confidence in its own parse, a placeholder until a calibrated capability exists.
- Evidence independence is counted per source *type*, a conservative reading of ADR-003's Independence Rule.
  Revisit if two distinct sources of the same type should count as independent.
- Dev-dependency advisory: vitest 2.x (moderate, dev only, not shipped). The fixed vitest 4/5 lines did not
  resolve cleanly with this npm version (arborist error) and vitest 5 requires Node >= 22.12 (CI also tests Node 20).
- Scout regression has 2 pre-existing failing tests (see README, "Validation status").
