import type { ObservationSet } from "../domain/observationSet.js";
import { HistoricalComparisonSchema, PulseSchema } from "../domain/pulse.js";
import type { HistoricalComparison, Pulse } from "../domain/pulse.js";
import { CrossSubjectError } from "./errors.js";
import type { Context } from "./context.js";

/**
 * Aggregate ObservationSets of ONE subject into a Pulse. Mixed subjects are
 * rejected: the core never combines different subjects.
 */
export function createPulse(
  sets: readonly ObservationSet[],
  ctx: Context,
  historical?: HistoricalComparison,
): Pulse {
  const [first, ...rest] = sets;
  if (!first) throw new Error("createPulse requires at least one ObservationSet");
  if (rest.some((s) => s.subject_id !== first.subject_id)) {
    throw new CrossSubjectError("A Pulse aggregates exactly one subject; ObservationSets span multiple subjects.");
  }
  const starts = sets.map((s) => Date.parse(s.timeframe.start));
  const ends = sets.map((s) => Date.parse(s.timeframe.end));
  return PulseSchema.parse({
    id: ctx.newId("pulse"),
    subject_id: first.subject_id,
    observation_set_ids: sets.map((s) => s.id),
    timeframe: {
      start: new Date(Math.min(...starts)).toISOString().replace(/\.\d{3}Z$/, "Z"),
      end: new Date(Math.max(...ends)).toISOString().replace(/\.\d{3}Z$/, "Z"),
    },
    ...(historical ? { historical_comparison: HistoricalComparisonSchema.parse(historical) } : {}),
  });
}
