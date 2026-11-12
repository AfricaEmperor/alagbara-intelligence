import { z } from "zod";
import { ClaimSchema, EvidenceStrengthSchema, IdSchema } from "./common.js";

export const ContradictionSchema = z.strictObject({
  id: IdSchema,
  observation_ids: z.array(IdSchema).min(2),
  description: z.string().min(1),
});
export type Contradiction = z.infer<typeof ContradictionSchema>;

/**
 * "Finding confidence" is expressed solely as `evidence.evidence_strength`.
 * No generic `confidence` field exists anywhere (ADR-001/003); strict objects
 * reject it if supplied.
 */
export const FindingSchema = z.strictObject({
  id: IdSchema,
  pulse_id: IdSchema,
  claim: ClaimSchema,
  evidence: z.strictObject({
    source_types: z.array(z.string().min(1)).min(1),
    evidence_strength: EvidenceStrengthSchema,
    contradictions: z.array(ContradictionSchema),
  }),
});
export type Finding = z.infer<typeof FindingSchema>;
