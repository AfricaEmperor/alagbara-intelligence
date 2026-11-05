# AP001_SECURITY_AUDIT

Operation AP-001-R1 · Track A1 · Authority: AUDIT ONLY · Date: 2026-11-05
Audited: `alagbara-intelligence` @ `2e91fb2`, `pulse-l1` @ `6036ff3` (branch `claude/ap-001-cotonou-event-venue-radar-kr48v6`), security branch `origin/fix/security-boundary-v0.1`.
**No migration was applied to any Supabase project. No RLS, credential or permission was changed. No repo file was modified by this audit other than adding these documents.**

Legend: **[V]** verified by reproducible observation (method given) · **[I]** inferred · **[U]** unverified assumption.

## 1. Scope of what could and could not be inspected

| Item | Status |
|---|---|
| Live Supabase org: 6 projects listed (read-only `list_projects`) | [V] |
| `ALAGBARA Development` (`pvpaxhaflkdvcxghpndz`, ACTIVE): tables, migrations, security advisors, branches | [V] read-only |
| `alagbara-intelligence` (`hbcxiyyuqgjokvypqrqr`) and `pulse-production` (`iefjpxhcyvbkerkiiuzd`): **INACTIVE (paused)** | [V] status. Contents, grants, policies, storage: **[U] — not inspected.** Inspecting would require `restore_project`, a state change outside this authority. |
| Which project AP-001 is meant to use | **[U]** No repo pins a project ref (`.env.example` holds placeholders only; grep of both repos found no ref, key or JWT). |
| Effective permissions of the production data plane | **[U]** (paused projects) |

## 2. Verified facts

**F1 [V] — The only active project holds an unrelated domain.** `ALAGBARA Development` contains 7 `public.world_*` tables (Abuja world model; 2/14/15/14 rows in four of them) and 4 migrations (20261104…). It has **no radar, intelligence-request or PULSE tables**, no storage buckets (`storage.buckets` = 0 rows), **0 preview branches**, and **0 security-advisor lints**. All 15 tables show RLS enabled. → There is currently no Supabase target for AP-001; an isolated branch database does not yet exist (creating one is a reserved action).

