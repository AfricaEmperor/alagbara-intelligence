import type { Signal } from "../../domain/signal.js";

/** Text content of a Signal payload of the form `{ content: string }`, else undefined. */
export function textContent(signal: Signal): string | undefined {
  const payload = signal.payload;
  if (payload !== null && typeof payload === "object" && "content" in payload) {
    const content = (payload as { content: unknown }).content;
    if (typeof content === "string") return content;
  }
  return undefined;
}

/**
 * Fixed confidence the Sprint 1 pattern extractors assign when their literal
 * pattern matches. This is the extractor's confidence in its own parse
 * (capability_confidence), NOT evidence and NOT channel trust.
 */
export const PATTERN_MATCH_CONFIDENCE = 0.9;
