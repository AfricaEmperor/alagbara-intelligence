MuseOps Schema Freeze v0.1

Patch level: v0.1.1 (ADR-004). See "Changelog and Migration Notes" at the end of this document.

Contract-boundary note (v0.1.1)

Fields typed "Date" below are serialized as ISO 8601 UTC strings with a "Z"
designator (for example 2026-08-24T10:00:00Z) in all contracts and in the
TypeScript implementation. Timeframes require start <= end.

Purpose

This document defines the first stable domain model of MuseOps.

The objective of v0.1 is to establish a reliable provenance chain:

Source
  ↓
Signal
  ↓
Observation
  ↓
ObservationSet
  ↓
Pulse
  ↓
Finding

Every Finding must be traceable back to its original Signal.

This schema intentionally avoids inference, business logic, and automated reasoning.

---

Core Design Rules

Observation ≠ Interpretation

An Observation represents something detected.

A Finding represents a structured statement supported by evidence.

No component in the core should transform an observation into an unsupported conclusion.

---

Provenance is Mandatory

Every object created from external information must preserve its origin.

The chain must remain auditable:

Finding
 ↓
Pulse
 ↓
ObservationSet
 ↓
Observation
 ↓
Signal
 ↓
Source
 ↓
SourceType

---

Source Model

SourceType

A stable reference describing a signal channel.

type SourceType = {
  id: string;

  type:
    | "android_notification"
    | "screenshot"
    | "shared_image"
    | "user_upload"
    | "api_response";

  default_channel_trust?:
    | "high"
    | "medium"
    | "low";
}

"default_channel_trust" represents the intrinsic reliability of the channel.

It is not the confidence of an individual observation.

Defaults (ADR-004):

| type | default_channel_trust |
|---|---|
| android_notification | high |
| user_upload | medium |
| screenshot | medium |
| shared_image | low |
| api_response | (explicitly unset) |

"api_response" has no default until a concrete adapter exists. The field is
omitted for that type, and creating a Source of that type requires an explicit
channel_trust. No fallback value is ever applied.

Namespace: this SourceType is the MuseOps signal-channel vocabulary. It is
unrelated to the "SourceType" Prisma enum in pulse-l1 (who submitted curated
data). The two are never unified; the TypeScript export is "ChannelSourceType".

---

Source

A concrete source instance.

type Source = {
  id: string;

  type_id: string;

  channel_trust:
    | "high"
    | "medium"
    | "low";

  created_at: Date;
}

"channel_trust" describes the source channel.

It does not describe evidence strength.

---

Signal Model

A Signal is an immutable incoming event.

type Signal = {
  id: string;

  source_id: string;

  payload: unknown;

  captured_at: Date;
}

Signals are archived.

They are never deleted after processing.

---

Capability Model

Capabilities describe the method used to produce an observation.

Retained v0.1 vocabulary (Sprint 1 implements "nlp" only; "ocr" and "vision"
are valid values with no implementation):

type Capability =
  | "nlp"
  | "ocr"
  | "vision";

Capabilities are categories, not business entities.

They do not contain configuration or logic.

---

Observation Model

An Observation represents a detected fact.

type Observation = {
  id: string;

  signal_id: string;

  subject_candidate?: string;

  claim: {
    type: string;
    value: unknown;
  };

  capability: Capability;

  capability_confidence: number; // 0.0 to 1.0 inclusive

  created_at: Date;
}

"capability_confidence" measures the confidence of the producing capability.

It is numeric (0.0 to 1.0, finite), as specified by ADR-003 and ADR-001. The
legacy enum spelling ("high" | "medium" | "low") is invalid and is rejected.

It is not evidence strength.

---

Subject Model

A Subject represents an internal identity.

type Subject = {
  id: string;

  type:
    | "creator"
    | "hashtag";

  status:
    | "new"
    | "active"
    | "verified";

  created_at: Date;
}

Sprint 1 supported subject types:

- creator
- hashtag

Other subject types are deferred.

---

External Identity Model

ExternalIdentity connects a Subject to an external platform identity.

