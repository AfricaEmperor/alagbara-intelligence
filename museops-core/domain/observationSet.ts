import { z } from "zod";
import { IdSchema, TimeframeSchema } from "./common.js";

export const ObservationSetSchema = z.strictObject({
  id: IdSchema,
  subject_id: IdSchema,
  observation_ids: z.array(IdSchema).min(1),
  timeframe: TimeframeSchema,
});
export type ObservationSet = z.infer<typeof ObservationSetSchema>;
