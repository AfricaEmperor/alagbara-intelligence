# MuseOps Core — Integration Contract (v0.1.0)

Audience: Pulse L1, Escape App and any future consumer. **No consumer integration is implemented yet.**

## 1. What consumers receive

Versioned JSON Schema (draft 2020-12) artifacts, generated from the Zod schemas:

```
museops-core/contracts/v0.1/
  manifest.json               contract_version + sha256 per schema file
  raw-input | source-type | source | signal | observation | subject |
  external-identity | observation-set | pulse | finding | provenance-chain  .schema.json
```

`$id` has the form `urn:alagbara:museops:contract:<version>:<name>`. Consumers pin a contract version and
should verify the `sha256` values in `manifest.json`. Consumers never import the package at runtime and never
share a database with the core.

## 2. Versioning and compatibility

- `contract_version` is semver. The directory is `v<major>.<minor>`.
- Patch: documentation or validation clarifications that accept/reject the same documents.
- Minor: additive and backward-compatible (new optional field, new enum value). Consumers must tolerate
  unknown enum values they do not act on.
- Major: removing/renaming a field, tightening validation of accepted documents, or changing a meaning.
- Any schema change requires an ADR, an impact analysis and a migration note (schema-freeze policy). The CI
  step `contracts:check` fails if the committed artifacts differ from the Zod source.
- A new `v<major>.<minor>/` directory is added for each minor/major; old directories are kept.

## 3. Identifier semantics

- Ids are opaque, non-empty strings. Prefixes in examples (`src_`, `sig_`, `obs_`, `sub_`) are conventions, not validated.
- Ids are unique within their entity type and never reused. Producers choose the id scheme.
- Timestamps are ISO 8601 UTC with a `Z` designator.
- `subject_id` is a MuseOps-internal identity. It is not a platform id; platform ids are `ExternalIdentity.value`.

## 4. Validation and rejection behaviour

- Every object schema is closed (`additionalProperties: false`): unknown fields are rejected, notably
  `confidence`, and `evidence_strength` on an Observation.
- `capability_confidence` must be a number in [0, 1]; `"high" | "medium" | "low"` is rejected.
- `Finding.pulse_id` is required and non-empty.
- Some rules cannot be expressed in JSON Schema and are enforced by the library only: `timeframe.start <= end`,
  "a creator candidate needs an account_id or handle", cross-object reference integrity (`ProvenanceError`),
  single-subject Pulses (`CrossSubjectError`). Consumers validating with JSON Schema alone must re-check these
  or treat the producer as authoritative.
- A rejected document must be rejected whole; consumers do not repair or default fields.

## 5. Provenance requirements

Every Finding must be traceable: Finding → Pulse → ObservationSet → Observation → Signal → Source → SourceType.
`ProvenanceChain` is a derived audit record. Producers must retain Signals (immutable, never deleted).
A document whose chain cannot be resolved must not be treated as evidence.

## 6. Trust semantics

`channel_trust` (Source), `capability_confidence` (Observation, number 0–1) and `evidence_strength`
(Finding, high/medium/low) are independent. Consumers must not merge, rename or average them.
`api_response` Sources must carry an explicit `channel_trust`.

## 7. Pulse Creator → MuseOps ExternalIdentity mapping (contract, not implemented)

pulse-l1 `Creator` (prisma/schema.prisma) is an application record with `name`, optional `handle`, `type`. It
maps to MuseOps only as follows:

| Pulse | MuseOps | Rule |
|---|---|---|
| `Creator.id` | *(none)* | Not a MuseOps identifier. A consumer may store a MuseOps `subject_id` against it; the core does not know Pulse ids. |
| `Creator.handle` | `ExternalIdentity{platform:"tiktok", identifier_type:"handle", value}` | Only when the handle is known to be a TikTok handle. Exact string; no normalization, no case folding. Initial `identity_link_status: "observed"`. |
| `Creator.name` | *(none)* | A display name is not an identifier and cannot be resolved (`CreatorCandidateSchema` rejects it). |
| TikTok numeric id | `ExternalIdentity{identifier_type:"account_id"}` | Preferred over handle. Pulse has no such field today. |
| Pulse `SourceType` (VENUE_SUBMITTED, ...) | *(none)* | Different concept. Never mapped onto `ChannelSourceType`. |

No automatic merging: two Pulse creators are never combined because their names or handles look similar. A handle
change is a new observed identity, not a rename. `confirmed` / `linked` require a human or an explicit
account_id match and are out of scope for v0.1.

## 8. Escape consumption boundary

escape-app is an independent scaffold with no data model (README: no runtime dependency, shared database or
package import with other systems without an explicit interface contract). Boundary:

- Escape may read contract artifacts and validate documents it receives or produces.
- Escape may not import `@alagbara/museops-core`, read its storage, or call into it at runtime.
- Escape may display Findings only with their `evidence_strength` and `source_types`; it must not present
  `capability_confidence` or `channel_trust` as certainty about a claim.
- Transport (file export, queue, API) is undecided and is a separate, explicitly approved step.
  pulse-l1's existing Radar feed (`docs/SCOUT_MUSE_PULSE_PIPELINE.md` on a Pulse feature branch) is a precedent:
  a file-based, versioned export reviewed by a human before import.

## 9. Not covered

Relationship/graph claims, audience or influence scoring, commercial relationships, and any combination of two
subjects' observations are out of scope for the entire core.
