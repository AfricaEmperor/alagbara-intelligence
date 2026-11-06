# ORACLE Decision Contract v0.1

**Contract ID:** `alagbara.oracle.decision.v1`  
**Status:** PROPOSED — design contract, not yet runtime-enforced  
**Canonical home:** `AfricaEmperor/alagbara-intelligence`  
**Scope:** Cross-domain, multi-market ALAGBARA decision support  
**Initial consumers:** SCOUT, MUSEOPS, PULSE, ANA, FLYNN and authorized human operators  
**Execution authority:** Human approval through the applicable CONTROL policy; Zuberi may execute only an approved handoff within its granted permissions.

## 1. Purpose

ORACLE converts traceable intelligence into explicit, reviewable decision proposals. It must preserve the distinction between observed evidence, interpretation, recommendation, authorization and execution.

ORACLE is cross-domain. It is not a PULSE feature, a repository-specific service, an autonomous approval authority, or a substitute for domain owners.

## 2. Decision lifecycle

1. **Observe:** accept evidence from registered ALAGBARA sources and domain systems.
2. **Validate:** check provenance, freshness, integrity, relevance, access rights and conflicts.
3. **Interpret:** state the inference and uncertainty separately from source facts.
4. **Recommend:** propose an action, alternatives and expected outcomes.
5. **Authorize:** request the exact approval required by policy.
6. **Handoff:** issue a bounded execution package only after authorization.
7. **Verify:** compare observed execution results with expected outcomes.
8. **Learn:** append the decision, approval, execution and outcome to institutional memory.

A recommendation is not an instruction. A handoff is not permission to exceed the approved scope.

## 3. Canonical decision envelope

Every ORACLE decision proposal must carry:

| Field | Requirement | Meaning |
|---|---|---|
| `contract_version` | Required | Version of this contract |
| `decision_id` | Required, unique | Stable identifier for the decision |
| `created_at` | Required | UTC timestamp of proposal creation |
| `status` | Required | `draft`, `proposed`, `awaiting_authorization`, `authorized`, `rejected`, `handed_off`, `executing`, `verified`, `closed`, `blocked`, or `superseded` |
| `domain` | Required | Business/operational domain, independent of repository |
| `market` | Required | Market scope; support one, multiple, or `global` |
| `decision_context` | Required | Question to resolve, objective, constraints and time horizon |
| `evidence[]` | Required, at least one | Traceable facts, source, timestamps, confidence and limitations |
| `analysis` | Required | Inference, assumptions, counter-evidence and uncertainty |
| `confidence` | Required | Calibrated score, band, method and explanation |
| `recommendation` | Required | Specific proposed action and rationale |
| `alternatives[]` | Required | At least one alternative, including defer/no-action where relevant |
| `expected_impact` | Required | Outcomes, metrics, direction, horizon and assumptions |
| `risks[]` | Required | Risk, likelihood, severity, mitigation and owner |
| `authorization` | Required | Required authority, scope, approval state and conditions |
| `execution_handoff` | Required | Bounded task package or explicit `not_ready` |
| `review_and_expiry` | Required | Review time, expiry and supersession rules |
| `audit` | Required | Actor/system, timestamps, immutable event references |

## 4. Evidence contract

Each evidence item must contain:
- `evidence_id`: stable reference.
- `claim`: concise factual statement supported by the item.
- `source`: system, source type, source identifier and URI/reference where available.
- `observed_at`: when the underlying event or fact was observed.
- `captured_at`: when ALAGBARA acquired it.
- `market` and `domain`: applicability.
- `evidence_type`: `direct_observation`, `first_party_record`, `third_party_report`, `derived_metric`, `expert_input`, or `assumption`.
- `reliability`: source reliability assessment and its basis.
- `limitations`: missingness, sampling, bias, access restrictions, freshness or verification gaps.
- `content_hash` or immutable source-event reference where supported.

