# SCOUT Intelligence Fabric

Evidence-first acquisition primitives for ALAGBARA. SCOUT captures source observations with provenance; it does not verify the truth of claims contained in a page.

## SCOUT-001: First Evidence Acquisition

A minimal, opt-in adapter retrieves one explicitly supplied public HTML page using Python's standard library, extracts visible text and title, and emits a JSON observation. It has a 15-second timeout and a 1 MB response cap. It does not use browser automation, evade access controls, or crawl links.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
scout-acquire https://example.org --output evidence.json
```

Use only sources you are authorized to access. Respect terms, robots policies where applicable, rate limits, privacy, and law. Run one source at a time; no scheduler or autonomous actions are included.

## Evidence contract

Each record preserves source URL, collection method, adapter, timestamps, captured text, and a deterministic observation identifier. A captured page is an observation of what the page returned at collection time—not independent verification of its assertions. Keep observed, derived, unverified, and unknown states distinct; preserve contradictions rather than silently resolving them.

## Next

Add a reviewed source-specific adapter, raw-response retention with integrity hashes, and tests against controlled fixtures before enabling recurring collection.
