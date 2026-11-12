import { z } from "zod";
import { TrustLevelSchema } from "../domain/common.js";
import { SignalSchema } from "../domain/signal.js";
import type { Signal } from "../domain/signal.js";
import { ChannelSourceTypeSchema, SourceSchema, resolveChannelTrust } from "../domain/source.js";
import type { Source } from "../domain/source.js";
import { deepFreeze } from "./context.js";
import type { Context } from "./context.js";

export const RawInputSchema = z.strictObject({
  source: ChannelSourceTypeSchema,
  content: z.string().min(1),
  /** Required when the source type has no default trust (api_response). */
  channel_trust: TrustLevelSchema.optional(),
});
export type RawInput = z.infer<typeof RawInputSchema>;

export interface IngestResult {
  source: Source;
  signal: Signal;
}

/**
 * Create an immutable Source + Signal from raw input. The payload is stored
 * verbatim; no interpretation happens here.
 */
export function ingestSignal(rawInput: unknown, ctx: Context): IngestResult {
  const input = RawInputSchema.parse(rawInput);
  const now = ctx.now();
  const trust = resolveChannelTrust(input.source, input.channel_trust);

  const source = SourceSchema.parse({
    id: ctx.newId("src"),
    type_id: input.source,
    channel_trust: trust,
    created_at: now,
  });
  const signal = SignalSchema.parse({
    id: ctx.newId("sig"),
    source_id: source.id,
    payload: { content: input.content },
    captured_at: now,
  });
  return deepFreeze({ source, signal });
}
