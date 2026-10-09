# ALAGBARA Intelligence — Live Schema / Repository Reconciliation

**Checkpoint:** 2026-10-09  
**Supabase project inspected read-only:** `hbcxiyyuqgjokvypqrqr`  
**Repository baseline:** `feat/ail-runtime-v0.2` at `d7cfca94df5607f4910eb4a3f3304d04441c048e`  
**Status:** PARTIAL RECONCILIATION — source migration baseline is incomplete. No database was changed.

## Summary

The live Supabase migration ledger contains 15 applied migrations. The inspected repository baseline contains two flat SQL artifacts, `supabase/migration.sql` and `supabase/empire_ops.sql`, but no timestamped source files for the 15 migration records. The new security proposal in `supabase/migrations/20261009000000_security_boundary_v1.sql` is a forward-only proposal on the remediation branch; it is not applied and must not be treated as part of the live migration ledger.

The live schema includes:
- `cases`, `market_field_observations`
- `alagbara_cases`
- `big_intelligence_requests`, `big_intelligence_evidence`
- `alagbara_claims`, `alagbara_entities`, `alagbara_relationships`, `alagbara_graph_proposals`

The live `big_intelligence_requests` table includes the four EmpireOps state columns plus `empire_ops_token`. The repository's `supabase/empire_ops.sql` declares only the four state columns and index; it does not declare `empire_ops_token`. The live database has the request/evidence lifecycle RPCs whose exact function bodies were inspected read-only, but their original migration files are absent from the inspected repository tree.

## Migration-by-migration inventory

| Applied version | Live migration name | Source in repository | Reconciliation state |
|---|---|---|---|
| `20260821121102` | `create_field_evidence_schema` | `supabase/migration.sql` is a conceptual match | Partial: no timestamped source or checksum equivalence |
| `20260825032825` | `create_alagbara_decision_loop_cases` | Not found | Missing source |
| `20260825040415` | `add_vision_current_state_sovereignty_outcome` | Not found | Missing source |
| `20260825041953` | `add_user_ownership_boundary` | Not found | Missing source |
| `20260917125713` | `big_intelligence_request_public_intake` | Not found | Missing source |
| `20260917130002` | `recreate_big_intelligence_requests_and_intake` | Not found | Missing source |
| `20260917165137` | `add_controlled_big_intelligence_memory_rpc` | Not found | Missing source |
| `20260917165202` | `fix_big_intelligence_memory_rpc_privileges` | Not found | Missing source |
| `20260917165555` | `add_big_intelligence_status_rpc` | Not found | Missing source |
| `20260917193329` | `add_intelligence_evidence_ledger` | Not found | Missing source |
| `20260925112732` | `alagbara_49ft_core` | Not found | Missing source |
| `20260925112735` | `price_parity_transaction` | Not found | Missing source |
| `20260925112739` | `alagbara_realtime` | Not found | Missing source |
| `20260925112749` | `alagbara_entity_graph` | Not found | Missing source |
| `20260925113814` | `alagbara_graph_proposals` | Not found | Missing source |

## Observed function-level drift and security contract

The live functions were inspected using `pg_get_functiondef` and migration-ledger listing only. Findings:
- `create_big_intelligence_request` stores `internal_nonce` in `metadata` and returns it in JSON.
- `update_big_intelligence_request_status`, `record_big_intelligence_evidence`, and `complete_big_intelligence_request` authorize updates by matching that metadata nonce.
- `get_recent_big_intelligence_memory` reads recent requests across the table without an owner/tenant predicate.
- `read_big_intelligence_empire_ops` and `write_big_intelligence_empire_ops` require `empire_ops_token`.
- The live creation function does not populate `empire_ops_token`; the live write function only updates rows where the stored token equals the supplied token. Therefore first initialization appears unable to succeed for a newly created request.
- The RPCs are `SECURITY DEFINER`. The proposed migration changes their search path to empty and qualifies public objects.

These are findings from schema/function inspection, not claims that live requests were exercised.

## Canonicalization plan — no production writes

1. Recover each missing timestamped migration source from the authoritative backup/version-control location, if available. The live migration ledger alone records versions/names, not the original SQL body.
2. For each source file, compute and record a checksum; compare its declared version/name with the live ledger.
3. Capture a read-only schema inventory: columns, constraints, indexes, policies, grants, function definitions, triggers and realtime publication membership.
4. Compare the recovered migration replay against a disposable database. Do not reset or replay against production.
5. Resolve any drift explicitly in a reconciliation migration; never edit historical migration files to pretend they were what production applied.
6. Add the proposed security migration as a new forward-only migration only after source recovery and non-production tests.
7. Re-run read-only inventory and record an approved baseline commit.

## Unresolved items

- Original SQL bodies for 14 migration versions are not present as timestamped repository artifacts; the field-evidence source is only a conceptual match.
- No independent disposable PostgreSQL/Supabase instance was available in this checkpoint.
- The proposed security migration has not been executed against any database.
- The security CI workflow can run application-level contract tests, but it is not a substitute for testing SQL grants and function behavior in disposable PostgreSQL.
- Public intake still needs edge-level rate limiting/usage ceilings before deployment.
- Multi-tenant ownership is not yet represented on `big_intelligence_requests`; shared memory remains disabled by proposal until that boundary is designed.

**Decision:** do not claim the schema baseline is fully reconciled. The inventory is documented; canonical reconstruction is blocked on recovering missing migration SQL and validating replay in a disposable database.
