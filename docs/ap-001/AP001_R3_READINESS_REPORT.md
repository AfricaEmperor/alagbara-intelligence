# AP001_R3_READINESS_REPORT

Operation AP-001-R3 — Real Identity & Persistence Readiness · 2026-11-05 · Branch `claude/ap-001-cotonou-event-venue-radar-kr48v6`
Raw outputs: `docs/ap-001/evidence_r3/` (R3_01 … R3_07). **No deployment. No Supabase write, migration, restore, setting change or credential action. No outreach. No merge.**

## 0. Recommendation: **HOLD**

AP-001 is now **ready for real project configuration**: the authentication code path is complete and tested end to end against a mock identity provider, and the corrected Supabase migration passes a disposable-PostgreSQL suite (93 tests, two-session concurrency, 9/9 mutation checks). It is **not** ready to run for real, because no Supabase target is designated (R3-A **BLOCKED**), the real Auth service has never been exercised, and the migration has never run on Supabase. Those need the Sovereign's decisions (§14). Nothing here should be read as production-readiness.

Claim classes: **VERIFIED** (observed directly, output stored) · **TESTED LOCALLY** (automated, local/mock/disposable only) · **IMPLEMENTED, NOT VERIFIED** · **BLOCKED** · **NOT STARTED**. Nothing is VERIFIED against a real Supabase Auth server or a Supabase-hosted copy of the new schema.

| Objective | Result | Class |
|---|---|---|
| R3-A Supabase environment readiness | Inventory + read-only inspection complete; **target selection BLOCKED** (none designated; branch creation not authorized; Auth settings unreadable with available tools) | VERIFIED (facts) / BLOCKED (selection) |
| R3-B Real Supabase Auth path | Sign-in (email OTP), session validation on every request, sign-out, fail-closed everywhere; 133-case matrix | TESTED LOCALLY (mock IdP) |
| R3-C Corrected persistence migration | v2 draft, explicit grants/RLS, definer functions, single-transaction review; 93 SQL tests + concurrency + 9/9 mutants | TESTED LOCALLY (PostgreSQL 16, stubbed Supabase roles) |
| R3-D SQLite/Supabase parity | Contract, mapping, backfill generator, read-only reconciliation, rollback; 6 parity tests incl. review-operation equivalence | TESTED LOCALLY; **parity with Supabase itself NOT claimed** |
| R3-E Release configuration | Variable inventory, sentinel leak audit (13 checks), placeholder-only `.env.example` | TESTED LOCALLY |

## 1. Gate 0 — baseline (VERIFIED)
| | alagbara-intelligence | pulse-l1 |
|---|---|---|
| Branch | `claude/ap-001-cotonou-event-venue-radar-kr48v6` | same |
| HEAD at R3 start | `199ee25` (= remote, 0/0 ahead-behind, clean) | `bd8c345` (= remote, 0/0, clean) |
| Matches reported R2 commits | **yes** | **yes** |
| `main` | `bc6433f` (untouched) | `6b28678` (untouched) |
R2 evidence re-read: access matrix 83/83, e2e 24/24 recorded in `evidence/`. R3 code commits: intelligence `17d5d0f`; PULSE `358d266`; later commits listed in the final handover message (this report is committed after them).
Supabase inventory was re-pulled, not assumed: still six projects, statuses unchanged.

## 2. R3-A — Supabase environment readiness (read-only; VERIFIED unless stated)

| Project | Ref | Status | Classification for AP-001 |
|---|---|---|---|
| ALAGBARA Development | `pvpaxhaflkdvcxghpndz` | ACTIVE_HEALTHY, PG 17, created 2026-11-03 | **Only plausible candidate**; "development" by name only (not explicitly designated for AP-001) |
| himma-foods-crm | `wsbshwwhlzfhlpxeuaoy` | ACTIVE_HEALTHY | Unrelated business system; treated as production-like; **not inspected, off-limits** |
| pulse-production | `iefjpxhcyvbkerkiiuzd` | INACTIVE (paused) | Production by name; contents UNKNOWN; **not restored** |
| alagbara-intelligence | `hbcxiyyuqgjokvypqrqr` | INACTIVE (paused) | Contents UNKNOWN; **not restored** |
| Nightlife MVP, AfricaEmperor's Project | `cyfgedjlaerhyotplpig`, `lwslsjdafhfqygucwbuj` | INACTIVE | Unknown; not inspected |

