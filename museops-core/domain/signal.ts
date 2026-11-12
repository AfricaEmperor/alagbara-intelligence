import { z } from "zod";
import { IdSchema, TimestampSchema } from "./common.js";

/** Immutable incoming event. Archived; never deleted after processing. */
export const SignalSchema = z.strictObject({
  id: IdSchema,
  source_id: IdSchema,
  payload: z.unknown(),
  captured_at: TimestampSchema,
});
export type Signal = z.infer<typeof SignalSchema>;
