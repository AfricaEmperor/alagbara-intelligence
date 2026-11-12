# @alagbara/museops-core

Provenance-first MuseOps domain library: **Source → Signal → Observation → ObservationSet → Pulse → Finding**
with a minimal Identity Resolver. TypeScript + Zod. No framework dependencies, no database, no network I/O.
Private package (`"private": true`); it is not published.

Hosted in `alagbara-intelligence` as a sibling of `scout-intelligence-fabric/` (independent Python fabric, untouched).
Pulse L1 and Escape consume versioned JSON Schema contracts only: see `docs/integration-contract.md`.

## Status and provenance of this code

**Reconstructed, not recovered.** A search of every branch of all eight repositories found no MuseOps Sprint 1
implementation, so the "10/10 tests" reported earlier could not be inspected or reproduced. This package was
rebuilt from the approved specifications in `docs/` (vision, architecture, schema freeze, ADR-001..003, Sprint 1
kickoff) plus the founder decisions recorded in ADR-004. No historical test result is claimed. The current suite
is new.

## Layout

```
domain/        Zod schemas + types (Source, Signal, Observation, Subject, ExternalIdentity, ObservationSet, Pulse, Finding, ProvenanceChain)
application/   ingestSignal, identityResolver, createObservationSet, createPulse, createFinding (+ evidence rules)
capabilities/nlp/   CreatorExtractor, HashtagExtractor (capability = "nlp")
contracts/v0.1/     generated JSON Schema artifacts + manifest (committed; CI verifies they match the Zod source)
fixtures/tiktok/    stephanie-live.json, easyboy-update.json
tests/         vitest suites
scripts/       generate-contracts.ts (the only file I/O in the package)
docs/          vision, architecture, schema-freeze-v0.1 (patched to v0.1.1), ADR-001..004, integration-contract, discussions, proposals
index.ts       explicit public API
```

## Commands

```bash
npm ci
npm run typecheck        # tsc --noEmit
npm run lint             # eslint
npm test                 # vitest: unit, Zod validation, contract tests
npm run contracts:check  # fail if contracts/ differ from the Zod schemas
npm run contracts:generate
npm run build            # tsc -> dist/
npm run validate         # all of the above, in order
```

CI: `.github/workflows/museops-core.yml` (Node 20 and 22) plus a separate Scout pytest job.

## Rules enforced in code

- Trust dimensions never merge: `channel_trust` (Source), `capability_confidence` (Observation, number 0–1),
  `evidence_strength` (Finding). No generic `confidence` field; schemas are strict.
- Channel trust defaults (ADR-004): android_notification high; user_upload medium; screenshot medium;
  shared_image low; **api_response unset** (explicit `channel_trust` required, no fallback).
- Pulse's `SourceType` and MuseOps' channel `SourceType` are different things; this package exports
  `ChannelSourceType`.
- Identity: creator = `account_id` exact, then `handle` exact; hashtag = `lowercase(remove("#"))`; no merging; a
  display name is not an identifier.
- No inference above Finding: a Pulse is single-subject; claims are never combined across subjects; no
  relationship/collaboration code path exists (tested).
- Evidence (ADR-003 MVP): single reliable source → medium; ≥2 independent source types, none low-trust → high;
  contradiction or only low-trust → low.

## Not built

Vision/OCR, API clients, Android capture, graph/relationship/audience/commercial layers, contradiction detection,
Pulse/Escape integration code, persistence.
