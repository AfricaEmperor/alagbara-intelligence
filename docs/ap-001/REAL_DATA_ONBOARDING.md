# Real-data onboarding — 30 to 50 authorized Cotonou event posters

Goal: load real posters **with permission**, review every one, and measure how well the system reads real Cotonou material.
No real poster has been loaded by anyone yet; every number the system has produced so far comes from **synthetic** fixtures.

## 0. Rules that cannot be relaxed
1. **Permission first.** A poster is used only if its owner (organizer, venue, or the page that published it) allowed it. Record
   who and how in the **permission note** — the system refuses an upload or a manifest row without one.
2. **No scraping, no log-in tricks, no private profiles.** Posters arrive as files you were given or saved from public pages you
   are allowed to use. Do not bulk-download platforms.
3. **Never invent.** If a poster has no date, price, venue or organizer, the field stays *unknown*. A weekday is not a date.
4. **A poster proves what it says, not that the event is real.** Evidence stays *unverified*; nothing is "verified" because it was
   extracted from a poster. The venue's *verified* status needs a written note about an independent check.
5. **Phone numbers on posters are personal data of the organizers.** They are stored as extracted claims and shown only to
   signed-in reviewers. A venue contact is published only when you mark it public and write why that is allowed. Get legal advice
   before any public launch (Benin data-protection rules have not been reviewed here).
6. **No contact.** Onboarding never involves messaging a venue or organizer from the system.

## 1. Prepare (about 30 minutes)
1. `scripts/ap001.sh setup && scripts/ap001.sh up`; confirm OCR: the Upload page says "OCR: available (Tesseract, French+English)".
2. In *Sources*, register one source per origin of posters (e.g. `organizer-awa`, `club-x-whatsapp`) and approve each yourself.
   Do not mix origins in one source: provenance is only as good as the source id.
3. Make an inbox folder, e.g. `inbox/2026-11-batch1/`, containing **only** the poster images/videos for that batch. Keep originals; the
   system copies, it never moves or edits them.

## 2. Load
**One at a time** (best for the first 5): console → *Upload*.
**In bulk** (a manifest): create `manifest.csv` next to the files:
```
file,source_id,permission_note,source_url,transcription_file
afro_night_nov.jpg,organizer-awa,"Awa (organizer) agreed by WhatsApp on 2026-11-02 that we may use her posters",https://www.facebook.com/…/posts/…,
brunch_live.png,club-x-whatsapp,"Club X manager sent this poster for the pilot, email 2026-11-03",,brunch_live.txt
```
Then: `.venv/bin/radar --data .ap001/data ingest-manifest manifest.csv --root inbox/2026-11-batch1 --report batch1-report.csv`.
The report has one row per file: `ingested`, `duplicate` (already loaded: safe to re-run), `needs_transcription`, or `rejected` with the reason.
One bad row never stops the others. **Back up** (`scripts/ap001.sh backup`) before and after each batch.

## 3. Review every event (the actual work)
For each event, with the poster open next to the extraction:
1. Check **title, date, start/end, venue, district, organizer, performers, ticket, category**.
2. Fix what is wrong; tick *not on the poster* for anything absent. If the date shows only a weekday, leave the date unknown.
3. If two posters describe one event, make sure both agree or correct the field to settle the conflict; if an event is a duplicate of
   another with a *different* title, reject one (see Known limits).
4. **Approve** only when you would stand behind every visible field. **Request correction** if you must check with the organizer
   outside the system. **Reject** if it is not an event, is a duplicate, or you were not allowed to use it.
5. Aim for **no more than 10 minutes per poster** at the start; if it takes longer, note why — that is a finding.

## 4. Build the venue directory as you go
Open each new venue (*Venues*): set category and district, confirm the spelling, merge near-duplicates, add the venue's **own**
official links (tick the confirmation only if you checked the page), add a public contact only with an authorization note. Mark
*verified* only with a note such as "official Instagram page shows the same address and events". Leave anything you can't confirm
as *unverified*.

## 5. Measure (after the first 10, and again at 30–50)
`scripts/ap001.sh report` (or *Backup & checks*): per field, **read** / **replaced by you** / **filled by you**, plus median minutes
from upload to first decision, unresolved conflicts, events without a date. Judge by the fields that matter commercially (venue,
date, start time, title):
* a field **replaced** in more than ~30 % of reviewed events needs extractor work before scaling;
* a field **read** in under ~70 % of events means posters carry it in a form OCR misses (stylized fonts, images of text over photos);
* record the failing poster types — these become the next bounded work package. Thresholds are starting points, not findings.

## 6. Done means
* 30–50 posters loaded, each with a permission note; every event decided by a named person;
* `scripts/ap001.sh verify` passes; a backup exists and verifies;
* the quality report is saved with the batch (`scripts/ap001.sh report > report-batch1.json`);
* the list of poster types that failed is written down;
* nothing was published that a human did not approve.

## 7. Known limits you will meet
* Two posters of one event with **different titles** are not merged automatically (the sample shows it: "NUIT AFRO" vs "NUIT AFRO VOL. 3").
  There is no event-merge button yet: reject the duplicate.
* Handwriting, heavy stylization, and text baked into photographs are read poorly or not at all; use the transcription box.
* Video posters: the first frames are OCR'd; spoken details are not transcribed (no speech-to-text is installed).
* French is the target language; Fon/Yoruba-only posters will need transcription.
* Dates without a year ("14 novembre") stay unknown on purpose.
