import type { Context } from "../../application/context.js";
import { normalizeHashtag } from "../../application/identityResolver.js";
import { ObservationSchema } from "../../domain/observation.js";
import type { Observation } from "../../domain/observation.js";
import type { Signal } from "../../domain/signal.js";
import { PATTERN_MATCH_CONFIDENCE, textContent } from "./payload.js";

const HASHTAG = /#[\p{L}\p{N}_]+/gu;

/** capability = "nlp". One observation per distinct normalized hashtag in the text. */
export function extractHashtagObservations(signal: Signal, ctx: Context): Observation[] {
  const text = textContent(signal);
  if (text === undefined) return [];
  const seen = new Set<string>();
  const out: Observation[] = [];
  for (const raw of text.match(HASHTAG) ?? []) {
    const normalized = normalizeHashtag(raw);
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    out.push(
      ObservationSchema.parse({
        id: ctx.newId("obs"),
        signal_id: signal.id,
        subject_candidate: normalized,
        claim: { type: "hashtag", value: normalized },
        capability: "nlp",
        capability_confidence: PATTERN_MATCH_CONFIDENCE,
        created_at: ctx.now(),
      }),
    );
  }
  return out;
}
