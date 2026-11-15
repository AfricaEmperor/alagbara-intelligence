# VILLAWAY-001 / PI-EXT-001 — Bounded Implementation Package

Status: authorized isolated work package; implementation not yet started.
Repository: AfricaEmperor/alagbara-intelligence
Base branch: feat/museops-pi-001-partner-intelligence
Base commit: 82acc4b355f58eedefe428bc55f61536c7e97119
Work branch: feat/villaway-001-acquisition-intelligence

## Mission

Extend the existing Partner Intelligence vertical slice into a minimal, evidence-backed hospitality acquisition and booking journey:

Prospect → Requirement → Qualification → Property Match → Introduction → Booking → Commission Attribution → Reconciliation.

This package is a bounded implementation order, not a production authorization.

## Existing foundations to reuse

- `partner_intel.models`: Entity, RelationshipClaim, AttributeClaim, TimePeriod and evidence-state vocabulary.
- `partner_intel.claimbook.ClaimBook`: evidence traceability, non-overwriting claims and deterministic contradictions.
- `partner_intel.profile.build_profile`: current-period qualification and human-question read model.
- `partner_intel.acquire.acquire_operator_url`: single operator-supplied URL within an approved public_html source.
- `ana_engine.store.RadarStore`: existing SQLite evidence, audit, transaction and event persistence.

Do not create a second evidence store. Do not infer authority, availability, booking confirmation or causal referral from graph proximity.

## Work packages

### WP-A — Durable Partner Intelligence

Inspect existing store schema and migration conventions first. Add durable entity and claim persistence within RadarStore only if compatible with current migration design.

Required properties:
- schema versioning and reversible/backup-aware migration approach;
- immutable entity/claim identity;
- idempotent writes;
- parameterized SQL;
- evidence references validated against the existing evidence ledger;
- conflicting claims coexist; same ID with different content is rejected;
- audit actor/action/subject/detail for meaningful writes;
- restart durability tests.

Do not silently change existing event or evidence semantics.

### WP-B — Hospitality domain contracts

Add minimal validated contracts for:
- AccommodationProperty;
- HospitalityOperator;
- AccommodationRequirement;
- PropertyMatch;
- IntroductionRecord.

Property fields must distinguish observed facts from operator-supplied assertions and unknown values. Availability must have a validity interval; expired or unknown availability is not current. Booking authority requires its own evidence.

Reuse Partner Intelligence entities and relationships where appropriate. Do not overload VENUE or COMMERCIAL_NEED with booking-specific payloads.

### WP-C — Booking lifecycle

Add:
- Booking;
- immutable BookingOffer snapshot;
- BookingConfirmation;
- append-only BookingEvent.

Allowed lifecycle:
DRAFT → OFFERED → ACCEPTED → CONFIRMED → COMPLETED
Exception states: CANCELLED, EXPIRED, DISPUTED.

Enforce valid transitions, idempotency keys, optimistic concurrency/version checks, immutable accepted offer terms and audit history. Keep payment state separate from booking state. Confirmation must reference evidence; a proposed match is not a reservation.

### WP-D — Referral and commission

Add:
- CommissionAgreement (versioned);
- CommissionEntitlement;
- CommissionEvent;
- ReconciliationRecord.

Keep earned, invoiced, received and paid states distinct. Calculate only from an applicable agreement and eligible, evidenced attribution. An INTRODUCES claim alone does not prove a completed booking or commission entitlement. Preserve disputes and corrections as events; do not overwrite history.

### WP-E — Synthetic end-to-end proof

Create fictional fixtures only. Demonstrate:
1. prospect requirement created;
2. qualification produced with evidence references and explicit unknowns;
3. property and operator represented with dated evidence;
4. property match records criteria and unmet requirements;
5. human-reviewed introduction records introducer and causal evidence;
6. offer snapshot accepted;
7. booking confirmed using synthetic confirmation evidence;
8. commission entitlement calculated from a versioned agreement;
9. invoice/receipt/payout reconciliation represented independently.

## Cross-cutting security requirements

Before any real customer data is considered:
- establish tenant ownership on prospects, properties, bookings and financial records;
- enforce authorization server-side on every read and write;
- separate platform operator, property operator, customer, introducer and administrator capabilities;
- derive audit actor from authenticated context, never a client-supplied identity string;
- define purpose limitation, retention and access rules for personal data;
- prevent cross-tenant reads/writes in tests.

The current branch specification explicitly states that personal-data purpose limitation, retention and access control are not implemented. Treat these as blockers for real customer data. Do not assume the connected development Supabase project is approved for VILLAWAY tenancy.

## Validation / acceptance

- Existing Partner Intelligence tests continue to pass.
- Every non-unknown commercial claim resolves to evidence in RadarStore and preserves provenance.
- Conflicting ownership/availability/authority assertions remain visible.
- Expired/unknown availability cannot qualify as current supply.
- Match output explains criteria and unmet requirements.
- Introduction attribution requires explicit causal evidence and human review.
- Invalid booking transitions are rejected.
- Replaying an idempotency key does not create duplicate transactions or audit events.
- Stale concurrent writes are rejected.
- Accepted offer snapshots cannot be silently modified.
- Commission uses a versioned agreement; payment and payout are separate.
- Restart durability and tenant-isolation tests pass.
- Synthetic journey is reproducible offline.

## Stop conditions

Stop and report rather than improvise if:
- base branch SHA changes before work starts;
- the migration design conflicts with existing store behavior;
- tenant/actor authorization cannot be enforced;
- a change requires hosted Supabase, production credentials or production migration;
- real customer data or external contact is required to prove the flow;
- existing Partner Intelligence regressions appear;
- required test execution is unavailable.

## Explicit exclusions

No merge to the base branch. No deployment. No production Supabase writes or migrations. No external messages, outreach, booking confirmations or financial transactions. No real customer personal/financial data. No autonomous scraping, login, social-account access or crawler. No unrelated AP-001, SEC-001, ORACLE or Pulse changes.

## Required executor report

Return:
1. verified execution identity and environment;
2. base SHA and working tree state;
3. dependency/change plan;
4. changed-file inventory;
5. commit SHA and branch;
6. exact existing and new test commands/results;
7. security and tenant-isolation evidence;
8. unresolved risks and next recommendation.

A completed feature branch is not production approval. Independent review and founder approval are required before merge or deployment.
