import type { Context } from "../../application/context.js";
import { ObservationSchema } from "../../domain/observation.js";
import type { Observation } from "../../domain/observation.js";
import type { Signal } from "../../domain/signal.js";
import { PATTERN_MATCH_CONFIDENCE, textContent } from "./payload.js";

const PATTERNS: ReadonlyArray<{ re: RegExp; event_type: string }> = [
  { re: /^\s*(.+?)\s+is LIVE on TikTok\s*$/i, event_type: "live_started" },
  { re: /^\s*(.+?)\s+posted an update\s*$/i, event_type: "posted_update" },
];

/**
 * capability = "nlp". Emits one observation per matched literal pattern:
 * subject_candidate (the displayed name, unresolved) + a single-subject claim.
 * It never relates two creators and never infers beyond the text.
 */
export function extractCreatorObservations(signal: Signal, ctx: Context): Observation[] {
  const text = textContent(signal);
  if (text === undefined) return [];
  for (const { re, event_type } of PATTERNS) {
    const match = re.exec(text);
    const name = match?.[1]?.trim();
    if (name) {
      return [
        ObservationSchema.parse({
          id: ctx.newId("obs"),
          signal_id: signal.id,
          subject_candidate: name,
          claim: { type: "creator_event", value: { event_type } },
          capability: "nlp",
          capability_confidence: PATTERN_MATCH_CONFIDENCE,
          created_at: ctx.now(),
        }),
      ];
    }
  }
  return [];
}
