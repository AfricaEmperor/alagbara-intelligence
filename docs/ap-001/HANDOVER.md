# AP-001 Handover — Cotonou Event Radar + Venue Intelligence

> **Updated by AP-001-R2.** Status, evidence and release recommendation: see `AP001_R2_RELEASE_EVIDENCE.md` (recommendation: **HOLD**). The review flow below changed: the shared token was removed; reviewers authenticate (Supabase Auth, mock-tested only) and decisions carry client ids and versions. R1 audits (`AP001_*_AUDIT.md`) describe the pre-remediation state.

Branch (all repos): `claude/ap-001-cotonou-event-venue-radar-kr48v6`. Baseline: `main` @ `bc6433f` (alagbara-intelligence), `6b28678` (pulse-l1).

## Loop (working today, local)
```
radar register-source up1 upload "Operator uploads"; radar approve-source up1 --by <human>
radar ingest-upload up1 poster.png [poster.png.txt sidecar | tesseract if installed]
radar export-feed --output <pulse-l1>/radar-data/feed.json        # PULSE reads this
# in pulse-l1:  npm ci && npm run build && npm start   -> /radar (reviewer sign-in required; see .env.example)
radar apply-decisions <pulse-l1>/radar-data/decisions/            # directory of <decision_id>.json files
```
Env (PULSE): `RADAR_FEED_PATH`, `RADAR_MEDIA_DIR`, `RADAR_DECISIONS_DIR`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` (auth unconfigured => everything denied). No shared token exists.

## Limits (not hidden)
- No OCR engine installed here: text comes from operator sidecar `.txt` (marked `unverified`) or Tesseract when present. Transcription provider is interface-only. OCR/video paths are untested against real posters.
- Extraction is rule-based FR/EN; tested on synthetic posters only. `by <name>` organizer phrasing is not matched. Quality on real Cotonou posters is unmeasured.
- Persistence is local SQLite. Supabase migration is a **.DRAFT, unapplied**; RLS untested against a database.
- Facebook Graph: boundary only (no network). Requires approved app + Page permissions.
- Not built: Opportunity Pipeline (WP-06), recurring ingestion/notifications, Lagos config, review UI auth beyond shared token (replace with Supabase Auth + `radar_reviewers`).
- `escape-app` is empty; PULSE lives in `pulse-l1` (not in the original repo map). Runtime/security branches of alagbara-intelligence touch no SCOUT Python; the security branch carries RLS migrations that WP-04 must reconcile before any apply.

## Bounded work packages for Zuberi (not yet started; assign deliberately)
| WP | Repo / files | Depends | Acceptance |
|---|---|---|---|
| WP-04 | alagbara-intelligence `supabase/`, new `ana_engine/supabase_store.py` | security branch review, human approval to apply | AT-13 against a Supabase **branch** DB; RLS denial tests |
| WP-02b | `scout_fabric/facebook.py` | Meta app approval, token in secret store | mocked-Graph retry/idempotency tests; AT-01 for Facebook |
| WP-03b | `ana_engine/` | 30+ real, consented posters | measured field accuracy; golden-set tests |
| WP-05b | pulse-l1 `app/radar/` | WP-04 | Supabase Auth reviewers replace token |
| WP-06 | new `opportunities` module | WP-04 | AT-16: activation rejected without named human approval; no outbound contact |
