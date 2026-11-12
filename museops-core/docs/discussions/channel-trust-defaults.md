# Discussion: default_channel_trust for remaining SourceTypes

Status: Draft — not an ADR yet. For discussion before Sprint 2.
Logged as an open gap in docs/adr/NOTES.md.

## Context

schema-freeze-v0.1.md defines `default_channel_trust: "high"|"medium"|"low"` per
SourceType, but only `android_notification` has a value fixed anywhere in the
docs (ADR-003: "high"). The other four SourceType values from schema-freeze are
undefined:

- `screenshot`
- `shared_image`
- `user_upload`
- `api_response`

Sprint 1's museops-core correctly left these unset rather than inventing values
(per ADR-001 Rule 1 — no hidden inference — this extends to not inventing trust
levels either).

## What channel_trust actually measures (per ADR-003)

"How reliable is this source type, structurally, independent of any single
observation?" It is not about content quality or capability confidence — it's
about the channel itself. Two lenses that seem to matter based on the
android_notification precedent:

1. **Provenance integrity** — can the payload be tampered with before MuseOps
   sees it?
2. **Directness** — is there an intermediary (a human relaying, a re-share,
   a re-encode) between the origin event and the signal?

`android_notification = high` fits both: it comes straight from an installed
app's own notification API, no human transcription step, hard to spoof without
compromising the device itself.

## Options for each type

**`user_upload`**
- Directly provided by the user with clear intent, but content itself could be
  anything (a photo of a screen, a forwarded meme, a doctored image) — the
  *channel* doesn't validate the *content*.
- Candidate: `medium` — direct and intentional, but no structural guarantee
  against tampering or misattribution.

**`screenshot`**
- User-captured, same tampering risk as any image, plus screenshots are
  trivially editable before upload.
- Candidate: `medium` or `low` — leaning toward the same tier as `user_upload`
  unless you want to explicitly signal "even less verified" for screenshots.

**`shared_image`**
- Implies it arrived via a share/forward, so there's now an additional hop
  (someone else selected and sent it) plus the same editability concern.
- Candidate: `low` — most hops between origin and MuseOps, least structural
  guarantee.

**`api_response`**
- The odd one out: "API" isn't one channel, it's a category of channels with
  wildly different trust profiles (a verified platform API vs. a scraped
  third-party endpoint).
- Open question worth raising before assigning any single default: does
  `api_response` deserve a static `default_channel_trust` at all, or does it
  need to be split into more specific SourceTypes later (e.g.
  `tiktok_api_response` vs. generic `api_response`)? Assigning one flat value
  now risks the same "single term hiding multiple concepts" problem ADR-003
  was written to avoid for confidence — worth not repeating it for trust.

## Suggested framing for the eventual ADR

Rather than "pick 4 values," the ADR probably needs to answer: does trust vary
by *hop count* from origin to MuseOps (directness), by *tamper resistance*
(can the payload be edited before capture), or both independently? Right now
`android_notification=high` satisfies both criteria simultaneously, which is
why it was easy. The other four don't cleanly satisfy both, so a one-line
"screenshot=medium" style answer may under-specify the actual reasoning future
readers will need.

## Not decided here

This document raises the dimensions; it does not set the values. That's your
call, then it becomes ADR-004 (or an ADR-003 amendment) before any Sprint that
depends on these four source types.
