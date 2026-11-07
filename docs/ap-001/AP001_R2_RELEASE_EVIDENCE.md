# AP001_R2_RELEASE_EVIDENCE

Operation AP-001-R2 (remediation) · 2026-11-05 · Branch `claude/ap-001-cotonou-event-venue-radar-kr48v6`
Repos: `alagbara-intelligence` (HEAD at report time: see §3), `pulse-l1` (HEAD `bd8c345` + this report's companion commit none). Baselines at R2 start: intelligence `9b993db`, PULSE `6036ff3`; `main` untouched (`bc6433f` / `6b28678`).

## 0. Release recommendation (read this first)

**HOLD. Do not deploy, preview-deploy or merge to `main`.** The persistence and access-control defects identified in R1 are fixed and **tested locally**; the critical dependency exposure is **resolved and verified**. But authentication has only been tested against a **mock identity provider** (no Supabase project exists to test against, and no sign-in flow exists), the Supabase persistence path is untouched and still has a defective draft, and the hosting model is unresolved. These are blockers, not polish (§8).

Classification used throughout:
- **VERIFIED** — directly observed in this session by a command whose output is stored in `evidence/`.
- **TESTED LOCALLY** — passes automated tests in local/disposable/mock conditions; says nothing about production, real Supabase, or real posters.
- **IMPLEMENTED, NOT VERIFIED** — code exists; no test proves it.
- **BLOCKED** — cannot proceed without an authorization or external dependency.
- **NOT STARTED**.

Nothing in this report is "VERIFIED" against a real Supabase project, a deployed environment, or real-world poster data.

## 1. Scope and boundaries kept
Authorized work only: local code, disposable local databases, local installs, tests, docs, pushes to the AP-001 branch. **Not done (by instruction):** no migration applied, no Supabase write or restore, no credential created/rotated/disclosed, no deployment (preview or production), no external contact, no merge, no branch-protection change, no delegation to Zuberi (identity/permissions still unverified), no change to `main`, `alagbara-core`, `power-enterprise-control-room`, `escape-app`, `alagbara` (each: 0 local changes — VERIFIED).
Step 8 diff inspection: secret-pattern scan of all added lines in both repos — 0 hits; no `radar-data`, `.sqlite3`, `.env`, `.bak` files tracked — VERIFIED.

## 2. Before / after defect register

| ID | Defect (from R1 audit) | Before | After | Status |
|---|---|---|---|---|
| C1 | Stale read-modify-write erased a human approval | Reproduced: final `pending` after an approval | Stale writes raise `StaleWrite`; approvals never silently lost; state+decision+audit atomic | **TESTED LOCALLY** (27 tests; both interleavings deterministic) |
| C2 | Radar pages/media public, unreviewed data + contacts exposed | All `/radar*` and `/api/radar/media` returned 200 unauthenticated | Default deny: 401 without credentials, 404/403 without reviewer role; media reviewer-only | **TESTED LOCALLY** (83-case matrix, mock IdP) |
| C3 | `next@14.2.35` critical advisories | `npm audit`: 1 critical, 2 high (30 advisory entries) | `next@16.4.5`; `npm audit` and `--omit=dev`: **0 vulnerabilities** | **VERIFIED** (`evidence/02`, `05`) |
| M1 | Shared review token; reviewer name self-asserted | Token + free-text reviewer | Token path **removed**; reviewer = server-validated session id; role from `app_metadata` | **TESTED LOCALLY** against mock; real Supabase Auth **BLOCKED** (§8) |
| — | No replay protection / client decision id | Server generated id per POST | Client `decisionId`, exclusive-create files, replay returns original outcome, id reuse with other payload → 409 | **TESTED LOCALLY** |
| — | Decision applied without version check | None | `version_seen` required; stale → rejected once, one audit row | **TESTED LOCALLY** |
| — | Feed export could leave a truncated file | `write_text` in place | write-temp, fsync, atomic rename; crash keeps previous feed | **TESTED LOCALLY** |
| — | Malformed feed masked as "no feed" | Any error → null | `missing` vs `invalid` distinguished, logged, nothing shown on invalid; decisions refused (503) | **TESTED LOCALLY** |
| — | No logging on Radar | 0 log calls | Structured denial/decision/feed-error logs (no tokens, no PII) | **IMPLEMENTED, NOT VERIFIED** (emission not asserted by tests) |
| H1 | Draft Supabase migration defective (3 bugs) | Draft in repo | **Unchanged.** Corrected SQL exists only in the R1 audit (verified on scratch Postgres). Not placed in `migrations/` (migrations not authorized) | **BLOCKED** |
| H2/H3 | `main` intake endpoint: CORS `*`, no auth/rate limit; anon policies in `migration.sql` | Present | Untouched (outside AP-001 scope) | **NOT STARTED** |
| H4 | No Supabase target; security branch unapplied | Same | Same | **BLOCKED** |
| M2 | File-based feed/decisions/media not serverless-compatible | Same | Same | **BLOCKED** (hosting undecided) |
| M3 | No security headers | Same | Radar paths now send `no-store`, `noindex`, `nosniff` (proxy); media sends CSP `sandbox`. Site-wide headers **not** added | **TESTED LOCALLY** (Radar only) |
| L1 | Anonymous `submissions` insert | Same | Untouched | **NOT STARTED** |

### Defects found *during* R2 by the new tests (all fixed, regression-covered)
1. `auth provider down` classified as 401 "invalid credentials" (network failure surfaces as status `0`) → now 503 fail-closed. *Found by the access matrix.*
2. Review API checked staleness **before** replay: a retried, already-recorded decision returned 409. → replay check first. *Found by cross-repo e2e (E10).*
3. Stale decision files re-rejected (new audit row) on every `apply-decisions` run → rejections keyed by `decision_id`, recorded once.
4. `NEXT_PUBLIC_*` env vars are inlined at **build** time even in server code → a runtime-configured deployment would read "not configured" (denies, safe, but confusing). Server-only `SUPABASE_URL`/`SUPABASE_ANON_KEY` are read at runtime; documented in `.env.example`.
5. Test harness `child.kill()` left stale servers (including a leftover Next 14 server) causing a hang → harness spawns Node directly in its own process group (VERIFIED: 0 stray processes afterwards).

## 3. Files and components changed

**alagbara-intelligence** — `5 files, +590/−100` since R1 baseline `9b993db` (all under `scout-intelligence-fabric/`):
`src/ana_engine/store.py` (versioning, transactions, decisions table, idempotent apply, local migration+backup), `pipeline.py` (atomic ingest transaction; reopen only on new contradiction), `cli.py` (decision id / expected version flags; atomic export), `tests/test_zr01_integrity.py` (new, 27 tests), `tests/test_radar_flow.py` (**one existing test updated**: decision rows now require ≥8-char `decision_id` and `version_seen` — a deliberate contract change, reported openly).
Commits: `0b28cbb` (ZR-01), `b289d51` (ZR-04 Python side), plus the docs commit for this report.

**pulse-l1** — `30 files, +1414/−216` since `6036ff3`:
- *Dependency/framework (ZR-03, `cb8c33b`)*: `package.json`, `package-lock.json`, `tsconfig.json` and `next-env.d.ts` (auto-adjusted by Next 16: `jsx: react-jsx`), `.nvmrc`, `engines`; **async `params`/`searchParams` migration in 7 existing files** (consumer pages `[city]`, `event/[id]`, `creator/[id]`, `venue/[id]`; routes `rsvp/[eventId]`, `save/[eventId]`, `events/[id]`) — the only edits to non-AP-001 code, mechanical, status codes unchanged (14/14 routes).
- *Access control (ZR-02, `7d1ff6c`)*: new `proxy.ts`, `lib/radar/auth.ts`, `lib/radar/access.ts`; rewritten `lib/radar/decisions.ts`, `lib/radar/feed.ts`, `app/api/radar/review/route.ts`, `app/api/radar/media/[name]/route.ts`; all `app/radar/**` pages route data through `pageAccess`; `.env.example`; `scripts/radar/mock-auth.mjs`, `access-test.mjs`.
- *Integration (ZR-04, `bd8c345`)*: `scripts/radar/e2e-integration.mjs`, review-API replay ordering.
Removed: `RADAR_REVIEW_TOKEN`, `x-review-token`, `RADAR_DECISIONS_PATH` (replaced by `RADAR_DECISIONS_DIR`).

## 4. Test commands and actual outputs (stored in `docs/ap-001/evidence/`)

| Command | Result (actual) | Class |
|---|---|---|
| `pytest -v` (scout-intelligence-fabric) | `63 passed` (5 baseline SCOUT + 13 contracts + 18 flow + 27 ZR-01); list in `evidence/06` | TESTED LOCALLY |
| `rm -rf node_modules .next && npm ci` (pulse-l1) | `added 133 packages in 9s` | VERIFIED |
| `npm run typecheck` | exit 0 | VERIFIED |
| `npm run build` | `Next.js 16.4.5 (Turbopack)` · `✓ Compiled` · `Finished TypeScript` · `✓ Generating static pages (16/16)`; **warning: "React 18 support is deprecated in Next.js 16 and will be removed in Next.js 17"** | VERIFIED |
| `npm audit` / `npm audit --omit=dev` | `found 0 vulnerabilities` / `found 0 vulnerabilities` | VERIFIED |
| `npm run test:radar-access` | `83/83 passed` (mock IdP) — `evidence/03` | TESTED LOCALLY |
| `RADAR_CLI=… npm run test:radar-e2e` | `24/24 passed` — `evidence/04` | TESTED LOCALLY |
| Existing 14 non-radar routes, status before (Next 14) vs after (Next 16) | identical (`/`307, `/lagos`500, `/api/events`400, `/content`200 …); 500/501s are the pre-existing no-database behavior | VERIFIED (baseline captured pre-change; re-checked inside the matrix) |

Reproduce: `cd alagbara-intelligence/scout-intelligence-fabric && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]" && pytest -v`; then `cd pulse-l1 && npm ci && npm run build && npm run test:radar-access && RADAR_CLI=<venv>/bin/radar npm run test:radar-e2e`.

## 5. Dependency audit before and after

| | Before (`next@14.2.35`, lock at `6036ff3`) | After (`next@16.4.5`) |
|---|---|---|
| `npm audit --omit=dev` | **1 critical, 2 high** (30 advisory entries: next, postcss, source-map-js) | **0** |
| `npm audit` (incl. dev) | same 3 + (dev) | **0** (1 moderate `postcss-selector-parser` cleared by lockfile-only `npm audit fix`) |
| next / react / postcss / source-map-js | 14.2.35 / 18.3.1 / bundled 8.4.x / <1.2.2 | 16.4.5 / 18.3.1 / 8.5.26 / 1.2.2 |

Upgrade-path evidence (scratch lockfile-only trials, VERIFIED): `next@15.5.29` leaves the PostCSS **highs** (critical→moderate only); only `16.4.5` clears them. Next 16 declares React `^18.2||^19`, so **no React 19 migration was needed** — but Next 16 now warns React 18 is deprecated (§8).
Breaking changes absorbed: async `params`/`searchParams` (11 files); `next lint` removed (script was already non-functional — no ESLint config — replaced by `typecheck`); Node ≥ 20.9 (`engines`, `.nvmrc 22`); Turbopack is the default bundler (build verified); `middleware`→`proxy` naming adopted; tsconfig `jsx` rewritten by Next. Prisma 5.22 client works on the build (build only; **runtime DB behavior not tested — no database**).

## 6. Authentication and authorization test matrix (83 cases; full table `evidence/03`)

Identity provider: **local mock** of Supabase `GET /auth/v1/user` (`scripts/radar/mock-auth.mjs`). **TESTED LOCALLY**; not verified against real Supabase Auth.

| Actor / condition | Pages (`/radar*`) | Media | Review POST | Cases |
|---|---|---|---|---|
| No credentials | 401, no data | 401 | 401, nothing recorded | 7/7 |
| Invalid/unknown token | 404, no data | 401 | 401 | 7/7 |
| Authenticated, no role | 404 | 403 | 403, nothing recorded | 5/5 |
| Role only in `user_metadata` (user-editable) | 404 | 403 | 403 | 5/5 |
| Email unconfirmed | 404 | 403 | 403 | 5/5 |
| Unknown role value | 404 | 403 | 403 | 5/5 |
| Forged `x-radar-*`, `x-review-token`, body `reviewer`; `x-middleware-subrequest` bypass header | denied (401/404), no data | — | 401, nothing recorded | 3/3 |
| Reviewer / admin (bearer) | 200, data shown | 200, bytes identical, `no-store` | 200 | 6/6 + decisions |
| Cookie session (Supabase cookie name) | reviewer 200 / non-reviewer 404 | — | — | 2/2 |
| Media policy | — | referenced file 200; **file on disk but not in any event 404**; traversal 404; unknown hash 404 | — | 4/4 |
| Decision rules | — | — | recorded under session id (body `reviewer` ignored); replay → duplicate; id reuse (other decision / other reviewer) → 409; stale → 409; unknown event → 404; bad id/decision/JSON → 400; cross-site Origin / `Sec-Fetch-Site` → 403 | 11/11 |
| Auth **unconfigured** (even with a token the mock accepts) | 404 | 503 | 503, nothing recorded | 4/4 |
| Identity provider **down** | 404 | 503 (fail closed) | — | 2/2 |
| Static guarantees | every `loadFeed()` caller authenticates first; no shared token string anywhere; no service-role reference in Radar code | | | 3/3 |
| Non-radar routes unchanged | 14 baseline status codes identical | | | 14/14 |

**Not proven by this matrix:** real Supabase Auth behavior (token refresh, cookie chunking/format across `@supabase/ssr` versions, JWT expiry/revocation latency), a sign-in flow, MFA, reviewer provisioning, rate limiting of the Radar endpoints, behind-proxy `Host`/`Origin` handling in a real deployment, "unauthorized **activation**" (no activation feature exists — **NOT STARTED**, WP-06).

## 7. Persistence and idempotency results (`evidence/01`, `06`)
All **TESTED LOCALLY** (SQLite, threads against one file, one machine):
- Original defect reproduced as a test: two writers, stale write → `StaleWrite`, approval and version intact.
- `put_event` without a version cannot overwrite; stale review rejected and writes nothing (no decision row, no audit row).
- **Concurrency, 12 randomized-start races** (ingest vs approve) + **1 deterministic opposite interleaving** (ingestion holds the write lock; reviewer's approval is made stale): invariants hold every time — ingestion always lands; approval is either applied-and-in-history or rejected as stale; if later reopened it is an explicit system transition in history; final state equals last history row; exactly one audit row per applied human decision. *Honest note:* in my 60-run sampling the thread race always resolved "approval first" (ingestion is slower); the other order is covered by the deterministic test, not by chance.
- Corroborating evidence keeps approval; conflicting evidence reopens explicitly with history.
- Replay (3×, even with an outdated version) → `duplicate`, version/audit/decision counts unchanged; id reuse with different payload → `DecisionConflict`; invalid id/decision/reviewer/unknown event write nothing.
- Directory apply: replay of whole directory → no new effect; stale/invalid/ghost/no-version rows rejected, counted, audited **once**.
- Atomic ingest: injected crash mid-ingest rolls back venues, parties, events, links and audit; re-run recovers to exactly one event.
- Local migration: pre-ZR-01 DB gets a consistent backup (`radar.sqlite3.pre-zr01.bak`), versions backfilled to 1, old-style writers still run (events table unchanged), second open adds no backup.
- Atomic feed export: simulated crash before rename leaves the previous complete feed, no temp file left.
- Cross-repo e2e (24 checks): duplicates → one canonical event / two observations; contradictory time preserved (3 start-time claims, both values), version bumped, conflict visible in PULSE; missing date stays unknown ("Date unknown" tab only); stale decision rejected on **both** sides; fresh decision applied once and shown **Approved**; duplicate decision → no new audit rows; invalid reviewers rejected; missing media → 404 + event page still renders; truncated feed → explicit error, no data, decisions refused, recovery after re-export; half-written decision file rejected, applied after completion; decision history/audit consistent for every event.
- **Not claimed:** accuracy of extraction on real posters (all fixtures synthetic), multi-host or network-filesystem concurrency, Supabase persistence (AT-13 still pending), load/performance.

## 8. Remaining blockers and risks

| # | Item | Class |
|---|---|---|
| B1 | **Real authentication does not exist**: no designated Supabase project, no sign-in UI, no reviewer provisioning. Today nobody can sign in, so the surface is *safely unusable* outside tests. | BLOCKED |
| B2 | Supabase persistence (AT-13): draft migration still has the 3 R1 bugs; security-branch migrations unreconciled/unapplied; no branch DB created. | BLOCKED (reserved action) |
| B3 | Hosting model: feed/media/decisions are local files; serverless is incompatible; decision files are not cryptographically authenticated (rely on 0600 FS permissions and host trust). | BLOCKED |
| B4 | **React 18 deprecated by Next 16** ("removed in Next.js 17"): React 19 migration is a pending, untested upgrade. | NOT STARTED |
| B5 | `main`'s public intake endpoint (CORS `*`, no auth/rate limit, calls OpenAI) and anon policies in `migration.sql` untouched. | NOT STARTED |
| R1 | Radar logging/headers implemented but not asserted by tests; no rate limiting on Radar endpoints; the auth check makes one Auth-server call per request (latency/cost, no cache). | IMPLEMENTED, NOT VERIFIED |
| R2 | Mock IdP fidelity: the mock encodes my reading of Supabase's `/auth/v1/user` contract; a real server may differ (error shapes, cookie format). | UNVERIFIED |
| R3 | Extraction accuracy unmeasured; personal-data (poster phone numbers) legal basis unreviewed. | NOT STARTED |
| R4 | Zuberi identity and effective repo permissions still unverified; no delegation occurred. | BLOCKED |
| R5 | Prisma runtime behavior on Next 16 untested (no DB); only the build is verified. | NOT STARTED |
| R6 | Contract change: old JSONL decision rows (short ids, no `version_seen`) no longer apply — intended, but any such local files must be regenerated. | VERIFIED (by test) |

## 9. Rollback instructions (nothing was deployed, so there is no environment to roll back)

**alagbara-intelligence** (`scout-intelligence-fabric`):
1. Code: `git revert b289d51 0b28cbb` (newest first) on the AP-001 branch, or `git checkout 9b993db -- scout-intelligence-fabric/src scout-intelligence-fabric/tests`.
2. Data: any local `radar.sqlite3` opened by the new code gains tables (`event_versions`, `decisions`, `decision_rejections`) and keeps the `events` table unchanged, so old code still runs (without the version guard). To return to the exact pre-migration state restore `radar.sqlite3.pre-zr01.bak` (created automatically on first open of a pre-ZR-01 DB; consistent copy via SQLite backup API). New databases need no rollback.
3. Old decision files in PULSE's former JSONL format must be regenerated under the new rules.

**pulse-l1**:
1. Newest first: `git revert bd8c345 7d1ff6c cb8c33b`. Reverting `cb8c33b` restores `next@14.2.35` and **reintroduces the critical advisories** — do not do this on any reachable host.
2. After reverting: `rm -rf node_modules .next && npm ci`. Revert restores `lint` script and removes `engines`/`.nvmrc`.
3. Reverting `7d1ff6c` re-opens the unauthenticated Radar surface (R1 state). Prefer disabling `/radar` over reverting.
4. Env: removed `RADAR_REVIEW_TOKEN`, `RADAR_DECISIONS_PATH`; added `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `RADAR_DECISIONS_DIR` (anon key only; never service-role).

## 10. Definition-of-done check

| Criterion | Result |
|---|---|
| Stale ingestion cannot erase human approval | **TESTED LOCALLY** (§7) |
| Decisions are idempotent | **TESTED LOCALLY** |
| Unauthorized Radar/media access denied | **TESTED LOCALLY** (mock IdP) |
| Dependency exposure resolved or bounded | **VERIFIED** resolved (0 vulnerabilities); React 18 deprecation bounded as B4 |
| Existing regression tests pass | **VERIFIED**: 5 baseline SCOUT + 31 R0/R1 tests pass (one of the 36 updated, disclosed); 14 non-radar routes identical |
| New tests reproduce/prevent defects | **TESTED LOCALLY**: 27 + 83 + 24 |
| Production builds and static checks pass | **VERIFIED** (`npm ci`, typecheck, build) |
| Committed on authorized branch | **VERIFIED** (pushed; `main` untouched) |
| Reproducible evidence report | this document + `docs/ap-001/evidence/` |

**Not met, by design or dependency:** real authentication (B1), Supabase persistence (B2), deployment readiness (B3). Hence **HOLD**.

## 11. Recommended next authorizations (for Sovereign review)
1. Designate a Supabase project and authorize an **isolated branch database**; then run the corrected persistence design and the RLS matrix there (unblocks B2, and the real-Auth tests for B1).
2. Authorize building the **sign-in flow and reviewer provisioning** (Supabase Auth, admin-set `app_metadata.radar_role`) against that branch — then re-run `test:radar-access` against the real provider instead of the mock.
3. Decide the hosting model (stateful host vs Supabase-backed storage) before any preview deployment.
4. Authorize a **React 19 compatibility spike** (B4).
5. Keep outreach, pricing and deployment on hold until the above.
