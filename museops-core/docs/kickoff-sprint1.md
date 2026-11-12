# MuseOps Core — Sprint 1 Kickoff Prompt (for Claude Code)

Paste this into Claude Code after committing `docs/vision.md`, `docs/architecture.md`,
`docs/schema-freeze-v0.1.md`, and `docs/adr/ADR-001-*.md`, `ADR-002-*.md`, `ADR-003-*.md`
to the repo.

---

## Task

Build `museops-core`: a TypeScript domain library that proves the MuseOps provenance
chain end to end:

**Source → Signal → Observation → ObservationSet → Pulse → Finding**

with a minimal Identity Resolver (Creator = stable ID resolution, Hashtag = exact
normalized match).

Read `docs/vision.md`, `docs/architecture.md`, `docs/schema-freeze-v0.1.md`, and all
three ADRs before writing any code. They are the source of truth. Do not introduce any
field, enum value, or object not defined there. If something seems missing, stop and
propose it as a note for a future ADR instead of implementing it.

## Stack

TypeScript, Node.js, Vitest, Zod (schemas as source of truth, TS types via `z.infer`).

## Repo layout to create

```
museops-core/
├── package.json
├── tsconfig.json
├── vitest.config.ts
├── domain/
│   ├── source.ts            # SourceType, Source
│   ├── signal.ts            # Signal
│   ├── observation.ts       # Observation, Capability ("nlp" only in Sprint 1)
│   ├── observationSet.ts    # ObservationSet
│   ├── pulse.ts             # Pulse, HistoricalComparison
│   ├── finding.ts           # Finding, Contradiction
│   ├── subject.ts           # Subject
│   └── externalIdentity.ts  # ExternalIdentity
├── application/
│   ├── ingestSignal.ts          # create Source + Signal from raw input
│   ├── createObservationSet.ts  # group Observations by subject_id + timeframe
│   ├── createPulse.ts           # aggregate an ObservationSet into a Pulse
│   ├── createFinding.ts         # produce a Finding from a Pulse + evidence rules
│   └── identityResolver.ts      # resolveCreator(), resolveHashtag()
├── capabilities/
│   └── nlp/
│       ├── CreatorExtractor.ts  # capability="nlp" → subject_candidate + claim
│       └── HashtagExtractor.ts  # capability="nlp" → normalized hashtag claim
├── fixtures/
│   └── tiktok/
│       ├── stephanie-live.json
│       └── easyboy-update.json
└── tests/
    ├── provenanceChain.test.ts
    ├── identityResolution.test.ts
    └── noFalseInference.test.ts
```

## Fixtures (create exactly this content)

`fixtures/tiktok/stephanie-live.json`
```json
{
  "source": "android_notification",
  "content": "Stephanie is LIVE on TikTok"
}
```

`fixtures/tiktok/easyboy-update.json`
```json
{
  "source": "android_notification",
  "content": "EASYBOY posted an update"
}
```

## Domain rules (non-negotiable, from schema freeze + ADRs)

- **Source/SourceType**: `channel_trust` describes the channel, never an individual
  observation's confidence.
- **Signal**: immutable, archived, never deleted, holds `source_id` + raw `payload`.
- **Observation**: holds `capability` + `capability_confidence` — never `evidence_strength`.
  Sprint 1 capability value is `"nlp"` only, for both extractors.
- **Finding**: holds `evidence.evidence_strength` and `evidence.source_types` — never a
  generic `confidence` field anywhere in the system.
- **Identity**: `Subject` (internal) and `ExternalIdentity` (platform-observed) are
  separate types. No automatic merging. Creator resolution priority is
  `account_id` exact match → `handle` exact match. Hashtag resolution is
  `lowercase(remove("#"))`.
- **No business inference** below Finding. `"Stephanie is LIVE"` and
  `"EASYBOY posted an update"` must never combine into a relationship/collaboration
  claim — that's out of scope for the entire core, not just Sprint 1.

## Evidence strength default (flagged assumption — confirm before coding)

ADR-003 defines evidence_strength qualitatively but Sprint 1 fixtures only produce a
single android_notification source with no contradiction. Proposed default:

- Single reliable source, no contradiction → `evidence_strength = "medium"`
  (matches the ADR-003 worked example).
- `"high"` and `"low"` paths can exist in the type system but won't be exercised by
  Sprint 1 fixtures/tests — don't build speculative logic to reach them.

If you disagree with this default, stop and ask before implementing `createFinding.ts`.

## Required tests (describe behavior, don't over-specify implementation)

**`provenanceChain.test.ts`**
Build a Finding from the `stephanie-live` fixture through the full pipeline and assert
each layer's ID chain resolves back to the original Source: Finding → Pulse →
ObservationSet → Observation → Signal → Source. Assert it's impossible to construct a
Finding without a valid Pulse reference (type-level or runtime check).

**`identityResolution.test.ts`**
Feed two hashtag observations, `#Baddie` and `#baddie`, through `resolveHashtag()` and
assert they resolve to exactly one Subject (not two), with the normalized value
`"baddie"`. Also cover Creator resolution: two observations with the same `account_id`
but different handles resolve to the same Subject.

**`noFalseInference.test.ts`**
Run `stephanie-live.json` and `easyboy-update.json` through extraction independently
and assert: (a) two distinct Observations/Findings are produced, (b) nothing in the
output contains a relationship/collaboration claim between the two subjects, (c) no
code path exists that would combine them into such a claim.

## Explicitly do not build

Vision Agent, OCR, image/audio analysis, TikTok/Instagram/Facebook API clients, Ana
reasoning, Flynn orchestration, commercial scoring, automatic identity fusion,
username-change detection, cross-platform identity resolution.

## Before you start

Give me:
1. Confirmation you've read all the docs and the evidence_strength default above.
2. Any conflicts you see between this brief and the ADRs.
3. Then scaffold `package.json` + `tsconfig.json` + domain types first, run a quick
   type-check, and only then move to application/capabilities/tests.

Do not expand scope. If a gap appears, write a one-line note in `docs/adr/NOTES.md`
proposing a future ADR instead of implementing a workaround.
