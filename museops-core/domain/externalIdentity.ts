import { z } from "zod";
import { IdSchema } from "./common.js";

export const ExternalIdentitySchema = z.strictObject({
  id: IdSchema,
  subject_id: IdSchema,
  platform: z.enum(["tiktok"]),
  identifier_type: z.enum(["account_id", "handle", "normalized_hashtag"]),
  value: z.string().min(1),
  identity_link_status: z.enum(["observed", "confirmed", "linked"]),
});
export type ExternalIdentity = z.infer<typeof ExternalIdentitySchema>;
