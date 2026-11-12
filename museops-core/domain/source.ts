import { z } from "zod";
import { IdSchema, TimestampSchema, TrustLevelSchema } from "./common.js";
import type { TrustLevel } from "./common.js";

/**
 * MuseOps channel SourceType (schema-freeze-v0.1, patched in v0.1.1).
 *
 * NAMESPACE NOTE: this is the *signal channel* vocabulary. It is unrelated to
 * the `SourceType` Prisma enum in pulse-l1 (VENUE_SUBMITTED, PROMOTER_SUBMITTED,
 * ...), which describes who submitted curated data. The two must never be
 * unified; see docs/integration-contract.md for the explicit mapping policy.
 * The exported name is therefore `ChannelSourceType`.
 */
export const ChannelSourceTypeSchema = z.enum([
  "android_notification",
  "screenshot",
  "shared_image",
  "user_upload",
  "api_response",
]);
export type ChannelSourceType = z.infer<typeof ChannelSourceTypeSchema>;

/**
 * Founder-approved defaults (ADR-004). `null` means "explicitly unset":
 * api_response has no default until a concrete adapter exists, and no fallback
 * may be invented.
 */
export const DEFAULT_CHANNEL_TRUST: Readonly<Record<ChannelSourceType, TrustLevel | null>> =
  Object.freeze({
    android_notification: "high",
    user_upload: "medium",
    screenshot: "medium",
    shared_image: "low",
    api_response: null,
  });

export const SourceTypeDefinitionSchema = z.strictObject({
  id: IdSchema,
  type: ChannelSourceTypeSchema,
  /** Omitted when the default is explicitly unset (api_response). */
  default_channel_trust: TrustLevelSchema.optional(),
});
export type SourceTypeDefinition = z.infer<typeof SourceTypeDefinitionSchema>;

export const SourceSchema = z.strictObject({
  id: IdSchema,
  type_id: IdSchema,
  channel_trust: TrustLevelSchema,
  created_at: TimestampSchema,
});
export type Source = z.infer<typeof SourceSchema>;

export class ChannelTrustUnsetError extends Error {
  constructor(readonly sourceType: ChannelSourceType) {
    super(
      `No default channel_trust is defined for source type "${sourceType}"; ` +
        `an explicit channel_trust must be supplied. No fallback is applied.`,
    );
    this.name = "ChannelTrustUnsetError";
  }
}

/** Default trust for a type, or `undefined` when explicitly unset. */
export function defaultChannelTrust(type: ChannelSourceType): TrustLevel | undefined {
  return DEFAULT_CHANNEL_TRUST[type] ?? undefined;
}

/**
 * Resolve the channel_trust for a new Source. An explicit override always wins;
 * otherwise the type default is used; otherwise this throws (never guesses).
 */
export function resolveChannelTrust(type: ChannelSourceType, override?: TrustLevel): TrustLevel {
  const explicit = override === undefined ? undefined : TrustLevelSchema.parse(override);
  const resolved = explicit ?? defaultChannelTrust(type);
  if (resolved === undefined) throw new ChannelTrustUnsetError(type);
  return resolved;
}

export function sourceTypeDefinition(type: ChannelSourceType, id: string = type): SourceTypeDefinition {
  const trust = defaultChannelTrust(type);
  return SourceTypeDefinitionSchema.parse(
    trust === undefined ? { id, type } : { id, type, default_channel_trust: trust },
  );
}
