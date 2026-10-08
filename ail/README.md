# AIL — ALAGBARA Intelligence Language

Version: 0.2.0
Status: experimental runtime contract

AIL is the canonical, evidence-aware representation exchanged between ALAGBARA intelligence stages.

It is not a replacement for SCOUT, PULSE, ANA, or FLYNN. It is the typed language/contract that lets those capabilities exchange intelligence without collapsing observation, inference, uncertainty, provenance, or authorization into one undifferentiated text blob.

## Core laws
1. NO CLAIM WITHOUT PROVENANCE
2. NO EDGE WITHOUT PROVENANCE
3. OBSERVED != DERIVED
4. UNKNOWN != FALSE
5. UNVERIFIED != TRUE
6. CONFIDENCE != INTENT
7. DECAY != DELETION
8. DECISION != AUTHORIZATION
9. PROPOSAL != EXECUTION
10. CONTRADICTION MUST REMAIN REPRESENTABLE

## Epistemic states
- observed: directly represented by captured evidence
- derived: reasoned from observed material
- unverified: asserted or signalled but not sufficiently established
- unknown: materially missing information
- contradiction: incompatible observations/claims that must remain visible

## Runtime envelope
An AIL document has five sections:
- request: what the intelligence work is about
- evidence: source observations with provenance
- claims: typed statements tied to evidence
- reasoning: derived interpretation and uncertainty
- action: proposed/authorized/executed action state

## Minimal statement vocabulary
OBSERVE  source-backed observation
ASSERT   claim presented as a statement
DERIVE   conclusion produced from other claims
UNKNOWN  explicit knowledge gap
CONFLICT incompatible claims/observations
RELATE   relationship between entities; requires provenance
DECIDE   proposed decision; never implies authorization
AUTHORIZE explicit permission for an action
ACT      execution request/result

## Current integration
SCOUT -> evidence ledger -> ANA -> AIL envelope -> Ask BIG UI

The first runtime integration intentionally uses the existing API payload and does not require a database migration.

## Important implementation constraint
Current ANA facts do not yet carry claim-level evidence references. AIL v0.2 therefore records the evidence set used by the reasoning stage rather than pretending to have fine-grained claim provenance. Claim-level provenance is the next tightening step.
## Surface syntax

The first executable surface syntax is implemented in ail/parser.js and documented in ail/grammar.ebnf.

A valid operational chain is:

OBSERVE -> ASSERT -> DERIVE / UNKNOWN -> RELATE -> DECIDE -> AUTHORIZE -> EXECUTE

The boundary is deliberate: intelligence can formulate a decision, but only explicit authorization can cross into execution.
