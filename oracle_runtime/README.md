# ORACLE Runtime — v0.1

This package implements the first non-production ORACLE contract slice.

## Included
- JSON Schema Draft 2020-12 validation plus cross-field governance invariants.
- SCOUT read-only observation importer. It reads an already captured JSON observation; it does not fetch pages or mutate SCOUT.
- SQLite append-only event ledger with UPDATE/DELETE triggers and a SHA-256 hash chain.
- CONTROL authorization port that denies by default when no authoritative provider is configured and verifies exact decision/scope.
- Zuberi executor registry port. A role name is not an identity; handoff requires a verified identity reference and explicit permissions.
- MEMORY projection port for verified outcomes. Local append-only ledger is authoritative; external MEMORY integration requires an explicitly configured sink.

## Local use

```bash
cd oracle_runtime
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
PYTHONPATH=. pytest -q
```

## Important boundaries
- The fixture is synthetic and is not live market intelligence.
- No CONTROL provider is connected. Approval checks fail closed.
- No Zuberi endpoint is registered. Handoff is blocked until identity and permissions are verified.
- No external MEMORY sink is connected. Verified outcomes can be appended to the local ledger; external projection is not claimed.
- SQLite append-only triggers are application-level controls, not tamper-proof storage against an administrator who can replace the database file. Production requires managed immutable/WORM storage, access separation, backups and independent integrity verification.
- No production database, social account, crawler, deployment or external outreach is enabled.
