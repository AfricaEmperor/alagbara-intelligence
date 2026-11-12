import { z } from "zod";

/** Opaque, non-empty identifier. Prefix conventions are advisory, not validated. */
export const IdSchema = z.string().min(1);

/** ISO 8601 UTC timestamp with a `Z` designator, e.g. 2026-08-24T10:00:00Z. */
export const TimestampSchema = z.iso.datetime();

/** channel_trust vocabulary (ADR-003). Describes a channel, never an observation. */
export const TrustLevelSchema = z.enum(["high", "medium", "low"]);
export type TrustLevel = z.infer<typeof TrustLevelSchema>;

/** evidence_strength vocabulary (ADR-003). Describes a Finding, never a channel. */
export const EvidenceStrengthSchema = z.enum(["high", "medium", "low"]);
export type EvidenceStrength = z.infer<typeof EvidenceStrengthSchema>;

export const ClaimSchema = z.strictObject({
  type: z.string().min(1),
  value: z.unknown(),
});
export type Claim = z.infer<typeof ClaimSchema>;

export const TimeframeSchema = z
  .strictObject({ start: TimestampSchema, end: TimestampSchema })
  .refine((t) => Date.parse(t.start) <= Date.parse(t.end), {
    message: "timeframe.start must not be after timeframe.end",
  });
export type Timeframe = z.infer<typeof TimeframeSchema>;