**ALAGBARA Development, inspected with catalog `SELECT`s only (no DDL/DML, no user data):**
- 7 tables, all `world_*` (an unrelated Abuja world-model domain), RLS enabled on all; 4 migrations (`20261104…`); **0 branches**; security advisors: **0 lints**; **0 auth users, 0 with a `radar_role`** → no reviewer exists anywhere yet.
- Policies exist only for role `authenticated` (13); none for `anon` ⇒ anon is blocked by RLS.
- **Grants are wide by Supabase default:** `anon` and `authenticated` hold ALL table privileges (including `TRUNCATE`, which RLS does not govern) on every `world_*` table; RLS is the only barrier there. One function (`record_world_mission_result`, invoker, `search_path=public, pg_temp`) executable by `authenticated`.
- Role attributes: `postgres` — **not superuser, `BYPASSRLS`**; `service_role` — `BYPASSRLS`; `anon`/`authenticated` — no `BYPASSRLS`; `authenticator` login, no inherit.
- Default ACLs: schema `public` auto-grants ALL on tables and EXECUTE on functions to `anon`/`authenticated`/`service_role` (for objects created by `postgres` and `supabase_admin`). **A new schema receives none** — the reason the radar tables live in schema `radar`.
- `auth.uid()` exact definition read and mirrored in the local stub; `auth.users` has `email_confirmed_at`, `banned_until`, `deleted_at`, `raw_app_meta_data`.
- **Auth configuration (providers, email OTP enabled, sign-ups disabled, OTP length/expiry, JWT expiry, MFA, redirect URLs): UNVERIFIED** — no available tool reads it; must be checked in the dashboard. The PULSE code assumes email OTP is enabled and sign-ups are disabled.
- **Branching:** `list_branches` works (empty); whether the plan supports branches and at what cost is **UNKNOWN**; creating one is a write and is not authorized.

**Isolation and rollback strategy (proposal, nothing executed):** (1) preferred: a Supabase **branch** of ALAGBARA Development created by the Sovereign's authorization (own database; schema copy; no `world_*` data touched); (2) else a new, empty AP-001 development project; (3) never `pulse-production`/`himma-foods-crm`. Because the Auth user table is shared per project, reviewers provisioned in a shared project also exist for its other apps — a dedicated project/branch avoids that. Rollback of the schema: the documented `drop schema radar cascade` (+ one public function) on that database only, after exporting evidence and decisions; a branch is rolled back by deleting it.
**Status: R3-A target selection BLOCKED.** Local design and tests continued as instructed.

