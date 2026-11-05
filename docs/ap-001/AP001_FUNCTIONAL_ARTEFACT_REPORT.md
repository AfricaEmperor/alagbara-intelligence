# AP001_FUNCTIONAL_ARTEFACT_REPORT

AP-001 Functional Artefact Sprint · 2026-11-05 · Branch `claude/ap-001-cotonou-event-venue-radar-kr48v6` (both repos)

## 0. Decision

**GO — for a local, supervised operating pilot** (one operator, one machine, authorized posters, results reviewed by a named person).
**HOLD — for any deployment, any use by third parties, and any claim about accuracy on real Cotonou posters.**

The artefact works end to end and is demonstrated; but it has only ever read **synthetic** posters, its sign-in has only been
exercised against a **mock** identity provider, and nothing has run on Supabase. Section 8 lists exactly what blocks more.

## 1. Branch and commits (VERIFIED: pushed, trees clean, `main` untouched in both repos)

| Repo | Base at sprint start | Sprint commits | Head |
|---|---|---|---|
| `alagbara-intelligence` | `ed5d934` (R3) | `829be25` curation core · `aa89d15` · `12559f8` ops · `b8fe413` operator console · `a1a8972` launcher/report/demo · `ed1cab8` docs | final head printed at the end of this sprint's hand-over message (this report is its last commit) |
| `pulse-l1` | `f9a53a3` (R3) | `cc90a96` Radar UX · `77708c3` demo + local IdP · `9c7a721` env audit classification, build warnings | `9c7a721` |

## 2. Run it (the documented command sequence; tested from a clean state)

```bash
cd alagbara-intelligence          # pulse-l1 checked out beside it, same branch
scripts/ap001.sh setup            # venv + deps + PULSE build + OCR check         (19 s measured)
scripts/ap001.sh up               # operator console :8750, PULSE :3000, LOCAL DEMO identity provider   (<1 s measured)
scripts/ap001.sh sample           # optional: 3 synthetic posters -> 3 events
# operator: http://127.0.0.1:8750/  (name + launch key printed by `up`)   PULSE: http://127.0.0.1:3000/radar
scripts/ap001.sh demo             # automated acceptance demonstration (46 checks, writes docs/ap-001/demo/)
scripts/ap001.sh test             # every regression suite
scripts/ap001.sh backup | verify | report | publish | status | down
```
Documentation: `OPERATOR_GUIDE.md` (workflow, backup, restore, feed recovery, troubleshooting), `REAL_DATA_ONBOARDING.md`
(30–50 authorized posters: rules, manifest, review routine, venue directory, measurement, done criteria),
`sample-data/README.md`. Environment template: PULSE `.env.example` (placeholders only). Sample data: `sample-data/` (synthetic).

## 3. What was built (by priority)

**P1 Operating system.** A local **operator console** (`radar serve`, stdlib only, loopback only): register/approve sources, upload
(image/video, permission note required), evidence inbox for posters OCR could not read, event review with the original poster beside
what ANA read, corrections, approve/reject/request-correction, venue directory, publish, backup/verify. No manual database operation is
needed anywhere in the workflow. **Real OCR** (Tesseract, French+English) is wired in; a typed transcription is the fallback and is
marked *unverified*.
**P2 Real data.** `ingest-manifest` (permission note mandatory per poster, one bad row never stops the batch, idempotent re-runs,
per-row report), provenance preserved per record (source, capture time, evidence hash, extraction, verification state, reviewer
decision, event identity, venue link), `radar report` measuring per-field read/wrong/filled rates **from reviewers' own corrections,
over reviewed events only**. Never fabricated: missing dates, prices, venues, organizers stay unknown (tested).
**P3 Venue intelligence.** Name, district, address, coordinates, category, official links (https, matching domain, own-page
confirmation), contacts (public only with a written authorization note), verification (needs a note), associated events, source
evidence, last observed activity; near-duplicate names become *candidates* (never auto-merged) with a merge that deletes nothing and
redirects future uploads; contract 1.1.0 (additive).
**P4 PULSE.** Event listing with source and review indicators, exact-date filter plus window/category/district/venue filters, event
detail with full provenance and per-field "how it was read", venue directory and detail, loading skeletons on list pages, error and
not-found states, mobile-first; non-Radar routes untouched.
**P5 Operability.** One launcher, environment template, sample data, operator guide, backup (consistent online backup + manifest),
restore (moves existing data aside, refuses damaged backups), feed recovery (rebuild from the database; atomic writes), integrity
check, automated regression suite.
**P6 Auth and persistence (R3, continued).** Unchanged boundaries: local PostgreSQL and mock identity only; no Supabase write,
migration, deployment or outreach. The R3 PostgreSQL suites and parity tests still pass.