Evidence must not be silently upgraded from assumption or inference into observed fact. Conflicting evidence must be retained and explicitly reconciled or marked unresolved. Sensitive personal data must be minimized and handled under applicable access policy.

## 5. Confidence contract

Confidence is an epistemic assessment of the recommendation's support, not a probability of business success unless a calibrated predictive model explicitly defines it as such.

Required fields:
- `score`: numeric value from 0 to 1, when a defensible scoring method exists; otherwise null.
- `band`: `low`, `moderate`, `high`, or `unrated`.
- `method`: named rubric/model and version, or `qualitative`.
- `rationale`: why the score/band is warranted.
- `key_uncertainties[]`: unresolved facts that could change the decision.
- `calibration_status`: `validated`, `provisional`, or `not_calibrated`.

Do not fabricate numerical precision. If evidence is thin, stale, biased or contradictory, lower confidence or abstain. High confidence never overrides authorization.

## 6. Recommendation contract

A recommendation must state:
- The action in imperative, testable language.
- The intended beneficiary and business outcome.
- Why this option is preferred over alternatives.
- Preconditions and dependencies.
- Scope, market and time window.
- What must not be done.
- A measurable success criterion.
- A stop/rollback condition.

ORACLE must be able to recommend `defer`, `collect_more_evidence`, or `no_action`. It must not force an action when evidence or authority is insufficient.

## 7. Expected impact contract

Impact must be expressed as an outcome hypothesis, not a guaranteed result. Include:
- Metric or observable outcome.
- Baseline and baseline date, or `unknown`.
- Expected direction and range only where defensible.
- Measurement window.
- Assumptions and attribution limitations.
- Leading indicators and guardrail metrics.
- Owner/system responsible for measuring the outcome.

Financial, user, safety, reputation, compliance and operational impacts should be considered when material.

## 8. Risk contract

Each material risk records:
- Risk description and category.
- Likelihood and severity using a named qualitative or quantitative scale.
- Evidence and uncertainty supporting the assessment.
- Mitigation and contingency.
- Accountable risk owner.
- Residual risk after mitigation.
- Whether the risk requires escalation or blocks handoff.

Unmitigated critical risks block authorization and execution.

## 9. Authorization contract

Authorization is explicit, scoped, attributable and time-bounded. It records:
- `required_authority`: role or named approval authority from the active governance policy.
- `policy_reference`: exact policy/rule version.
- `scope`: permitted actions, resources, markets, environment and limits.
- `state`: `not_requested`, `pending`, `approved`, `rejected`, `expired`, or `revoked`.
- `approved_by`, `approved_at`, `expires_at`: required for approval.
- `conditions[]`: constraints that must be carried into execution.
- `evidence_reference`: approval event or audit record.

No implied consent, self-approval, approval by silence, or inherited authorization. Any material change in action, scope, risk, market, data class or environment invalidates the existing approval and requires reassessment.

## 10. Execution handoff contract

A handoff is created only when authorization is approved and all preconditions are met. Otherwise use `state: not_ready` and list blockers.

A ready handoff contains:
- `handoff_id` and `decision_id`.
- `executor_role` and verified `executor_identity` (never infer an identity from a role name).
- `task`: one bounded, testable objective.
- `allowed_actions[]` and `prohibited_actions[]`.
- `repositories[]`, resources, branches and environment scope where applicable.
- `inputs[]` with immutable evidence/contract references.
- `deliverables[]` and acceptance criteria.
- `validation_steps[]` with required evidence.
- `rollback_or_containment`.
- `approval_reference`, `issued_at`, `expires_at`.
- `reporting_destination` and escalation owner.

Zuberi is a cross-repository execution role. It is not automatically a GitHub identity or runtime. The handoff must resolve Zuberi to a verified, authorized execution endpoint and the actual permissions granted to that endpoint. If that mapping is missing, handoff remains `not_ready`.

## 11. Domain and market neutrality

