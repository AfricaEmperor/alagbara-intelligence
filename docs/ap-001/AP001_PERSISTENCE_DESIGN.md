# AP001_PERSISTENCE_DESIGN

Operation AP-001-R1 · Track A2 · AUDIT ONLY · 2026-11-05
Question: can the SQLite store (`ana_engine/store.py`) and a Supabase model coexist without data loss?
**Answer: yes, provided SQLite is demoted to a local cache/dev store, the Python worker is the single writer of intelligence tables, human decisions are append-only, and three verified defects are fixed first.** Legend: [V] verified, [I] inferred, [U] unverified.

## 1. Current identifiers (as implemented)

| Entity | ID scheme | Stable? |
|---|---|---|
| Evidence / observation | `sha256(source_id + "\n" + content_hash)` [V code `intake.py`] | Yes. Same bytes via two sources = two observations (intended); same bytes, same source = one (AT-09 test). |
| Event | Dated: `evt_` + sha1(norm_title\|date\|Cotonou)[:12]; undated: `evt_` + sha1(observation_id)[:12] [V `pipeline.py`] | Id is kept for life once assigned (merges attach to the existing id). 48-bit id: collision risk negligible at this scale [I]. |
| Venue | `ven_` + sha1(norm_name\|Cotonou)[:12] | Name-derived: a renamed venue becomes a new id; aliases exist but are never auto-created [I]. Fuzzy near-matches create a *new* `candidate` venue pointing at the old one (no auto-merge) [V test]. |
| Party | `<role3>_` + sha1(role\|name\|event_id) | Deliberately **per event**: same stage name ≠ same person; `possible_same_as` links for review [V test]. |
| Review decision | none in SQLite: only `audit` rows + overwritten `review_status` | **Gap**: decision not an entity. |

## 2. Observed behaviour relevant to persistence

- **Idempotency** [V]: re-ingesting identical bytes returns the same observation, creates no second evidence/event/party (test `test_at09…`). `obs_event` maps each observation to one event.
- **Conflict preservation** [V]: merged observations append `FieldClaim`s; `contradictions` recomputed from claims; nothing overwritten (test `test_at08_at10…`).
- **Reopen on new evidence** [V]: approved/rejected events return to `pending` when a new observation merges (audited).
- **Decision application** [V]: `apply-decisions` is idempotent by `decision_id`; malformed/anonymous rows rejected and audited.

## 3. Defects that would cause data loss in any coexistence

1. **Lost update** [V repro, AP001_SECURITY_AUDIT F3]: `put_event` = `INSERT OR REPLACE` from a stale read. A concurrent merge can erase an approval (or vice-versa). Fix: `version` column + conditional `UPDATE`; on conflict, re-read and re-merge claims (claims are a set-union so merge is commutative).
2. **Dual source of truth** [V on draft SQL]: `review_status` stored as column and inside the JSON doc. Fix: generate the column from the doc (verified) or drop one.
3. **Decisions are not first-class** [V]: only a mutable status + audit log. Fix: append-only `radar_decisions(decision_id PK, event_id, reviewer, decision, at, version_seen)`; `review_status` = fold of decisions (latest wins) — preserves history if status is later corrupted.
4. **Media is local-only** [V]: content-addressed files in `radar-data/media/`; Supabase would store only `raw_media_reference`. Fix: private storage bucket keyed by sha256, upload-then-verify hash, DB row references bucket path; never public.
5. **No SQLite backup/integrity step** [V code]; WAL not enabled.

## 4. Proposed model (Supabase) — mapping, not an applied schema

| SQLite | Supabase | Mutability |
|---|---|---|
| `evidence` | `radar_evidence` (PK `observation_id`), media in private bucket | **Immutable** (insert-only; unique on observation_id) |
| `events` | `radar_events` (PK `event_id`, `version`, doc) | Mutable via worker with version check |
| `venues`, `parties` | `radar_venues`, `radar_parties` | Mutable via worker; candidate links preserved |
| `obs_event` | `radar_obs_event` | Insert-only |
| `audit` | `radar_audit` | Append-only |
| decisions (new) | `radar_decisions` | Append-only; unique `decision_id` |
| `failures` | `radar_failures` | Append-only |