## 4. Test results (actual; `docs/ap-001/evidence_sprint/S_01_full_regression_via_launcher.txt`, run through `scripts/ap001.sh test`, `exit=0`)

| Suite | Result | Class |
|---|---|---|
| Python: SCOUT, ANA, curation, operator console (HTTP), ops, PostgreSQL parity | **114 passed** | TESTED LOCALLY |
| PostgreSQL migration suite (disposable local PG16) + two-session concurrency | **93/93**, stale=1, same-id=1 | TESTED LOCALLY |
| Mutation check on the migration | **9/9 killed** | TESTED LOCALLY |
| PULSE `npm ci`, typecheck, production build | pass; `npm audit` **0 vulnerabilities**; one warning: React 18 deprecated by Next 16 | VERIFIED |
| PULSE access-control matrix (mock IdP) | **133/133** (includes 14 pre-existing non-Radar routes) | TESTED LOCALLY |
| Cross-repo end-to-end | **24/24** | TESTED LOCALLY |
| PULSE UI test (real Chromium, 390 px) | **47/47** | TESTED LOCALLY |
| Environment / secret-boundary audit | **13/13** | TESTED LOCALLY |
| **Acceptance demonstration** (`docs/ap-001/demo/demo-transcript.txt`) | **46/46** | TESTED LOCALLY |

## 5. Demonstration scenario (what the 46 checks prove, in order)

1. Operator console refuses unauthenticated access and a wrong key; the operator signs in with name + launch key.
2. A source is registered (pending); an upload from it is **rejected and stores nothing**; a named operator approves it.
3. **A poster is uploaded** (`p1_nuit_afro.png`) → **SCOUT preserves the evidence**: SHA-256 equals the file's hash, bytes retrievable
   identically, capture time, source, permission note and *unverified* state recorded.
