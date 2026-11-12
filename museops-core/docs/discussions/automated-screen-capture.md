# Discussion: Automated Screen Capture as a Distinct Source

Status: Draft — not an ADR yet. Out of scope for Sprint 1 (Android Listener is
explicitly excluded per CLAUDE_CODE_PROMPT_SPRINT_1.md and the kickoff prompt).
For discussion whenever an Android capture module is actually scheduled.

## Context

schema-freeze-v0.1.md's SourceType enum includes `"screenshot"`, which — by
convention and by every current usage in the docs — implies a user-initiated
action: the person decided something was worth capturing and shared it.

Android exposes two mechanisms that let a system component trigger a screen
capture programmatically, without the user manually taking a screenshot:

- **MediaProjection API** — user grants a one-time permission via a system
  dialog; after that, the app can capture the screen on command (a signal,
  a schedule, a detected trigger event) with no further user action.
- **AccessibilityService** — can read screen content/structure directly
  (not just pixels), again without a manual screenshot step.

Both are legitimate, well-supported Android APIs — this is a feasibility
question with a clear "yes," not a hypothetical.

## Why this isn't just an implementation detail

Per ADR-001, Source is meant to describe the origin channel truthfully, and
per the Evidence Model (ADR-003), channel_trust is supposed to reflect
structural properties of that channel. An automated capture and a manual
screenshot differ on exactly the dimensions that discussion doc raised for
channel_trust:

| Dimension | Manual screenshot | Automated capture |
|---|---|---|
| Human curation before capture | Yes — user chose the moment | No — system-triggered |
| Editability before MuseOps sees it | Yes — can be cropped/edited before upload | Depends on pipeline; potentially none if captured→ingested directly |
| Directness (hops from origin event to signal) | User capture → (maybe edit) → upload | Trigger → capture → ingest, often fewer human hops |

These aren't cosmetic differences — they're the same two axes
(directness, tamper-resistance) the channel_trust discussion doc identified as
the actual drivers of trust level. Folding "automated capture" silently into
the existing `screenshot` SourceType would blur exactly the distinction
channel_trust exists to preserve, and would violate ADR-001's "no hidden
inference / one concept, one representation" spirit.

## Options to weigh later (not decided here)

1. **New SourceType**: e.g. `"automated_screen_capture"`, alongside
   `"screenshot"` for the manual case. Cleanest separation, but grows the
   enum.
2. **Modifier field on existing SourceType**: e.g. `capture_mode:
   "manual"|"automated"` attached to `screenshot`. Keeps the enum smaller but
   adds a new field not currently in schema-freeze — same "requires an ADR"
   bar either way per the Schema Change Policy.
3. **Fold into a broader Android adapter concept**: if the eventual Android
   Listener module produces several trigger-based signal types (capture,
   notification read, accessibility event), it may be worth designing that
   whole family in one ADR rather than adding capture-mode piecemeal.

## Open questions for whoever picks this up

- Does automated capture get its own `default_channel_trust`, or does it
  inherit from a decision made in the channel_trust ADR (since it's really a
  variant of the same underlying question: how much do we trust an image
  channel with no human curation step)?
- Should MediaProjection-based capture and AccessibilityService-based
  structured reads be treated as the *same* SourceType (both "automated,
  no manual step") or as genuinely different channels (one produces an
  image payload, the other produces structured UI data — arguably closer to
  `api_response` than `screenshot` in shape)?
- Permission/consent handling (the one-time MediaProjection grant) is a
  product/legal concern, not a domain-model concern, but worth flagging so
  it doesn't get lost — it belongs in whatever module actually implements
  the Android adapter, not in museops-core.

## Not decided here

This document exists so the question is on record before anyone builds an
Android capture module — not to preempt the ADR that should actually settle
it. Sprint 1 remains unaffected: no Android Listener work is in scope, and
nothing here should be implemented yet.