type ExternalIdentity = {
  id: string;

  subject_id: string;

  platform:
    | "tiktok";

  identifier_type:
    | "account_id"
    | "handle"
    | "normalized_hashtag";

  value: string;

  identity_link_status:
    | "observed"
    | "confirmed"
    | "linked";
}

---

Identity Resolution Rules

Creator

Resolution priority:

1. account_id exact match
2. handle exact match

Unsupported in v0.1:

- username rename detection
- cross-platform fusion
- automatic merging

---

Hashtag

Resolution:

normalized_hashtag =
lowercase(remove("#"))

Examples:

#Baddie
#baddie
#BADDIE

resolve to:

baddie

---

ObservationSet Model

An ObservationSet groups observations belonging to the same analytical unit.

type ObservationSet = {
  id: string;

  subject_id: string;

  observation_ids: string[];

  timeframe: {
    start: Date;
    end: Date;
  };
}

---

Pulse Model

Pulse aggregates observations over time.

type Pulse = {
  id: string;

  subject_id: string;

  observation_set_ids: string[];

  timeframe: {
    start: Date;
    end: Date;
  };

  historical_comparison?: HistoricalComparison;
}

---

HistoricalComparison

Memory capability placeholder.

v0.1 stores comparison structure only.

No automatic recognition exists.

type HistoricalComparison = {
  previous_pulse_id?: string;

  changes?: unknown[];
}

---

Finding Model

A Finding is the structured output of the core pipeline.

type Finding = {
  id: string;

  pulse_id: string;

  claim: {
    type: string;
    value: unknown;
  };

  evidence: {
    source_types: string[];

    evidence_strength:
      | "high"
      | "medium"
      | "low";

    contradictions: Contradiction[];
  };
}

---

Evidence Model

Three separate confidence dimensions

MuseOps intentionally separates:

Channel Trust

Question:

«How reliable is this source type?»

Example:

Android notification = high.

---

Capability Confidence

Question:

«How confident is the extraction method?»

Example:

NLP parser confidence.

---

Evidence Strength

Question:

«How strongly is this Finding supported by independent evidence?»

Example:

Multiple independent sources agree.

---

Contradiction Model

type Contradiction = {
  id: string;

  observation_ids: string[];

  description: string;
}

Contradictions are preserved.

They are not automatically resolved.

---

Out of Scope v0.1

The following are intentionally excluded:

- Vision Agent
- OCR implementation
- Audio analysis
- Memory Vision recognition
- Ana reasoning engine
- Flynn orchestration
- Business scoring
- Automatic collaboration detection
- Identity fusion

---

Schema Change Policy

Any modification to this schema requires:

1. An Architecture Decision Record (ADR)
2. Impact analysis
3. Migration strategy if persisted data is affected

The purpose of this freeze is not to prevent evolution.

It is to prevent accidental complexity.


---

Changelog and Migration Notes

v0.1.1 (ADR-004)

1. capability_confidence: enum -> number in [0, 1].
   Rationale: ADR-003 (Accepted) and ADR-001 both specify numeric values (example
   0.92); the v0.1 freeze text contradicted them. The freeze is corrected to the
   accepted ADRs.
   Migration: no persisted MuseOps data existed at the time of this patch (no
   MuseOps implementation was present in any repository). Any externally held
   data using "high" | "medium" | "low" must be re-expressed numerically by the
   producing capability; the core does NOT convert enum values to numbers,
   because that mapping would be an invented calibration.
   Compatibility: breaking relative to the v0.1 text; non-breaking relative to
   ADR-003.

2. default_channel_trust: required -> optional; values assigned for four types
   (table above); api_response explicitly unset.
   Compatibility: widening (a consumer that treats the field as required will
   break on api_response). Consumers must handle absence.

3. Date serialization pinned to ISO 8601 UTC strings (clarification, not a
   semantic change).

4. Capability enum unchanged (nlp | ocr | vision). Clarification that Sprint 1
   implements nlp only.

5. Terminology: "Finding confidence" is evidence_strength. No generic
   "confidence" field exists on any object; strict schemas reject it.
   "Provenance" is a derived chain (ProvenanceChain), not a stored field.

Contract version: package/contract 0.1.0 corresponds to this schema level (v0.1.1).
