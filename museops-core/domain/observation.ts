import { z } from "zod";
import { ClaimSchema, IdSchema, TimestampSchema } from "./common.js";

/** Retained v0.1 vocabulary. Sprint 1 implements "nlp" only. */
export const CapabilitySchema = z.enum(["nlp", "ocr", "vision"]);
export type Capability = z.infer<typeof CapabilitySchema>;

/**
 * Numeric capability_confidence in [0, 1] (ADR-003, ADR-004). The legacy
 * enum spelling ("high" | "medium" | "low") is rejected: z.number() does not
 * coerce, so strings fail validation.
 */
export const CapabilityConfidenceSchema = z.number().finite().min(0).max(1);

export const ObservationSchema = z.strictObject({
  id: IdSchema,
  signal_id: IdSchema,
  subject_candidate: z.string().min(1).optional(),
  claim: ClaimSchema,
  capability: CapabilitySchema,
  capability_confidence: CapabilityConfidenceSchema,
  created_at: TimestampSchema,
});
export type Observation = z.infer<typeof ObservationSchema>;