## 3. Architecture decisions
1. **Plain `supabase-js` + one own httpOnly cookie, not `@supabase/ssr`.** Verified in the installed library: `@supabase/ssr` 0.5.2 overrides `maxAge` with 400 days, and refreshing from a handler that cannot persist cookies rotates (destroys) the refresh token. Smallest safe design: the cookie `radar_session` holds only the short-lived access token + its expiry (**no refresh token**); every request re-validates with the Auth server; expired ⇒ sign in again (documented trade-off: reviewers re-authenticate hourly; no refresh implemented).
2. **Email OTP with `shouldCreateUser: false`:** the Radar can never create an account. Request-code responses are identical for authorized, unknown, rate-limited and malformed addresses (no enumeration). A session cookie is issued only if the verified user is a confirmed reviewer by server-side `app_metadata`.
3. **Role is read live** from the Auth server on every request (revocation is immediate) and from `app_metadata.radar_role` only; `user_metadata` is never read.
4. **Default deny, two layers:** `proxy.ts` (credential presence; redirect to sign-in for page navigations, 401 for APIs) and per-page/per-route verification in `lib/radar/access.ts`. The proxy is never the only gate.
5. **Clients only receive generic text** (`authentication required` / `forbidden` / `service unavailable` / `invalid or expired code`); reasons go to structured server logs without tokens or emails.
6. **Database: own schema `radar`, not exposed by default; explicit REVOKE/GRANT; RLS on every table; no write policy for any API role; writes only through `SECURITY DEFINER` functions with `search_path = ''`.** Reviewer identity is checked **live against `auth.users`** (not a possibly stale JWT claim) — mirrors what PULSE does per request. **One source of truth:** no separate reviewers table (the R1 design's second source caused the lock-out bug).
7. **`review_status` is a generated column** of the JSON document ⇒ column and JSON cannot diverge. Evidence, decisions, audit and links are append-only (triggers, `TRUNCATE` denied even for the owner).
8. **Ingestion cannot approve or reject.** `upsert_event` is versioned and may only reopen a decided event with a reason, recorded as a system decision.
9. **No FORCE RLS:** verified `postgres` has `BYPASSRLS`, so `SECURITY DEFINER` functions it owns bypass RLS; FORCE would add nothing and risk breaking them.

## 4. Authentication matrix — `scripts/radar/access-test.mjs` (mock IdP; TESTED LOCALLY)
Result: **133/133 passed** (`evidence_r3/R3_05`). Groups (counted from that output):

| Group | Passed |
|---|---|
| unauthenticated | 7/7 |
| invalid token | 7/7 |
| non-reviewer (no role) | 5/5 |
| non-reviewer (role only in user_metadata) | 5/5 |
| non-reviewer (email unconfirmed) | 5/5 |
| non-reviewer (unknown role value) | 5/5 |
| forged identity | 3/3 |
| authorized (reviewer) | 3/3 |
| authorized (admin) | 3/3 |
| media policy | 4/4 |
| decision | 11/11 |
| cookie session | 3/3 |
| expired session | 5/5 |
| invalid session | 5/5 |
| sign-in | 28/28 |
| sign-out | 2/2 |
| auth unconfigured | 7/7 |
| auth misconfigured | 1/1 |
| auth provider down | 5/5 |
| non-radar regression | 14/14 |
| static | 3/3 |
| logs | 2/2 |

Required R3-B acceptance tests → where proven: unauthenticated denied (`unauthenticated`); authenticated non-reviewer denied (`non-reviewer …`, 4 variants); authorized reviewer permitted (`authorized (reviewer/admin)`, `cookie session`, `sign-in`); expired session denied (`expired session`: expiry by clock without calling the provider, and provider-reported expiry); invalid session denied (`invalid token`, `invalid session`: 5 malformed cookie shapes); provider outage fails closed (`auth provider down`); missing configuration fails closed (`auth unconfigured`, `auth misconfigured`: plain-http non-local URL refused); media follows the same rules (media cases in every group, incl. cookie → media); existing non-radar routes unchanged (`non-radar regression` 14/14, identical to the pre-upgrade baseline).
**What this does NOT prove:** the behavior of a real Supabase Auth server (error shapes, OTP email delivery, rate limits, token expiry/revocation timing — the mock *assumes* `logout?scope=local` revokes the token), OTP settings, or any real reviewer sign-in. **BLOCKED** on a designated project and provisioned reviewers.

## 5. Grants / RLS matrix (from the catalog of the disposable database; `evidence_r3/R3_02`)

**Table privileges** (S=select, I=insert, U=update, D=delete, T=truncate; `-` = none). RLS applies on top for SELECT:
```
== effective TABLE privileges (from the catalog; RLS is applied on top, see RLS policies)
     table_name      |     role      | privileges_siudt 
---------------------+---------------+------------------
 audit               | anon          | -
 audit               | authenticated | S
 audit               | service_role  | IS
 decision_rejections | anon          | -
 decision_rejections | authenticated | S
 decision_rejections | service_role  | IS
 decisions           | anon          | -
 decisions           | authenticated | S
 decisions           | service_role  | IS
 events              | anon          | -
 events              | authenticated | S
 events              | service_role  | S
 evidence            | anon          | -
 evidence            | authenticated | S
 evidence            | service_role  | IS
 failures            | anon          | -
 failures            | authenticated | S
 failures            | service_role  | IS
 obs_event           | anon          | -
 obs_event           | authenticated | S
 obs_event           | service_role  | IS
 parties             | anon          | -
 parties             | authenticated | S
 parties             | service_role  | ISU
 venues              | anon          | -
 venues              | authenticated | S
 venues              | service_role  | ISU
(27 rows)
```
**Function EXECUTE privileges** (`definer` = SECURITY DEFINER; every definer function pins `search_path = ''`, tested):
```
== effective FUNCTION execute privileges
                                                         function                                                         | definer | anon | authenticated | service_role 
--------------------------------------------------------------------------------------------------------------------------+---------+------+---------------+--------------
 public.radar_review_event(p_decision_id text, p_event_id text, p_decision text, p_expected_version integer, p_note text) | f       | f    | t             | f
 radar.backfill_event(p_doc jsonb, p_version integer)                                                                     | t       | f    | f             | t
 radar.is_admin()                                                                                                         | t       | f    | t             | t
 radar.is_reviewer()                                                                                                      | t       | f    | t             | t
 radar.review_event(p_decision_id text, p_event_id text, p_decision text, p_expected_version integer, p_note text)        | t       | f    | t             | f
 radar.reviewer_role()                                                                                                    | t       | f    | t             | t
 radar.upsert_event(p_doc jsonb, p_expected_version integer, p_reopen_reason text)                                        | t       | f    | f             | t
(7 rows)
```
**RLS and policies** (no INSERT/UPDATE/DELETE policy exists; tested):
```
== RLS status and policies
     table_name      | rls_enabled 
---------------------+-------------
 audit               | t
 decision_rejections | t
 decisions           | t
 events              | t
 evidence            | t
 failures            | t
 obs_event           | t
 parties             | t
 venues              | t
(9 rows)

      tablename      |   policyname   |      roles      |  cmd   |        qual         
---------------------+----------------+-----------------+--------+---------------------
 audit               | admins_read    | {authenticated} | SELECT | radar.is_admin()
 decision_rejections | admins_read    | {authenticated} | SELECT | radar.is_admin()
 decisions           | reviewers_read | {authenticated} | SELECT | radar.is_reviewer()
 events              | reviewers_read | {authenticated} | SELECT | radar.is_reviewer()
 evidence            | reviewers_read | {authenticated} | SELECT | radar.is_reviewer()
 failures            | admins_read    | {authenticated} | SELECT | radar.is_admin()
 obs_event           | reviewers_read | {authenticated} | SELECT | radar.is_reviewer()
 parties             | reviewers_read | {authenticated} | SELECT | radar.is_reviewer()
 venues              | reviewers_read | {authenticated} | SELECT | radar.is_reviewer()
(9 rows)
```
**Effective access by actor** (each cell is a test in `radar_rls_test.sql`; groups `anon`, `non-reviewer(…)`, `reviewer`, `admin`, `review`, `ingest`, `grants`, `hardening`):

| Actor | Read radar data | Direct write | Review (`review_event`) | Ingest (`upsert_event`/`backfill_event`) | Audit/failures |
|---|---|---|---|---|---|
| `anon` | `42501` on every table; no schema usage | `42501` | `42501` | `42501` | `42501` |
| authenticated, no subject | 0 rows | `42501` | `28000` not authenticated | `42501` | 0 rows |
| authenticated non-reviewer (no role / role only in `user_metadata` / email unconfirmed / banned / deleted / unknown role value) | **0 rows** (RLS) | `42501` | `42501` not a reviewer | `42501` | 0 rows |
| reviewer | all radar rows | `42501` (also `TRUNCATE`) | applies / replays / rejects stale (see below) | `42501` | 0 rows (admin-only) |
| admin | all radar rows | `42501` | as reviewer | `42501` | **readable** |
| `service_role` (worker) | all | only `INSERT` on evidence/links/failures/decisions/audit, `INSERT/UPDATE` on venues/parties; **never** UPDATE/DELETE/TRUNCATE events or history | no EXECUTE | via `upsert_event`/`backfill_event` only | insert |
| owner (`postgres_sim`) | n/a | cannot UPDATE/DELETE history or TRUNCATE (triggers) | n/a | n/a | n/a |

Behaviors proven for `review_event`: applies with the right version (column = JSON); replay with an old version is a no-op (`duplicate`, no extra decision/audit row); `decision_id` reuse with another decision/event/reviewer → `23505`; stale → `40001` with nothing changed; unknown event → `P0002`; invalid decision/id/version/note → `22023`; **zero rows updated → `XX001` with no decision or audit row created** (forced with a trigger that skips the update); **audit insert failure rolls back the event update and the decision** (one transaction); hostile `search_path` cannot redirect the definer functions (decoy table untouched).
Ingestion: create must be `pending`; duplicate create `23505`; stale `40001`; **cannot approve** (`42501`); reopen without reason refused; reopen with reason recorded as a system decision + audit row, human approval kept; contract checks (timezone, evidence) `23514`.

## 6. PostgreSQL test outputs
- Scratch database on a local **PostgreSQL 16.15**; the migration is applied by a **non-superuser, `BYPASSRLS` owner** (`postgres_sim`), mirroring Supabase's `postgres` (verified attributes). Roles, `auth.uid()` and `auth.users` are stubbed from verified definitions. **PG 16 + stub ≠ Supabase PG 17: fidelity beyond the verified items is UNVERIFIED.**
- `SUMMARY: sql_tests 93 run, 0 failed; concurrency stale=1 same-id=1` (full table `evidence_r3/R3_02`).
- Concurrency (two real sessions):
```
== concurrency: two real sessions
session1:  {"status": "applied", "version": 2, "event_id": "evt_conc", "review_status": "approved"}  
session2:  ERROR:  stale version: event is at 2, reviewer saw 1 CONTEXT:  PL/pgSQL function radar.review_event(text,text,text,integer,text) line 56 at RAISE   (waited 1.060367193s on the row lock)
final: approved v2, decisions=1
same-id s1:  {"status": "applied", "version": 2, "event_id": "evt_conc2", "review_status": "approved"}  
same-id s2:  {"status": "duplicate", "version": 2, "event_id": "evt_conc2", "review_status": "approved"} 
concurrency checks: stale-after-lock=1 same-decision-id-idempotent=1
```
- **Mutation check** (`supabase/tests/mutation_check.py`): each mutant deliberately breaks the migration; the suite must fail.
```
KILLED  M1 review_event without pinned search_path              failing tests:  1  [hardening] every SECURITY DEFINER function pins search_path = ''
KILLED  M2 no replay (decision_id) handling                     failing tests:  4  [review] replay with an OLD version is a no-op (duplicate); [review
KILLED  M3 no stale-version check in review_event               failing tests:  1  [review] stale version rejected, nothing changes
KILLED  M4 RLS disabled on radar.events                         failing tests:  8  [non-reviewer(no role)] SELECT events/evidence/venues/parties/obs_e
KILLED  M5 anon granted SELECT on radar.events                  failing tests:  2  [grants] anon holds NO privilege of any kind on any radar table; [h
KILLED  M6 no reviewer check in review_event                    failing tests: 14  [non-reviewer(no role)] review_event -> not a reviewer; [non-review
KILLED  M7 exactly-one-row guard removed                        failing tests:  3  [integrity] zero rows updated -> XX001, no decision/audit rows; [in
KILLED  M8 decisions no longer append-only                      failing tests:  1  [immutability] even the owner cannot UPDATE/DELETE history
KILLED  M9 authenticated granted direct INSERT on events        failing tests:  1  [grants] authenticated holds ONLY SELECT on radar tables (no wri

9/9 mutants killed
```
  The first run had one **survivor** (M9: direct `INSERT` granted to `authenticated` was still blocked by RLS, so behavior tests could not see the grant layer); I added catalog-level grant assertions (group `grants`) and it is now killed. During development six of my own test *expectations* were also wrong (typos/inverted conditions), each analyzed individually and corrected in the test, never in the migration.
- The migration remains an unapplied `.DRAFT`; nothing was applied to any Supabase project.

## 7. SQLite ↔ Supabase parity assessment (R3-D)

**Persistence contract shared by both stores**

| Concept | SQLite | PostgreSQL (`radar.*`) | Rule |
|---|---|---|---|
| Event identity | `events.event_id` = `evt_` + sha1(norm_title\|date\|Cotonou)[:12], or sha1(first observation) when undated | `events.event_id` text PK, `doc->>'event_id' = event_id` (CHECK) | assigned once, never changes |
| Evidence identity & provenance | `evidence.observation_id` = sha256(source_id\nsha256(bytes)); doc has `content_hash`, source, collection method, `collected_at` | `evidence.observation_id` PK (64-hex CHECK), `content_hash` CHECK, doc ids CHECK; append-only | same bytes via a source = one observation |
| Versioning | `event_versions.version` (own table so old writers still run) | `events.version` | +1 per accepted change; stale write rejected |
| Reviewer identity | `decisions.reviewer` (text; PULSE writes the verified user id) | `decisions.reviewer` text = `auth.uid()::text` | server-derived, never client input |
| Decision ID | `decisions.decision_id` (client-supplied, 8–64 `[A-Za-z0-9-]`) | `decisions.decision_id` PK, same CHECK (or `sys-…`) | idempotency key |
| Audit history | `audit` (autoincrement id) | `audit` + `legacy_sqlite_id` unique | one row per applied human decision; append-only |
| Conflict resolution | claims are unioned; contradictions recomputed; reopen only on a *new* contradiction, as an explicit system decision | doc stores the same; `upsert_event` records the reopen | never overwrite a differing value |
| Idempotency | unique keys; `apply_decisions` per decision_id; rejections recorded once | PKs + `ON CONFLICT DO NOTHING`; `backfill_event` insert-if-absent; replay returns the original outcome | re-run = no-op |
| Timestamps / timezone | ISO-8601 text (UTC `+00:00`; event times carry `+01:00`, `Africa/Porto-Novo`) | `timestamptz` for `at`/`created_at`; event times stay inside the JSON verbatim; `timezone` CHECK = `Africa/Porto-Novo` | compare in UTC with microseconds |

**Tooling (implemented):** `radar pg-backfill-sql` writes an idempotent, single-transaction, never-overwriting SQL script (it never connects); `radar pg-reconcile --psql "<cmd>"` issues `SELECT`s only and prints differences; reconciliation queries are in `ana_engine/pg_sync.py` (`PG_QUERIES`).
**Backfill procedure (for the authorized branch DB):** freeze writers → `radar export-feed` snapshot + copy `radar.sqlite3` → generate the script → review → run as `service_role` → `radar pg-reconcile` must print `"parity": true` → only then switch the writer. **Duplicate detection:** PKs make duplicates impossible; reconciliation reports `only in sqlite/postgres` and `differs` per key. **Rollback:** the script is one transaction (failure leaves nothing); after commit, `drop schema radar cascade` on that database restores the pre-backfill state; SQLite is never modified, so it remains the authoritative fallback. **Failure recovery:** interrupted script ⇒ nothing committed ⇒ re-run; conflict ⇒ script aborts naming the event, nothing overwritten.

**What actually passed** (`tests/test_pg_parity.py`, disposable PG; TESTED LOCALLY): backfill of a store with approval, system reopen, re-approval, contradictions and parties reconciles with **zero differences** across evidence, venues, parties, events (doc + version), observation links and decisions (exact timestamps) and audit; running it twice is a no-op (`unchanged`); deliberate tampering is detected per key; a differing pre-existing row aborts the whole script and is never overwritten (nothing else inserted); an interrupted run leaves nothing and a full re-run reaches parity; and the **review operation behaves identically on both stores** for apply, replay, stale, id-reuse, invalid decision, invalid id, fresh-version and unknown event (every field identical except the clock stamp, bounded to < 5 s).
**Not covered, so NOT claimed:** `failures`, `decision_rejections`, legacy `applied_decisions`, media files (hashes are covered, bytes are not), `upsert_event` vs SQLite ingestion behavior, concurrency across the two stores, volume/performance, and **any run on real Supabase**. **Parity is therefore proven only between SQLite and a local PostgreSQL 16 stub, for the covered entities.**

## 8. Environment variable inventory (placeholders only; `.env.example`)
| Class | Variable | Read by | Notes |
|---|---|---|---|
| Public (browser-visible by design; inlined at build) | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | existing consumer code (`lib/supabase.ts`); Radar only as a fallback | anon/publishable key only |
| Authentication (server-only, runtime) | `SUPABASE_URL` (https required; http only for localhost), `SUPABASE_ANON_KEY` | Radar auth | **no default**: absent ⇒ deny |
| Server-only secrets | `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` | existing consumer app / Prisma; **never by Radar** | must never carry `NEXT_PUBLIC_` |
| Persistence / media (server-only) | `RADAR_FEED_PATH`, `RADAR_MEDIA_DIR`, `RADAR_DECISIONS_DIR` | Radar | file-based; Supabase persistence has no variable yet (not implemented) |
| Runtime flags | `NODE_ENV`; `DEV_MODE=false` (baseline; **not read by any code**, README says review before enabling) | | non-secret |
| Test-only | `RADAR_CLI` | e2e script | |
Python worker: no environment variables; paths via `--data`, database access only through an operator-supplied `psql` command or the generated SQL.

**R3-E verification (`scripts/radar/env-audit.mjs`, 13/13 — `evidence_r3/R3_07`):**
```
GROUP         RESULT CHECK
inventory     PASS   every env var read by the code is classified (10 found)
inventory     PASS   Radar code reads NO secret-class variable (service-role key, database URL)
inventory     PASS   no NEXT_PUBLIC_ variable has a secret-sounding name
fallbacks     PASS   no hard-coded Supabase project URL or key in source (no silent default project)
fallbacks     PASS   auth configuration has no default: absent => null => deny; plain-http non-local provider refused
secrets       PASS   .env.example holds names/placeholders only (10 variables; only non-secret true/false flags carry a value)
secrets       PASS   no .env / .env.local / key files tracked in git
leak(build)   PASS   no sentinel (service-role, DB password, anon, paths) in ANY client bundle (.next/static)
leak(build)   PASS   no sentinel inlined into server bundles either (all read at runtime from the environment)
leak(build)   PASS   client bundle was actually scanned (14 files)
leak(http)    PASS   no sentinel in any response body or header (9 probes incl. provider-unreachable paths)
leak(http)    PASS   provider unreachable: client sees only the generic 503, not the provider host or error
leak(logs)    PASS   no sentinel value in server logs

Variables found in code: DATABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_SUPABASE_URL, NODE_ENV, RADAR_CLI, RADAR_DECISIONS_DIR, RADAR_FEED_PATH, RADAR_MEDIA_DIR, SUPABASE_ANON_KEY, SUPABASE_URL
13/13 passed
```
Method: build **with sentinel values** in every secret-class variable, then scan every client bundle and server bundle, nine HTTP probes (including provider-unreachable paths) and the server logs. The scanner itself was validated with a canary placed in a `NEXT_PUBLIC_*` variable (found in 3 server bundles, proving it detects inlining and why runtime-read names are used). Hard-coded project URLs/keys: none; no default project; no secrets tracked.

## 9. Dependency and regression results (final run)
```
$ rm -rf node_modules .next && npm ci
added 133 packages in 23s
$ npm run typecheck
exit=0
$ npm run build
▲ Next.js 16.4.5 (Turbopack)
⚠ React 18 support is deprecated in Next.js 16 and will be removed in Next.js 17. Please upgrade to React 19. Learn more: https://nextjs.org/docs/messages/react-version
✓ Compiled successfully in 5.0s
  Finished TypeScript in 4.8s ...
✓ Generating static pages using 3 workers (16/16) in 411ms
$ npm audit
found 0 vulnerabilities
$ npm audit --omit=dev
found 0 vulnerabilities
```
| Check | Result | Class |
|---|---|---|
| Python `pytest` | ============================== 69 passed in 7.80s ============================== (63 pre-R3 + 6 PG parity) | TESTED LOCALLY |
| PostgreSQL SQL suite | sql_tests 93 run, 0 failed; concurrency stale=1 same-id=1 | TESTED LOCALLY |
| Mutation check | 9/9 killed | TESTED LOCALLY |
| PULSE `npm ci` / typecheck / production build / `npm audit` (full and prod) | pass / pass / pass / **0 vulnerabilities** | VERIFIED |
| Access matrix | 133/133 | TESTED LOCALLY |
| Cross-repo e2e | 24/24 passed | TESTED LOCALLY |
| Non-radar PULSE routes | 14/14 identical to baseline | VERIFIED |
Known warning carried forward: **Next 16 deprecates React 18** (removal in Next 17) — React 19 migration NOT STARTED.

## 10. Files changed (R3)
**alagbara-intelligence** — `supabase/migrations/…event_radar.sql.DRAFT` (rewritten v2, unapplied); `supabase/tests/{stub_supabase.sql, radar_rls_test.sql, run_local_pg.sh, mutation_check.py}` (new); `scout-intelligence-fabric/src/ana_engine/{pg_sync.py (new), cli.py, store.py}`; `tests/test_pg_parity.py` (new); docs (this report, `evidence_r3/`, addenda).
**pulse-l1** — new: `app/api/radar/auth/{signin,verify,signout}/route.ts`, `app/radar/signin/page.tsx`, `lib/radar/http.ts`, `scripts/radar/env-audit.mjs`; changed: `lib/radar/auth.ts` (rewritten), `lib/radar/access.ts`, `proxy.ts`, `app/radar/layout.tsx`, `app/api/radar/review/route.ts`, `scripts/radar/{mock-auth.mjs, access-test.mjs, e2e-integration.mjs}`, `.env.example`, `package.json`. No other consumer file touched.

## 11. Defects found and fixed during R3 (all by the new tests)
1. **Deadlock:** opening `RadarStore` ran a write statement on every open, so a process opening the store blocked behind another's long transaction (a flaky test pointed at it: 2/6 isolated failures, then 0/30 after the fix). Now it writes only when migration is needed.
2. Session cookie `Max-Age` could exceed the token lifetime by 1 s (supabase-js rounds `expires_at` up) — now bounded by `expires_in`.
3. Migration test mutant M9 survived (see §6) — grant-layer assertions added.
4. My own test-expectation errors and harness mistakes (tautological assertion removed before it ran; `SET ROLE` in a definer helper; unclosed script string) were corrected without touching product code.

## 12. Unresolved blockers and risks
| # | Item | Class |
|---|---|---|
| B1 | No designated Supabase target; branch creation not authorized | BLOCKED |
| B2 | Real Auth never exercised: OTP enabled? sign-ups disabled? JWT/OTP expiry? logout revocation? email delivery? | BLOCKED / UNVERIFIED |
| B3 | No reviewer exists (0 auth users in the only candidate); provisioning is an administrative Auth-API action not performed | BLOCKED |
| B4 | Migration never applied on Supabase (PG 17, real `auth` schema, PostgREST exposure, default ACLs of the target project) | BLOCKED |
| B5 | Radar still reads the feed from files, not from Supabase; the Supabase read path/worker connection is not implemented | NOT STARTED |
| B6 | No session refresh (hourly re-sign-in); no rate limiting on the sign-in endpoints beyond the provider's own | IMPLEMENTED, NOT VERIFIED |
| B7 | Hosting undecided; file-based feed/media/decisions incompatible with serverless; decision files unauthenticated beyond FS permissions | BLOCKED |
| B8 | React 18 deprecated by Next 16 | NOT STARTED |
| B9 | `main` intake endpoint (CORS `*`, no auth) and anon policies in `main/migration.sql` untouched | NOT STARTED |
| B10 | Extraction accuracy on real posters unmeasured; personal-data legal review pending | NOT STARTED |
| B11 | Zuberi identity/permissions unverified; no delegation | BLOCKED |

## 13. Rollback instructions
- **PULSE:** `git revert` the R3 commits (newest first). Reverting R3-B returns to R2's bearer/cookie boundary (still default-deny). Never revert past R2's access control while reachable. Env: R3 adds no new variable beyond R2.
- **Intelligence code:** `git revert` the R3 commits; the SQLite file is unchanged by parity tooling (read-only), and the store fix only changes *when* a write happens.
- **Migration:** nothing applied ⇒ nothing to roll back. If later applied to an authorized database: export `radar.evidence` and `radar.decisions` (append-only), then `begin; drop function if exists public.radar_review_event(text,text,text,integer,text); drop schema radar cascade; commit;` — it touches nothing else. On a Supabase branch, delete the branch instead.
- **Backfill:** a single transaction; failure leaves nothing; after commit, the same `drop schema` restores the pre-backfill state; SQLite remains authoritative.

## 14. Next authorization required (for GO)
1. **Designate the target**: authorize an isolated branch (or new dev project) for AP-001, and confirm its Auth settings (email OTP on, sign-ups off, expiry) — resolves B1/B2.
2. **Authorize applying the draft migration to that isolated database only**, and re-running `radar_rls_test.sql` + the parity tests against it (replacing the local stub) — resolves B4.
3. **Authorize reviewer provisioning** for named humans the Sovereign nominates (sets `app_metadata.radar_role` server-side) and one real sign-in test — resolves B3.
4. Decide hosting (B7), then a React 19 spike (B8). Keep outreach, pricing and deployment on hold.
GO requires 1–3; until then: **HOLD**.
