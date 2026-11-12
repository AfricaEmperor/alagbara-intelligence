import { z } from "zod";
import { IdSchema, TimeframeSchema } from "./common.js";

/** Memory placeholder: v0.1 stores comparison structure only. */
export const HistoricalComparisonSchema = z.strictObject({
  previous_pulse_id: IdSchema.optional(),
  changes: z.array(z.unknown()).optional(),
});
export type HistoricalComparison = z.infer<typeof HistoricalComparisonSchema>;

export const PulseSchema = z.strictObject({
  id: IdSchema,
  subject_id: IdSchema,
  observation_set_ids: z.array(IdSchema).min(1),
  timeframe: TimeframeSchema,
  historical_comparison: HistoricalComparisonSchema.optional(),
});
export type Pulse = z.infer<typeof PulseSchema>;
