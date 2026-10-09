# ALAGBARA Intelligence — Security Remediation Review Pack

Status: **PROPOSED / NOT APPLIED TO ANY DATABASE**

Branch: `fix/security-boundary-v0.1`
Base: `feat/ail-runtime-v0.2`
Baseline commit: `d7cfca94df5607f4910eb4a3f3304d04441c048e`

## Scope

1. Remove hard-coded Supabase URL/publishable-key fallbacks from privileged server routes.
2. Require `SUPABASE_SERVICE_ROLE_KEY` for server-side request lifecycle RPCs; never return the internal nonce or EmpireOps token to the browser.
3. Disable cross-request memory until an owner/tenant boundary exists.
4. Require a valid Supabase user JWT plus `ALAGBARA_OPERATOR_EMAILS` allowlist for EmpireOps transitions.
5. Remove wildcard CORS; same-origin calls work without wildcard CORS.
6. Enforce a request-body size ceiling and generic client-facing errors.
7. Add a forward-only SQL proposal to revoke client execution, harden SECURITY DEFINER search paths, and initialize the independent EmpireOps token once.

## Required server environment

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` or `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (verification of the operator JWT only)
- `SUPABASE_SERVICE_ROLE_KEY` (server-only; never `NEXT_PUBLIC_*`)
- `OPENAI_API_KEY`
- `ALAGBARA_OPERATOR_EMAILS` (comma-separated exact email allowlist)

The current public intake endpoint remains intentionally unauthenticated. This proposal does **not** claim to solve volumetric abuse: edge rate limiting / usage ceilings must be configured before deploying the public endpoint. No production endpoint should be exercised as a test.

## Important design boundary

The current request table has no requester/tenant ownership column. Therefore this patch disables shared recent-memory reads instead of pretending that cross-request data is owner-scoped. The operator allowlist is an interim single-organization boundary, not a multi-tenant authorization model. Add tenant ownership before supporting multiple independent customer organizations.

## Validation plan (non-production only)

- `npm run test:security`: static security-contract assertions.
- `npm run test:ail`: existing AIL unit tests.
- `npm run build`: compile/build check, only with isolated test environment values.
- Test SQL in a disposable local PostgreSQL/Supabase instance created from a reconciled baseline; do not apply to the connected production project.
- Confirm anon/authenticated cannot execute privileged RPCs; service_role can execute intended RPCs; memory RPC is unavailable to all API roles.
- Confirm missing/invalid operator JWT and non-allowlisted email are rejected before any EmpireOps database operation.
- Confirm a successful intake response contains no nonce/token.
- Confirm the first EmpireOps write stores a new independent token and subsequent writes require the same token.
- Confirm an incomplete initialization can be retried safely.

## Deployment blockers

- No verified rate limiter on public intake.
- No end-to-end run against a disposable database yet.
- SQL migration has not been applied and is not approved for production.
- Reconcile the 15 live migration records against repository source before treating this file as a canonical migration.

## Rollback posture

Do not roll back by restoring anonymous RPC execution or returning tokens to the browser. If the patch fails in a test environment, revert the branch changes there and investigate. Any production rollback requires a separately reviewed migration that preserves the server-only access boundary.
