import { z } from "zod";
import { IdSchema } from "./common.js";

/**
 * Provenance is a *derived* audit record (a resolved chain), not a stored
 * field on any entity. It answers: why does this Finding exist?
 * Finding → Pulse → ObservationSet → Observation → Signal → Source → SourceType.
 */
export const ProvenanceChainSchema = z.strictObject({
  finding_id: IdSchema,
  pulse_id: IdSchema,
  observation_set_ids: z.array(IdSchema).min(1),
  observation_ids: z.array(IdSchema).min(1),
  signal_ids: z.array(IdSchema).min(1),
  source_ids: z.array(IdSchema).min(1),
  source_types: z.array(IdSchema).min(1),
});
export type ProvenanceChain = z.infer<typeof ProvenanceChainSchema>;
