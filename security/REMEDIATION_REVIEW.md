# ALAGBARA Intelligence — Security Remediation Review Pack

Status: **PROPOSED / NOT APPLIED TO ANY DATABASE**

Branch: `fix/security-boundary-v0.1`  
Base: `feat/ail-runtime-v0.2`  
Base commit: `d7cfca94df5607f4910eb4a3f3304d04441c048e`  
Current reviewed commit at checkpoint: `c2926d57dad45b5962fbd9002e7f3859a709fdf0`

## Scope

1. Remove hard-coded Supabase URL/publishable-key fallbacks from privileged server routes.
2. Require `SUPABASE_SERVICE_ROLE_KEY` for server-side request lifecycle RPCs; never return the internal nonce or EmpireOps token to the browser.
3. Disable cross-request memory until an owner/tenant boundary exists.
4. Require a valid Supabase user JWT, confirmed email, and `ALAGBARA_OPERATOR_EMAILS` allowlist for EmpireOps transitions.
5. Remove wildcard CORS; same-origin calls work without wildcard CORS.
6. Enforce a request-body size ceiling, generic client-facing errors, and `Cache-Control: no-store`.
7. Add a forward-only SQL proposal to revoke client execution, harden SECURITY DEFINER search paths, and initialize the independent EmpireOps token once.
8. Recover all 15 applied migration SQL sources from the read-only `supabase_migrations.schema_migrations` ledger into timestamped `supabase/migrations/` files. A separate report documents replay gates.

## Required server environment

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` or `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (operator JWT verification only)
- `SUPABASE_SERVICE_ROLE_KEY` (server-only; never `NEXT_PUBLIC_*`)
- `OPENAI_API_KEY`
- `ALAGBARA_OPERATOR_EMAILS` (comma-separated exact email allowlist)

The current public intake endpoint remains intentionally unauthenticated. This proposal does **not** claim to solve volumetric abuse: edge rate limiting / usage ceilings must be configured before deployment. No production endpoint should be exercised as a test.

## Important design boundary

The current request table has no requester/tenant ownership column. Therefore this patch disables shared recent-memory reads instead of pretending that cross-request data is owner-scoped. The operator allowlist is an interim single-organization boundary, not a multi-tenant authorization model. Add tenant ownership before supporting multiple independent customer organizations.

## Validation performed without production access

- 8/8 read-only branch-content syntax/contract checks passed, including JavaScript parse checks for both route modules.
- A separate pass verified 11/11 security contract conditions before the final cache/error hardening changes; the later 8-check pass covers the current route content.
- No Supabase write, migration, production endpoint invocation, or production deployment was performed.
- GitHub Actions runs failed before any job steps executed (no test output); the workflow was removed rather than misrepresenting those runs as passing.
- Some branch pushes automatically triggered Vercel Preview builds through the repository integration. In-progress Preview deployments were canceled; the Preview URLs were not opened and no route was invoked. No production deployment was targeted.
- SQL grants/function behavior and clean migration replay remain untested because no disposable database was available.

## Required non-production tests before approval

- Run `npm run test:security` and `npm run test:ail` from a clean checkout.
- Run `npm run build` with placeholder-only test environment variables.
- Replay the 15 recovered migrations in a disposable PostgreSQL/Supabase database; compare tables, columns, constraints, indexes, policies, grants, functions, triggers and realtime publication membership.
- Apply the proposed sixteenth migration to that disposable database only; verify anon/authenticated cannot execute privileged RPCs, service_role can execute intended RPCs, and memory RPC is unavailable to API roles.
- Confirm missing/invalid operator JWT and non-allowlisted email are rejected before any EmpireOps database operation.
- Confirm successful intake responses contain no nonce/token and first/subsequent EmpireOps writes behave as intended.
- Confirm failed initialization can be retried safely.

## Deployment blockers

- No verified rate limiter on public intake.
- No SQL integration test against a disposable database yet.
- Security migration has not been applied and is not approved for production.
- Replay and object comparison for the recovered historical baseline remain outstanding.
- Multi-tenant ownership is not implemented.

## Rollback posture

Do not roll back by restoring anonymous RPC execution or returning tokens to the browser. If the patch fails in a test environment, revert the branch changes there and investigate. Any production rollback requires a separately reviewed migration that preserves the server-only access boundary.
