import { z } from "zod";
import { IdSchema, TimestampSchema } from "./common.js";

export const SubjectSchema = z.strictObject({
  id: IdSchema,
  type: z.enum(["creator", "hashtag"]),
  status: z.enum(["new", "active", "verified"]),
  created_at: TimestampSchema,
});
export type Subject = z.infer<typeof SubjectSchema>;
