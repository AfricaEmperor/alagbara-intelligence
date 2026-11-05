# AP-001 Operator Guide — Cotonou Event Radar & Venue Intelligence

For the person who runs the local artefact: load posters, check what the system read, correct it, approve or reject, publish.
Everything here runs on one machine. Nothing is deployed, nothing is sent to anyone, and nothing touches Supabase unless you
configure it yourself.

## 1. The one command sequence

Requirements: Python 3.11+, Node 20.9+, `npm`, and for reading posters automatically **Tesseract with French**
(`apt-get install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng`). Without Tesseract the system still works: a poster
waits in the **Evidence inbox** until you type what it says.

```bash
git clone https://github.com/AfricaEmperor/alagbara-intelligence && git clone https://github.com/AfricaEmperor/pulse-l1   # side by side
cd alagbara-intelligence && git checkout claude/ap-001-cotonou-event-venue-radar-kr48v6
(cd ../pulse-l1 && git checkout claude/ap-001-cotonou-event-venue-radar-kr48v6)

scripts/ap001.sh setup     # once: venv, dependencies, PULSE build, OCR check        (~20 s on a warm machine)
scripts/ap001.sh up        # starts the operator console, PULSE, and a LOCAL DEMO identity provider
scripts/ap001.sh sample    # optional: loads 3 synthetic posters so you can see the whole workflow
```
`up` prints two addresses and a **launch key** (random each time, kept in `.ap001/run/operator.key`):

| What | Where | How you get in |
|---|---|---|
| Operator console | http://127.0.0.1:8750/ | your name + the launch key |
| PULSE Radar | http://127.0.0.1:3000/radar | reviewer sign-in with a one-time code (see §6) |

Other commands: `status`, `down`, `publish`, `backup`, `verify`, `report`, `demo` (automated acceptance demonstration),
`test` (every regression suite). State lives in `.ap001/` (database, original posters, published feed, backups, logs).
Ports and location can be changed with `AP001_OPERATOR_PORT`, `AP001_PULSE_PORT`, `AP001_IDP_PORT`, `AP001_STATE`, `PULSE_DIR`.

## 2. The workflow (what you do, step by step)

1. **Start** — `scripts/ap001.sh up`, open the console, sign in with your name and the key. Your name is written on every action.
2. **Register an authorized source** — *Sources* → register (e.g. `venue-x-instagram`, label "Club X official page") → **Approve**.
   A source is a person or page that allowed you to use their posters. Nothing can be uploaded from a source that is not approved
   by a named person. Revoking a source keeps the evidence already collected.
3. **Upload a poster** — *Upload*: choose the source, the image or video, and write the **permission note** (who allowed it, how,
   when). Optionally add the link where you found it. Press upload.
4. **Evidence is preserved** — the original file is stored unchanged under its SHA-256, with capture time, source, your name and
   the permission note. It is marked *unverified*: an uploaded file proves what the poster says, not who published it or whether
   the event is real.
5. **Extraction** — OCR reads the image (or your typed transcription is used), then ANA extracts title, date, times, venue,
   district, organizer, performers, ticket, category. Anything not on the poster stays **unknown**. A weekday without a date
   ("samedi") never becomes a calendar date.
6. **Review and correct** — open the event. The original poster sits beside *what ANA read*, each value labelled
   **derived** (machine) / **unverified** (typed by a person) / **observed** (you checked it) / **unknown**. Change what is wrong,
   tick *not on the poster* for anything that isn't there, press **Save corrections**. Your correction is added as a new claim;
   what ANA read stays on record. Conflicts between two sources (e.g. 22:00 vs 23:00) are shown; correcting the field settles
   them and the competing values remain visible.
7. **Approve or reject** — **Approve**, **Request correction**, or **Reject**, with an optional note. The decision is recorded
   under your name. Pressing a button twice, or reloading and resubmitting, records nothing twice.
8. **Persist** — every step is saved immediately in the local database; there is no separate "save".
9. **Publish** — Dashboard → *Publish approved events*. Only approved events (and venues that have one, or that you verified)
   are written to the feed. Nothing unapproved ever goes out. Publishing again at any time rebuilds the feed from the database.
10. **See it in PULSE** — open `/radar` and sign in. The event appears with its venue, date, indicators and provenance.

## 3. Venues

