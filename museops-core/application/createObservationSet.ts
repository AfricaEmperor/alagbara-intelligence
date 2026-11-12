import { ObservationSetSchema } from "../domain/observationSet.js";
import type { ObservationSet } from "../domain/observationSet.js";
import { TimeframeSchema } from "../domain/common.js";
import type { Timeframe } from "../domain/common.js";
import type { Observation } from "../domain/observation.js";
import type { Context } from "./context.js";

/** An Observation paired with the Subject it was resolved to (application-level pairing, not persisted). */
export interface ResolvedObservation {
  observation: Observation;
  subject_id: string;
}

/**
 * Group observations by subject_id within a timeframe. One ObservationSet per
 * subject. Observations outside the timeframe are excluded. Sets never span subjects.
 */
export function createObservationSets(
  resolved: readonly ResolvedObservation[],
  timeframeInput: Timeframe,
  ctx: Context,
): ObservationSet[] {
  const timeframe = TimeframeSchema.parse(timeframeInput);
  const start = Date.parse(timeframe.start);
  const end = Date.parse(timeframe.end);
  const bySubject = new Map<string, string[]>();
  for (const { observation, subject_id } of resolved) {
    const at = Date.parse(observation.created_at);
    if (at < start || at > end) continue;
    const ids = bySubject.get(subject_id) ?? [];
    if (!ids.includes(observation.id)) ids.push(observation.id);
    bySubject.set(subject_id, ids);
  }
  return [...bySubject.entries()].map(([subject_id, observation_ids]) =>
    ObservationSetSchema.parse({ id: ctx.newId("oset"), subject_id, observation_ids, timeframe }),
  );
}
