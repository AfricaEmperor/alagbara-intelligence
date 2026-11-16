# VILLAWAY Command Center — Data Contract

Contract version: villaway-command-center/1.0
Status: v1 read-only projection contract
Classification: operational metadata; commercial/personal records excluded until access controls are verified

## 1. Contract principles

- The dashboard consumes normalized read models; it does not own business state.
- Each record identifies its authoritative source and source record.
- Missing values remain null/UNKNOWN; do not infer.
- Timestamps are ISO-8601 with explicit timezone (UTC preferred).
- IDs are stable opaque strings.
- State enums are case-sensitive.
- Evidence references resolve to the existing ALAGBARA evidence ledger; do not duplicate captured personal data.
- Every snapshot includes generated_at, source freshness and completeness.

## 2. Envelope

```json
{
  "contract_version": "villaway-command-center/1.0",
  "mission_id": "VILLAWAY-001",
  "generated_at": "2026-11-16T00:00:00Z",
  "mode": "SYNTHETIC",
  "sources": [
    {
      "source_id": "github-engineering",
      "kind": "GITHUB",
      "status": "AVAILABLE",
      "as_of": "2026-11-16T00:00:00Z",
      "freshness": "FRESH",
      "completeness": "PARTIAL",
      "record_count": 0,
      "error_code": null
    }
  ],
  "engineering": {},
  "commercial": {},
  "governance": {},
  "roadmap": [],
  "blockers": [],
  "acceptance": []
}
```

## 3. Common enums

SourceKind:
- GITHUB
- VILLAWAY_API
- ALAGBARA_EVIDENCE
- STATIC_FIXTURE

SourceStatus:
- AVAILABLE
- PARTIAL
- UNAVAILABLE
- NOT_CONNECTED

Freshness:
- FRESH
- STALE
- UNKNOWN

Completeness:
- COMPLETE
- PARTIAL
- UNKNOWN

DashboardMode:
- LIVE
- SYNTHETIC
- OFFLINE

Workstream:
- ENGINEERING
- COMMERCIAL
- GOVERNANCE

GateState:
- NOT_STARTED
- IN_PROGRESS
- BLOCKED
- READY_FOR_REVIEW
- ACCEPTED
- UNKNOWN

EvidenceState:
- VERIFIED
- OBSERVED
- ASSERTED
- DERIVED
- DISPUTED
- EXPIRED
- UNKNOWN

RiskState:
- NOT_IMPLEMENTED
- NOT_VERIFIED
- BLOCKED
- ACCEPTED
- UNKNOWN

## 4. Core record shapes

### SourceMeta
```json
{
  "source_id": "string",
  "kind": "GITHUB | VILLAWAY_API | ALAGBARA_EVIDENCE | STATIC_FIXTURE",
  "status": "AVAILABLE | PARTIAL | UNAVAILABLE | NOT_CONNECTED",
  "as_of": "ISO-8601 timestamp or null",
  "freshness": "FRESH | STALE | UNKNOWN",
  "completeness": "COMPLETE | PARTIAL | UNKNOWN",
  "record_count": 0,
  "error_code": "string or null"
}
```

### RoadmapGate
```json
{
  "gate_id": "string",
  "title": "string",
  "workstream": "ENGINEERING | COMMERCIAL | GOVERNANCE",
  "state": "GateState",
  "depends_on": ["gate-id"],
  "blocked_by": ["blocker-id"],
  "acceptance_criteria": ["string"],
  "evidence_refs": ["evidence-id"],
  "owner_role": "string or null",
  "updated_at": "ISO-8601 timestamp or null",
  "source_id": "string"
}
```

### Blocker
```json
{
  "blocker_id": "string",
  "title": "string",
  "workstream": "ENGINEERING | COMMERCIAL | GOVERNANCE",
  "severity": "CRITICAL | HIGH | MEDIUM | LOW",
  "state": "OPEN | MITIGATED | RESOLVED | UNKNOWN",
  "unblock_condition": "string",
  "owner_role": "string or null",
  "evidence_refs": ["evidence-id"],
  "updated_at": "ISO-8601 timestamp or null",
  "source_id": "string"
}
```

### EngineeringSnapshot
```json
{
  "repository": "owner/name",
  "branch": "string or null",
  "base_branch": "string or null",
  "head_sha": "string or null",
  "commits_ahead": 0,
  "open_issues": null,
  "open_pull_requests": null,
  "ci_state": "PASS | FAIL | RUNNING | NOT_RUN | UNKNOWN",
  "ci_checked_at": "ISO-8601 timestamp or null",
  "source_id": "github-engineering"
}
```

Counts are nullable. A null count means unavailable or not queried; it is not zero.