*Venues* lists every venue with category, district, verification and last observed activity. Venue names that are *nearly*
the same ("Club Exemple" / "Le Club Exemple") are never merged automatically: the second becomes a **candidate duplicate**, flagged on
its page. Open the surviving venue and use **Merge a duplicate into this venue**. Nothing is deleted: the old record stays,
points at the surviving one, its name becomes an alias, its events move, and future posters naming it resolve to the survivor.

On a venue page you can set: category, district, address, coordinates; **official links** (https, must be the venue's own page,
on the matching site); **contacts** (a contact is shown publicly **only** if you mark it public and write why that is allowed,
e.g. "number printed on the venue's own poster for bookings"); **verification** (*verified* needs a written note saying how).

## 4. Backup, verification and recovery

| Need | Do |
|---|---|
| Back up (database + original posters + sha256 manifest; safe while the console is running) | console *Backup & checks* → **Back up now**, or `scripts/ap001.sh backup` |
| Check everything is consistent (media hashes, links, decisions vs event status, orphan files) | `scripts/ap001.sh verify` (also shown on *Backup & checks*) |
| Verify a backup is intact | `.venv/bin/radar verify-backup .ap001/backups/backup-…` |
| Restore a backup | stop the console (`down`), then `.venv/bin/radar --data .ap001/data restore .ap001/backups/backup-… --force` — your current data is **moved aside** into `pre-restore-…`, never deleted; a damaged backup is refused |
| **Feed is missing, corrupt, or PULSE says "feed cannot be used"** | press **Publish** again (or `scripts/ap001.sh publish`). The feed is always rebuilt from the database; writes are atomic, so a crash leaves the previous complete feed. PULSE shows nothing rather than something wrong |
| An original poster is damaged or missing | `verify` names it; restore that file from a backup (hashes tell you which copy is right) |
| Database file damaged | restore the latest verified backup as above |

Back up before any bulk upload and at the end of every session. Keep backups off this machine too; they contain the evidence.

## 5. Measuring quality

*Backup & checks* → **Extraction quality**, or `scripts/ap001.sh report`. For every field it shows how often ANA read a value,
how often you replaced it, how often you filled a gap. It counts **only events you reviewed**; unreviewed events are never
assumed correct. These numbers are the honest answer to "does it read real Cotonou posters well enough?" — the synthetic sample
does not answer it.

## 6. Signing in to PULSE (and what is and is not real)

* **Local demo (what `up` starts):** a mock identity provider. Reviewer `rev@example.test`, one-time code `123456`. It exists so
  the real sign-in code runs on a laptop. **It is not authentication you should rely on.**
* **For anything real:** set `SUPABASE_URL` and `SUPABASE_ANON_KEY` (anon key only) before `up`. Then PULSE uses Supabase Auth: a
  person gets in only if an administrator has set `app_metadata.radar_role` to `reviewer` or `admin` on their Supabase user.
  This path has been tested only against the mock; see `AP001_R3_READINESS_REPORT.md` for what is still unverified.
* **The operator console is a local tool, not a multi-user system.** It binds to 127.0.0.1 only and asks for a per-launch key
  plus a name; the name is self-declared. It protects against other websites and other people on the network, not against
  someone who already has your session or your machine.

## 7. What it will not do

It never contacts a venue or organizer, never posts anything, never scrapes a social platform, never logs into one, and
never reads private profiles. Facebook/Instagram/web adapters are **disabled**; only operator uploads are enabled. Posters from
a page you do not control are used only with the page owner's permission, recorded in the permission note.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Wrong name or key" / "Too many attempts" | key is in `.ap001/run/operator.key`; after 5 failures wait a minute |
| Poster stored but no event | no OCR text: *Evidence inbox* → open it → type the text (stored as *unverified*) |
| Every field wrong on a real poster | stylized fonts defeat OCR: use the transcription box; report it (it feeds the quality numbers) |
| PULSE redirects to sign-in | normal without a session; sign in with the code from §6 |
| PULSE says "No radar feed yet" | nothing published: Dashboard → Publish |
| "Decision NOT recorded … event changed" | someone (or a second upload) changed the event since you opened it: reload and review the current values |
| Port already in use | `AP001_OPERATOR_PORT=… AP001_PULSE_PORT=… scripts/ap001.sh up` |
| `up` ran but nothing answers | `scripts/ap001.sh status`; logs in `.ap001/run/*.log` |