**F2 [V] — AP-001 draft migration is defective (3 bugs), proven on a disposable local Postgres 16** (not Supabase; roles `anon/authenticated/service_role` and `auth.uid()` stubbed; default privileges mimic Supabase's grant-all-then-RLS model). Method: apply `20261105000000_ap001_event_radar.sql.DRAFT`, then `SET ROLE` probes.
- **B1 – reviewers cannot read anything.** A user present in `radar_reviewers` sees **0** rows of `radar_events`. Cause: policies test `exists(select … from radar_reviewers)`, and `radar_reviewers` has RLS enabled with no policy, so the subquery returns nothing under the caller's role. *Fails closed (safe) but the feature is dead.*
- **B2 – split source of truth.** `radar_review_event()` updates the `review_status` column only; after approving, column = `approved`, `doc->>'review_status'` = `pending`. Anything reading the JSON document (the export feed does) shows the wrong state.
- **B3 – no replay protection.** Calling the same approval twice writes 2 audit rows.
- Correct behaviours also verified: `anon` sees 0 rows and gets `permission denied` on the RPC; a non-reviewer authenticated user is rejected (`not a reviewer`); direct `UPDATE`/`INSERT` by `authenticated` is blocked by RLS (status unchanged).
- **Corrected design verified on the same scratch DB:** `SECURITY DEFINER is_reviewer()` helper used by policies (reviewer reads 1 row, non-reviewer 0, anon 0); `review_status` generated from the document (column = doc = `approved`); `decision_id` primary key makes replay a no-op (1 decision row after 2 calls); `version` check rejects a stale write (`stale version…`). SQL kept in §6 below. It has **not** been placed in the migrations folder.

**F3 [V] — A human approval can be silently overwritten (data-integrity, Critical).** Two `RadarStore` instances read the same event; one commits `approved`; the other commits an unrelated merge from its stale read. Final state: `pending`. Cause: read-modify-write with `INSERT OR REPLACE`, no transaction or version check (`ana_engine/store.py` `put_event`, `pipeline.process_evidence`). Reproduced by script (output: `review_status after both writes: pending`).

**F4 [V] — Public, unauthenticated radar surface in PULSE.** `/radar`, `/radar/review`, `/radar/event/[id]`, `/radar/venues*`, `/api/radar/media/[name]` return 200 with no credential (curl, local production build). They render **unreviewed, machine-extracted** data (labelled "Awaiting review"), source hashes, and public contact phone numbers taken from posters. If deployed as-is, this publishes unreviewed information, contrary to the AP-001 rule against publishing as verified without review (the UI labels state, but the data is public).

**F5 [V] — Main-branch `intelligence-request` endpoint (existing, not AP-001) is publicly callable and wide open.** `app/api/intelligence-request/route.js` on `main`: `Access-Control-Allow-Origin: *` (line 161); POST needs no auth and calls OpenAI (`OPENAI_API_KEY`) and Supabase with the **anon/publishable** key (lines 55–61). The security branch's own review pack states there is no verified rate limiter and no disposable-DB test.

**F6 [V] — Main `supabase/migration.sql` grants anon broad access:** policy `anon can read cases … using (true)` and `anon can insert field observations … with check (true)`. (File content; whether applied to a live project: [U].)

**F7 [V] — Security branch is not applied and not tested against a database.** `20261009000000_security_boundary_v1.sql` revokes client execution on 6 privileged RPCs and moves them to `service_role`; the branch's `REMEDIATION_REVIEW.md` records "PROPOSED / NOT APPLIED", 15 recovered baseline migrations unreplayed, multi-tenant ownership absent.

**F8 [V] — No secrets in the audited repos.** Regex scan for `*.supabase.co` refs, `service_role`, `sb_secret`, `eyJ…` in `alagbara-intelligence` and `pulse-l1` (excluding `node_modules`) found only `.env.example` placeholders and README guidance. (Main's route reads keys from env only; the hard-coded fallbacks described in the security pack were not found on `main`.)

**F9 [V] — Dependency vulnerabilities in PULSE.** `npm audit --omit=dev` on `pulse-l1`: 3 findings — **1 critical** (`next@14.2.35`, direct; ~25 advisories incl. unauthenticated RCE in Image Optimization for AVIF/SVG, server-function endpoint disclosure, DoS, cache poisoning; audit's fix is `next@16.4.5`, a breaking major), 2 high (transitive `postcss`, `source-map-js`). Applicability to our routes is [U] (we do not use `next/image` or rewrites in `/radar`); upgrade needs a compatibility test.

**F10 [V] — SQL policy design in PULSE `0001_l1_schema.sql`:** RLS enabled on 11 tables; public read of published rows; `users/saves/rsvps/shares` scoped by `auth.uid()`; `public submission insert with check (true)` (anonymous insert, no rate limit).

## 3. Inferred risks

- **I1 (high confidence)** PULSE's own RLS is not the effective boundary for its application path: the app uses Prisma over `DATABASE_URL`, which typically connects as an owner role that bypasses RLS. Authorization therefore lives in app code, where only dev-placeholder identity exists (`lib/session.ts`: cookie → `isTest` user).
- **I2** Prisma Postgres schema (`events.venueId` NOT NULL, `CurationStatus` etc.) differs from the radar contract (venue optional, evidence states). Direct reuse of PULSE tables for radar data would force invented values; keep radar tables separate.
- **I3** Local-filesystem feed/decisions/media (`radar-data/`) will not work on serverless hosting (ephemeral/read-only FS). PULSE's hosting target is [U]: no `vercel.json`/`.vercel` in `pulse-l1`; the security pack mentions a Vercel preview integration for the `alagbara-intelligence` repo only. `pulse-l1/README.md` itself says "Do not deploy as production-ready".
- **I4** Review token is a single shared secret with no rate limit or lockout → brute-force exposure once public.
- **I5** Personal data: posters carry phone numbers; the radar stores and displays them. Legal basis/retention under Benin's data-protection rules is **[U] — needs counsel**; not asserted here.
- **I6** `next.config.mjs` sets no security headers (CSP, frame, referrer) [V: file has only `reactStrictMode`]; impact is [I].

## 4. Unverified assumptions (explicit)
- U1 `pulse-production` / `alagbara-intelligence` projects' schema, grants, storage and RLS state.
- U2 Whether `supabase_migrations` ledger of those projects equals the 15 recovered files.
- U3 Backup/PITR availability per plan; rollback of any prior migration. No down-migrations exist in either repo [V: none found].
- U4 That `service_role` key handling is server-only in deployment (no deployment inspected).

## 5. Findings by severity

| # | Severity | Finding | Evidence |
|---|---|---|---|
| C1 | **Critical** | Human review decisions can be lost to stale writes | F3 repro |
| C2 | **Critical** | Radar pages (incl. unreviewed data, contacts) public if deployed | F4 |
| C3 | **Critical** | `next@14.2.35` critical advisories | F9 |
| H1 | High | Draft migration: reviewers locked out; status divergence; replay | F2 |
| H2 | High | Public AI-backed intake: CORS `*`, no auth, no rate limit (main) | F5 |
| H3 | High | Anonymous broad policies in `main/migration.sql` (applied state unknown) | F6 |
| H4 | High | No Supabase target; security migration unapplied/untested; 2 key projects paused | F1, F7, U1 |
| M1 | Medium | Shared review token, self-asserted reviewer name | AUTH audit |
| M2 | Medium | Serverless-incompatible file storage | I3 |
| M3 | Medium | No security headers; no request logging/rate-limit | I6 |
| L1 | Low | Anonymous `submissions` insert unthrottled | F10 |

## 6. Recommended corrective actions (none executed)

1. **Do not deploy** `/radar*` or `/api/radar/*` publicly until gated behind authenticated reviewers (see AP001_AUTHORIZATION_AUDIT). Public discovery view, if ever launched, must show **approved events only**, no evidence hashes, no extracted contacts.
2. Replace `INSERT OR REPLACE` with optimistic concurrency (`version` column; `UPDATE … WHERE version=?`), make `review_status` a single source of truth, and move decisions to an append-only table with unique `decision_id`.
3. Replace the draft migration with the verified design below; require disposable-DB tests (anon/authenticated/service_role matrix) before any apply.
4. Create an **isolated Supabase branch** from a project the Principal designates (F1: none today) — reserved action, needs Gate 3.
5. Reconcile `fix/security-boundary-v0.1` with that branch: replay 15 recovered migrations on a disposable DB, then apply the 16th; add rate limiting at the edge; remove wildcard CORS.
6. Upgrade `next` after a compatibility spike (major), `npm audit fix` for transitive; add `engines`/`.nvmrc`.
7. Add security headers, structured logging, and a health endpoint.
8. Counsel review of personal-data handling before any public deployment.

### Verified corrected SQL (scratch DB only; not committed to `supabase/migrations/`)
```sql
create table radar_reviewers(user_id uuid primary key references auth.users,
  role text not null check (role in ('reviewer','admin')));
create table radar_events(event_id text primary key, doc jsonb not null, version int not null default 1,
  review_status text generated always as (doc->>'review_status') stored);
create table radar_decisions(decision_id uuid primary key, event_id text not null,
  reviewer uuid not null, decision text not null, at timestamptz default now());
alter table radar_reviewers enable row level security;
alter table radar_events enable row level security;
alter table radar_decisions enable row level security;
create function is_reviewer() returns boolean language sql stable security definer
  set search_path = public as $$ select exists(select 1 from radar_reviewers where user_id = auth.uid()) $$;
revoke all on function is_reviewer() from public, anon; grant execute on function is_reviewer() to authenticated;
create policy r_read on radar_events for select to authenticated using (is_reviewer());
create policy d_read on radar_decisions for select to authenticated using (is_reviewer());
create function radar_review_event(p_decision_id uuid, p_event text, p_decision text, p_expected_version int)
returns void language plpgsql security definer set search_path = public as $$
declare s text := case p_decision when 'approve' then 'approved' when 'reject' then 'rejected'
                  when 'request_correction' then 'correction_requested' end;
begin
  if not is_reviewer() then raise exception 'not a reviewer'; end if;
  if s is null then raise exception 'invalid decision'; end if;
  if exists(select 1 from radar_decisions where decision_id = p_decision_id) then return; end if;
  update radar_events set doc = jsonb_set(doc,'{review_status}',to_jsonb(s)), version = version + 1
   where event_id = p_event and version = p_expected_version;
  if not found then raise exception 'stale version'; end if;
  insert into radar_decisions values (p_decision_id, p_event, auth.uid(), p_decision);
end $$;
revoke all on function radar_review_event(uuid,text,text,int) from public, anon;
grant execute on function radar_review_event(uuid,text,text,int) to authenticated;
```
Observed results of this design: reviewer reads 1 row; non-reviewer 0; anon 0; approve → column = doc = `approved`, version 2; replay → 1 decision row; stale version → rejected; non-reviewer RPC → rejected.
Not yet tested: evidence/venue/party tables, storage policies, `service_role` write path, role-based `admin` separation.

## 7. Rollback and recovery (current state)
No down-migrations exist (security-branch pack: "do not roll back by restoring anonymous RPC execution"). SQLite store has no backup, no WAL mode set, no integrity check [V: code]. PITR/backups for Supabase: [U]. Recommendation: forward-only migrations with a paired reviewed rollback script, branch-DB rehearsal, nightly export of evidence + decisions (append-only, hash-verified).

---
## R3 status of the R1 findings (2026-11-05)

| ID | R1 finding | R3 status | Class |
|---|---|---|---|
| C1 | Stale write erased an approval | Fixed in SQLite (R2) and in the migration design; concurrency proven with two real PostgreSQL sessions | TESTED LOCALLY |
| C2 | Radar public if deployed | Default deny + real Auth path (R3-B); 133-case matrix against a mock IdP | TESTED LOCALLY; real Auth BLOCKED |
| C3 | `next` critical advisories | `next@16.4.5`, `npm audit` 0 | VERIFIED |
| H1 | Draft migration defective | **Replaced by v2** (own schema, explicit grants, RLS, definer functions with empty `search_path`, live reviewer check, single-transaction review, replay/stale/exactly-one-row guards, generated status): 93 SQL tests, 2 concurrency tests, 9/9 mutants killed — **still unapplied** | TESTED LOCALLY; apply BLOCKED |
| H2/H3 | `main` intake endpoint; anon policies in `main/migration.sql` | Untouched (out of AP-001 scope) | NOT STARTED |
| H4 | No Supabase target | Re-inventoried: ALAGBARA Development is the only plausible candidate (0 auth users, unrelated Abuja data, wide default grants); **not designated** | BLOCKED |
| M1 | Shared review token | Removed (R2); individual reviewers via OTP (R3) | TESTED LOCALLY |
| M2 | File-based storage vs serverless | Unchanged | BLOCKED |
| M3 | Headers / logging | Radar: `no-store`, `noindex`, `nosniff`, CSP sandbox on media; structured denial logs; **site-wide headers not added** | TESTED LOCALLY (Radar only) |

New R3 facts established read-only on a live project (VERIFIED): `postgres` is not a superuser but has `BYPASSRLS`; `service_role` has `BYPASSRLS`; `anon`/`authenticated` do not; schema `public` auto-grants ALL privileges (incl. `TRUNCATE`) to `anon`/`authenticated`/`service_role`, a new schema does not; real `auth.uid()` reads `request.jwt.claims.sub` or the legacy claim.