- `domain` identifies the business capability or operating domain (for example nightlife, travel/hospitality, commerce, finance or institutional operations).
- `market` identifies geographic or commercial market scope (for example Lagos, Cotonou, Abuja, Benin, Nigeria or global).
- Repository names are implementation metadata, not domain identity.
- One decision may span multiple domains or markets, but each impact, risk and authorization must state its applicability.
- Parallel-market strategies must not silently turn one market into a later pilot. If a market is excluded, the decision must state why and who authorized the exclusion.

## 12. State machine and invariants

Allowed progression:

`draft → proposed → awaiting_authorization → authorized → handed_off → executing → verified → closed`

Alternative terminal or interrupt states: `rejected`, `blocked`, `superseded`. Approval may expire or be revoked before execution; the proposal returns to authorization review. Execution failures require a new decision or approved recovery path.

Invariants:
1. No evidence, no decision proposal.
2. No provenance, no evidence acceptance.
3. No explicit authorization, no consequential execution.
4. No verified executor identity and scope, no handoff.
5. No acceptance evidence, no completion claim.
6. No audit event, no state transition.
7. No silent mutation of a decision after approval; revisions create a new version and preserve history.
8. ORACLE cannot approve its own recommendation or grant permissions.
9. Zuberi cannot broaden the approved scope.
10. Domain systems remain authoritative for their own operational records.

## 13. Initial PULSE example (illustrative, not live evidence)

- **Domain:** nightlife
- **Markets:** Lagos and Cotonou
- **Question:** Which DJ/creator acquisition cohort should the team prioritize next?
- **Evidence:** verified creator/venue/event records with source, capture time, market, reach/engagement provenance and verification status. If unavailable, record the gap rather than inventing cohort metrics.
- **Confidence:** unrated until source coverage and measurement quality are assessed.
- **Recommendation:** prepare a bounded acquisition experiment only after evidence sufficiency is established.
- **Expected impact:** improved qualified creator coverage and attributable event-content supply; baseline and target remain unknown until measured.
- **Risk:** biased platform coverage, duplicate identities, stale event information, consent and outreach constraints.
- **Authorization:** human approval for outreach, account access, spend or publication.
- **Execution handoff:** Zuberi receives a scoped task only after identity, endpoint, permissions and approval are verified.

## 14. Implementation boundary

This document defines the normative contract. A first non-production runtime slice now exists under `oracle_runtime/`: JSON Schema validation with cross-field governance checks, synthetic fixtures, a SQLite append-only hash-chained event ledger, a read-only SCOUT observation importer, a read-only adapter for the Power Enterprise Control Room authority policy and repository registry, a separate fail-closed CONTROL approval-provider port, a verified-executor registry port, and a MEMORY outcome projection port.

The runtime does **not** establish that ORACLE is production-ready. No authoritative CONTROL approval provider or live approval endpoint, Zuberi endpoint, external MEMORY sink, live database, production migration, scoring model, scheduler, or production integration is connected. The read-only CONTROL policy reader evaluates the repository registry and deny-by-default policy; it does not grant mutation authority. The local SQLite ledger is not tamper-proof against an administrator able to replace its file. CI has been registered, but the first GitHub Actions run failed before job steps started (runner id 0); tests have not yet been observed executing.

Remaining stages:
1. Validate this contract with domain owners and governance owner.
2. Obtain successful runtime CI execution and resolve runner startup failures.
3. Add non-production persistence integration with managed storage and independent access controls.
4. Connect the read-only SCOUT adapter to a verified observation feed.
5. Register the authoritative CONTROL policy provider and verify real approval events.
6. Register Zuberi's actual runtime identity, endpoint and least-privilege permissions.
7. Connect the authorized MEMORY sink, then add outcome reconciliation and confidence calibration.

## 15. Versioning

- Additive optional fields: minor version.
- Breaking required-field, state-machine or authorization changes: major version.
- Clarifications without behavior change: patch revision.
- Every stored decision retains the exact contract version used at creation.
