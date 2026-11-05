# AP001_AUTHORIZATION_AUDIT

Operation AP-001-R1 · Track A3 · AUDIT ONLY · 2026-11-05
Subject: transition from the shared-token review (`pulse-l1` `lib/radar/decisions.ts`, `app/api/radar/review/route.ts`) to individually authenticated reviewers. [V] verified · [I] inferred · [U] unverified.

## 1. Required properties vs current state

| Required property | Current state | Evidence | Gap |
|---|---|---|---|
| Named reviewer identity | `reviewer` is a free-text form field; only non-empty is checked | [V] `recordDecision`: `input.reviewer?.trim()` | **Forgeable.** Anyone holding the token can record a decision as any name. Audit trail identity is untrusted. |
| Role-based authorization | None. One shared secret `RADAR_REVIEW_TOKEN`; same power for approve/reject/correct | [V] `authorize()` | No roles, no least privilege, no revocation per person; rotating the token locks out everyone. |
| Server-side decision validation | Decision enum + non-empty ids validated; **event existence not checked** in PULSE; token compared constant-time; disabled when env unset | [V] code; [V] live probes: wrong token 401, empty reviewer 400, bad decision 400, valid 200 | Nonexistent `eventId` is accepted into the decisions file; rejected later by `apply-decisions` (audited as `decision_rejected`). No state-machine rule (e.g. reject→approve allowed without comment). |
| Audit trail | PULSE: JSONL row (`decision_id`, event, decision, reviewer, note, timestamp). Intelligence store: `audit` row on apply. | [V] | Two stores, no hash chain; reviewer string untrusted; timestamp is server clock of the PULSE host. |
| Replay protection | `decision_id` is generated **server-side per request**, so an HTTP replay creates a new decision. `apply-decisions` dedupes only identical `decision_id`s. | [V] code; local: `apply` twice → `skipped_duplicate` | Replays/double-submits produce duplicate decisions; no client-supplied idempotency key; no version-seen check (reviewer may approve a page that changed underneath — see persistence defect C1). |
| Rejection of unauthorized activation | **Not testable**: commercial-opportunity activation does not exist yet (WP-06 not built). Review is the only state-changing action. | [V] no activation code in either repo | Must be designed before WP-06: activation requires a named human with role `admin`, an approved source event, and an audited decision id. |
| Reviewer enumeration / brute force | Token has no rate limit or lockout; failures not logged | [V] no logging or limiter in `app/api/radar` | Exposed if public. |
| Transport | Token sent in form body or header; no CSRF concern while token is secret and not cookie-based | [I] | Fine for interim; replaced by session auth later (then CSRF protection is needed). |

Overall assessment: **adequate only for a single trusted operator on a private host; not adequate for multiple reviewers, any public/preview deployment, or audit-grade provenance.**

## 2. Recommended target design (not implemented)

**Identity:** Supabase Auth (email OTP/magic-link; MFA for `admin`) on an isolated project/branch designated by the Principal. Reviewer identity = `auth.uid()` from a verified JWT, never a form field. Sign-ups disabled; users are invited by an admin.
**Roles:** table `radar_reviewers(user_id, role in ('reviewer','admin'))` (SQL verified in AP001_SECURITY_AUDIT §6). `reviewer`: read queue, approve/reject/request correction. `admin`: manage reviewers, activate commercial opportunities (WP-06). `service_role`: used only by the Python worker, never in browser code or PULSE client bundles.
**Validation (server-side, in the database):** `radar_review_event(decision_id uuid, event_id, decision, expected_version)` verified to: reject non-reviewers and anon, reject invalid decisions, make a repeated `decision_id` a no-op (replay), and reject a stale `expected_version` (lost-update guard). Add: reject when event does not exist (currently `update … where` simply matches 0 rows → `stale version`; give it a distinct error), require a note for `reject` and `request_correction`.
**Client contract:** PULSE generates `decision_id` (uuid) when rendering the form and sends it with `version_seen`; double-click and replay become harmless.
**Audit:** append-only `radar_decisions` (verified) + `radar_audit`; periodically export hash-chained snapshot (each row hashes the previous) to detect tampering [I].
**Activation gate (WP-06 prerequisite):** `activate_opportunity(opportunity_id, decision_id)` callable only by `admin`; requires the linked event `review_status = 'approved'`; writes an audit row; no code path sends outbound messages — activation only records a human decision. Acceptance test AT-16: non-admin and anon calls rejected, verified on a disposable DB.
**Public surface:** reviewers' UI behind login; any public view reads an RLS view of approved events only.

## 3. Migration path from the shared token (reversible steps)
1. Keep the shared token but add: event-existence check, client `decision_id`, rate limit, structured logs (low risk; can ship before Supabase).
2. On a branch DB: apply corrected reviewer schema; seed reviewers manually.
3. Add Supabase Auth to PULSE `/radar/review`; remove token path (feature-flag first, then delete).
4. Add role tests (anon / non-reviewer / reviewer / admin / service_role) to CI against a disposable Postgres (the local Postgres 16 method used in this audit works without Docker).

## 4. Unverified
- U1 Supabase Auth settings of any project (providers, signup toggle, MFA, JWT expiry) — no project inspected for this.
- U2 Whether `ALAGBARA_OPERATOR_EMAILS` operator allowlist model (security branch) should be reused for PULSE reviewers; it is single-organization only per that branch's own notes.
- U3 Zuberi's verified identity and effective repository permissions: **not verified** — no handle, token or invitation was provided; `gh` auth in this environment is invalid (`GH_TOKEN` rejected). No work was delegated.
