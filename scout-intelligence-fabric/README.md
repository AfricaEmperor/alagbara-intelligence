# SCOUT Intelligence Fabric

A modular, evidence-first acquisition layer for ALAGBARA. Source adapters collect observations; the fabric normalizes provenance and preserves uncertainty. It does **not** treat scraped content as verified truth.

## Design principles
- Adapter-based acquisition (Agent-Reach, Scrapling, browser automation are optional integrations).
- Evidence provenance is mandatory: source URL, observed time, collection time, method, and raw-record reference.
- Keep observed, derived, unverified, and unknown states distinct.
- Preserve contradictions; never silently resolve them.
- Respect source terms, access controls, rate limits, privacy, and applicable law.
- No autonomous external actions in this scaffold.

## Layout
- `src/scout_fabric/models.py`: canonical observation/evidence models.
- `src/scout_fabric/normalize.py`: deterministic normalization helpers.
- `config/sources.example.yaml`: adapter configuration template.
- `schemas/observation.schema.json`: interchange contract.
- `tests/`: contract tests.

## Quick start
Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

This is a scaffold, not a production crawler. Add a source adapter only after documenting authorization, collection limits, and expected provenance.
