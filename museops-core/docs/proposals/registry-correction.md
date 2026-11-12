# Proposal — Portfolio registry corrections for MuseOps (NOT APPLIED)

Target repo: `power-enterprise-control-room`. This repository was **not modified**; the diff below is a proposal
for review. Existing entries are untouched except where marked.

## Evidence

| Finding | Evidence |
|---|---|
| `pulse-nightlife` maps to `escape-app` | `registry/portfolio.yaml` line ~36 |
| `pulse-l1` is absent from the repository map | `registry/repositories.yaml` (no `pulse-l1` entry) |
| pulse-l1 is "Pulse Nightlife" | `pulse-l1/README.md`: "Pulse L1 — Pulse Nightlife" |
| Escape is a separate product | `escape-app/README.md`: "Independent application repository for the Escape product… PULSE L1 remains a separate repository" |
| No MuseOps entry exists | `registry/*.yaml` contain no MuseOps reference |
| MuseOps lives in `alagbara-intelligence` | founder decision, MUSEOPS-IMPL-001 |

## Proposed changes

1. `registry/repositories.yaml`: add
   `- { id: pulse-l1, full_name: "AfricaEmperor/pulse-l1", integration_mode: read_only_initially }`
2. `registry/portfolio.yaml`, venture `pulse-nightlife`: `repositories: [escape-app]` → `repositories: [pulse-l1]`.
   Confirmed by the READMEs above. Lifecycle stays `UNKNOWN` (pulse-l1's own README says it has not been
   independently rebuilt).
3. `escape-app`: remove from `pulse-nightlife`. **Founder decision required**: which venture owns Escape
   (a new venture, or a section of an existing one)? Do not guess; until decided, list it in
   `repositories.yaml` only (already present) and leave it unassigned.
4. Register MuseOps under the ALAGBARA intelligence-infrastructure venture without changing repository
   boundaries. The registry schema (0.1) has no component concept, so either:
   - (a) zero schema change: extend `alagbara-os.next_proof` / add a `notes:` line:
     "Includes MuseOps Core at alagbara-intelligence/museops-core (lifecycle IMPLEMENTED-UNPROVEN until acceptance
     criteria in museops-core/README.md pass in CI)"; or
   - (b) minimal schema extension (recommended, needs approval): an optional `components:` list on a venture:
     ```yaml
     components:
       - id: museops-core
         repository: alagbara-intelligence
         path: museops-core
         lifecycle: IMPLEMENTED_UNPROVEN
         evidence: "museops-core/README.md validation commands"
     ```
   Lifecycle uses the registry's own vocabulary (`contracts/status-vocabulary.md`); `VERIFIED` requires the CI
   run evidence, which does not exist yet.

## Not proposed

No repository is merged, renamed or created; `integration_mode` values are unchanged; no other venture is touched.