4. **ANA extracts with real OCR**: venue *Club Exemple*, district *Haie Vive*, date 2026-11-28, 22:00–04:00 (overnight handled),
   organizer, performers, ticket, category. Title read as "NUIT AFRO" (the poster's second line "VOL. 3" was lost).
5. **The operator corrects the title** to "NUIT AFRO VOL. 3"; the original reading stays in the claim list; a double-submit is ignored.
6. **Approve → persisted**; the same decision replayed 3 times changes nothing: **1 event, 1 human decision, 1 review audit row**.
   A stale decision is refused and the approval stands. The integrity check passes.
7. **Publish**: the feed holds exactly the approved event, Africa/Porto-Novo times, evidence hash, permission note, the corrected field
   named, **no operator identity**.
8. **PULSE**: without credentials → redirect to sign-in, nothing leaks; media → 401; a signed-in non-reviewer → 404 and cannot even
   obtain a session; the reviewer signs in with a one-time code and sees the event with the **correct venue, date, indicators and
   provenance** (hash, source, permission note, "origin not verified", "Reviewed by a person", per-field provenance), opens the
   original poster (bytes identical), and sees a clear empty state for another date.
9. The 14 pre-existing PULSE routes return their pre-sprint status codes.
10. A forged (bad CSRF) or cross-site request cannot publish. Screenshots captured from **real browsers**: operator desktop, PULSE phone.

**Honest limit of the demonstration:** the brief asks for a *real* event poster. None is available in this environment and none may
be used without its owner's permission, so the demonstration uses a **synthetic, clearly fictional poster** rendered for the purpose
(`sample-data/posters/`). The pipeline is identical for a real poster; whether it reads real posters well is **unmeasured** and is
exactly what the onboarding procedure and `radar report` exist to measure.

## 6. Files changed (since R3)
**alagbara-intelligence** — 34 files, +3029/−24. New: `ana_engine/{curation, ops, operator_app, operator_routes}.py`,
`tests/{test_curation, test_ops, test_operator_app}.py`, `scripts/ap001.sh`, `sample-data/**`, `docs/ap-001/{OPERATOR_GUIDE,
REAL_DATA_ONBOARDING, AP001_FUNCTIONAL_ARTEFACT_REPORT}.md`, `docs/ap-001/{demo, evidence_sprint}/**`. Changed: `store.py`
(feed 1.1.0, corrections table), `pipeline.py` (human-resolved conflicts, merged-venue redirect), `extract.py` (French "X présente"
organizer, OCR 0/O repair in times, category priority), `models.py` (contract 1.1.0 venue fields and validators), `intake.py`
(source URL + permission metadata), `text_providers.py`, `cli.py`.
**pulse-l1** — 24 files, +681/−159. New: Radar route group `(app)` with gating layout, list/detail pages, `loading.tsx` (lists
only), `error.tsx`, `not-found.tsx`, `scripts/radar/{ui-test, demo, mock-auth-server}.mjs`. Changed: `Parts.tsx`, `lib/radar/{feed,
access}.ts`, `radar.css`, env-audit classification.

## 7. Defects found and fixed during the sprint (every one by a test, several only by a real browser)
| # | Defect | Found by | Fix |
|---|---|---|---|
| 1 | **Operator console answered some POSTs without reading the body; on a browser's keep-alive connection the next request was corrupted (501 on the very next page)** | **looking at a screenshot** (all 41 scripted checks had passed: the test client opened a new connection per request) | always drain the body first; new regression test, verified to fail on the old handler |
| 2 | **Browser login got 403**: my `Referrer-Policy: no-referrer` made browsers send `Origin: null`, which the same-origin check correctly refuses | real-browser sign-in in the demo | `Referrer-Policy: same-origin`; `Origin: null` still refused; test |
| 3 | Adding `loading.tsx` made denied Radar requests return **200** (stream started before the access check) | access matrix (25 failures) | gate moved to a route-group layout outside the loading boundary; loading only on list pages, so detail pages keep real 404s |
| 4 | Published feed leaked the operator identity (in evidence metadata) and private venue contacts/operator name (in the venue embedded in each event) | curation tests | single `public_venue` sanitizer; metadata `operator` stripped at export |
| 5 | Re-submitting a saved correction form showed an error | HTTP test | recorded `correction_id` recognised first |
| 6 | `Date.parse("2099-02-30")` silently rolls to March 2, so an impossible date filter was accepted | UI test | round-trip validation |
| 7 | Launcher: `up` never returned when its output was piped, and recorded the wrong PID | running it | `exec` in redirected subshells |
| 8 | Extractor: "X PRÉSENTE" organizer missed (my first regex matched "présentent"), `O4H` unread, "Brunch Live" classified as concert | OCR on a real image | fixed + tests |
| 9 | Four Turbopack whole-project tracing warnings | build output | opt-out on runtime-env paths |
Also found and *not* fixed because they are limits, not bugs: see §8.

## 8. Outstanding dependencies and risks (what still blocks more than a local pilot)
| # | Item | Class |
|---|---|---|
| B1 | **No real poster has been read.** Extraction quality on real Cotonou material is unmeasured; accuracy claims are forbidden until the 30–50-poster batch is reviewed | NOT STARTED (procedure + measurement ready) |
| B2 | Reviewer sign-in is **mock-tested only**; no Supabase project designated, no reviewer exists, Auth settings unread, nothing applied to Supabase (all R3 blockers stand) | BLOCKED |
| B3 | The operator console is a **local, single-operator tool**: self-declared name, per-launch key; not identity assurance and not multi-user | BY DESIGN |
| B4 | Corrections, venue contacts/links/merges, and the 1.1.0 fields exist **only in SQLite**; the PostgreSQL draft migration and parity tooling do not cover them yet (parity tests still pass for what they cover) | NOT STARTED |
| B5 | **Duplicate events with different titles are not detected** (sample: "NUIT AFRO" vs "NUIT AFRO VOL. 3"); there is no event-merge action, only reject | NOT STARTED |
| B6 | Hosting undecided; feed/media/decisions are local files; React 18 deprecated by Next 16 | BLOCKED / NOT STARTED |
| B7 | No speech-to-text for video; OCR weak on stylized/handwritten/Fon-only posters; dates without a year stay unknown by design | KNOWN LIMIT |
| B8 | Personal data on posters (phone numbers) and Benin data-protection obligations not legally reviewed; permission notes are free text and are shown to reviewers | NOT STARTED |
| B9 | Backups are local; no off-machine copy or schedule | OPERATOR TASK |
| B10 | Operator-console security (CSRF, Origin, escaping, lockout) is tested locally, not penetration-tested | IMPLEMENTED, NOT VERIFIED beyond tests |
| B11 | Zuberi identity/permissions still unverified; no delegation | BLOCKED |

## 9. Recommended next authorization
1. **Authorize the real-data batch**: 30–50 posters, each with a written permission note, reviewed by a named person, using `REAL_DATA_ONBOARDING.md`;
   decide by the quality report (§5 of that guide) whether extractor work is needed before scaling.
2. R3's items unchanged: designate an isolated Supabase target, authorize applying the draft migration there, authorize reviewer provisioning.
3. Authorize extending the PostgreSQL draft + parity tooling to corrections and venue operations (B4) and an event-merge action (B5).
4. Keep outreach, pricing, public posting and deployment on hold.
