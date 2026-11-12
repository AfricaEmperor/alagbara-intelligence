// Public API of @alagbara/museops-core. Anything not exported here is internal.
export * from "./domain/common.js";
export * from "./domain/source.js";
export * from "./domain/signal.js";
export * from "./domain/observation.js";
export * from "./domain/subject.js";
export * from "./domain/externalIdentity.js";
export * from "./domain/observationSet.js";
export * from "./domain/pulse.js";
export * from "./domain/finding.js";
export * from "./domain/provenance.js";

export * from "./application/context.js";
export * from "./application/errors.js";
export * from "./application/ingestSignal.js";
export * from "./application/identityResolver.js";
export * from "./application/createObservationSet.js";
export * from "./application/createPulse.js";
export * from "./application/evidence.js";
export * from "./application/createFinding.js";

export { extractCreatorObservations } from "./capabilities/nlp/CreatorExtractor.js";
export { extractHashtagObservations } from "./capabilities/nlp/HashtagExtractor.js";
export { PATTERN_MATCH_CONFIDENCE } from "./capabilities/nlp/payload.js";

export const MUSEOPS_CONTRACT_VERSION = "0.1.0" as const;
