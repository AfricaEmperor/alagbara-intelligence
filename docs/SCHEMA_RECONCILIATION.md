# ALAGBARA Intelligence — Live Schema / Repository Reconciliation

**Checkpoint:** 2026-10-09  
**Supabase project inspected read-only:** `hbcxiyyuqgjokvypqrqr`  
**Base branch/commit:** `feat/ail-runtime-v0.2` / `d7cfca94df5607f4910eb4a3f3304d04441c048e`  
**Remediation branch:** `fix/security-boundary-v0.1`  
**Status:** SOURCE RECOVERED FROM LIVE MIGRATION LEDGER; REPLAY VALIDATION STILL REQUIRED. No database was changed.

## Reconciliation result

The live migration ledger contains 15 applied migrations. The repository baseline previously contained only two flat SQL artifacts, `supabase/migration.sql` and `supabase/empire_ops.sql`, and lacked the timestamped migration sources.

The original SQL statement arrays were recovered read-only from `supabase_migrations.schema_migrations` and committed as timestamped files under `supabase/migrations/`. This recovers the database's recorded applied SQL as a version-controlled baseline; it does not yet prove that a clean database can replay the complete history or that every resulting object exactly matches production.

## Recovered applied migrations

| Version | Name | Recovered source file |
|---|---|---|
| `20260821121102` | `create_field_evidence_schema` | `supabase/migrations/20260821121102_create_field_evidence_schema.sql` |
| `20260825032825` | `create_alagbara_decision_loop_cases` | `supabase/migrations/20260825032825_create_alagbara_decision_loop_cases.sql` |
| `20260825040415` | `add_vision_current_state_sovereignty_outcome` | `supabase/migrations/20260825040415_add_vision_current_state_sovereignty_outcome.sql` |
| `20260825041953` | `add_user_ownership_boundary` | `supabase/migrations/20260825041953_add_user_ownership_boundary.sql` |
| `20260917125713` | `big_intelligence_request_public_intake` | `supabase/migrations/20260917125713_big_intelligence_request_public_intake.sql` |
| `20260917130002` | `recreate_big_intelligence_requests_and_intake` | `supabase/migrations/20260917130002_recreate_big_intelligence_requests_and_intake.sql` |
| `20260917165137` | `add_controlled_big_intelligence_memory_rpc` | `supabase/migrations/20260917165137_add_controlled_big_intelligence_memory_rpc.sql` |
| `20260917165202` | `fix_big_intelligence_memory_rpc_privileges` | `supabase/migrations/20260917165202_fix_big_intelligence_memory_rpc_privileges.sql` |
| `20260917165555` | `add_big_intelligence_status_rpc` | `supabase/migrations/20260917165555_add_big_intelligence_status_rpc.sql` |
| `20260917193329` | `add_intelligence_evidence_ledger` | `supabase/migrations/20260917193329_add_intelligence_evidence_ledger.sql` |
| `20260925112732` | `alagbara_49ft_core` | `supabase/migrations/20260925112732_alagbara_49ft_core.sql` |
| `20260925112735` | `price_parity_transaction` | `supabase/migrations/20260925112735_price_parity_transaction.sql` |
| `20260925112739` | `alagbara_realtime` | `supabase/migrations/20260925112739_alagbara_realtime.sql` |
| `20260925112749` | `alagbara_entity_graph` | `supabase/migrations/20260925112749_alagbara_entity_graph.sql` |
| `20260925113814` | `alagbara_graph_proposals` | `supabase/migrations/20260925113814_alagbara_graph_proposals.sql` |

The recovered SQL was copied from the ledger's stored `statements` arrays. No SQL was executed during recovery. The two flat SQL files remain legacy/convenience artifacts and should not be considered the canonical ordered migration history.

## Live schema inventory

The live schema includes:
- `cases`, `market_field_observations`
- `alagbara_cases`
- `big_intelligence_requests`, `big_intelligence_evidence`
- `alagbara_claims`, `alagbara_entities`, `alagbara_relationships`, `alagbara_graph_proposals`

The live `big_intelligence_requests` table includes `empire_ops_loop_id`, `empire_ops_status`, `empire_ops_state`, `empire_ops_events`, and `empire_ops_token`. The existing flat `supabase/empire_ops.sql` declares only the four state columns and index; the token column is not represented there.

## Observed function-level drift and security contract

The live function definitions were inspected read-only using `pg_get_functiondef`. Findings:
- `create_big_intelligence_request` stores `internal_nonce` in `metadata` and returns it in JSON.
- `update_big_intelligence_request_status`, `record_big_intelligence_evidence`, and `complete_big_intelligence_request` authorize changes by matching that metadata nonce.
- `get_recent_big_intelligence_memory` reads recent requests without an owner/tenant predicate.
- `read_big_intelligence_empire_ops` and `write_big_intelligence_empire_ops` require `empire_ops_token`.
- The live creation function does not populate `empire_ops_token`; the live write function only updates rows where the stored token equals the supplied token. Initializing a newly created request therefore appears unable to succeed.
- These functions are `SECURITY DEFINER`; the security proposal hardens search paths and revokes client-role execution.

These are source/schema findings, not claims that live requests were exercised.

## Remaining reconciliation work

1. Verify the recovered 15 filenames and versions exactly match the live ledger.
2. Compare recovered migration-created objects against the read-only live inventory: columns, constraints, indexes, policies, grants, function definitions, triggers, and realtime publication membership.
3. Replay all 15 recovered migrations in a disposable PostgreSQL/Supabase database. Do not reset or replay against production.
4. Resolve replay failures and drift explicitly; do not rewrite historical migration files to make them appear different from the recorded applied SQL.
5. Review and test `supabase/migrations/20261009000000_security_boundary_v1.sql` as a proposed forward-only sixteenth migration. It is not in the live ledger and has not been applied.
6. After replay succeeds, record a baseline manifest with Git blob IDs or cryptographic checksums, schema inventory, test evidence, and the exact branch commit.

## Unresolved items / gates

- Clean-database replay and SQL privilege integration tests have not been run because no disposable database was used in this checkpoint.
- The proposed security migration has not been executed against any database.
- Public intake still needs edge-level rate limiting and usage ceilings before deployment.
- `big_intelligence_requests` has no requester/tenant ownership field. Shared recent-memory access remains disabled by proposal until an explicit ownership model is implemented.
- GitHub Actions runs failed before any job steps were executed; the workflow was removed rather than treating that as a test result. Read-only branch-content syntax/contract checks passed separately.

**Decision:** the historical SQL source is now recovered and versioned, but the baseline is not certified until the ordered replay and live-vs-replay object comparison pass in a disposable environment.
