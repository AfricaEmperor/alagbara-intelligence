# VILLAWAY Command Center — Dashboard Specification

Status: v1 specification; isolated implementation target
Repository: AfricaEmperor/alagbara-intelligence
Branch: feat/villaway-001-acquisition-intelligence
Surface: read-only operational dashboard
Audience: founder / mission operator
Primary decision: what must happen next to produce one attributable, completed, paid hospitality transaction?

## 1. Product boundary

The Command Center is an operational read model. It is not a new CRM, booking engine, evidence store, task manager, or source of truth.

Authoritative boundaries:
- Engineering delivery: GitHub branch, commits, issues, pull requests, workflow/test runs.
- Commercial execution: VILLAWAY domain records for buyers, requirements, properties, matches, introductions, bookings and commission/reconciliation.
- Evidence and operational memory: existing ALAGBARA / SCOUT evidence ledger and audit trail.
- Dashboard: read-only projection of those sources, with source links and freshness metadata.

Never infer a commercial lifecycle state from a GitHub issue state. Never infer a confirmed booking from a match or introduction. Never infer commission entitlement from an INTRODUCES relationship alone.

## 2. Users and operating cadence

Primary user: mission owner reviewing execution and deciding the next intervention.
Use cadence: daily operational review and milestone-gate review.
Initial release is single-operator, read-only, with no public access and no external actions.

## 3. Information architecture

### A. Mission overview (default landing view)
- Mission: VILLAWAY-001
- Current phase and active work package
- Next gate and its explicit acceptance criteria
- Critical blocker(s), severity, owner/role, last updated, unblock condition
- Separate engineering and commercial status summaries
- Last successful source refresh and per-source freshness

### B. Roadmap
- Dependency graph: specification/data contract → dashboard build → validation; separately show VILLAWAY work packages WP-A through WP-E.
- Gate states: NOT_STARTED, IN_PROGRESS, BLOCKED, READY_FOR_REVIEW, ACCEPTED.
- A gate is accepted only when its acceptance evidence is attached.
- Show dependencies and blocked-by links; do not calculate a blended completion percentage.

### C. Engineering
- Branch and base branch
- Current head commit and latest relevant commits
- Open issues / pull requests associated with VILLAWAY
- CI/test status and run timestamp, when available
- Changed-file count and review status, when available
- Missing or unavailable GitHub evidence is displayed as UNKNOWN, not green.

### D. Commercial pipeline
Show distinct stage counts and actionable records for:
1. Buyer/prospect
2. Requirement
3. Qualification
4. Property/operator verification
5. Property match
6. Human-reviewed introduction
7. Booking
8. Commission attribution
9. Reconciliation

A count is shown only when backed by source records and a defined population. Empty source = “No records yet”, not zero commercial progress. Distinguish unknown, stale, expired, disputed and verified states.

### E. Risk and governance
- Security/tenant isolation readiness
- Authenticated actor and authorization status
- Personal-data controls
- Source permissions and freshness
- Open stop conditions and unresolved risks
- Explicitly distinguish NOT_IMPLEMENTED, NOT_VERIFIED, BLOCKED and ACCEPTED.

### F. Acceptance ledger
For each gate: criterion, required evidence, evidence reference, reviewer, decision, timestamp and unresolved exception. This is the audit trail for claims made by the dashboard.

## 4. Core interaction

- Global filters: workstream (Engineering / Commercial / Governance), gate, state and time window where supported.
- Selecting a card/row opens a detail panel with source, status rationale, evidence links, owner and next action.
- Roadmap nodes reveal dependencies and acceptance evidence.
- Source links open the authoritative GitHub record or ALAGBARA evidence record.
- No create/update/delete controls in v1.
- No automated outreach, booking, payment, external messaging or delegation.

## 5. State and metric rules

- Use explicit enums from the data contract.
- UNKNOWN is not equivalent to NOT_STARTED.
- STALE is a freshness overlay, not a lifecycle state.
- BLOCKED requires a recorded blocker and unblock condition.
- ACCEPTED requires acceptance evidence and a reviewer/decision record.
- Show timestamps with timezone.
- Show counts only with source coverage and as-of timestamp.
- Do not show percentage completion unless the numerator, denominator, gate weights (if any), and acceptance rules are explicitly defined. v1 intentionally omits aggregate percentage.
- Do not aggregate booking state with payment state.
- Commission states EARNED, INVOICED, RECEIVED and PAID remain separate.

## 6. Data-source adapters

v1 adapters are read-only:
- GitHub adapter: repository, branch, commits, issues, PRs and CI evidence. Missing connector scopes or unavailable endpoints produce UNKNOWN with an error/freshness note.
- VILLAWAY adapter: domain records when the domain API/read model exists. Until then the commercial panel must show “Source not connected” or “No records yet” according to verified source state; never fabricate fixtures as real.
- ALAGBARA evidence adapter: evidence references, provenance, audit events and acceptance decisions. Do not copy raw personal data into dashboard snapshots.

The initial build may use a clearly labelled static contract fixture for layout verification only. Fixture mode must be visibly marked DEVELOPMENT / SYNTHETIC and must never be mistaken for live operational data.

## 7. Security and privacy

- Read-only by default.
- No secrets or credentials in browser bundles, source control, fixtures or logs.
- Server-side authorization is mandatory before connecting real commercial or personal data.
- Enforce tenant scoping at the source/API, not with client-side filtering.
- Do not expose personal contact details unless the user's role, purpose and retention policy authorize them.
- Audit access to sensitive records when the source supports it.
- Until access controls are verified, use synthetic-only fixtures.
- Do not connect production Supabase or migrate production data as part of this dashboard task.

## 8. Visual and responsive requirements

- Dense but legible command-centre layout; prioritize exceptions and next actions over decoration.
- Clear separation of Engineering, Commercial and Governance workstreams.
- Neutral status palette; color must not be the sole state indicator.
- Responsive layout: wide desktop first, usable tablet/mobile stacked layout.
- Accessible headings, keyboard focus, semantic tables, sufficient contrast and explicit loading/empty/error states.
- No animated charts or ornamental metrics.

## 9. Acceptance criteria

1. Opening view shows current phase, next gate and critical blocker without interaction.
2. Engineering and commercial status are visually and semantically separate.
3. Every displayed operational claim has a source reference and as-of timestamp.
4. Unknown, stale, blocked, disputed and accepted are distinguishable.
5. No synthetic fixture is presented as real data.
6. No blended completion percentage or unsupported KPI appears.
7. Booking, payment and commission states are not conflated.
8. Dashboard has no write or external-action capability in v1.
9. Sensitive data is absent from fixtures and client bundles.
10. Empty, loading, partial-source and error states are implemented.
11. Desktop and mobile layouts remain usable.
12. Build and automated checks pass in the repository's supported environment before claiming validation.

## 10. Explicit non-goals

No new SaaS purchase, no Buildy, no new CRM, no parallel evidence store, no production deployment, no production database mutation, no external contact, no live booking/payment action, and no merge to the base branch without separate approval.
