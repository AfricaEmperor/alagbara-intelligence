# MUSEOPS-PI-001 — Online Partner Intelligence vertical slice

Branch `feat/museops-pi-001-partner-intelligence`, based on the AP-001 Radar tip (`2cd60ec`). Not merged, not deployed.
Everything lives in `scout-intelligence-fabric/` (Python, stdlib only) so it reuses SCOUT/ANA directly.

## 1. Phase 0 — reconciliation (what exists, what was reused)
| Concern | Existing home | Used here |
|---|---|---|
| Source registry + authorization | `scout_fabric/sources.py` (`SourceRegistry`, human `approved_by`, `UnauthorizedSource`) | **Reused unchanged.** Acquisition requires an approved `public_html` source. |
| Evidence ledger | `radar_contracts.EvidenceRecord` + `ana_engine.store.RadarStore.evidence` (+ `failures`, `audit`) | **Reused unchanged.** All evidence, including fixtures, is an `EvidenceRecord` in the existing ledger. |
| Evidence vocabulary | `radar_contracts.EVIDENCE_STATES` (observed / derived / unverified / unknown) | **Reused.** |
| Bounded fetch | `scout_fabric.acquire.acquire_public_page` (1 MB, 15 s, no credentials, public HTML) | **Reused**; injected so tests need no network. |
| Claim-with-provenance pattern | `radar_contracts.FieldClaim` (event fields only) | Pattern followed; its `field` vocabulary is event-specific, so partner claims are a sibling type that points at the same ledger. |
| Contradiction / unknown / graph-proposal ledgers | `feat/reconstruction-kernel-v0-1` (`scout/*`) — unmerged, different layout | **Not imported** (would couple two unmerged branches). Contradictions are derived deterministically and carried on the profile; reuse of those ledgers is a later, separate decision. |
| Persistence | `RadarStore` (SQLite) + `pg_sync` | **No new store, table or file.** Claims are in memory this slice; see §6. |
| Identity resolution | none in `main`/Radar for partners; MuseOps Core (TS, uncommitted elsewhere) has a resolver | **None built.** Entities are identified by explicit ids; no fuzzy merging. |
| AP-001 Cotonou-specific code | `radar_contracts.TIMEZONE/CITY`, `markets.py`, `Venue/Event/Party` | **Not touched.** Partner contracts carry no market/timezone assumption. |
| pulse-l1 | Radar review/import app on its own feature branch | **No edits.** Pulse consumes Radar feeds, not partner claims; no contract between them is introduced. |
| alagbara-core | Travel command view; no evidence/claim contracts | Reference only; nothing reusable. |
| Baseline CI/tests | Radar branch: 120 Python tests pass; `main`: 2 pre-existing Scout failures (not on this branch) | Full suite now 153 pass (120 + 33 new). |

## 2. What was added (all new files unless noted)
- `scout-intelligence-fabric/src/partner_intel/` — `models.py` (10 entity types, 10 relations, endpoint typing, `TimePeriod`, claims, `Contradiction`), `claimbook.py` (validation, provenance resolution, contradiction detection), `profile.py` (13-section Partner Lead Profile + opportunity state), `acquire.py` (operator-supplied public URL), `fixtures.py` (loader), `__init__.py`.
- `scout-intelligence-fabric/fixtures/partner_intel/` — three **synthetic** fixtures (A, B, C).
- `scout-intelligence-fabric/tests/test_partner_intel.py`, `tests/test_partner_acquire.py` — 33 tests.
- `.github/workflows/scout-radar-ci.yml` (modified) — adds this branch to the push trigger only.

## 3. Rules the code enforces
1. A claim stores **references** to ledger evidence; source URL, collection method and capture date are resolved from the ledger. It also stores the observation date (when the source says it), time period, state, `asserted` (a source may deny), `raw_excerpt` (must occur in the cited evidence text) and a separate `interpretation` that no logic reads.
2. A claim's state may not exceed the strength of its evidence (an `unverified` blog cannot support an `observed` claim).
3. Conflicting claims coexist; a re-used `claim_id` with different content is refused; contradictions are derived (`assertion_denial`, `conflicting_values`, `conflicting_owner`, `period_conflict`). Unknown periods are treated as possibly overlapping.
4. Function is not authority: leading a function yields `decision_authority: unknown` unless a `DECISION_AUTHORITY` claim with its own evidence exists.
5. Intermediary presence is not causation: every candidate carries `causation_established: false`; the basis is `introduction_evidenced` only when an `INTRODUCES` claim exists, else `co_presence`.
6. Opportunity state uses only claims whose period provably covers `as_of`. WATCH = no current need (or need without current capacity). QUALIFIED = current need + capacity. ACTIVATABLE = additionally observed/derived need and intent, a current evidenced introduction path, and no unresolved contradiction on need/intent/capacity.
7. The Next Human Question targets the most consequential unknown in this order: need, blocking contradiction, capacity, intent, introduction path, decision authority.

## 4. Acquisition boundary (Phase 3)
`acquire_operator_url(url, source_id, registry, store)` fetches **one** operator-supplied public URL inside an **approved** `public_html` source (host and path prefix). Rejections happen before any network call and are recorded in the existing `failures` table with an authorized alternative. No crawler, scheduler, login, browser automation, social-account access or messaging exists in the package (tested by source inspection).

## 5. Fixtures (Phase 4) — IMPORTANT
The three named research fixtures (Don Julio × AMVCA/Diageo; Budweiser × BUDX/DJ Consequence; Don Julio × Zero Gravity Lagos) were **not found** in any branch of the eight repositories, Google Drive or Notion, and no evidence about real companies was invented. The tests therefore use **synthetic, fictional** fixtures with the same structure (A: historical sponsorship with a denial and a function-without-authority; B: platform + performer + conflicting agency representation, need and capacity but no intent; C: finished venue activation plus a separately evidenced current need). Every organisation, person and URL (`fixtures.invalid`) is fictional. Real fixtures drop into the same `partner-fixture/0.1` schema; the acceptance tests would then need their expected states re-derived from the real evidence.

## 6. Known limitations
- Claims are not persisted. The next task is a `partner_claims` table inside `RadarStore` (schema migration, versioning, audit rows) — not a second store.
- Entity identity is explicit-id only; no alias or fuzzy resolution.
- Contradiction detection is structural (same subject/relation/object or entity/attribute). Semantic conflicts are not found.
- Opportunity rules are a documented MVP policy, not a calibrated score; thresholds (3 structural hops, 0.8 source concentration, the need > contradiction > capacity > intent > path > authority order) are design choices needing human review.
- Acquisition handles static public HTML only; claim extraction from text is manual (fixtures) — no NLP in this slice.
- Not wired to Pulse; no UI. No claim is verified against reality; `observed` means the page said it.
- `ruff` still reports 9 style notes (`dict()` literals) in the new tests; the existing code has 14 unrelated findings. Ruff is not part of CI.

## 7. Security implications
Public, online sources only, behind human approval recorded in the registry; no credentials, cookies, private social data, outbound contact or autonomous access. Operator-supplied text is stored as evidence and never executed or interpolated into queries (SQLite writes use parameterised statements in the existing store). Profiles describe people (names, roles) drawn from public pages: treat them as personal data (purpose limitation, retention and access control are **not** implemented here) and do not publish profiles outside the operator surface.

## 8. Next smallest executable task
Add a `partner_claims` table (+ migration and audit rows) to `ana_engine.store.RadarStore` with idempotent writes, then export a profile through the existing operator route — after the founder supplies the three real fixtures so expected states can be fixed from real evidence.