Ownership: **only the worker (service role, server-side) writes evidence/events/venues/parties**; **reviewers write only through `radar_review_event()`** (SQL verified in AP001_SECURITY_AUDIT §6). PULSE reads through RLS-scoped views, never the service role.

## 5. Synchronization and recovery strategy

1. **Authority:** during pilot, SQLite remains the dev/offline store; Supabase becomes system of record only after Gate 3. Never two writers of the same event: pick one per environment.
2. **One-way, idempotent backfill SQLite → Supabase:** upsert evidence by `observation_id` (insert-if-absent, then compare `content_hash`; mismatch = halt and alert, never overwrite); events by `event_id` with version check; decisions by `decision_id`. Re-running the backfill must be a no-op (test with the existing AT-09 style fixtures).
3. **Round-trip check:** after backfill, export feed from both stores and diff canonical JSON (events, claims, contradictions, evidence hashes). Zero diff is the acceptance criterion for "no data loss".
4. **Conflict policy:** claims union; contradictions recomputed; status = fold of decisions; new conflicting evidence reopens review (already implemented).
5. **Recovery:** nightly hash-verified export of evidence + decisions (append-only tables) to separate storage; events and venues are *rebuildable* from evidence + decisions by replaying the pipeline (deterministic given pinned `extraction_version` — to be tested; currently [I]).
6. **Versioning:** record `extraction_version` on every claim set; re-extraction creates new claims, never edits old ones.
7. **Rollback:** forward-only migrations with reviewed paired rollback; rehearse on a branch DB.

## 6. Acceptance tests proposed for the persistence work package (none run on Supabase yet)
- P1 backfill twice → second run reports 0 changes.
- P2 concurrent approve + merge → both survive (decision present, claims merged) or one is rejected with `stale version`.
- P3 evidence hash mismatch on upsert → halted, no overwrite.
- P4 feed parity SQLite vs Supabase = zero diff.
- P5 reviewer RLS matrix (anon / non-reviewer / reviewer / admin / service_role) on every radar table.
- P6 delete-and-rebuild events from evidence + decisions reproduces the same canonical feed.

## 7. Verdict
Coexistence is **feasible and low-risk if sequenced**: fix C1/H1 first (local, no DB needed), prove P1–P6 on a disposable DB, then on a branch DB. Without the fixes, a migration would convert a latent local bug into silent production data loss.

---
## R3 update (2026-11-05) — what changed since this design was written

The R1 design above is superseded where it conflicts with the following. Full detail and evidence: `AP001_R3_READINESS_REPORT.md` §3, §5–§7.

| R1 statement | R3 status |
|---|---|
| "Mutable events need a version check" | **Done in SQLite** (R2) and **in the corrected migration** (`events.version`, `upsert_event`, `review_event` with row lock) — TESTED LOCALLY |
| "Decisions are an append-only entity" | **Done** both sides; `decision_id` PK; replay = no-op; id reuse with different payload rejected — TESTED LOCALLY, behaviorally identical on SQLite and PostgreSQL (parity test) |
| "`review_status` single source of truth" | **Done**: generated column of the JSON document |
| "Reviewer table `radar_reviewers`" | **Dropped**: reviewer = Auth user with server-side `app_metadata.radar_role`, checked live against `auth.users` (one source of truth) |
| "Backfill idempotent, hash-checked, diffed" | **Implemented** (`ana_engine/pg_sync.py`, CLI `pg-backfill-sql` / `pg-reconcile`) and TESTED LOCALLY against a disposable PG 16: zero-difference reconciliation, idempotent re-run, divergence detection, conflict abort without overwrite, interrupted-run recovery |
| "Media in a private storage bucket" | **NOT STARTED** (hashes reconcile; bytes do not) |
| "Rebuild events from evidence + decisions" (test P6) | **NOT STARTED** |
| Audit on SQLite had no natural key | `legacy_sqlite_id` added to `radar.audit` / `radar.failures` for idempotent backfill |
| Open question: SQLite store took the write lock on every open | **Fixed** (R3): a deadlock the tests found; now writes only when a migration is needed |

Not covered by reconciliation (so not claimed): `failures`, `decision_rejections`, legacy `applied_decisions`, media bytes, ingestion-path equivalence (`upsert_event` vs SQLite pipeline), cross-store concurrency, volume. Nothing has run on Supabase.
