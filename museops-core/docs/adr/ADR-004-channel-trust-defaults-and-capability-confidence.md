# ADR-004 — Channel Trust Defaults and capability_confidence Representation

Status: Accepted (founder-approved, MUSEOPS-IMPL-001)
Version: v0.1.1
Amends: `schema-freeze-v0.1.md` (patched to v0.1.1). Clarifies ADR-001 and ADR-003; does not change them.
Supersedes: the open items in `docs/discussions/channel-trust-defaults.md` (decided below).

## Context

1. `schema-freeze-v0.1.md` typed `capability_confidence` as `"high" | "medium" | "low"`, while ADR-003
   (Accepted) and ADR-001 specify a number in 0.0–1.0 (example `0.92`).
2. Only `android_notification` had a `default_channel_trust` (ADR-003: high); four SourceTypes were unset.
3. `api_response` is a category of channels, not one channel; a single flat default would reproduce the
   "one term hiding several concepts" problem ADR-003 was written to avoid.
4. The pulse-l1 repository already defines an unrelated Prisma enum named `SourceType`.

## Decisions

### A. capability_confidence is numeric

`capability_confidence: number`, finite, `0 <= x <= 1`. The strings `"high" | "medium" | "low"` are rejected.
The core never converts between the enum and numbers (that mapping would be an invented calibration).
It remains distinct from `channel_trust` (a Source property) and `evidence_strength` (a Finding property).
"Finding confidence" is expressed only as `evidence.evidence_strength`; no generic `confidence` field exists.

### B. Channel trust defaults

| SourceType | default_channel_trust | Rationale (from the discussion draft's two axes) |
|---|---|---|
| `android_notification` | high | Direct from an installed app's API; hard to tamper without device compromise (ADR-003). |
| `user_upload` | medium | Direct and intentional, but the channel does not validate content. |
| `screenshot` | medium | User-curated, but editable before upload; same tier as `user_upload`. |
| `shared_image` | low | Extra human hop (re-share) plus the same editability. |
| `api_response` | **unset** | See C. |

The ordering encodes both axes: directness (hop count) and tamper resistance. A default can always be
overridden by an explicit `channel_trust` on a concrete Source (for example, a verified adapter).

### C. api_response

Retained as a SourceType. Its default is explicitly unset (`null` in `DEFAULT_CHANNEL_TRUST`; the field is
omitted in `SourceTypeDefinition`). Creating a Source of this type without an explicit `channel_trust` raises
`ChannelTrustUnsetError`. No fallback score is applied. A split (for example `tiktok_api_response`) is
deferred until a real adapter exists; if added, it is an additive enum value and needs its own ADR.

### D. Capability

`nlp | ocr | vision` is retained. Sprint 1 implements `nlp` only; `ocr` and `vision` are valid enum values with
no implementation.

### E. Namespacing

MuseOps' SourceType is the *signal-channel* vocabulary and is exported as `ChannelSourceType`. It is never
merged with pulse-l1's `SourceType` (submitter provenance). Mapping, if ever needed, is explicit and lives in
the consumer (see `docs/integration-contract.md`).

## Consequences

- Positive: the accepted ADRs and the freeze agree; trust levels are auditable; no invented values.
- Negative: `default_channel_trust` is optional, so consumers must handle absence; any externally held enum
  confidences must be re-expressed numerically by their producer.
- Migration: no persisted MuseOps data existed (no implementation was present in any repository); see the
  Changelog in the schema freeze.

## Out of scope

Automated screen capture as a distinct source (`docs/discussions/automated-screen-capture.md`) remains an
open discussion; no SourceType is added for it.
