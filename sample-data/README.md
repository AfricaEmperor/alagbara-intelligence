# Sample data (synthetic)

Everything here is **fictional**: "Club Exemple", "Bar Fictif", "Studio Fictif", "NUIT AFRO VOL. 3". The posters are rendered
from the HTML files beside them (`posters/*.html` -> `posters/*.png`). They exist so the whole pipeline, including real OCR,
can be exercised and demonstrated without touching any real organizer's material.

* `p1_nuit_afro` - a clean poster: OCR reads most fields; it misreads nothing fatal but splits the title across two lines.
* `p2_nuit_afro_flyer` - the same fictional event from another "source" with a conflicting start time (22:00 vs 23:00).
* `p3_brunch_samedi` - only says "Samedi midi": the date must stay **unknown**.

Load them: `scripts/ap001.sh sample` (registers a source `sample-uploads`, approved by "sample-loader", then batch-ingests
`manifest.csv`). These say **nothing** about accuracy on real Cotonou posters; see `docs/ap-001/REAL_DATA_ONBOARDING.md`.