### CommercialPipelineSnapshot
```json
{
  "prospects": {"count": null, "source_id": "string"},
  "requirements": {"count": null, "source_id": "string"},
  "qualified_requirements": {"count": null, "source_id": "string"},
  "verified_properties": {"count": null, "source_id": "string"},
  "matches": {"count": null, "source_id": "string"},
  "introductions": {"count": null, "source_id": "string"},
  "bookings": {"count": null, "source_id": "string"},
  "completed_bookings": {"count": null, "source_id": "string"},
  "commission_earned": {"amount_minor": null, "currency": null, "source_id": "string"},
  "commission_invoiced": {"amount_minor": null, "currency": null, "source_id": "string"},
  "commission_received": {"amount_minor": null, "currency": null, "source_id": "string"},
  "commission_paid": {"amount_minor": null, "currency": null, "source_id": "string"}
}
```

Monetary values use integer minor units plus ISO-4217 currency. Never sum different currencies. Each count must include an as-of timestamp in its containing source metadata. Do not show a zero where the source is not connected.

### CommercialRecord
```json
{
  "record_id": "string",
  "record_type": "PROSPECT | REQUIREMENT | PROPERTY | OPERATOR | MATCH | INTRODUCTION | BOOKING | COMMISSION | RECONCILIATION",
  "state": "domain-specific state string",
  "evidence_state": "EvidenceState",
  "evidence_refs": ["evidence-id"],
  "source_id": "string",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp",
  "expires_at": "ISO-8601 timestamp or null",
  "summary": "non-sensitive summary"
}
```

No contact names, phone numbers, emails, identity documents, guest details or payment credentials in v1 dashboard snapshots.

### GovernanceItem
```json
{
  "control_id": "string",
  "title": "string",
  "state": "NOT_IMPLEMENTED | NOT_VERIFIED | BLOCKED | ACCEPTED | UNKNOWN",
  "scope": "string",
  "evidence_refs": ["evidence-id"],
  "owner_role": "string or null",
  "updated_at": "ISO-8601 timestamp or null",
  "source_id": "string"
}
```

### AcceptanceRecord
```json
{
  "acceptance_id": "string",
  "gate_id": "string",
  "criterion": "string",
  "decision": "PENDING | ACCEPTED | REJECTED | WAIVED",
  "reviewer_role": "string or null",
  "evidence_refs": ["evidence-id"],
  "decided_at": "ISO-8601 timestamp or null",
  "source_id": "string"
}
```

## 5. Domain state boundaries

Booking state and payment state are separate dimensions.

Booking lifecycle:
- DRAFT
- OFFERED
- ACCEPTED
- CONFIRMED
- COMPLETED
- CANCELLED
- EXPIRED
- DISPUTED

Payment/reconciliation state:
- NOT_DUE
- DUE
- INVOICED
- PARTIALLY_RECEIVED
- RECEIVED
- PARTIALLY_PAID
- PAID
- DISPUTED
- UNKNOWN

Commission lifecycle dimensions:
- EARNED
- INVOICED
- RECEIVED
- PAID
- DISPUTED

A record may have booking_state=COMPLETED and payment_state=DUE. Do not collapse these into one status.

Availability:
- availability_state: AVAILABLE | UNAVAILABLE | UNKNOWN | EXPIRED
- valid_from and valid_until required for dated availability claims.
- Expired availability cannot qualify a property as currently available.

Introduction attribution:
- introduction_state: PROPOSED | REVIEWED | ACCEPTED | REJECTED
- causal_evidence_ref required before accepted attribution.
- INTRODUCES graph edge alone is insufficient.

## 6. Provenance and evidence

Every material assertion must carry:
- source_id
- source_record_id
- evidence_refs (zero only when the field is explicitly UNKNOWN)
- evidence_state
- observed_at / asserted_at where applicable
- valid_from / valid_until where time-bounded

Evidence references must resolve in the existing ALAGBARA evidence ledger. The dashboard does not store raw excerpts or copied page content.

## 7. Null, unknown and empty semantics

- null: value unavailable, not queried, or not applicable; include reason where possible.
- UNKNOWN: source explicitly cannot establish the state.
- empty array: source queried successfully and returned no matching records.
- NOT_CONNECTED: source adapter has not been connected.
- STALE: source data exists but is beyond its declared freshness threshold.
- PARTIAL: some records or fields were unavailable; disclose coverage.

Do not transform null into 0, UNKNOWN into NOT_STARTED, or NOT_CONNECTED into an empty result.

## 8. Initial source mapping

Engineering:
- GitHub repository/branch/commit endpoints → EngineeringSnapshot
- GitHub issues/PRs → engineering work items and roadmap evidence
- GitHub Actions workflow runs → ci_state and ci_checked_at when accessible

Commercial:
- No verified live VILLAWAY API/read model is currently established in this work package.
- Until connected, commercial values must be null with source status NOT_CONNECTED, or synthetic fixture data in SYNTHETIC mode.
- Never derive live commercial counts from GitHub issues.

ALAGBARA:
- Existing evidence ledger → evidence_refs and provenance
- Existing audit/decision records → acceptance and governance history where schema supports them

## 9. Versioning and compatibility

- Additive optional fields may be introduced within 1.x.
- Breaking enum/shape changes require a new major contract version.
- Unknown enum values must be rendered as UNKNOWN and preserved in raw source metadata for diagnosis.
- Snapshot consumers must tolerate absent optional fields.
- Contract fixtures and validation tests must be committed with the implementation.
